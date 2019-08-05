# Python built-in modules and packages
from dataclasses import dataclass
from typing import Dict, List, Union, Tuple


# --- Useful type hints ---
TableName = str
DatafieldName = str
PacketType = str
PacketData = Union[int, str, float]
Packet = Dict[DatafieldName, PacketData]
Message = Dict[str, List[Packet]]
RowDB = List[Tuple[DatafieldName, PacketData]]
DbFormat = Dict[str, List[DatafieldName]]

# Database table formats
dbFormats: DbFormat = {
    "gps": [
        "timestamp",
        "date",
        "hour",
        "tbr_serial_id",
        "SLIM_status",
        "longitude",
        "latitude",
        "pdop",
        "FIX",
        "num_sat_tracked",
        "comment",
    ],
    "tbr": [
        "timestamp",
        "date",
        "hour",
        "tbr_serial_id",
        "temperature",
        "temperature_data_raw",
        "noise_avg",
        "noise_peak",
        "frequency",
        "comment",
    ],
    "tag": [
        "timestamp",
        "date",
        "hour",
        "tbr_serial_id",
        "comm_protocol",
        "frequency",
        "tag_id",
        "tag_data",
        "tag_data_raw",
        "tag_data_2",  # DS256
        "tag_data_raw_2",  # DS256
        "snr",
        "millisecond",
        "comment",
    ],
}


@dataclass
class DatabasePacket:
    table: TableName
    columns: Tuple[str]
    values: Tuple[PacketData]
    numOfValues: int = 0
    sql_columns: str = ""
    sql_values: str = ""

    def __post_init__(self):
        self.numOfValues = len(self.values)
        self._handle_sql_columns()
        self._handle_sql_values()

    def _handle_sql_columns(self):
        """
        Uses columns=('col_name_1', 'col_name_2', ..., 'col_name_n')
        to set self.sql_columns='(col_name_1, col_name_2, ..., col_name_3)'
        """
        iterable = iter(self.columns)
        column_names = f"({next(iterable)}"
        while True:
            try:
                column_names += f", {next(iterable)}"
            except StopIteration:
                column_names += ")"
                break
        self.sql_columns = column_names

    def _handle_sql_values(self):
        """
        Uses numOfValues to set self.sql_values='(?, ?, ..., ?)' for safer sql insertion
        """
        self.sql_values = f"({'?, '*(self.numOfValues - 1)}?)"


def convert_msg_to_database_format(msg: Message, msgID: int) -> List[DatabasePacket]:
    dbmsg: List[DatabasePacket] = []
    for i, packet in enumerate(msg.payload):
        type: TableName = packet["packetType"]
        dbformat: List[DatafieldName] = dbFormats[type]
        columns, values = [], []  # type: List[str], List[PacketData]
        for datafield in dbformat:
            if datafield in packet:
                columns.append(datafield)
                values.append(packet[datafield])
        # add message_id to packet
        columns.insert(0, "message_id")
        values.insert(0, msgID)
        dbPacket = DatabasePacket(type, tuple(columns), tuple(values))
        dbmsg.append(dbPacket)
    return dbmsg
