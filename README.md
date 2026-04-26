# BDCOM OLT Disconnection Automation Tool
# Model (BDCOM GP3600-16B • GP3600-16B-2DC)

A Python-based automation tool for managing subscriber disconnections on BDCom Optical Line Terminals (OLTs) with support for FTTH (Fiber to the Home) and HFC/Cable networks.

## Overview

This tool automates the process of disconnecting subscribers from BDCom OLT systems by:
- Processing soft-disconnection files containing subscriber account numbers
- Connecting to OLT devices via Telnet
- Formatting and organizing subscriber data
- Managing FTTH-specific disconnections
- Handling concurrent operations across multiple OLTs
- Logging all operations for audit purposes

## Project Structure

```
bdcom.discon/
├── app.py                          # Main entry point and orchestration logic
├── disconnect.py                   # OLT connection and disconnection operations
├── format.py                       # File formatting and data processing utilities
├── generate.py                     # Data generation and file conversion functions
├── logs/                           # Operation logs and audit trails
├── settings/                       # Configuration files
│   ├── ip-addresses.json           # OLT IP address mappings
│   ├── ip-addresses2.json          # Alternative OLT IP address mappings
│   └── secrets.json                # Telnet credentials (username/password)
├── soft-discon/                    # Input and output directory
│   └── soft-discon.txt             # Input file with subscriber account numbers
└── tftp/                           # TFTP file transfer directory
    ├── disconnect.py               # TFTP-specific utilities
    └── sort.py                     # File sorting utilities
```

## Workflow

The tool executes the following workflow:

1. **File Validation** - Ensures the soft-discon folder contains valid input files
2. **OLT Communication** - Connects to OLT and sends files via TFTP
3. **File Processing Loop** - Monitors TFTP folder for generated files
4. **Format & Extract** - Formats ONU descriptions and extracts MAL codes
5. **Reference Matching** - Matches subscriber accounts to reference list
6. **Categorization** - Separates FTTH and HFC/Cable subscribers
7. **Disconnection** - Executes async disconnection operations
8. **Logging** - Records all operations to process log

## Key Features

- **Async Operations**: Supports parallel disconnection across multiple OLTs (configurable limit)
- **Multi-format Support**: Handles FTTH and HFC/Cable subscriber types separately
- **Error Handling**: Comprehensive exception handling with custom error classes
- **Telnet Automation**: Automated login and command execution on OLT devices
- **TFTP Integration**: File transfer protocol for bulk data exchange
- **Detailed Logging**: Timestamped operation logs for audit and troubleshooting
- **Concurrent Throttling**: Configurable semaphores to prevent resource exhaustion

## Prerequisites

### Required Python Packages
- `telnetlib3` - Telnet protocol implementation
- `nmap` - Network scanning utilities
- `send2trash` - Safe file deletion

Install dependencies:
```bash
pip install telnetlib3 python-nmap send2trash
```

### Configuration Files

#### `settings/secrets.json`
Contains OLT Telnet credentials:
```json
[
  {
    "username": "admin",
    "password": "password"
  }
]
```

#### `settings/ip-addresses2.json`
Contains OLT IP address mappings for automated discovery and connection.

## Configuration Parameters

Key configuration parameters in the source files:

- `RETRY_DELAY` - Delay between connection retries (seconds)
- `MAX_RETRIES` - Maximum connection retry attempts
- `TELNET_TIMEOUT` - Telnet command timeout (seconds)
- `CHUNK_SIZE` - Commands per batch (default: 15)
- `CHUNK_DELAY` - Delay between command chunks (seconds)
- `MAX_CONCURRENT_OLTS` - Maximum concurrent OLT connections (default: 4)
- `TFTP_SERVER` - TFTP server IP (192.168.21.6)
- `TFTP_PORT` - TFTP port (69)

## Usage

### Basic Execution

```bash
python app.py
```

### Workflow Steps

1. **Review Input File**
   - Place subscriber account numbers in `soft-discon/soft-discon.txt`
   - Format: `MAL-XXXXXX [Description]` (one per line)

2. **Run the Script**
   - The tool will prompt to review `soft-discon.txt`
   - Press Enter to continue processing

3. **Generated Files**
   - `FOR_DISCONNECTION_FORMATTED.txt` - Extracted and formatted accounts
   - `FOR_DISCONNECTION_FTTH.txt` - FTTH subscriber list
   - `FOR_DISCONNECTION.txt` - HFC/Cable and other subscribers

4. **Confirm Disconnection**
   - Review generated files in `soft-discon/` folder
   - Press Enter to begin disconnection process

## Output Files

- **soft-discon/FOR_DISCONNECTION_FORMATTED.txt** - Formatted subscriber list (Account | Name)
- **soft-discon/FOR_DISCONNECTION_FTTH.txt** - FTTH-only subscriber list
- **soft-discon/FOR_DISCONNECTION.txt** - HFC/Cable subscriber list
- **logs/process.log** - Complete operation audit trail

## Error Handling

The tool defines custom exception classes:
- `TelnetAutomationError` - Base exception for automation errors
- `ConnectionError` - OLT connection failures
- `LoginError` - Authentication failures
- `CommandError` - Command execution failures

All errors are logged with timestamps for troubleshooting.

## Performance Considerations

- **Concurrency**: Uses `asyncio` with a semaphore to limit concurrent OLT connections to 4 (configurable)
- **Rate Limiting**: Implements chunk-based command delivery with configurable delays
- **Batch Processing**: Processes commands in batches to prevent OLT overload

## Safety Features

- **Dry Run Mode**: Set `DRY_RUN = True` to test without making changes
- **User Confirmation**: Requires manual review and confirmation before each stage
- **Audit Logging**: All operations logged with timestamps
- **File Validation**: Checks for empty or missing input files before processing

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "No files found in soft-discon folder" | Verify `soft-discon.txt` exists and is not empty |
| "TFTP folder is empty" | Wait for OLT to generate files or check network connectivity |
| Connection timeout | Verify OLT IP addresses in `settings/ip-addresses2.json` and network connectivity |
| Authentication failed | Check credentials in `settings/secrets.json` |

## Logging

All operations are logged to `logs/process.log` with timestamps:

```
[2026-04-26 10:30:45] Files found in the folder. Proceeding...
[2026-04-26 10:30:46] Processing: soft-discon/soft-discon.txt
[2026-04-26 10:30:47] All files processed...
```

## Notes

- The tool requires network access to OLT devices
- TFTP server must be accessible at 192.168.21.6:69
- Telnet port (default 23) must be open on OLT devices
- Ensure proper backups before executing bulk disconnections
- Review all generated files before confirming disconnection

## License

Internal Use Only

## Support

For issues or questions, review the operation logs in `logs/process.log` for detailed error information.
