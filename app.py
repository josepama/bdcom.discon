import sys, asyncio
from format import *
from generate import *
from disconnect import *

# Entry Point
if __name__ == "__main__":

    # Make sure 2_DISCON folder is not empty, Log then exit
    if not file_list or os.path.getsize(file_list[0]) == 0:
        log(f"No files found in {SOFT_DISCON_FOLDER} or file is empty. Verify location and filenames.")
        sys.exit(1)

    try:
        # Talk to OLT, send files to TFTP
        SEND_FILES_FROM_OLT_TO_TFTP()

        # Loop until generated files are present in the 1_TFTP folder
        while True:

            # Files are present, Begin processing
            if IS_FILES_PRESENT():
                log("Files found in the folder. Proceeding...")

                # Format files to readable format, then save
                FORMAT_ONU_DESCRIPTION_AND_SAVE_TO_FILE()

                # Get all MAL-XXXXXX from soft-discon.txt
                input("Review soft-discon.txt file, Then press Enter to continue...")
                PROCESS_SOFT_DISCONNECTION_FILE() # -> save a file: FOR_DISCONNECTION_FORMATTED.txt

                # Match FOR_DISCONNECTION_FORMATTED.txt to REFERENCE-LIST.txt
                # Return all found subs, Two files will be saved;

                # 1. FOR_DISCONNECTION_FTTH.txt - (FTTH-SUBS)
                # 2. FOR_DISCONNECTION.txt - (HFC/CABLE-ALONE/FTTH-W/O DISPLAY NAMES)
                MATCH_AND_SORT_FORMATTED_FILE_TO_REFERENCE_LIST()

                # Begin Disconnection
                # TRUE: async
                # FALSE: not async
                input("\nReady to begin disconnection, Press Enter to continue...")
                asyncio.run(BEGIN_FTTH_SUBS_DISCONNECTION(parallel=True))

                # exit Loop
                break

            else:
                log("ERROR: {TFTP_FOLDER} is empty.")
                input("\nCopy generated files into "+"'soft-discon'"+" folder, Then press Enter.")
                continue

    except KeyboardInterrupt:
        log("Interrupted by user")
        sys.exit(1)

    except Exception as e:
        log(f"Unhandled Error: {e}")
        sys.exit(1)

sys.exit(0)
# (Get-PSReadlineOption).HistorySavePath