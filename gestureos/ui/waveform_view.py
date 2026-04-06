"""Protocol Waveform View — logic analyzer style visualization.

Shows UART, I2C (SDA/SCL), and CAN bus waveforms as digital signals.
"""

from typing import List

import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont


COLORS = {
    "uart": (46, 204, 113),
    "i2c_sda": (52, 152, 219),
    "i2c_scl": (155, 89, 182),
    "can": (230, 126, 34),
}


class WaveformView(pg.PlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackground("#0a0a23")
        self.setTitle("Protocol Waveforms (Logic Analyzer)", color="w", size="11pt")
        self.setLabel("bottom", "Sample")
        self.showGrid(x=True, y=False, alpha=0.15)
        self.setMouseEnabled(x=True, y=False)
        self.setYRange(-0.5, 7.5, padding=0)

        left = self.getAxis("left")
        left.setTicks([[(0.5, "UART TX"), (2.5, "I2C SDA"), (4.5, "I2C SCL"), (6.5, "CAN")]])

    def update_waveforms(self, uart: List[int], i2c_sda: List[int],
                         i2c_scl: List[int], can_bits: List[int]):
        self.clear()

        left = self.getAxis("left")
        left.setTicks([[(0.5, "UART TX"), (2.5, "I2C SDA"), (4.5, "I2C SCL"), (6.5, "CAN")]])

        # Separator lines
        for y in [2, 4, 6]:
            line = pg.InfiniteLine(pos=y - 0.3, angle=0,
                                   pen=pg.mkPen(color=(50, 50, 50), width=1, style=Qt.PenStyle.DashLine))
            self.addItem(line)

        # UART: offset 0
        if uart:
            self._draw_digital(uart, offset=0, color=COLORS["uart"])

        # I2C SDA: offset 2
        if i2c_sda:
            self._draw_digital(i2c_sda, offset=2, color=COLORS["i2c_sda"])

        # I2C SCL: offset 4
        if i2c_scl:
            self._draw_digital(i2c_scl, offset=4, color=COLORS["i2c_scl"])

        # CAN: offset 6
        if can_bits:
            self._draw_digital(can_bits, offset=6, color=COLORS["can"])

    def _draw_digital(self, data: List[int], offset: float, color: tuple):
        if not data:
            return

        xs = []
        ys = []
        for i, val in enumerate(data):
            y = offset + (val * 1.0)
            if i > 0:
                xs.append(i)
                ys.append(ys[-1])
            xs.append(i)
            ys.append(y)

        pen = pg.mkPen(color=color, width=2)
        self.plot(xs, ys, pen=pen)
