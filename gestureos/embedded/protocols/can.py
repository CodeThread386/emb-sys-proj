"""CAN Protocol Simulator — frame-level CAN 2.0A encoding.

Models the actual CAN frame structure: SOF, arbitration ID, control,
data, CRC, ACK, EOF. Includes priority-based arbitration.
"""

import threading
import time
from typing import List
from dataclasses import dataclass, field

from gestureos import config


@dataclass
class CANFrame:
    timestamp: float
    arb_id: int              # 11-bit arbitration ID
    dlc: int                 # data length code (0–8)
    data: List[int]          # payload bytes
    is_remote: bool = False  # RTR frame
    # Bit-level structure (simplified visual)
    frame_bits: str = ""
    description: str = ""

    @property
    def priority(self) -> int:
        return self.arb_id  # lower = higher priority


class CANSimulator:
    def __init__(self):
        self._lock = threading.Lock()
        self._history: List[CANFrame] = []
        self._max_frames = 30
        self._bus_load_pct: float = 0.0
        self._frame_count = 0

    def send_frame(self, arb_id: int, data: List[int],
                   description: str = "", is_remote: bool = False) -> CANFrame:
        """Build a CAN 2.0A standard frame with proper field structure."""
        arb_id &= 0x7FF  # 11-bit
        dlc = min(8, len(data))
        data = data[:dlc]

        # Build frame bit representation
        sof = "0"                                         # Start of Frame
        id_bits = f"{arb_id:011b}"                        # 11-bit ID
        rtr = "1" if is_remote else "0"                   # RTR
        ide = "0"                                         # IDE (standard)
        r0 = "0"                                          # Reserved
        dlc_bits = f"{dlc:04b}"                           # DLC
        data_bits = "".join(f"{b:08b}" for b in data)     # Data field

        payload_for_crc = id_bits + rtr + ide + r0 + dlc_bits + data_bits
        crc = self._calc_crc15(payload_for_crc)
        crc_bits = f"{crc:015b}"

        crc_del = "1"
        ack = "0"       # ACK slot (dominant = acknowledged)
        ack_del = "1"
        eof = "1111111"  # 7 recessive bits

        frame_bits = (
            f"SOF:{sof} | "
            f"ID:{id_bits} | "
            f"RTR:{rtr} IDE:{ide} r0:{r0} | "
            f"DLC:{dlc_bits} | "
            f"DATA:{data_bits if data_bits else 'none'} | "
            f"CRC:{crc_bits} | "
            f"ACK:{ack} | "
            f"EOF:{eof}"
        )

        frame = CANFrame(
            timestamp=time.time(),
            arb_id=arb_id,
            dlc=dlc,
            data=data,
            is_remote=is_remote,
            frame_bits=frame_bits,
            description=description,
        )

        with self._lock:
            self._history.append(frame)
            self._frame_count += 1
            if len(self._history) > self._max_frames:
                self._history = self._history[-self._max_frames:]

            total_bits = 1 + 11 + 1 + 1 + 1 + 4 + (dlc * 8) + 15 + 1 + 1 + 1 + 7
            bit_time_us = 1_000_000 / config.CAN_BAUD_RATE
            frame_time_us = total_bits * bit_time_us
            self._bus_load_pct = min(100, frame_time_us / 1000 * 10)

        return frame

    def _calc_crc15(self, bits_str: str) -> int:
        """CAN CRC-15 with polynomial 0x4599."""
        crc = 0
        for bit_ch in bits_str:
            bit = int(bit_ch)
            msb = (crc >> 14) & 1
            crc = (crc << 1) & 0x7FFF
            if msb ^ bit:
                crc ^= 0x4599
        return crc

    def get_history(self) -> List[CANFrame]:
        with self._lock:
            return list(self._history)

    @property
    def bus_load(self) -> float:
        with self._lock:
            return self._bus_load_pct

    @property
    def frame_count(self) -> int:
        return self._frame_count

    @staticmethod
    def decode_frame_str(frame: CANFrame) -> str:
        data_hex = " ".join(f"{b:02X}" for b in frame.data)
        return f"ID=0x{frame.arb_id:03X} DLC={frame.dlc} [{data_hex}]"
