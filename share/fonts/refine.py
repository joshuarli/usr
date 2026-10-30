#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["fonttools"]
# ///
"""Make optically softened variants of Viacheslav Slavinsky's Glass TTY VT220.

Original: https://github.com/svofski/glasstty (The Unlicense)
Run: ./refine.py [--variant both|soft|smooth] [--force]

This adds matching box drawing, block, arrow and prompt glyphs in the
original scanline style, then leaves horizontal metrics, line spacing
and Unicode mapping intact. Eligible 50-unit-high scanline contours
are made a little fuller, with their rounded shoulders refined.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from fontTools.ttLib import TTFont

import coverage

DEFAULT_SOURCE = Path(__file__).resolve().parent / "v1.ttf"
UPSTREAM_GIT_BLOB_SHA = "8ebdd7bba9c82d418979af7bc9d84acd1fee0ffb"
SOURCE_SIZE = 88404
STROKE_HEIGHT = 50
EXPECTED_STROKES = 4448


@dataclass(frozen=True)
class Variant:
    label: str
    height: int
    cap_soften: float

    @property
    def family(self) -> str:
        return f"Glass TTY {self.label}"

    @property
    def ps_name(self) -> str:
        return f"GlassTTY{self.label}-Medium"

    @property
    def filename(self) -> str:
        return f"GlassTTY-{self.label}.ttf"


VARIANTS = {
    "soft": Variant("Soft", 62, 3.0),
    "smooth": Variant("Smooth", 70, 5.0),
}


def git_blob_hash(raw: bytes) -> str:
    return hashlib.sha1(
        b"blob " + str(len(raw)).encode("ascii") + b"\x00" + raw
    ).hexdigest()


def read_source(path: Path) -> bytes:
    data = path.expanduser().read_bytes()
    if len(data) != SOURCE_SIZE or git_blob_hash(data) != UPSTREAM_GIT_BLOB_SHA:
        raise ValueError(
            f"Input {path} differs from the verified original Glass TTY VT220 "
            "file (v1.ttf). Use your unmodified v1.ttf."
        )
    return data


def smooth_scanlines(font: TTFont, variant: Variant) -> int:
    """Modify only independent, 50-unit-tall strokes; leave .notdef alone."""
    glyphs = font["glyf"]
    touched = 0

    for name in font.getGlyphOrder():
        glyph = glyphs[name]
        if glyph.isComposite() or glyph.numberOfContours <= 0:
            continue

        coords, endpoints, flags = glyph.getCoordinates(glyphs)
        changed = False
        first = 0
        for last in endpoints:
            indices = range(first, last + 1)
            first = last + 1
            xs = [coords[i][0] for i in indices]
            ys = [coords[i][1] for i in indices]
            ymin, ymax = min(ys), max(ys)
            if ymax - ymin != STROKE_HEIGHT:
                continue

            xmin, xmax = min(xs), max(xs)
            cy = (ymin + ymax) / 2.0
            cx = (xmin + xmax) / 2.0
            reach = min(60.0, (xmax - xmin) * 0.48)
            gain = variant.height / STROKE_HEIGHT
            for i in indices:
                x, y = coords[i]
                # Add ink symmetrically, retaining the original stroke center.
                new_y = round(cy + (y - cy) * gain)
                new_x = x

                # Shape the rounded *shoulders*, not the end tips or the stem.
                # The original is already curved; this is an optical nudge.
                dist = min(x - xmin, xmax - x)
                if 0 < dist < reach:
                    y_proximity = max(0.0, (abs(y - cy) - 12.0) / 13.0)
                    x_proximity = 1.0 - dist / reach
                    inward = (
                        variant.cap_soften * min(1.0, y_proximity) * x_proximity
                    )
                    new_x = x + round(inward if x < cx else -inward)
                coords[i] = (new_x, new_y)

            touched += 1
            changed = True

        if changed:
            # Keep original on/off-curve flags, contours, glyph instructions.
            glyph.coordinates = coords
            glyph.recalcBounds(glyphs)

    return touched


def rename_font(font: TTFont, variant: Variant) -> None:
    names = font["name"]
    # Mac and Windows naming records are both populated for CoreText.
    records = {
        1: variant.family,
        2: "Medium",
        3: f"GlassTTY {variant.label} 1.0; original by Viacheslav Slavinsky",
        4: variant.family + " Medium",
        5: "Version 1.0",
        6: variant.ps_name,
        16: variant.family,
        17: "Medium",
    }
    for name_id, value in records.items():
        names.setName(value, name_id, 3, 1, 0x409)
        names.setName(value, name_id, 1, 0, 0)

    # A different internal fontRevision avoids stale cache collisions.
    font["head"].fontRevision = 1.0 if variant.label == "Soft" else 1.1
    # The original is fixed-pitch; preserve all advance widths exactly.
    # The original has six zero-advance special glyphs. All ordinary glyphs
    # use the same 500-unit cell; keep those zero advances untouched.
    advances = {v[0] for v in font["hmtx"].metrics.values() if v[0] > 0}
    if advances != {500}:
        raise ValueError("Source no longer has its 500-unit text-cell width")
    font["post"].isFixedPitch = 1


def build(data: bytes, variant: Variant) -> bytes:
    font = TTFont(io.BytesIO(data), recalcBBoxes=True, recalcTimestamp=False)
    coverage.add_coverage(font)
    originals = dict(font["hmtx"].metrics)
    cmap = font.getBestCmap()
    count = smooth_scanlines(font, variant)
    if count != EXPECTED_STROKES:
        raise ValueError(
            f"Expected {EXPECTED_STROKES} scanline contours, found {count}"
        )
    rename_font(font, variant)
    if font["hmtx"].metrics != originals or font.getBestCmap() != cmap:
        raise AssertionError("A metric or Unicode mapping unexpectedly changed")
    result = io.BytesIO()
    font.save(result)
    out = result.getvalue()
    font.close()

    # Validate the serialized, installed form—not just the in-memory font.
    test = TTFont(io.BytesIO(out), recalcTimestamp=False)
    try:
        assert dict(test["hmtx"].metrics) == originals
        assert test.getBestCmap() == cmap
        assert test["name"].getDebugName(1) == variant.family
        assert len(test.getGlyphOrder()) == len(originals)
    finally:
        test.close()
    return out


def write_font(path: Path, data: bytes, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(
            f"{path} exists; specify --force to replace your own prior build"
        )
    fd, temp = tempfile.mkstemp(prefix=".glasstty-", suffix=".ttf", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source", type=Path, default=DEFAULT_SOURCE,
        help="Local original font (default: v1.ttf next to this script)",
    )
    parser.add_argument(
        "--variant", choices=(*VARIANTS.keys(), "both"), default="both"
    )
    parser.add_argument(
        "--install", action="store_true",
        help="Install the distinct font families into ~/Library/Fonts on macOS"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path.cwd() / "glasstty-build"
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    output = (
        Path("~/Library/Fonts").expanduser()
        if args.install else args.output_dir.expanduser()
    )
    choices = (
        tuple(VARIANTS.values()) if args.variant == "both"
        else (VARIANTS[args.variant],)
    )
    data = read_source(args.source)
    for variant in choices:
        out = output / variant.filename
        rebuilt = build(data, variant)
        write_font(out, rebuilt, args.force)
        print(f"{variant.family}: {out} ({len(rebuilt):,} bytes)")

    print(
        "\nRestart Ghostty, run `ghostty +list-fonts`, and set "
        "`font-family = Glass TTY Soft` or `font-family = Glass TTY Smooth`."
    )
    print("Keep your original Glass TTY VT220 installed for comparison.")


if __name__ == "__main__":
    main()
