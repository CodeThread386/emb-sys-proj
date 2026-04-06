"""DAC Simulator — Digital to Analog reconstruction.

Takes a digital value and reconstructs an analog voltage with
step-function output and optional smoothing to show reconstruction filter.
"""

import threading
from typing import List
from dataclasses import dataclass

from gestureos import config


@dataclass
class DACOutput:
    digital_input: int
    analog_voltage: float
    resolution: int
    vref: float


class DACSimulator:
    def __init__(self, resolution: int = config.ADC_RESOLUTION_BITS, vref: float = config.ADC_VREF):
        self._resolution = resolution
        self._vref = vref
        self._lock = threading.Lock()
        self._latest: DACOutput = DACOutput(0, 0.0, resolution, vref)
        self._history: List[float] = []
        self._max_history = config.WAVEFORM_VISIBLE_SAMPLES

    def convert(self, digital_value: int) -> DACOutput:
        """Convert a digital value to an analog voltage."""
        digital_value = max(0, min((2**self._resolution) - 1, digital_value))
        voltage = (digital_value / (2**self._resolution)) * self._vref

        out = DACOutput(
            digital_input=digital_value,
            analog_voltage=voltage,
            resolution=self._resolution,
            vref=self._vref,
        )

        with self._lock:
            self._latest = out
            self._history.append(voltage)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        return out

    def get_latest(self) -> DACOutput:
        with self._lock:
            return self._latest

    def get_history(self) -> List[float]:
        with self._lock:
            return list(self._history)
