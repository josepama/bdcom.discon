import sys, telnetlib3
import os, re, json, time
import nmap, socket, subprocess
from datetime import datetime
from pathlib import Path
from send2trash import send2trash

TFTP_PORT = 69
TFTP_SERVER = "192.168.21.6"

# GET user-path
user_path = os.path.expanduser("~")

# LOGGING
LOG_FILE = user_path + r"\Desktop\bdcom.discon\logs\process.log"
def log(message):
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] {message}"
        print(line)

        with open(LOG_FILE, "a", encoding="utf-8", errors="replace") as lf:
            lf.write(line + "\n")

    except Exception:
        print("LOGGING FAILURE:", message)


# CUSTOM Exception
class TelnetAutomationError(Exception):
    pass

# LOAD JSON files
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

# LOAD credentials
SECRETS = user_path + r"\Desktop\bdcom.discon\settings\secrets.json"
def load_credentials():
    data = load_json(SECRETS, "Credentials")
    if (
        not isinstance(data, list)
        or not data
        or "username" not in data[0]
        or "password" not in data[0]
    ):
        raise TelnetAutomationError("Credentials JSON structure invalid")
    return data[0]["username"], data[0]["password"]

# LOAD IP-addresses
IP_FILE = user_path + r"\Desktop\bdcom.discon\settings\ip-addresses.json"
def load_ip_addresses():
    data = load_json(IP_FILE, "IP addresses")
    if not isinstance(data, list):
        raise TelnetAutomationError("IP address JSON must be a list")

    validated = []
    for entry in data:
        if (
            not isinstance(entry, dict)
            or "ip" not in entry
            or "filename" not in entry
            or not isinstance(entry["filename"], list)
            or len(entry["filename"]) != 2
        ):
            log(f"Skipping invalid IP entry: {entry}")
            continue
        validated.append(entry)

    if not validated:
        raise TelnetAutomationError("No valid IP entries found")

    return validated


# Check TFTP service
def check_TFTP_server(host, port):
    nm = nmap.PortScanner()
    try:
        # Perform UDP scan on the specified port
        nm.scan(hosts=host, ports=str(port), arguments='-sU -Pn -n')

        # Check if host is in scan result
        if host not in nm.all_hosts():
            log(f"No response from {host}.")
            return False

        # Get UDP port state
        port_info = nm[host]['udp'][port] if 'udp' in nm[host] and port in nm[host]['udp'] else None
        if port_info:
            state = port_info['state']
            log(f"TFTP Server on {TFTP_SERVER}:{TFTP_PORT} is {state.upper()}")
            return True if "open" in state.lower() else False

        else:
            log(f"ERROR: UDP port {port} not found in scan results for {host}.")
            return False

    except nmap.PortScannerError as e:
        log(f"Nmap error: {e}")
        return False

    except Exception as e:
        log(f"Unexpected error: {e}")
        return False


COMMAND_WAIT = 1
MAX_RETRIES = 2 
LOGIN_TIMEOUT = 3
TELNET_TIMEOUT = 5

# TELNET FUNCTIONS
def connect_OLT(host):
    try:
        return telnetlib3.Telnet(host, timeout=TELNET_TIMEOUT)
    except socket.gaierror:
        raise TelnetAutomationError("DNS resolution failed")
    except socket.timeout:
        raise TelnetAutomationError("Connection timed out")
    except ConnectionRefusedError:
        raise TelnetAutomationError("Connection refused")
    except Exception as e:
        raise TelnetAutomationError(f"Connection error: {e}")

def login_OLT(tn, username, password):
    try:
        tn.read_until(b"Username:", LOGIN_TIMEOUT)
        tn.write(username.encode() + b"\n")

        tn.read_until(b"Password:", LOGIN_TIMEOUT)
        tn.write(password.encode() + b"\n")

        time.sleep(1)
        output = tn.read_very_eager()

        if b">" not in output:
            raise TelnetAutomationError("Login failed (prompt not detected)")

    except EOFError:
        raise TelnetAutomationError("Remote host closed connection")
    except socket.timeout:
        raise TelnetAutomationError("Login timed out")
    except Exception as e:
        raise TelnetAutomationError(f"Login error: {e}")

def send_command(tn, command, wait=COMMAND_WAIT):
    try:
        tn.write(command.encode() + b"\n")
        time.sleep(wait)

        return tn.read_very_eager().decode("utf-8", errors="replace")
    except Exception as e:
        raise TelnetAutomationError(f"Command failed [{command}]: {e}")

def disconnect_OLT(tn):
    try:
        tn.write(b"exit\n")
        tn.close()

    except Exception:
        pass


TFTP_PATH = r"C:\Program Files\Tftpd64\tftpd64.exe"
def TFTP_SERVER_INSTALLED():
    return True if os.path.isfile(TFTP_PATH) else False

tftp_running = subprocess.getoutput("tasklist | findstr tftpd64.exe")
def TFTP_SERVER_RUNNING():
    return True if tftp_running else False

def CLOSE_TFTP_SERVER():
    if TFTP_SERVER_RUNNING():
        subprocess.getoutput("taskkill -f -t -im tftpd64.exe")
        log("TFTP Server closed.")


# Telnet to OLT, send files to TFTP
def SEND_FILES_FROM_OLT_TO_TFTP():
    try:
        username, password = load_credentials()
        IP_LIST = load_ip_addresses()

    except TelnetAutomationError as e:
        log(f"FATAL: {e}")
        return 1

    if(check_TFTP_server(TFTP_SERVER, TFTP_PORT)):
        log("Sending files to TFTP...")
        overall_errors = False

        for entry in IP_LIST:
            host = entry["ip"]
            FILENAME, OLT_NAME = entry["filename"]
            log(f"Connecting to {OLT_NAME} ({host})")

            tn = None
            success = False

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    log(f"Attempt {attempt} of {MAX_RETRIES}")
                    tn = connect_OLT(host)
                    login_OLT(tn, username, password)

                    send_command(tn, "enable")
                    send_command(tn, "config")

                    TFTP_CMD = (
                        f"show gpon onu-description | "
                        f"tftp {FILENAME}.txt {TFTP_SERVER}"
                    )

                    send_command(tn, TFTP_CMD, wait=3)
                    log(f"SUCCESS: {FILENAME}.txt sent to TFTP")

                    send_command(tn, "exit")
                    send_command(tn, "exit")

                    success = True
                    break

                except TelnetAutomationError as e:
                    log(f"ERROR: ({OLT_NAME}): {e}")
                    time.sleep(2)

                finally:
                    if tn:
                        disconnect_OLT(tn)
                        tn = None

            if not success:
                overall_errors = True
                log(f"FAILED after retries: {OLT_NAME}")
    else:
        sys.exit(0)

    log(F"SUCCESS: All files are sent to TFTP Server on: {TFTP_SERVER}")

    # Close TFTP-Server App
    CLOSE_TFTP_SERVER()
    return 1 if overall_errors else 0


FILENAME_PATTERN = re.compile(r"^(MAL|ABC)-.*\.txt$", re.IGNORECASE)
TFTP_FOLDER = user_path + r"\Desktop\bdcom.discon\tftp"
REFERENCE_LIST = user_path + r"\Desktop\bdcom.discon\tftp\REFERENCE-LIST.txt"

def IS_FILES_PRESENT():
    return any(os.path.isfile(os.path.join(TFTP_FOLDER, f)) for f in os.listdir(TFTP_FOLDER))

# Forcec open (no encoding failures)
def force_open(path):
    # Always succeeds; bad bytes replaced with �
    return open(path, "r", encoding="utf-8", errors="replace")

def delete_Generated_TFTP_files():
    folder = Path(TFTP_FOLDER)

    if not folder.exists():
        log("Folder {TFTP_FOLDER} does not exist.")
        return

    file_pattern = list(folder.glob("MAL-*.txt")) + list(folder.glob("ABC-*.txt"))
    if not file_pattern:
        log("No files matched the pattern MAL-*.txt or ABC-*.txt")
        return

    for file in file_pattern:
        try:
            send2trash(str(file))
            log(f"File moved to Recycle Bin: {file}")

        except Exception as e:
            print(f"Error moving {file}: {e}")

# Format Reference file
# to a more readable format

def FORMAT_ONU_DESCRIPTION_AND_SAVE_TO_FILE():
    records = []
    files_to_delete = []
    errors_found = False

    # Validate input folder
    if not os.path.isdir(TFTP_FOLDER):
        log(f"ERROR: TFTP folder not found: {TFTP_FOLDER}")
        return 1

    try:
        files = os.listdir(TFTP_FOLDER)

    except Exception as e:
        log(f"ERROR: Cannot list directory: {e}")
        return 1

    if not files:
        log("WARNING: TFTP folder is empty")
        return 0

    # Process files
    for filename in files:
        if not FILENAME_PATTERN.match(filename):
            continue

        filepath = os.path.join(TFTP_FOLDER, filename)
        log(f"Processing file: {filename}")

        try:
            with force_open(filepath) as f:
                lines = f.readlines()

            if not lines:
                log(f"WARNING: Empty file skipped: {filename}")
                continue

            i = 0
            file_has_valid_records = False

            while i < len(lines):
                line = lines[i].rstrip()

                if not line.startswith("GPON"):
                    i += 1
                    continue

                # Split on 2+ spaces
                parts = re.split(r"\s{2,}", line)

                # Pad missing fields
                while len(parts) < 4:
                    parts.append("N/A")

                intf, description, sn, loid = parts[:4]

                oper_status = "N/A"
                config_status = "N/A"

                # Status line (if exists)
                if i + 1 < len(lines):
                    status_parts = re.split(
                        r"\s{2,}",
                        lines[i + 1].strip()
                    )
                    if len(status_parts) >= 1:
                        oper_status = status_parts[0]
                    if len(status_parts) >= 2:
                        config_status = status_parts[1]

                records.append((
                    filename,
                    intf,
                    description,
                    sn,
                    loid,
                    oper_status,
                    config_status
                ))

                file_has_valid_records = True
                i += 2

            if file_has_valid_records:
                files_to_delete.append(filepath)
            else:
                log(f"WARNING: No GPON records found in {filename}")

        except Exception as e:
            errors_found = True
            log(f"ERROR processing {filename}: {e}")

    # Write to file
    if records:
        try:
            with open(REFERENCE_LIST, "w", encoding="utf-8") as f:
                header = (
                    f"{'File':<14}"
                    f"{'Interface':<15}"
                    f"{'Description':<45}"
                    f"{'SN':<18}"
                    f"{'LOID':<8}"
                    f"{'Status':<12}"
                    f"{'Config':<9}\n"
                )
                f.write(header)
                f.write("-" * 119 + "\n")

                for r in records:
                    f.write(
                        f"{r[0]:<14}"
                        f"{r[1]:<15}"
                        f"{r[2]:<45}"
                        f"{r[3]:<18}"
                        f"{r[4]:<8}"
                        f"{r[5]:<12}"
                        f"{r[6]:<9}\n"
                    )

            log(f"REFERENCE file created saved as: {REFERENCE_LIST}")

        except Exception as e:
            log(f"ERROR writing REFERENCE file: {e}")
            return 1
    else:
        log("WARNING: No records collected; REFERENCE file not created")
    
    delete_Generated_TFTP_files()
    return 1 if errors_found else 0
