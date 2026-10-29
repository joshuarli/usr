#!/usr/bin/env python3
"""CPU-reference tests for the automatic Black Phosphor highlight pulse.

The original detector mistook cursor glyph dimensions for the text cell.
These tests verify actual pixel-color classification with synthetic terminal
screens, including bar-cursor independence, reverse video, and selections.
GLSL compilation and visual GPU behavior still need testing in Ghostty.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "base/.config/ghostty"
SHADER = (ROOT / "shaders/black-phosphor-pulse.glsl").read_text()
CONFIG = (ROOT / "config.ghostty").read_text()
THEME = (ROOT / "themes/Black Phosphor").read_text()

def number(name: str) -> float:
    result = re.search(r"const float " + name + r" = ([0-9.]+);", SHADER)
    assert result, f"missing shader constant: {name}"
    return float(result.group(1))

def rgb(hex_color: str) -> tuple[float, float, float]:
    return tuple(int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5))

def max_delta(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return max(abs(x - y) for x, y in zip(a, b, strict=True))

def theme_delta(value: tuple[float, ...], reference: tuple[float, ...]) -> float:
    return min(max_delta(value, reference),
               max_delta(value, tuple(x*x for x in reference)))

def smoothstep(a: float, b: float, value: float) -> float:
    x = max(0.0, min(1.0, (value - a)/(b - a)))
    return x*x*(3.0 - 2.0*x)

def gate(a: tuple[float, ...], b: tuple[float, ...],
         bg: tuple[float, ...], selection: tuple[float, ...]) -> float:
    fill = tuple((x+y)*0.5 for x, y in zip(a, b, strict=True))
    stable = 1.0 - smoothstep(0.07, 0.16, max_delta(a, b))
    color = smoothstep(number("BG_MIN"), number("BG_FULL"), theme_delta(fill, bg))
    unselected = smoothstep(number("SEL_MIN"), number("SEL_FULL"),
                            theme_delta(fill, selection))
    return stable * color * unselected

def pulse(time: float, pixel_x: float) -> float:
    phase = (time / number("PULSE_PERIOD_S") -
             pixel_x * number("PHASE_PER_PIXEL")) % 1.0
    triangle = 1.0 - abs(2.0*phase - 1.0)
    return smoothstep(0.27, 0.93, triangle)

def main() -> None:
    assert "custom-shader = shaders/black-phosphor-pulse.glsl" in CONFIG
    assert "custom-shader-animation = true" in CONFIG
    assert "custom-shader-animation = always" not in CONFIG
    assert "font-family = Glass TTY Soft" in CONFIG
    assert SHADER.count("void mainImage(") == 1
    assert SHADER.count("texture(iChannel0,") == 7
    assert "PULSE_LIFT" in SHADER
    assert number("BG_MIN") < 0.025
    assert number("BG_FULL") < 0.070
    assert "iTime" in SHADER
    assert "iCurrentCursor" not in SHADER
    assert "iCursorVisible" not in SHADER
    assert "themeColorDistance(fill, iBackgroundColor)" in SHADER
    assert "themeColorDistance(fill, iSelectionBackgroundColor)" in SHADER
    assert "fragColor = vec4(color, center.a)" in SHADER
    assert not re.search(r"\b(?:for|while|do|sin|cos|tan|pow|sqrt|exp)\s*\(", SHADER)

    bg = rgb(re.search(r"^background = (#[0-9a-f]{6})$", THEME, re.M).group(1))
    selection = rgb(re.search(r"^selection-background = (#[0-9a-f]{6})$", THEME, re.M).group(1))
    highlighted = rgb("#eed9a3")
    dark_ink = rgb("#242118")
    regular_ink = rgb("#eaf0e7")
    w, h = 240, 90
    screen = [[bg for _ in range(w)] for _ in range(h)]

    # Two labeled regions plus ordinary bright text on default black.
    for y in range(20, 60):
        for x in range(35, 205):
            screen[y][x] = highlighted
    for col in range(8):
        x0 = 40 + col * 19
        for y in range(28, 52):
            for x in range(x0 + 7, x0 + 10):
                screen[y][x] = dark_ink
    for y in range(29, 53):
        for x in range(8, 11):
            screen[y][x] = regular_ink

    def sample(image: list[list[tuple[float, ...]]], x: int, y: int) -> tuple[float, ...]:
        return image[max(0, min(h-1, y))][max(0, min(w-1, x))]

    def screen_gate(image: list[list[tuple[float, ...]]], x: int, y: int) -> float:
        dx, dy = int(number("PROBE_X_PX")), int(number("PROBE_Y_PX"))
        return gate(sample(image, x+dx, y+dy), sample(image, x-dx, y-dy),
                    bg, selection)

    assert screen_gate(screen, 48, 39) > 0.95  # Dark glyph on ANSI yellow
    assert screen_gate(screen, 85, 39) > 0.95  # Highlighted background
    assert screen_gate(screen, 10, 39) == 0.0  # Ordinary bright glyph
    assert screen_gate(screen, 50, 15) == 0.0  # Default background
    assert screen_gate(screen, 206, 39) == 0.0 # Outside highlight region

    # At least 60% of the central highlight remains active, even with ink.
    coverage = sum(screen_gate(screen,x,y) > 0.5
                   for x in range(48,195) for y in range(30,50)) / (147*20)
    assert coverage > 0.60, coverage

    # Selection color is excluded, including in linear-ish color space.
    selected = [[bg for _ in range(w)] for _ in range(h)]
    for y in range(20, 60):
        for x in range(35,205):
            selected[y][x] = selection
    assert screen_gate(selected, 100, 40) == 0.0
    approx_linear = tuple(x*x for x in selection)
    assert gate(approx_linear,approx_linear,bg,selection) == 0.0

    # Low-intensity ANSI black now needs strong gating too, not near-zero.
    assert gate(rgb("#1b2225"), rgb("#1b2225"), bg, selection) > 0.95

    # Reverse-video (light background/dark ink) and truecolor both trigger.
    for hcolor in ("#eaf0e7", "#344f6d", "#f09386", "#a1e6e9"):
        c = rgb(hcolor)
        assert gate(c,c,bg,selection) > 0.9, hcolor

    # Simulate vertical-bar, underline and hidden cursors: classification
    # has no cursor input and MUST remain active for all three.
    for cursor_width in (2, 18, 0):
        assert screen_gate(screen, 85, 39) > 0.95, cursor_width

    # Temporal movement is nontrivial, periodic, and varies across columns.
    period = number("PULSE_PERIOD_S")
    assert 3.0 < period < 5.0
    assert 0.15 < number("PULSE_INK") < 0.35
    values = [pulse(i*period/30, 85.0) for i in range(30)]
    assert min(values) == 0.0 and max(values) > 0.95
    assert abs(pulse(1.2, 85.0)-pulse(1.2+period,85.0)) < 1e-10
    assert abs(pulse(1.2, 85.0)-pulse(1.2,185.0)) > 0.1
    print("Ghostty CRT highlight: pixel-color and animation tests passed.")

def demo() -> None:
    """Hold actual ANSI backgrounds on screen for a visible shader test."""
    import time

    print("\nHold Ghostty focused for at least 4 seconds.")
    print("The filled labels should shimmer in place; normal text should not.\n")
    print("\033[43;30m  COMPILING  ANSI YELLOW BACKGROUND  \033[0m")
    print("\033[7m  REVERSE VIDEO  INVERSE TEXT  \033[0m")
    print("\033[40;97m  ANSI BLACK BACKGROUND  \033[0m")
    print("\033[48;2;42;60;80;97m  DARK TRUECOLOR BACKGROUND  \033[0m")
    print("\033[48;2;110;47;84;97m  MUTED RED TRUECOLOR BACKGROUND  \033[0m")
    print("Ordinary text: no animation should be visible.")
    time.sleep(12)


if __name__ == "__main__":
    import sys

    main()
    if "--demo" in sys.argv:
        demo()
