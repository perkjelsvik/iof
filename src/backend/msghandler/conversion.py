# Python built-in modules and packages
import logging
import datetime as dt
from typing import Union, Dict, Callable, Tuple, Optional

# Third-party modules and packages
import toml

# Local modules and packages
from src.backend.msghandler.protocol import codetypes, CODE_TBR


# --- Useful type hints ---
# Packet data can be int, float, and str
PacketData = Union[str, int, float]
Packet = Dict[str, PacketData]
MetaDict = Dict[str, Dict[str, Union[int, float]]]
ConversionFunction = Callable[[str, Packet], PacketData]
ConversionMapping = Dict[str, ConversionFunction]

# create logger with 'mqtt_client' and with stream level DEBUG; file level WARNING
logger = logging.getLogger("mqtt_client.msghandler.payload_conversion")


def _init_metadata() -> Tuple[bool, MetaDict]:
    """
    Loads metadata_conversion.toml if it exists.
    The file holds tag_id and frequency combinations with a known conversion_factor.
    """
    _metadata, _metaDict = False, {}  # type: bool, MetaDict
    try:
        _metaDict = toml.load("src/backend/.config/metadata_conversion.toml")
    except FileNotFoundError:
        logger.info("NB! no metadata config file found. Will only store raw data")
    except Exception:
        logger.exception("Caught an error while loading metadata conversion")
    else:
        _metadata = True
    return (_metadata, _metaDict)


_metaFlag, _metaTable = _init_metadata()  # type: bool, MetaDict


def _get_metadata_conversion_factor(packet: Packet) -> Optional[float]:
    """
    Only used if there is metadata for the current project.
    Checks if there is a match between packet tag_id and frequency and metadata with
    this tag_id and frequency combination with a known conversion factor.
    Returns the conversion factor if it exists.
    """
    # Will not work if packet["commCode"] haven't been handled
    if "frequency" not in packet:
        # _convert_comm_protocol adds comm_protocol and frequency to packet
        _ = _convert_comm_protocol_frequency("commCode", packet)
    tag_id, frequency = packet["tag_id"], packet["frequency"]
    for row in _metaTable:
        id, freq = _metaTable[row]["tag_id"], _metaTable[row]["frequency"]
        if (id, freq) == (tag_id, frequency):
            return _metaTable[row]["conversion_factor"]
    return None


def _convert_tag_data(metadata: bool) -> Callable[[str, Packet], Union[int, float]]:
    """
    Closure function that checks if there is metadata for the project.
    | If there is not, the same raw integer data is returned back without checking.
    | If there is metadata, the function returns converted data if conversion factor
        exists for this specific tag_id and frequency.
    """

    def _local_conversion_func(key: str, packet: Packet) -> Union[int, float]:
        # Always returns tag_data_raw if there is no metadata
        if metadata:
            # Check if conversion factor exists for tag_id & frequency combination
            conversionFactor = _get_metadata_conversion_factor(packet)
            if conversionFactor is not None:
                # If conversion factor exists, adds converted tag_data to packet
                logger.info(f"|{'---'*3} Conversion factor exists")
                tag_data: float = packet[key] * conversionFactor
                return tag_data
        return packet[key]

    return _local_conversion_func


def _convert_lat_long(key: str, packet: Packet) -> float:
    """
    Current precision is 5 decimal places. Hardware does support up to 7 decimal places,
    but is limited to 5 decimal places currently as it is deemed to be sufficient.
    """
    latlong = packet[key]
    precision = 10e4  # 100000.0
    return latlong / precision  # truncuating


def _convert_fix(key: str, packet: Packet) -> str:
    """
    Based on page 313 of https://www.u-blox.com/sites/default/files/products/documents/
    u-blox8-M8_ReceiverDescrProtSpec_%28UBX-13003221%29_Public.pdf
    PDF: u-blox 8 / u-blox M8 - Receiver Description Including Protocol Specification
    Converts fix number to matching fix information.
    """
    fixKey = packet[key]
    quality = {
        0: "no fix",
        1: "dead reckoning only",
        2: "2D-fix",
        3: "3D-fix",
        4: "GNSS + dead reckoning combined",
        5: "time only fix",
        "default": f"Invalid fix value: {fixKey}",
    }
    fix = quality.get(fixKey, quality["default"])
    if fixKey not in range(0, 6):
        logger.error(f"Invalid GPS fix key! {fixKey} - corrupt data?")
    return fix


def _convert_pdop(key: str, packet: Packet) -> float:
    """
    Converts pdop to correct value.
    """
    precision = 10
    pdop = packet[key] / precision
    return pdop


def _convert_comm_protocol_frequency(key: str, packet: Packet) -> int:
    """
    Uses commCode to determine comm_protocol and frequency, then adds these two fields
    to the packet dictionary, before returning back the original code so that this
    datafield in the packet remains unchanged.
    """
    code = packet[key]
    if code == CODE_TBR:
        return code
    comm_protocol, frequency = codetypes[code]  # type: str, int
    packet.update({"comm_protocol": comm_protocol, "frequency": frequency})
    return code


def _convert_temperature(key: str, packet: Packet) -> float:
    """
    Temperature conversion formula from ThelmaBioTel documentation.
    Converts temperature from 0-255 integer to (-5.5, ..., 20.5) degrees celsius float.
    """
    temperature = (packet[key] - 50) / 10
    return temperature


def _convert_timestamp_datetime(key: str, packet: Packet) -> int:
    """
    Convert UTX UNIC timestamp to 'YYYY-MM-DD HH:MM:SS' string. Timestamp is UTC time,
    converted datetime string is local timezone time. Also extracts hour of timestamp 
    to integer. Returns timestamp back to avoid changes in the timestamp datafield.
    """
    date_format = "%Y-%m-%d %H:%M:%S"
    ts = packet[key]  # extract packet UTC timestamp
    date = dt.datetime.fromtimestamp(ts).strftime(date_format)  # converts to local TZ
    hour = int(dt.datetime.fromtimestamp(ts).strftime("%H"))  # extract hour too
    packet.update({"date": date, "hour": hour})  # add date and hour to packet payload
    return ts  # return ts to keep original value in packet


# A dict mapping packet data to functions handling them
# |-- Keywords omitted from dict does not require any handling

_conversion_functions: ConversionMapping = {
    "longitude": _convert_lat_long,
    "latitude": _convert_lat_long,
    "FIX": _convert_fix,
    "pdop": _convert_pdop,
    "timestamp": _convert_timestamp_datetime,
    "commCode": _convert_comm_protocol_frequency,
    "tag_data": _convert_tag_data(_metaFlag),
    "tag_data_2": _convert_tag_data(_metaFlag),  # DS256 case
    "temperature": _convert_temperature,
}


def convert_packet_payload(packet: Packet) -> Packet:
    """
    Iterates through packet datafield and checks whether they are in the
    ConverisonMapping dict.
        | If a datafield exists, the relevant conversion function is called.
        | The functions will either return converted data, or the same raw data,
            but adding new or converted datafields to the packet while executing.
        | Datafields not in the ConversionMapping are ignored
    Returns converted packet.
    """
    logger.info(f"|{'---'*2} Converting packet data")
    for datafield in dict(packet):
        if datafield in _conversion_functions:
            packet[datafield] = _conversion_functions[datafield](datafield, packet)
    return packet
