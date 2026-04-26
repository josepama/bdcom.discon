import os, json, telnetlib3
import time, asyncio, socket
from collections import defaultdict

from format import *
from generate import *

# Config
user_path = os.path.expanduser("~")

DRY_RUN = False # Set False to actually disconnect
RETRY_DELAY = 5

JSON_PATH = user_path + r"\Desktop\bdcom.discon\settings\ip-addresses2.json"

# Custom Exceptions
class TelnetAutomationError(Exception): pass
class ConnectionError(TelnetAutomationError): pass
class LoginError(TelnetAutomationError): pass
class CommandError(TelnetAutomationError): pass

# Load JSON files 
def load_json(path, description):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return json.load(f)
    except FileNotFoundError:
        raise TelnetAutomationError(f"{description} file not found: {path}")
    except json.JSONDecodeError as e:
        raise TelnetAutomationError(f"Invalid JSON in {description}: {e}")
    except Exception as e:
        raise TelnetAutomationError(f"Failed to load {description}: {e}")


def load_credentials():
    data = load_json(SECRETS, "Credentials")
    if not isinstance(data, list) or not data or "username" not in data[0] or "password" not in data[0]:
        raise TelnetAutomationError("Credentials JSON structure invalid")
    return data[0]["username"], data[0]["password"]


def load_olt_ip_map(path):
    data = load_json(path, "OLT IP map")
    log(f"Loaded {len(data)} OLT IP mappings")
    return {item["OLT"][0]: item["IP"] for item in data}


def parse_text_file(path):
    olt_interfaces = defaultdict(list)

    with open(path, "r") as f:
        for line in f:

            line = line.strip()
            if not line or line.startswith("OLT") or line.startswith("-"):
                continue

            parts = line.split()
            if len(parts) >= 2:
                olt_interfaces[parts[0]].append(parts[1])

    log(f"Parsed interfaces for {len(olt_interfaces)} OLTs")
    return olt_interfaces


#  TELNET Functions (ASYNC) 
async def connect_OLT(host):
    try:
        return await asyncio.wait_for(
            telnetlib3.open_connection(host),
            timeout=TELNET_TIMEOUT
        )
    except asyncio.TimeoutError:
        raise ConnectionError("Connection timed out")
    except socket.gaierror:
        raise ConnectionError("DNS resolution failed")
    except ConnectionRefusedError:
        raise ConnectionError("Connection refused")
    except Exception as e:
        raise ConnectionError(f"Connection error: {e}")


async def login_OLT(reader, writer, username, password):
    try:
        await asyncio.sleep(0.5)
        writer.write(username + "\n")

        await asyncio.sleep(0.5)
        writer.write(password + "\n")

        await asyncio.sleep(1)
        output = await reader.read(1024)

        if ">" not in output and "#" not in output:
            raise LoginError("Prompt not detected after login")

    except Exception as e:
        raise LoginError(f"Login error: {e}")


async def send_command(writer, reader, command, wait=COMMAND_WAIT):
    try:
        writer.write(command + "\n")
        await asyncio.sleep(wait)

        output = await reader.read(1024)
        error_keywords = ["Invalid", "Error", "Unknown command", "Incomplete command", "Failure"]
        if any(word in output for word in error_keywords):
            raise CommandError(f"Device rejected command: {command}")
        return output
    
    except CommandError:
        raise

    except Exception as e:
        raise CommandError(f"Command failed [{command}]: {e}")


async def disconnect_OLT(writer):
    try:
        writer.write("exit\n")
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass


#  Disconnection Logic
async def disconnect_subs(olt, ip, interfaces, username, password):
    if DRY_RUN:
        log(f"[DRY-RUN] {olt} ({ip})")
        for interface in interfaces:
            log(f"Would disconnect {interface}")
        return

    for attempt in range(1, MAX_RETRIES + 1):
        reader, writer = None, None
        try:
            log(f"{olt}: Connecting to {ip} (Attempt {attempt})")
            reader, writer = await connect_OLT(ip)
            await login_OLT(reader, writer, username, password)

            for interface in interfaces:
                try:
                    log(f"{olt}: Deactivating: {interface}")
                    await send_command(writer, reader, "enable")
                    await send_command(writer, reader, "config")
                    await send_command(writer, reader, f"interface {interface}")
                    await send_command(writer, reader, "gpon onu virtual-port 1 no-shutdown")
                    await send_command(writer, reader, "exit")
                    await send_command(writer, reader, "exit")
                    await send_command(writer, reader, "exit")

                except CommandError as ce:
                    log(f"{olt} {interface}: COMMAND ERROR → {ce}")
                    continue

            await disconnect_OLT(writer)
            log(f"{olt}: Completed successfully")
            return

        except (ConnectionError, LoginError, TelnetAutomationError) as e:
            log(f"{olt}: ERROR → {e}")
        finally:
            if writer:
                await disconnect_OLT(writer)

        if attempt < MAX_RETRIES:
            log(f"{olt}: Retrying in {RETRY_DELAY} seconds...")
            await asyncio.sleep(RETRY_DELAY)
        else:
            log(f"{olt}: FAILED after {MAX_RETRIES} attempts")

#  Main Async Function 
async def BEGIN_FTTH_SUBS_DISCONNECTION(parallel=True):
    start = time.perf_counter()
    log("INFO: DISCONNECTION STARTED")

    username, password = load_credentials()
    olt_ip_map = load_olt_ip_map(JSON_PATH)
    olt_interfaces = parse_text_file(FOR_DISCONNECTION_FTTH)

    tasks = []
    for olt, interfaces in olt_interfaces.items():
        ip = olt_ip_map.get(olt)
        if not ip:
            log(f"WARNING: No IP found for {olt}, skipping")
            continue
        if parallel:
            tasks.append(disconnect_subs(olt, ip, interfaces, username, password))
        else:
            await disconnect_subs(olt, ip, interfaces, username, password)

    if parallel:
        await asyncio.gather(*tasks)

    end = time.perf_counter()
    duration = end - start
    mins, secs = divmod(duration, 60)

    log(f"INFO: DISCONNECTION Finished in {int(mins)}m {secs:.4f}s")

if __name__ == "__main__":
    asyncio.run(BEGIN_FTTH_SUBS_DISCONNECTION(parallel=True))