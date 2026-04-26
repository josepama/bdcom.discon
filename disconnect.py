import os, json, telnetlib3
import time, asyncio, socket
from collections import defaultdict

from format import *
from generate import *

user_path = os.path.expanduser("~")

DRY_RUN = False
RETRY_DELAY = 5
MAX_RETRIES = 2
TELNET_TIMEOUT = 5

COMMAND_TIMEOUT = 5
READ_SIZE = 4096

CHUNK_SIZE = 15
CHUNK_DELAY = 0.3

MAX_CONCURRENT_OLTS = 4
SEM = asyncio.Semaphore(MAX_CONCURRENT_OLTS)
JSON_PATH = user_path + r"\Desktop\bdcom.discon\settings\ip-addresses2.json"

class TelnetAutomationError(Exception): pass
class ConnectionError(TelnetAutomationError): pass
class LoginError(TelnetAutomationError): pass
class CommandError(TelnetAutomationError): pass

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

    if not isinstance(data, list) or not data:
        raise TelnetAutomationError("Invalid credentials format")

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
async def read_until(reader, timeout=COMMAND_TIMEOUT, size=READ_SIZE):
    try:
        return await asyncio.wait_for(reader.read(size), timeout)
    except asyncio.TimeoutError:
        return ""

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
        raise ConnectionError(f"{e}")

async def login_OLT(reader, writer, username, password):
    writer.write(username + "\n")
    await asyncio.sleep(0.5)
    await read_until(reader)

    writer.write(password + "\n")
    await asyncio.sleep(0.5)
    output = await read_until(reader)

    if ">" not in output and "#" not in output:
        raise LoginError("Prompt not detected after login")

async def send_command(writer, reader, commands):
    try:
        writer.write("\n".join(commands) + "\n")
        output = await read_until(reader)

        error_keywords = ["Invalid", "Error", "Unknown", "Incomplete", "Failure"]
        if any(word in output for word in error_keywords):
            raise CommandError("Device rejected batch commands")

        return output
    except Exception as e:
        raise CommandError(f"{e}")

async def disconnect_OLT(writer):
    try:
        writer.write("exit\n")
        writer.close()
        await writer.wait_closed()

    except Exception:
        pass


#  Disconnection Logic
async def disconnect_subs(olt, ip, interfaces, username, password):
    results = {
        "olt": olt,
        "ip": ip,
        "total": len(interfaces),
        "success": 0,
        "failed": 0,
        "errors": []
    }

    if DRY_RUN:
        log(f"[DRY-RUN] {olt} ({ip}) → {len(interfaces)} interfaces")
        return results

    for attempt in range(1, MAX_RETRIES + 1):
        reader, writer = None, None

        try:
            log(f"{olt}: Connecting ({attempt}/{MAX_RETRIES})")

            reader, writer = await connect_OLT(ip)
            await login_OLT(reader, writer, username, password)

            # Enter config mode once
            await send_command(writer, reader, ["enable", "config"])

            total = len(interfaces)

            for i in range(0, total, CHUNK_SIZE):
                chunk = interfaces[i:i + CHUNK_SIZE]

                log(f"{olt}: Chunk {i+1}-{i+len(chunk)}/{total}")

                cmd_map = [] # Track which interface maps to which command for error handling
                commands = []

                for interface in chunk:
                    log(f"{olt}: Deactivating: {interface}")
                    commands += [
                        f"interface {interface}",
                        "gpon onu virtual-port 1 shutdown",
                        "exit"
                    ]
                    cmd_map.append(interface)

                try:
                    output = await send_command(writer, reader, commands)

                    # Validate per interface (basic check)
                    for interface in cmd_map:
                        if any(err in output for err in ["Error", "Invalid", "Failure"]):
                            results["failed"] += 1

                            results["errors"].append((interface, "Command rejected"))
                            log(f"{olt}: FAIL {interface}")

                        else:
                            results["success"] += 1

                except CommandError as ce:
                    log(f"{olt}: Chunk failed → {ce}")

                    # fallback: process individually
                    for interface in chunk:
                        try:
                            log(f"{olt}: Deactivating: {interface}")

                            cmds = [
                                f"interface {interface}",
                                "gpon onu virtual-port 1 shutdown",
                                "exit"
                            ]

                            await send_command(writer, reader, cmds)
                            results["success"] += 1

                        except Exception as e:
                            results["failed"] += 1
                            results["errors"].append((interface, str(e)))
                            log(f"{olt}: FAIL {interface} → {e}")

                await asyncio.sleep(CHUNK_DELAY)

            # Exit config
            await send_command(writer, reader, ["exit", "exit"])

            log(f"{olt}: SUCCESS → {results['success']} OK/{results['failed']} FAIL")
            return results

        except (ConnectionError, LoginError, CommandError, TelnetAutomationError) as e:
            log(f"{olt}: ERROR → {e}")

        finally:
            if writer:
                await disconnect_OLT(writer)

        if attempt < MAX_RETRIES:
            log(f"{olt}: Retrying in {RETRY_DELAY}s...")
            await asyncio.sleep(RETRY_DELAY)

        else:
            log(f"{olt}: HARD FAIL")

    return results


async def bounded_disconnect(*args):
    async with SEM:
        return await disconnect_subs(*args)

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
            log(f"WARNING: No IP for {olt}")
            continue

        if parallel:
            tasks.append(bounded_disconnect(olt, ip, interfaces, username, password))
        else:
            result = await disconnect_subs(olt, ip, interfaces, username, password)
            tasks.append(result)

    results = await asyncio.gather(*tasks) if parallel else tasks

    total_ok = sum(r["success"] for r in results if r)
    total_fail = sum(r["failed"] for r in results if r)

    log("*----------* SUMMARY *----------*")
    for r in results:
        if not r:
            continue
        log(f"{r['olt']} → SUCCESS:{r['success']} FAIL:{r['failed']}")

    log(f"TOTAL → SUCCESS:{total_ok} FAIL:{total_fail}")

    duration = time.perf_counter() - start
    mins, secs = divmod(duration, 60)
    log(f"FINISHED in {int(mins)}m {secs:.2f}s")

if __name__ == "__main__":
    try:
        asyncio.run(BEGIN_FTTH_SUBS_DISCONNECTION(parallel=True))

    except Exception as e:
        log(f"Unhandled Error: {e}")
        sys.exit(1)