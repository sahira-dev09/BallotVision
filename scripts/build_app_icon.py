"""Build a multi-resolution BallotVision .ico from the SVG logo."""

import os
import struct
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPen
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "app" / "assets" / "ballotvision_logo.svg"
ICO = ROOT / "app" / "assets" / "ballotvision.ico"
CHEVRON = ROOT / "app" / "assets" / "icons" / "chevron_down.png"
SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def _png_bytes(image: QImage) -> bytes:
    array = QByteArray()
    buffer = QBuffer(array)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(array)


def _write_ico(path: Path, images: list[tuple[int, bytes]]) -> None:
    count = len(images)
    offset = 6 + 16 * count
    header = struct.pack("<HHH", 0, 1, count)
    directory = b""
    blobs = b""
    for size, blob in images:
        stored = 0 if size >= 256 else size
        directory += struct.pack("<BBBBHHII", stored, stored, 0, 0, 1, 32, len(blob), offset)
        blobs += blob
        offset += len(blob)
    path.write_bytes(header + directory + blobs)


def main() -> None:
    app = QGuiApplication(sys.argv)
    renderer = QSvgRenderer(str(SVG))
    assert renderer.isValid(), SVG
    images = []
    for size in SIZES:
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        inset = 1 if size <= 24 else 0
        renderer.render(painter, QRectF(inset, inset, size - inset * 2, size - inset * 2))
        painter.end()
        images.append((size, _png_bytes(image)))
    _write_ico(ICO, images)
    chevron = QImage(24, 24, QImage.Format.Format_ARGB32)
    chevron.fill(Qt.GlobalColor.transparent)
    painter = QPainter(chevron)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#22D3EE"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    painter.drawLine(6, 9, 12, 15)
    painter.drawLine(12, 15, 18, 9)
    painter.end()
    CHEVRON.parent.mkdir(parents=True, exist_ok=True)
    chevron.save(str(CHEVRON))
    print("wrote", ICO, ICO.stat().st_size, "bytes", "sizes", SIZES)
    print("wrote", CHEVRON)
    app.quit()


if __name__ == "__main__":
    main()
