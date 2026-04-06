"""ADC/DAC Pipeline Visualization.

Shows the analog input signal, SAR approximation steps,
and DAC reconstruction output.
"""

from typing import List

import pyqtgraph as pg
import numpy as np
from PyQt6.QtCore import Qt

from gestureos.embedded.peripherals.adc import ADCConversion


class ADCView(pg.PlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackground("#0a0a23")
        self.setTitle("ADC/DAC Pipeline", color="w", size="11pt")
        self.setLabel("bottom", "Sample")
        self.setLabel("left", "Value")
        self.showGrid(x=True, y=True, alpha=0.15)
        self.addLegend(offset=(60, 10))

        self._adc_curve = self.plot([], [], pen=pg.mkPen(color=(46, 204, 113), width=2),
                                    name="ADC (digital)")
        self._dac_curve = self.plot([], [], pen=pg.mkPen(color=(231, 76, 60), width=1,
                                    style=Qt.PenStyle.DashLine), name="DAC (reconstructed)")
        self._analog_curve = self.plot([], [], pen=pg.mkPen(color=(52, 152, 219), width=1),
                                       name="Analog input")

    def update_data(self, adc_history: List[int], dac_history: List[float],
                    max_val: int, vref: float):
        if not adc_history:
            return

        xs = list(range(len(adc_history)))
        self._adc_curve.setData(xs, adc_history)

        if dac_history:
            dxs = list(range(len(dac_history)))
            scaled_dac = [v / vref * max_val for v in dac_history]
            self._dac_curve.setData(dxs, scaled_dac)

        smoothed = []
        alpha = 0.3
        val = adc_history[0]
        for v in adc_history:
            val = alpha * v + (1 - alpha) * val
            smoothed.append(val)
        self._analog_curve.setData(xs, smoothed)

        self.setYRange(0, max_val * 1.05, padding=0)
