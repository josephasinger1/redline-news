#!/usr/bin/env python3
"""Generate the app icons (tachometer mark) as PNGs using only stdlib.

Run once; outputs web/icons/icon-192.png, icon-512.png, apple-touch-icon.png.
"""

import math
import struct
import zlib
from pathlib import Path

BG = (11, 11, 16)
RING = (242, 242, 245)
RED = (232, 16, 45)


def png_bytes(width, height, rows):
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + bytes(row) for row in rows)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )


def blend(base, top, alpha):
    return tuple(round(b * (1 - alpha) + t * alpha) for b, t in zip(base, top))


def smooth(dist, edge, feather=1.5):
    """1 inside, 0 outside, soft edge."""
    if dist < edge - feather:
        return 1.0
    if dist > edge + feather:
        return 0.0
    return (edge + feather - dist) / (2 * feather)


def render(size):
    cx = cy = size / 2
    r_outer = size * 0.40
    r_inner = size * 0.30
    hub = size * 0.075
    needle_w = size * 0.045
    # dial sweep: 135deg (lower-left) clockwise 270deg to 45deg (lower-right)
    start, sweep = 135.0, 270.0
    needle_angle = math.radians(start + sweep * 0.86)  # deep in the redline
    nx, ny = math.cos(needle_angle), math.sin(needle_angle)
    needle_len = size * 0.36

    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            px, py = x + 0.5 - cx, y + 0.5 - cy
            d = math.hypot(px, py)
            color = BG

            ang = (math.degrees(math.atan2(py, px)) - start) % 360.0
            on_arc = ang <= sweep
            if on_arc and r_inner - 2 < d < r_outer + 2:
                a = smooth(d, r_outer) * smooth(r_inner * 2 - d, r_inner)
                if a > 0:
                    frac = ang / sweep
                    col = RED if frac > 0.78 else RING
                    fade = 0.55 + 0.45 * frac
                    color = blend(color, col, a * fade)

            # needle: distance from segment (0,0)->(needle_len * n)
            t = max(0.0, min(needle_len, px * nx + py * ny))
            seg_d = math.hypot(px - nx * t, py - ny * t)
            a = smooth(seg_d, needle_w)
            if a > 0 and t > 0:
                color = blend(color, RED, a)

            a = smooth(d, hub)
            if a > 0:
                color = blend(color, RING, a)

            row.extend(color)
        rows.append(row)
    return png_bytes(size, size, rows)


def main():
    out = Path(__file__).resolve().parent.parent / "web" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for name, size in (("icon-192.png", 192), ("icon-512.png", 512), ("apple-touch-icon.png", 180)):
        (out / name).write_bytes(render(size))
        print("wrote", out / name)


if __name__ == "__main__":
    main()
