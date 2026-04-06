"""Bluetooth Low Energy (BLE) Simulator — advertising + GATT-like data model.

Models BLE advertisement packets and a simplified GATT characteristic
for sending gesture commands wirelessly. Demonstrates RS232/BT syllabus topic.
"""

import threading
import time
import struct
from typing import List, Optional
from dataclasses import dataclass, field


@dataclass
class BLEAdvertisement:
    timestamp: float
    adv_type: str        # "ADV_IND", "ADV_NONCONN_IND"
    addr: str            # simulated MAC address
    rssi: int            # signal strength (dBm)
    payload: bytes
    name: str = ""
    # Decoded fields
    fields_decoded: List[str] = field(default_factory=list)


@dataclass
class GATTCharacteristic:
    uuid: str
    name: str
    value: bytes
    properties: str      # "R", "W", "RW", "N" (notify)
    last_write_time: float = 0.0


class BLESimulator:
    def __init__(self):
        self._lock = threading.Lock()
        self._adv_history: List[BLEAdvertisement] = []
        self._max_history = 30
        self._device_name = "GestureOS-MCU"
        self._mac = "AA:BB:CC:DD:EE:01"

        self._characteristics: List[GATTCharacteristic] = [
            GATTCharacteristic(
                uuid="0000FFE1-0000-1000-8000-00805F9B34FB",
                name="Gesture Command",
                value=b"\x00",
                properties="RW",
            ),
            GATTCharacteristic(
                uuid="0000FFE2-0000-1000-8000-00805F9B34FB",
                name="System Status",
                value=b"\x01",
                properties="RN",
            ),
            GATTCharacteristic(
                uuid="0000FFE3-0000-1000-8000-00805F9B34FB",
                name="ADC Reading",
                value=b"\x00\x00",
                properties="R",
            ),
        ]

        self._connected = False
        self._adv_count = 0

    def send_advertisement(self, gesture_code: int = 0) -> BLEAdvertisement:
        """Generate a BLE advertisement packet with proper AD structure."""
        # Build AD structures
        # Type 0x01: Flags (LE General Discoverable, BR/EDR Not Supported)
        flags = bytes([0x02, 0x01, 0x06])
        # Type 0x09: Complete Local Name
        name_bytes = self._device_name.encode("utf-8")
        name_ad = bytes([len(name_bytes) + 1, 0x09]) + name_bytes
        # Type 0xFF: Manufacturer specific (gesture code)
        mfg_data = bytes([0x03, 0xFF, gesture_code & 0xFF, 0x00])

        payload = flags + name_ad + mfg_data

        decoded = [
            f"Flags: 0x06 (LE General Discoverable)",
            f"Name: {self._device_name}",
            f"Mfg Data: gesture=0x{gesture_code:02X}",
        ]

        adv = BLEAdvertisement(
            timestamp=time.time(),
            adv_type="ADV_IND",
            addr=self._mac,
            rssi=-40 - (self._adv_count % 20),
            payload=payload,
            name=self._device_name,
            fields_decoded=decoded,
        )

        with self._lock:
            self._adv_history.append(adv)
            self._adv_count += 1
            if len(self._adv_history) > self._max_history:
                self._adv_history = self._adv_history[-self._max_history:]

        return adv

    def write_characteristic(self, index: int, value: bytes):
        if 0 <= index < len(self._characteristics):
            self._characteristics[index].value = value
            self._characteristics[index].last_write_time = time.time()

    def read_characteristic(self, index: int) -> Optional[bytes]:
        if 0 <= index < len(self._characteristics):
            return self._characteristics[index].value
        return None

    def get_adv_history(self) -> List[BLEAdvertisement]:
        with self._lock:
            return list(self._adv_history)

    def get_characteristics(self) -> List[GATTCharacteristic]:
        return list(self._characteristics)

    @property
    def adv_count(self) -> int:
        return self._adv_count

    @property
    def device_name(self) -> str:
        return self._device_name

    @staticmethod
    def decode_adv_str(adv: BLEAdvertisement) -> str:
        return f"[{adv.adv_type}] {adv.addr} RSSI={adv.rssi}dBm \"{adv.name}\" ({len(adv.payload)}B)"
