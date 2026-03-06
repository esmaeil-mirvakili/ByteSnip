"""Convert assets/icons/code_color.svg → assets/icons/ByteSnip.icns using Qt + sips + iconutil."""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
SVG = ROOT / "assets" / "icons" / "code_color.svg"
OUT = ROOT / "assets" / "icons" / "ByteSnip.icns"

# Render SVG → 1024×1024 PNG via Qt (PySide6 is already a project dependency).
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

app = QApplication(sys.argv)

renderer = QSvgRenderer(str(SVG))
if not renderer.isValid():
    sys.exit(f"ERROR: could not load {SVG}")

img = QImage(1024, 1024, QImage.Format.Format_ARGB32)
img.fill(0)
painter = QPainter(img)
renderer.render(painter)
painter.end()

with tempfile.TemporaryDirectory() as tmp:
    src_png = Path(tmp) / "src.png"
    iconset = Path(tmp) / "ByteSnip.iconset"
    iconset.mkdir()

    img.save(str(src_png))

    # Build the iconset folder with all required sizes.
    for size in (16, 32, 128, 256, 512):
        subprocess.run(
            ["sips", "-z", str(size), str(size), str(src_png),
             "--out", str(iconset / f"icon_{size}x{size}.png")],
            check=True, capture_output=True,
        )
        size2 = size * 2
        subprocess.run(
            ["sips", "-z", str(size2), str(size2), str(src_png),
             "--out", str(iconset / f"icon_{size}x{size}@2x.png")],
            check=True, capture_output=True,
        )

    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(OUT)],
        check=True,
    )

print(f"Created {OUT}")
