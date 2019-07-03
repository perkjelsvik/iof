# Python built-in modules and packages
from typing import Mapping, Tuple

# Local modules and packages
from src.backend.msghandler import protocol as C


# --- Useful type hints ---
# Packet data can be int, float and str, but raw packet data is only integers
DatafieldName = str
Packet = Mapping[DatafieldName, int]
PacketTypeLengthFormat = Tuple[int, str, C.PacketFormat]


def get_packet_length_type_and_format(code: int) -> PacketTypeLengthFormat:
    """
    Returns packet length and unpacking format based on code. If code is 255, packet is
    a TBR sensor msg. If code is a (valid) key in msghandler.protocol codetypes
    dictionary, get associated communication protocol and insert unpacking format for
    this communication protocol in packet unpacking format.
    Unpacking formats defined in msghandler.protocol.
    """
    length = 0
    if code == C.CODE_TBR:
        format = list(C.tbr)
    elif code in list(C.codetypes.keys()):
        format = list(C.tag)
        # C.codetypes maps codeKey to communication protocol
        comm, _ = C.codetypes[code]
        # Add specific comm protocol datafield handling to format
        for datafield in reversed(C.comm_protocols[comm]):
            format.insert(C.COMM_ID_INDEX, datafield)
    else:
        raise ValueError(f"Wrong comm_protocol! code {code} is not supported")
    type = _get_packet_type(format)
    for segment in format:
        length += segment.numBytes
    return (length, type, format)


def unpack_packet(packetData: bytes, format: C.PacketFormat) -> Packet:
    """
    Unpacks bytes msg packet using format defined in msghandler.protocol.
    Iterates trough each segment of a message and unpacks the datafields contained
    inside. A segment consists of complete byte datafields and/or datafields of bits.
    Returns packet as a dictionary.
    """
    index, packet = 0, {}  # type: int, Packet
    # segment = [numBytes, Datafields]
    for segment in format:
        # datafield = [name, length, bits, MSB]
        for datafield in segment.datafields:
            packData = None
            data = packetData[index : index + datafield.length]
            packData = int.from_bytes(data, C.ENDIAN)
            if datafield.MSB is not None:
                # If LSB, the last bytes of the segment instead
                if datafield.MSB is False:
                    i = index + segment.numBytes
                    data = packetData[i - datafield.length : i]
                packData = _mask_data_from_bytes(data, datafield)
            else:
                packData = int.from_bytes(data, C.ENDIAN)
            packet.update({datafield.name: packData})
        index += segment.numBytes
    return packet


def _get_packet_type(format: C.PacketFormat) -> str:
    """
    Returns a string of packet type name based on unpacking format.
    """
    if format == C.gps:
        return "gps"
    elif format == C.tbr:
        return "tbr"
    else:
        # tag format is not static, and so should be placed in the else-clause
        return "tag"


def _mask_data_from_bytes(packetData: bytes, format: C.DataField) -> int:
    """
    Masks bytes based on format defined in msghandler.protocol,
    containing length of datafield, number of bits and wheter MSB or LSB.
    Returns masked bytes data as integer data.
    """
    shiftedData, shiftCount, length = [], format.length, format.length * 8
    # Extract bits from each byte, shift them appropiately
    for byte in packetData:
        shiftCount -= 1
        shiftedData.append(byte << shiftCount * 8)
    # Sum together the shifted bits, retaining bit information
    data = sum(shiftedData)
    # Mask out MSB bits by right-shifting data: 0b10011010 --> 0b1001
    #   | This also shifts the data to its correct value
    if format.MSB:
        maskedData = data >> (length - format.bits)
    # Mask out LSB bits by bit-masking data: 0b10011010 --> 0b1010
    else:
        mask = (1 << format.bits) - 1
        maskedData = mask & data
    return maskedData


def mask(data, lenData, bits, MSB):
    shiftedData, shiftCount, length = [], lenData, lenData * 8
    for byte in data:
        shiftCount -= 1
        shiftedData.append(byte << shiftCount * 8)
    data = sum(shiftedData)
    if MSB:
        maskedData = data >> (length - bits)
    else:
        mask = (1 << bits) - 1
        maskedData = mask & data
    return maskedData
