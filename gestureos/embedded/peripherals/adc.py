"""ADC Simulator — Successive Approximation Register (SAR) ADC model.

Converts the webcam frame brightness (analog input) to a digital value,
step-by-step through the SAR algorithm. Visualizes the conversion pipeline.
"""

import threading
from typing import List, Tuple
from dataclasses import dataclass, field

from gestureos import config


@dataclass
class ADCConversion:
    """One complete A/D conversion with step-by-step SAR approximation."""
    analog_input: float       # input voltage (0–Vref)
    digital_output: int       # final digital result
    resolution: int           # number of bits
    vref: float               # reference voltage
    steps: List[Tuple[int, float, bool]] = field(default_factory=list)
    # Each step: (bit_position, comparator_threshold, bit_value)


class ADCSimulator:
    def __init__(self, resolution: int = config.ADC_RESOLUTION_BITS, vref: float = config.ADC_VREF):
        self._resolution = resolution
        self._vref = vref
        self._lock = threading.Lock()
        self._latest_conversion: ADCConversion = ADCConversion(0, 0, resolution, vref)
        self._history: List[int] = []
        self._max_history = config.WAVEFORM_VISIBLE_SAMPLES

    def convert(self, brightness_0_255: float) -> ADCConversion:
        """Run a full SAR conversion on the input brightness.

        Maps brightness (0–255) to voltage (0–Vref), then performs
        successive approximation bit by bit.
        """
        v_in = (brightness_0_255 / 255.0) * self._vref
        v_in = max(0.0, min(self._vref, v_in))

        digital = 0
        steps = []
        dac_output = 0.0

        for bit in range(self._resolution - 1, -1, -1):
            digital |= (1 << bit)
            dac_output = (digital / (2**self._resolution)) * self._vref

            if dac_output > v_in:
                digital &= ~(1 << bit)
                steps.append((bit, dac_output, False))
            else:
                steps.append((bit, dac_output, True))

        conv = ADCConversion(
            analog_input=v_in,
            digital_output=digital,
            resolution=self._resolution,
            vref=self._vref,
            steps=steps,
        )

        with self._lock:
            self._latest_conversion = conv
            self._history.append(digital)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        return conv

    def get_latest(self) -> ADCConversion:
        with self._lock:
            return self._latest_conversion

    def get_history(self) -> List[int]:
        with self._lock:
            return list(self._history)

    @property
    def max_value(self) -> int:
        return (2**self._resolution) - 1

    @property
    def resolution(self) -> int:
        return self._resolution

    @property
    def lsb_voltage(self) -> float:
        return self._vref / (2**self._resolution)
