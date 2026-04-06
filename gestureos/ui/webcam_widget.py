"""Webcam feed widget with gesture overlay."""

from PyQt6.QtWidgets import QLabel
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap
import numpy as np


class WebcamWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(320, 240)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #111; border: 1px solid #333; border-radius: 4px;")
        self.setText("Webcam Feed")

    def update_frame(self, frame: np.ndarray):
        if frame is None:
            return
        h, w, ch = frame.shape
        bpl = ch * w
        img = QImage(frame.data, w, h, bpl, QImage.Format.Format_BGR888)
        pix = QPixmap.fromImage(img).scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self.setPixmap(pix)
