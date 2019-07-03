# Python built-in modules and packages
from dataclasses import dataclass
from typing import Mapping, Tuple, List, Optional


# Constants
MSB = True
LSB = False
HEADER_TYPE_INDEX = 0x01
HEADER_00B_INDEX = 0x06
HEADER_GPS_INDEX = 0x10
HEADER_TYPE_GPS = 0x01
REF_TIMESTAMP = 0x04
CODE_TBR = 0xFF
CODE_INDEX = 0x01
COMM_ID_INDEX = 0x02
COMM_PROTOCOL_LIST = ["R256", "R04K", "R64K", "S256", "R01M", "S64K", "HS256", "DS256"]
ENDIAN = "big"  # for int.from_bytes() unpacking of complete bytes (no bit masking)

# ---- Protocol format ----
# | A packet consists of datafields spread over slices of data with overlapping bits
@dataclass
class DataField:
    name: str
    length: int
    bits: Optional[int] = None
    MSB: Optional[bool] = None


@dataclass
class PacketSlice:
    numBytes: int
    datafields: List[DataField]


# --- Useful type hints ---
PacketFormat = List[PacketSlice]
CodeKeyMap = Tuple[str, int]  # (protocol, tag frequency)
CodeType = Mapping[int, CodeKeyMap]

# COMBAK(perkjelsvik) - Implement as this dataclass instead of list - removes need for checking type
@dataclass
class PacketType:
    type: str
    format: PacketFormat


# Initialize dict of mappings
codetypes: CodeType = {}
frequency = 69
value = 0
for i in range(0, 15):
    for j in range(0, 8):
        codetypes.update({value: (COMM_PROTOCOL_LIST[j], frequency)})
        value += 1
    value += 8
    frequency += 1
    if value == 144:
        frequency = 63
del frequency, value, i, j  # Only needed to initalize codetypes

# Packet unpacking format for all packet types and header
header: PacketFormat = [
    PacketSlice(
        2, [DataField("tbr_serial_id", 2, 14, MSB), DataField("headerType", 1, 2, LSB)]
    ),
    PacketSlice(4, [DataField("ref_timestamp", 4)]),
]

gps: PacketFormat = [
    PacketSlice(
        5, [DataField("SLIM_status", 2, 14, MSB), DataField("longitude", 4, 26, LSB)]
    ),
    PacketSlice(4, [DataField("pdop", 1, 7, MSB), DataField("latitude", 4, 25, LSB)]),
    # PacketSlice(4, [DataField("latitude", 4, 25, MSB), DataField("pdop", 1, 7, LSB)]),
    PacketSlice(
        1, [DataField("FIX", 1, 3, MSB), DataField("num_sat_tracked", 1, 5, LSB)]
    ),
]

tag: PacketFormat = [
    PacketSlice(1, [DataField("timestamp", 1)]),
    PacketSlice(1, [DataField("commCode", 1)]),  # id/data/frequency added in unpacking
    PacketSlice(2, [DataField("snr", 1, 6, MSB), DataField("millisecond", 2, 10, LSB)]),
]

tbr: PacketFormat = [
    PacketSlice(1, [DataField("timestamp", 1)]),
    PacketSlice(1, [DataField("commCode", 1)]),
    PacketSlice(2, [DataField("temperature", 2), DataField("temperature_data_raw", 2)]),
    PacketSlice(1, [DataField("noise_avg", 1)]),
    PacketSlice(1, [DataField("noise_peak", 1)]),
    PacketSlice(1, [DataField("frequency", 1)]),
]

# mapping of communication protocol and tag_id/tag_data unpacking
# |-- Appropiate unpacking added to copy of tag PacketFormat when unpacking
comm_protocols: Mapping[str, PacketFormat] = {
    "R256": [PacketSlice(1, [DataField("tag_id", 1)])],
    "R04K": [PacketSlice(2, [DataField("tag_id", 2)])],
    "R64K": [PacketSlice(2, [DataField("tag_id", 2)])],
    "S256": [
        PacketSlice(1, [DataField("tag_id", 1)]),
        PacketSlice(1, [DataField("tag_data", 1), DataField("tag_data_raw", 1)]),
    ],
    "R01M": [PacketSlice(3, [DataField("tag_id", 3)])],
    "S64k": [
        PacketSlice(2, [DataField("tag_id", 2)]),
        PacketSlice(1, [DataField("tag_data", 1), DataField("tag_data_raw", 1)]),
    ],
    "HS256": [
        PacketSlice(1, [DataField("tag_id", 1)]),
        PacketSlice(2, [DataField("tag_data", 2), DataField("tag_data_raw", 2)]),
    ],
    "DS256": [
        PacketSlice(1, [DataField("tag_id", 1)]),
        PacketSlice(1, [DataField("tag_data", 1), DataField("tag_data_raw", 1)]),
        PacketSlice(1, [DataField("tag_data_2", 1), DataField("tag_data_2_raw", 1)]),
    ],
}
