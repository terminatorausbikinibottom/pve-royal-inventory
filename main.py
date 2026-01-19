#!/usr/bin/env python3
"""
Generate a Royal TSX JSON document from Proxmox VE inventory.

- Uses Proxmox API token auth
- Outputs SSH connections for VMs + LXCs
- Royal TSX compatible object structure
"""

from __future__ import annotations

from collections import defaultdict
import json
import os
import logging
import sys
from typing import Dict, List, Any
from ipaddress import ip_address, ip_network

from proxmoxer import ProxmoxAPI


# ----------------------------
# Configuration (env-based)
# ----------------------------
from dotenv import load_dotenv

load_dotenv()

PVE_HOST = os.environ["PVE_HOST"]
PVE_PORT = int(os.getenv("PVE_PORT", "8006"))
PVE_USER = os.environ.get("PVE_USER")
PVE_TOKEN_ID = os.environ["PVE_TOKEN_ID"]
PVE_TOKEN_SECRET = os.environ["PVE_TOKEN_SECRET"]
PVE_VERIFY_TLS = os.getenv("PVE_VERIFY_TLS", "true").lower() == "true"

CRED_ID = os.environ.get("CRED_ID")
CRED_USERNAME = os.environ.get("CRED_USERNAME")
CRED_PASSWORD = os.environ.get("CRED_PASSWORD")

ALLOWED_SUBNET = os.getenv("ALLOWED_SUBNET", "10.10.0.0/16")
PREFERRED_SUBNET = os.getenv("PREFERRED_SUBNET", "10.10.99.0/24")

# ----------------------------
# Logging
# ----------------------------
LOGLEVEL = os.environ.get("LOGLEVEL", "WARNING").upper()
logging.basicConfig(level=LOGLEVEL)

# ----------------------------
# Proxmox helpers
# ----------------------------


def filter_preferred_ips(ips: List[str]) -> List[str]:
    """Filter IPs to allowed subnet, preferring specific subnet."""
    allowed_net = ip_network(ALLOWED_SUBNET)
    preferred_net = ip_network(PREFERRED_SUBNET)

    allowed: List[str] = []
    preferred: List[str] = []

    for ip in ips:
        try:
            addr = ip_address(ip)
        except ValueError:
            continue

        if addr.version != 4:
            continue

        if addr not in allowed_net:
            continue

        allowed.append(ip)

        if addr in preferred_net:
            preferred.append(ip)

    if preferred:
        return sorted(preferred)

    return sorted(allowed)


def get_vm_ips_qemu(pve: ProxmoxAPI, node: str, vmid: int) -> List[str]:
    try:
        data = pve.nodes(node).qemu(vmid).agent("network-get-interfaces").get()
        logging.debug("VM %s/%s agent data: %s", node, vmid, data)
    except Exception:
        return []

    ips: List[str] = []
    for iface in data.get("result", []):
        for addr in iface.get("ip-addresses", []):
            if addr.get("ip-address-type") == "ipv4":
                ips.append(addr["ip-address"])

    return filter_preferred_ips(ips)


def get_vm_ips_lxc(pve: ProxmoxAPI, node: str, vmid: int) -> List[str]:
    try:
        cfg = pve.nodes(node).lxc(vmid).config.get()
    except Exception:
        return []

    ips: List[str] = []
    for key, value in cfg.items():
        if key.startswith("net") and "ip=" in value:
            for part in value.split(","):
                if part.startswith("ip="):
                    ip = part.split("=")[1].split("/")[0]
                    ips.append(ip)

    return filter_preferred_ips(ips)


# ----------------------------
# Main
# ----------------------------


def main() -> None:
    pve = ProxmoxAPI(
        PVE_HOST,
        port=PVE_PORT,
        user=PVE_USER,
        token_name=PVE_TOKEN_ID,
        token_value=PVE_TOKEN_SECRET,
        verify_ssl=PVE_VERIFY_TLS,
    )

    logging.debug("BASE URL: %s", pve)

    resources = pve.cluster.resources.get()
    resources = [r for r in resources if r["type"] in ("qemu", "lxc")]

    connections: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for res in resources:
        vmid = res["vmid"]
        node = res["node"]
        name = res.get("name", f"vm-{vmid}")
        vmtype = res["type"]

        ips: List[str] = []

        if vmtype == "qemu" and res.get("status") == "running":
            ips = get_vm_ips_qemu(pve, node, vmid)
        elif vmtype == "lxc":
            ips = get_vm_ips_lxc(pve, node, vmid)

        if not ips:
            continue  # skip entries without usable IPs

        for ip in ips:
            connections[node].append(
                {
                    "Type": "TerminalConnection",
                    "TerminalConnectionType": "SSH",
                    "Name": f"{vmid} ({name})",
                    "ComputerName": ip,
                    "CredentialID": CRED_ID,
                }
            )

    # Build folder structure: one folder per node
    node_folders = [
        {
            "Type": "Folder",
            "Name": node,
            "Objects": conns,
        }
        for node, conns in connections.items()
    ]

    royal_document = {
        "Objects": [
            {
                "Type": "Credential",
                "Name": "Services SSH",
                "UserName": CRED_USERNAME,
                "ID": CRED_ID,
                "Path": "/Credentials",
            },
            *node_folders,
        ]
    }

    json.dump(royal_document, sys.stdout, separators=(",", ":"), ensure_ascii=False)


if __name__ == "__main__":
    main()
