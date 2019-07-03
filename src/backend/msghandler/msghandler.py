# Python built-in modules and packages
import logging
from dataclasses import dataclass
from pprint import pprint
from typing import Dict, List, Union

# Local modules and packages
from src.backend.msghandler import protocol as C
from src.backend.msghandler import packet as pack
from src.backend.msghandler import conversion


# --- Useful type hints ---
# Packet data can be int, float and str, but raw packet data is only integers
DatafieldName = str
PacketData = Union[int, str, float]
Packet = Dict[DatafieldName, PacketData]
Header = Packet

# create logger with 'mqtt_client' and with stream level DEBUG; file level WARNING
logger = logging.getLogger("mqtt_client.msghandler")


@dataclass
class Message:
    header: Packet  # currently not used except for print
    payload: List[Packet]


class MessageHandlingError(ValueError):
    pass


def handle_message(data: bytes) -> Message:
    """
    Return unpacked and converted internetoffish message as a dictonary with msg header
    and payload as list data. Adds tbr_serial_id and correct timestamp to each packet,
    and sets gps data as a packet in payload rather than header.
    Takes bytes data as input, formatted according to protocol used in SLIM hardware.
    Each packet is handled so that data is converted or changed appropriately (commCode
    3 becomes 'S256' f. ex. and tag_data with conversion factor is handled etc.)
    """
    if data == b"":
        raise ValueError("Message has no data!")
    index, packetNum, payload = 0, 0, []  # type: int, int, List[Packet]
    err = None

    # Extract tbr_serial_id, headertype, and ref_timestamp
    logger.info("Unpacking message")
    header: Header = pack.unpack_packet(data[index : C.HEADER_00B_INDEX], C.header)
    index = C.HEADER_00B_INDEX
    if header["headerType"] == C.HEADER_TYPE_GPS:
        packet = pack.unpack_packet(data[index : C.HEADER_GPS_INDEX], C.gps)
        _add_tbr_id_type_and_timestamp(header, packet, type="gps")
        payload.append(conversion.convert_packet_payload(packet))
        index = C.HEADER_GPS_INDEX

    # Unpack payload data
    while index < len(data):
        # Unpacking format based on comm_protocol - length needed for index
        comm = data[index + C.CODE_INDEX]
        try:
            length, type, format = pack.get_packet_length_type_and_format(comm)
        except ValueError as WrongCommCode:
            logger.error(WrongCommCode)
            logger.warning("Because of variable index, can't unpack rest of message!")
            err = WrongCommCode
            break
        else:
            packetNum += 1
            logger.info(f"|{'---'*1} Unpacking packet {packetNum} ({type})")
            packet = pack.unpack_packet(data[index : index + length], format)
            _add_tbr_id_type_and_timestamp(header, packet, type)
            payload.append(conversion.convert_packet_payload(packet))
            index += length
    if err is not None:
        raise MessageHandlingError(f"Failed message handling: {err}")
    msg = Message(header, payload)
    logger.info("Done unpacking message: \n")
    pprint(msg.header, indent=4, width=1)
    pprint(msg.payload, indent=4, width=1)
    print()  # for nicer printing
    return msg


def _add_tbr_id_type_and_timestamp(header: Packet, packet: Packet, type: str) -> None:
    # GPS packet does not send timestamp information
    # | GPS timestamp is therefore set to reference_timestamp of message
    if type == "gps":
        packet.update({"timestamp": 0})
    tbr_id = header["tbr_serial_id"]
    timestamp = header["ref_timestamp"] + packet["timestamp"]

    # check if timestamp has overflowed due to rare error in tbr msg transfer order
    timedifference = timestamp - header["ref_timestamp"]
    if timedifference > 250:
        timestamp = header["ref_timestamp"] - (255 - timedifference)
    packet.update({"tbr_serial_id": tbr_id, "timestamp": timestamp, "packetType": type})
