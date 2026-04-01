# PVE Royal Inventory

Generate a Royal TSX JSON document from Proxmox VE inventory, creating SSH connections for all VMs and LXC containers.

## Features

- **API Token Authentication**: Secure authentication using Proxmox API tokens
- **Automatic IP Discovery**: Retrieves IP addresses from QEMU guest agents and LXC configs
- **Subnet Filtering**: Configurable subnet filtering with preferred subnet selection
- **Royal TSX Compatible**: Generates proper Royal TSX document structure with folders and credentials
- **Node Organization**: Automatically organizes connections by Proxmox node

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Proxmox VE cluster with API access
- Royal TSX (for importing the generated document)

> **Note**: This script has been tested with passwordless SSH login via present SSH keys configured in `~/.ssh/config`.

## Installation

1. Clone the repository:
   ```bash
   git clone https://codeberg.org/terminatorausbikinibottom/pve-royal-inventory.git
   cd pve-royal-inventory
   ```

2. Install dependencies:
   ```bash
   # Using uv (recommended)
   uv sync

   # Or using pip
   pip install -e .
   ```

3. Create a `.env` file with your configuration:
   ```bash
   cp .env.example .env
   ```

## Configuration

Create a `.env` file in the project root with the following variables:

```env
# Proxmox VE Connection
PVE_HOST=pve1.example.com
PVE_PORT=8006
PVE_USER=root@pam
PVE_TOKEN_ID=inventory
PVE_TOKEN_SECRET=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
PVE_VERIFY_TLS=true

# Royal TSX Credentials
CRED_ID=ssh-credentials-id
CRED_USERNAME=your-ssh-username
CRED_PASSWORD=your-ssh-password (or empty for passwordless login)

# IP Filtering (optional)
ALLOWED_SUBNET=10.10.0.0/16
PREFERRED_SUBNET=10.10.99.0/24

# Logging (optional)
LOGLEVEL=WARNING
```

### Configuration Options

| Variable           | Required | Default         | Description                             |
| ------------------ | -------- | --------------- | --------------------------------------- |
| `PVE_HOST`         | Yes      | -               | Proxmox VE hostname or IP               |
| `PVE_PORT`         | No       | `8006`          | Proxmox VE API port                     |
| `PVE_USER`         | No       | -               | Proxmox user (optional with token auth) |
| `PVE_TOKEN_ID`     | Yes      | -               | API token name                          |
| `PVE_TOKEN_SECRET` | Yes      | -               | API token secret                        |
| `PVE_VERIFY_TLS`   | No       | `true`          | Verify TLS certificates                 |
| `CRED_ID`          | No       | -               | Royal TSX credential ID                 |
| `CRED_USERNAME`    | No       | -               | SSH username for connections            |
| `CRED_PASSWORD`    | No       | -               | SSH password for connections            |
| `ALLOWED_SUBNET`   | No       | `10.10.0.0/16`  | CIDR subnet to filter IPs               |
| `PREFERRED_SUBNET` | No       | `10.10.99.0/24` | Preferred CIDR subnet                   |
| `LOGLEVEL`         | No       | `WARNING`       | Log level (DEBUG, INFO, WARNING, ERROR) |

### Setting up Proxmox API Token

1. Log in to Proxmox VE web interface
2. Navigate to **Datacenter** → **Permissions** → **API Tokens**
3. Click **Add** to create a new token:
   - User: `root@pam` (or your user)
   - Token ID: `inventory`
   - Privilege Separation: Unchecked (or configure appropriate permissions)
4. Copy the generated token secret to your `.env` file

## Usage

### Command Line

Generate Royal TSX document and save to file:

```bash
uv run main.py > inventory.json
```

With custom log level:

```bash
LOGLEVEL=DEBUG uv run main.py > inventory.json
```

### Royal TSX Dynamic Folder

To automatically refresh your inventory in Royal TSX, set up a [Dynamic Folder](https://docs.royalapps.com/r2023/royalserver/royal-server-configuration/dynamic-folder.html):

1. In Royal TSX, create a new **Dynamic Folder**
2. Set the **Script Interpreter** to `/bin/zsh`
3. Add the following script:

```bash
set -euo pipefail

cd "/path/to/pve-royal-inventory"

# uv automatically:
# - creates/uses .venv
# - installs dependencies from pyproject.toml
# - respects environment variables (.env already loaded by python-dotenv)

uv run --quiet main.py
```

4. Set the **Reload Interval** as desired (e.g., 5 minutes)
5. Save the dynamic folder

The script will automatically update your SSH connections based on your Proxmox inventory.

## How It Works

1. **Connect to Proxmox API**: Uses token authentication to connect to your Proxmox cluster
2. **Fetch Resources**: Retrieves all QEMU VMs and LXC containers from the cluster
3. **Discover IP Addresses**:
   - For QEMU VMs: Uses the guest agent to fetch network interfaces
   - For LXC containers: Parses network configuration from the container config
4. **Filter IPs**: Applies subnet filtering, preferring IPs in the preferred subnet
5. **Generate Document**: Creates a Royal TSX JSON document with:
   - Credential object for SSH authentication
   - Folder per Proxmox node
   - SSH connection per VM/container with discovered IP

## Output Structure

The generated JSON follows this structure:

```json
{
  "Objects": [
    {
      "Type": "Credential",
      "Name": "Services SSH",
      "UserName": "your-username",
      "ID": "credential-id",
      "Path": "/Credentials"
    },
    {
      "Type": "Folder",
      "Name": "node1",
      "Objects": [
        {
          "Type": "TerminalConnection",
          "TerminalConnectionType": "SSH",
          "Name": "100 (vm-name)",
          "ComputerName": "10.10.99.10",
          "CredentialID": "credential-id"
        }
      ]
    }
  ]
}
```

## Troubleshooting

### No IPs discovered

- **QEMU VMs**: Ensure the QEMU guest agent is installed and running in the VM
- **LXC containers**: Check that network interfaces are properly configured in the container config

### TLS verification errors

Set `PVE_VERIFY_TLS=false` in your `.env` file if using self-signed certificates.

### Permission errors

Ensure your API token has the following privileges:
- `VM.Audit` on all VMs/containers
- `Sys.Audit` on all nodes

### Enable debug logging

Set `LOGLEVEL=DEBUG` to see detailed information about the discovery process:

```bash
LOGLEVEL=DEBUG uv run main.py > inventory.json
```

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
