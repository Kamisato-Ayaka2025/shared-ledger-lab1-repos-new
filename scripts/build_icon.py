"""Generate the existing tray design as a multi-resolution Windows icon."""

from pathlib import Path
import struct
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

app = QApplication([])
images = []
sizes = (16, 24, 32, 48, 64, 128, 256)
for size in sizes:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor("#187662"))
    painter = QPainter(pixmap)
    painter.setPen(QColor("white"))
    font = QFont("Microsoft YaHei")
    font.setWeight(QFont.Weight.Bold)
    font.setPixelSize(round(size * 2 / 3))
    painter.setFont(font)
    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "同")
    painter.end()
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    images.append(bytes(buffer.data()))
header = struct.pack("<HHH", 0, 1, len(images))
offset = 6 + 16 * len(images)
for size, data in zip(sizes, images):
    header += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
    offset += len(data)
target = Path(__file__).resolve().parents[1] / "src/tongzhang/assets/tongzhang.ico"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(header + b"".join(images))
print(target)
