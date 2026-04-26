import os, re, glob
from send2trash import send2trash
from generate import log, user_path, REFERENCE_LIST

# Output text file
SOFT_DISCON_FOLDER = user_path + r"\Desktop\bdcom.discon\soft-discon"
SOFT_DISCONNECTION_FORMATTED = os.path.join(SOFT_DISCON_FOLDER, "FOR_DISCONNECTION_FORMATTED.txt")

# Find all text files starting with 'soft-discon' and ending with '.txt'
file_list = sorted(glob.glob(os.path.join(SOFT_DISCON_FOLDER, "soft-discon*.txt")))

# Get all MAL-XXXXXX from soft-discon.txt
def PROCESS_SOFT_DISCONNECTION_FILE():
    combined_lines = []
    for file_path in file_list:
        try:
            # Read the text file
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
                log(f"Processing: {file_path}")

            if not text.strip():
                log(f"Skipping empty file: {file_path}")
                continue

            # Insert a newline before every occurrence of 'MAL-' except the first one
            formatted_text = re.sub(r'(?<!^)(MAL-)', r'\n\1', text)

            # Remove leading/trailing spaces and empty lines
            lines = [line.strip() for line in formatted_text.splitlines() if line.strip()]

            # Split each line into Account # and Name
            for line in lines:
                parts = line.split(' ', 1)
                if len(parts) == 2:
                    account, name = parts
                else:
                    account = parts[0]
                    name = ''
                combined_lines.append(f"{account} | {name}")

        except Exception as e:
            log(f"Error processing {file_path}: {e}")

    # Write FOR_DISCONNECTION_FORMATTED text file
    try:
        with open(SOFT_DISCONNECTION_FORMATTED, "w", encoding="utf-8") as f:
            f.write("\n".join(combined_lines))
        log(f"All files processed. For DISCONNECTION FORMATTED file saved to '{SOFT_DISCONNECTION_FORMATTED}'")

    except Exception as e:
        log(f"Error writing For DISCONNECTION FORMATTED file: {e}\n")


FOR_DISCONNECTION_FTTH = user_path + r"\Desktop\bdcom.discon\soft-discon\FOR_DISCONNECTION_FTTH.txt"
FOR_DISCONNECTION = user_path + r"\Desktop\bdcom.discon\soft-discon\FOR_DISCONNECTION.txt"

ACCOUNT_PATTERN = re.compile(r"MAL-(\d+)")
REF_SPLIT_PATTERN = re.compile(r"\s{2,}")

# 5–6 digit account numbers, underscore-safe
DESC_ACCOUNT_PATTERN = re.compile(r"(?<!\d)\d{5,6}(?!\d)")

# 2ND PROCESS
def MATCH_AND_SORT_FORMATTED_FILE_TO_REFERENCE_LIST():
    # READ SUBSCRIBERS WITH NAMES
    accounts = []  # List of tuples: (int_account_num, full_account_str, name_str)
    with open(SOFT_DISCONNECTION_FORMATTED, "r", encoding="utf-8") as f:
        for line in f:
            match = ACCOUNT_PATTERN.search(line)

            if match:
                acc_num_str = match.group(1)
                acc_num_int = int(acc_num_str)

                # Extract subscriber name (everything after '|', stripped)
                # Example line: MAL-123456 | DELA CRUZ C. JUAN JR.

                parts = line.split('|')
                name = parts[1].strip() if len(parts) > 1 else ""
                accounts.append((acc_num_int, f"MAL-{acc_num_str}", name))

    # READ REFERENCE-LIST.txt
    with open(REFERENCE_LIST, "r", encoding="utf-8") as f:
        ref_lines = f.readlines()

    matched_rows = []
    not_found_accounts = []

    # MATCH
    for acc_num_int, acc_num_full, name in accounts:
        found = False

        for line in ref_lines:
            parts = REF_SPLIT_PATTERN.split(line.strip())
            if len(parts) < 4:
                continue

            description = parts[2]
            desc_accounts = [int(n) for n in DESC_ACCOUNT_PATTERN.findall(description)]

            if acc_num_int in desc_accounts:
                file_name = os.path.splitext(parts[0])[0]
                interface = parts[1]
                sn = parts[3]

                matched_rows.append((file_name, interface, description, sn))
                found = True
                break

        if not found:
            not_found_accounts.append((acc_num_full, name))
            clean_name = re.split(r"\s{2,}", name)[0]
            log(f"Subscriber NOT FOUND {acc_num_full} - {clean_name}")

    # SORT BY FILE
    matched_rows.sort(key=lambda x: x[0])

    # WRITE FOR DISCONNECTION FTTH FILE (FIXED WIDTH)
    with open(FOR_DISCONNECTION_FTTH, "w", encoding="utf-8") as f:
        header = (
            "OLT".ljust(6) +
            "Interface".ljust(14) +
            "Description".ljust(35) +
            "SN\n"
        )
        f.write(header)
        f.write("-" * 68 + "\n")

        for file_name, interface, description, sn in matched_rows:
            line = (
                file_name.ljust(6) +
                interface.ljust(14) +
                description.ljust(35) +
                sn + "\n"
            )
            f.write(line)

    # WRITE FOR DISCONNECTION FILE (HFC, CABLE-ALONE, FTTH W/O DISPLAY NAMES)
    with open(FOR_DISCONNECTION, "w", encoding="utf-8") as nf:
        nf.write("Account #\tSubscriber Name\n")
        nf.write("-" * 27 + "\n")
        for acc_num_full, name in not_found_accounts:
            clean_name = re.split(r"\s{2,}", name)[0]
            nf.write(f"{acc_num_full}\t{clean_name}\n")

    # Delete REFERENCE-List & FORMATTED DISCON file
    send2trash(REFERENCE_LIST)
    log(f"File moved to Recycle Bin: {REFERENCE_LIST}")

    send2trash(SOFT_DISCONNECTION_FORMATTED)
    log(f"File moved to Recycle Bin: {SOFT_DISCONNECTION_FORMATTED}")

    log(f"FTTH subscribers for DISCONNECTION written to '{FOR_DISCONNECTION_FTTH}'")
    log(f"For DISCONNECTION Subscribers saved to '{FOR_DISCONNECTION}'")
