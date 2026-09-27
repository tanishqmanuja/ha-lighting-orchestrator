"""Brand image checks (no HA needed): files exist, valid PNGs, usable size."""
import struct
from pathlib import Path

BRAND_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "halo" / "brand"
REQUIRED = [
    "icon.png",
    "logo.png",
    "icon@2x.png",
    "logo@2x.png",
    "dark_icon.png",
    "dark_logo.png",
]


def _png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", f"{path.name} is not a PNG"
    width, height = struct.unpack(">II", data[16:24])
    return width, height


def test_brand_files_exist():
    missing = [name for name in REQUIRED if not (BRAND_DIR / name).is_file()]
    assert not missing, f"missing brand files: {missing}"


def test_brand_images_square_and_large():
    for name in REQUIRED:
        width, height = _png_size(BRAND_DIR / name)
        assert width == height, f"{name} should be square, got {width}x{height}"
        assert width >= 512, f"{name} too small: {width}x{height}"
