# Copyright (C) Planetary Power, Inc - All Rights Reserved
# Unauthorized copying of this file, via any medium is strictly prohibited
# Proprietary and confidential
# Written by Matthew West <mwest@planetarypower.com>, August 2016
# References:
#   [1] AM335x Sitara Processors Technical Reference Manual

"""
This module implements two functions which get the unique ids located
on the TI am335 chip, which are factory-set, non-rewritable values
unique among all am335x chips. It will be used as a unique hardware
identifier.
"""

import struct
from mmap import mmap

CONTROL_MODULE_START_ADDRESS = 0x44E10000  # [1] p.179
CONTROL_MODULE_END_ADDRESS = 0x44E11FFF  # [1] p.179
CONTROL_MODULE_SIZE = CONTROL_MODULE_END_ADDRESS \
                      - CONTROL_MODULE_START_ADDRESS
MAC_ID0_LO_OFFSET = 0x630  # [1] p.1441
MAC_ID0_HI_OFFSET = 0x634  # [1] p.1442
MAC_ID1_LO_OFFSET = 0x638  # [1] p.1443
MAC_ID1_HI_OFFSET = 0x63C  # [1] p.1444
MAC_ID0, MAC_ID1 = None, None


def _get_ids():
    global MAC_ID0, MAC_ID1
    file_handler = open("/dev/mem", "r+b")
    mem = mmap(file_handler.fileno(),
               CONTROL_MODULE_SIZE,
               offset=CONTROL_MODULE_START_ADDRESS)
    mac_id0_lo_packed_reg = mem[MAC_ID0_LO_OFFSET:MAC_ID0_LO_OFFSET + 4]
    mac_id0_hi_packed_reg = mem[MAC_ID0_HI_OFFSET:MAC_ID0_HI_OFFSET + 4]
    mac_id1_lo_packed_reg = mem[MAC_ID1_LO_OFFSET:MAC_ID1_LO_OFFSET + 4]
    mac_id1_hi_packed_reg = mem[MAC_ID1_HI_OFFSET:MAC_ID1_HI_OFFSET + 4]

    mac_id0_lo = struct.unpack('<L', mac_id0_lo_packed_reg)[0]
    mac_id0_hi = struct.unpack('<L', mac_id0_hi_packed_reg)[0]

    mac_id0_bytes = [None] * 6
    mac_id0_bytes[0] = (mac_id0_lo & 0xff00) >> 8  # byte 0
    mac_id0_bytes[1] = (mac_id0_lo & 0x00ff)  # byte 1
    mac_id0_bytes[2] = (mac_id0_hi & 0xff000000) >> 24  # byte 2
    mac_id0_bytes[3] = (mac_id0_hi & 0x00ff0000) >> 16  # byte 3
    mac_id0_bytes[4] = (mac_id0_hi & 0x0000ff00) >> 8  # byte 4
    mac_id0_bytes[5] = (mac_id0_hi & 0x000000ff)  # byte 5

    MAC_ID0 = 0
    for i, byte in enumerate(mac_id0_bytes):
        MAC_ID0 |= ((byte & 0xff) << (i * 8))

    mac_id1_lo = struct.unpack('<L', mac_id1_lo_packed_reg)[0]
    mac_id1_hi = struct.unpack('<L', mac_id1_hi_packed_reg)[0]

    mac_id1_bytes = [None] * 6
    mac_id1_bytes[0] = (mac_id1_lo & 0xff00) >> 8  # byte 0
    mac_id1_bytes[1] = (mac_id1_lo & 0x00ff)  # byte 1
    mac_id1_bytes[2] = (mac_id1_hi & 0xff000000) >> 24  # byte 2
    mac_id1_bytes[3] = (mac_id1_hi & 0x00ff0000) >> 16  # byte 3
    mac_id1_bytes[4] = (mac_id1_hi & 0x0000ff00) >> 8  # byte 4
    mac_id1_bytes[5] = (mac_id1_hi & 0x000000ff)  # byte 5

    MAC_ID1 = 0
    for i, byte in enumerate(mac_id1_bytes):
        MAC_ID1 |= ((byte & 0xff) << (i * 8))

# Get the IDs
_get_ids()
