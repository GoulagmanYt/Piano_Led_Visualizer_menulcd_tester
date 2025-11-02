from __future__ import annotations
from PIL import Image
from PySide6.QtGui import QImage

def pil_to_qimage(im: Image.Image) -> QImage:
    if im.mode != "RGB":
        im = im.convert("RGB")
    w, h = im.size
    # bytes per line = 3 * width for RGB888
    data = im.tobytes()
    qimg = QImage(data, w, h, 3 * w, QImage.Format.Format_RGB888)
    # Make a deep copy to avoid using the memory buffer from Python after the function returns
    return qimg.copy()