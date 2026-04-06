"""8051 Register and Memory Map viewer."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QFrame,
    QScrollArea,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


SFR_DISPLAY_ORDER = [
    "ACC", "B", "PSW", "SP", "DPL", "DPH",
    "P0", "P1", "P2", "P3",
    "TCON", "TMOD", "TL0", "TH0", "TL1", "TH1",
    "SCON", "SBUF", "IE", "IP", "PCON",
]

PSW_BITS = ["P", "—", "OV", "RS0", "RS1", "F0", "AC", "CY"]
IE_BITS = ["EX0", "ET0", "EX1", "ET1", "ES", "—", "—", "EA"]
TCON_BITS = ["IT0", "IE0", "IT1", "IE1", "TR0", "TF0", "TR1", "TF1"]


class RegisterView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels: dict = {}
        self._bit_labels: dict = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        title = QLabel("8051 SFR Map")
        title.setFont(QFont("Monospace", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: #00d4ff;")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(2)

        mono = QFont("Monospace", 10)

        for i, name in enumerate(SFR_DISPLAY_ORDER):
            row, col = divmod(i, 3)

            name_lbl = QLabel(f"{name}:")
            name_lbl.setFont(mono)
            name_lbl.setStyleSheet("color: #888;")
            name_lbl.setFixedWidth(45)

            val_lbl = QLabel("0x00")
            val_lbl.setFont(QFont("Monospace", 10, QFont.Weight.Bold))
            val_lbl.setStyleSheet("color: #2ecc71;")
            val_lbl.setFixedWidth(40)

            bin_lbl = QLabel("00000000")
            bin_lbl.setFont(QFont("Monospace", 9))
            bin_lbl.setStyleSheet("color: #666;")

            self._labels[name] = (val_lbl, bin_lbl)

            base_col = col * 3
            grid.addWidget(name_lbl, row, base_col)
            grid.addWidget(val_lbl, row, base_col + 1)
            grid.addWidget(bin_lbl, row, base_col + 2)

        layout.addLayout(grid)

        # Bit-field breakdown for key registers
        for reg_name, bit_names in [("PSW", PSW_BITS), ("IE", IE_BITS), ("TCON", TCON_BITS)]:
            frame = QFrame()
            frame.setStyleSheet("background: #0d1b2a; border-radius: 3px; padding: 2px;")
            fl = QHBoxLayout(frame)
            fl.setContentsMargins(4, 2, 4, 2)
            fl.setSpacing(1)

            rl = QLabel(f"{reg_name}:")
            rl.setFont(QFont("Monospace", 9))
            rl.setStyleSheet("color: #888;")
            rl.setFixedWidth(40)
            fl.addWidget(rl)

            bit_lbls = []
            for bn in reversed(bit_names):
                bl = QLabel(f"{bn}\n0")
                bl.setFont(QFont("Monospace", 8))
                bl.setAlignment(Qt.AlignmentFlag.AlignCenter)
                bl.setStyleSheet("color: #555; background: #1a1a2e; border-radius: 2px; padding: 1px;")
                bl.setFixedWidth(32)
                fl.addWidget(bl)
                bit_lbls.append(bl)

            self._bit_labels[reg_name] = list(reversed(bit_lbls))
            layout.addWidget(frame)

        # Memory view
        self._mem_label = QLabel("IRAM[0x00–0x3F]: 00 " * 16)
        self._mem_label.setFont(QFont("Monospace", 8))
        self._mem_label.setStyleSheet("color: #555; background: #0d1b2a; padding: 4px; border-radius: 3px;")
        self._mem_label.setWordWrap(True)
        layout.addWidget(self._mem_label)

        layout.addStretch()

    def update_state(self, snapshot: dict):
        sfr = snapshot.get("sfr", {})
        for name in SFR_DISPLAY_ORDER:
            if name in sfr and name in self._labels:
                val = sfr[name]
                vlbl, blbl = self._labels[name]

                old_text = vlbl.text()
                new_text = f"0x{val:02X}"
                vlbl.setText(new_text)
                blbl.setText(f"{val:08b}")

                if old_text != new_text and old_text != "0x00":
                    vlbl.setStyleSheet("color: #e74c3c; font-weight: bold;")
                else:
                    vlbl.setStyleSheet("color: #2ecc71; font-weight: bold;")

        for reg_name, bit_names in [("PSW", PSW_BITS), ("IE", IE_BITS), ("TCON", TCON_BITS)]:
            if reg_name in sfr and reg_name in self._bit_labels:
                val = sfr[reg_name]
                lbls = self._bit_labels[reg_name]
                for i, (bl, bn) in enumerate(zip(lbls, bit_names)):
                    bit_val = (val >> i) & 1
                    bl.setText(f"{bn}\n{bit_val}")
                    if bit_val:
                        bl.setStyleSheet("color: #2ecc71; background: #1a3a2e; border-radius: 2px; padding: 1px;")
                    else:
                        bl.setStyleSheet("color: #555; background: #1a1a2e; border-radius: 2px; padding: 1px;")

        iram_hex = snapshot.get("iram", "")
        if iram_hex:
            hex_bytes = [iram_hex[i:i+2] for i in range(0, min(128, len(iram_hex)), 2)]
            lines = []
            for row in range(0, len(hex_bytes), 16):
                addr = f"0x{row:02X}"
                row_hex = " ".join(hex_bytes[row:row+16])
                lines.append(f"{addr}: {row_hex}")
            self._mem_label.setText("\n".join(lines))
