"""Generate ``assets/icon.png`` and ``assets/icon.ico`` from code.

Committing a binary icon is fine, but committing the *recipe* means the mark
can be recoloured to match a team's branding with a two-line edit and no
image editor. The script uses only the standard library (``zlib`` + ``struct``):
it rasterises the mark with 3x3 supersampling, writes the PNG chunks by hand
and packs the multi-resolution ICO container itself.

Usage::

    python tools/make_icon.py [--accent-from "#5B8CFF"] [--accent-to "#7C5CFF"]
"""

from __future__ import annotations

import argparse
import math
import struct
import zlib
from pathlib import Path
from typing import List, Sequence, Tuple

#: Master rendering size; every ICO entry is downsampled from this.
MASTER = 256

#: Sizes packed into the .ico, largest first (Windows picks per context).
ICO_SIZES = (256, 128, 64, 48, 32, 16)

RGBA = Tuple[float, float, float, float]


# ----------------------------------------------------------------------
# Geometry
# ----------------------------------------------------------------------
def rounded_rect_sdf(px: float, py: float, cx: float, cy: float,
                     half_w: float, half_h: float, radius: float) -> float:
    """Signed distance from ``(px, py)`` to a rounded rectangle (<0 = inside)."""
    dx = abs(px - cx) - (half_w - radius)
    dy = abs(py - cy) - (half_h - radius)
    outside = math.hypot(max(dx, 0.0), max(dy, 0.0))
    inside = min(max(dx, dy), 0.0)
    return outside + inside - radius


def segment_distance(px: float, py: float, x1: float, y1: float,
                     x2: float, y2: float) -> float:
    """Shortest distance from a point to a line segment."""
    vx, vy = x2 - x1, y2 - y1
    wx, wy = px - x1, py - y1
    length_sq = vx * vx + vy * vy
    t = 0.0 if length_sq == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / length_sq))
    return math.hypot(px - (x1 + t * vx), py - (y1 + t * vy))


def polyline_distance(px: float, py: float, points: Sequence[Tuple[float, float]]) -> float:
    """Shortest distance to a polyline (round joins fall out of the minimum)."""
    return min(segment_distance(px, py, points[i][0], points[i][1],
                                points[i + 1][0], points[i + 1][1])
               for i in range(len(points) - 1))


def hex_to_rgb(value: str) -> Tuple[int, int, int]:
    value = value.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def over(top: RGBA, bottom: RGBA) -> RGBA:
    """Straight-alpha "source over" composite."""
    ta = top[3]
    if ta <= 0:
        return bottom
    ba = bottom[3]
    out_a = ta + ba * (1 - ta)
    if out_a <= 0:
        return (0.0, 0.0, 0.0, 0.0)
    return tuple(
        (top[i] * ta + bottom[i] * ba * (1 - ta)) / out_a for i in range(3)
    ) + (out_a,)


# ----------------------------------------------------------------------
# The mark
# ----------------------------------------------------------------------
def sample(x: float, y: float, accent_from: str, accent_to: str) -> RGBA:
    """Colour of the icon at continuous coordinates ``(x, y)`` in master space."""
    size = float(MASTER)
    pixel = (0.0, 0.0, 0.0, 0.0)

    # 1. Rounded-square plate with a diagonal gradient.
    plate = rounded_rect_sdf(x, y, size / 2, size / 2, 121, 121, 58)
    plate_alpha = max(0.0, min(1.0, 0.5 - plate))
    if plate_alpha > 0:
        ratio = max(0.0, min(1.0, (x + y) / (2 * size)))
        r1, g1, b1 = hex_to_rgb(accent_from)
        r2, g2, b2 = hex_to_rgb(accent_to)
        pixel = over((r1 + (r2 - r1) * ratio, g1 + (g2 - g1) * ratio,
                      b1 + (b2 - b1) * ratio, plate_alpha), pixel)

    # 2. Soft inner highlight so the plate does not read as flat at 256 px.
    glow = rounded_rect_sdf(x, y - 26, size / 2, size / 2, 104, 92, 52)
    glow_alpha = max(0.0, min(1.0, -glow / 90.0)) * 0.16 * plate_alpha
    if glow_alpha > 0:
        pixel = over((255.0, 255.0, 255.0, glow_alpha), pixel)

    # 3. Checkmark - the whole identity of the app in one stroke.
    check = polyline_distance(x, y, [(74, 132), (112, 172), (184, 88)])
    check_alpha = max(0.0, min(1.0, 12.5 - check)) * plate_alpha
    if check_alpha > 0:
        pixel = over((255.0, 255.0, 255.0, check_alpha), pixel)

    return pixel


def render_master(accent_from: str, accent_to: str, supersample: int = 3) -> List[List[RGBA]]:
    """Render the mark at :data:`MASTER` with ``supersample``x supersampling."""
    rows: List[List[RGBA]] = []
    step = 1.0 / supersample
    offset = step / 2.0
    weight = 1.0 / (supersample * supersample)
    for py in range(MASTER):
        row: List[RGBA] = []
        for px in range(MASTER):
            r = g = b = a = 0.0
            for sy in range(supersample):
                for sx in range(supersample):
                    sr, sg, sb, sa = sample(px + offset + sx * step,
                                            py + offset + sy * step,
                                            accent_from, accent_to)
                    r += sr * sa
                    g += sg * sa
                    b += sb * sa
                    a += sa
            if a > 0:
                row.append((r / a, g / a, b / a, a * weight))
            else:
                row.append((0.0, 0.0, 0.0, 0.0))
        rows.append(row)
    return rows


def downsample(master: List[List[RGBA]], size: int) -> bytes:
    """Area-average ``master`` down to ``size`` x ``size`` RGBA bytes."""
    out = bytearray()
    scale = MASTER / float(size)
    for y in range(size):
        y0, y1 = int(y * scale), max(int(y * scale) + 1, int((y + 1) * scale))
        for x in range(size):
            x0, x1 = int(x * scale), max(int(x * scale) + 1, int((x + 1) * scale))
            r = g = b = a = 0.0
            count = 0
            for sy in range(y0, min(y1, MASTER)):
                for sx in range(x0, min(x1, MASTER)):
                    pr, pg, pb, pa = master[sy][sx]
                    r += pr * pa
                    g += pg * pa
                    b += pb * pa
                    a += pa
                    count += 1
            count = count or 1
            if a > 0:
                out += bytes((int(round(r / a)), int(round(g / a)),
                              int(round(b / a)), int(round(255 * a / count))))
            else:
                out += b"\x00\x00\x00\x00"
    return bytes(out)


# ----------------------------------------------------------------------
# Encoders
# ----------------------------------------------------------------------
def encode_png(width: int, height: int, rgba: bytes) -> bytes:
    """Minimal RGBA PNG encoder (filter type 0 on every scanline)."""
    raw = bytearray()
    stride = width * 4
    for y in range(height):
        raw.append(0)
        raw += rgba[y * stride:(y + 1) * stride]

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


def encode_ico(images: List[Tuple[int, bytes]]) -> bytes:
    """Pack ``(size, png_bytes)`` pairs into a PNG-compressed ICO container."""
    count = len(images)
    header = struct.pack("<HHH", 0, 1, count)
    offset = 6 + 16 * count
    directory = b""
    body = b""
    for size, png in images:
        directory += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size, 0 if size >= 256 else size,
            0, 0, 1, 32, len(png), offset,
        )
        body += png
        offset += len(png)
    return header + directory + body


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the CheckMod icon.")
    parser.add_argument("--accent-from", default="#5B8CFF")
    parser.add_argument("--accent-to", default="#7C5CFF")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "assets"))
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print("rendering master ...")
    master = render_master(args.accent_from, args.accent_to)

    pngs: List[Tuple[int, bytes]] = []
    for size in ICO_SIZES:
        print(f"  {size}x{size}")
        pngs.append((size, encode_png(size, size, downsample(master, size))))

    (out_dir / "icon.png").write_bytes(dict(pngs)[256])
    (out_dir / "icon.ico").write_bytes(encode_ico(pngs))
    print(f"wrote {out_dir / 'icon.png'} and {out_dir / 'icon.ico'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
