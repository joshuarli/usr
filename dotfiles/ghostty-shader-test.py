#!/usr/bin/env python3
"""Static and synthetic checks for Black Phosphor's automatic ANSI pulse.

No external dependencies; real GLSL compilation requires Ghostty on macOS.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "base/.config/ghostty"
SHADER = (ROOT / "shaders/black-phosphor.glsl").read_text()
CONFIG = (ROOT / "config.ghostty").read_text()
THEME = (ROOT / "themes/Black Phosphor").read_text()


def number(name: str) -> float:
    match = re.search(r"const float " + name + r" = ([0-9.]+);", SHADER)
    assert match, name
    return float(match.group(1))


def rgb(hex_value: str) -> tuple[float, float, float]:
    return tuple(int(hex_value[i:i + 2], 16) / 255 for i in (1, 3, 5))


def delta(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return max(abs(x - y) for x, y in zip(a, b, strict=True))


def smoothstep(low: float, high: float, x: float) -> float:
    p = max(0.0, min(1.0, (x - low) / (high - low)))
    return p * p * (3.0 - 2.0 * p)


def grid_column(pixel: float, cursor: float, width: float) -> int:
    return math.floor((pixel - cursor % width) / width)


def pulse(t: float, col: int, row: int) -> float:
    phase = (
        t / number("PULSE_PERIOD_S") - col * number("PHASE_PER_CELL")
        + row * number("ROW_PHASE")
    ) % 1.0
    return smoothstep(0.20, 0.92, 1.0 - abs(2.0 * phase - 1.0))


def main() -> None:
    assert "custom-shader = shaders/black-phosphor.glsl" in CONFIG
    assert "custom-shader-animation = true" in CONFIG
    assert "custom-shader-animation = always" not in CONFIG
    assert "font-family = Glass TTY Soft" in CONFIG
    assert SHADER.count("texture(iChannel0,") == 6
    assert SHADER.count("void mainImage(") == 1
    assert all(name in SHADER for name in (
        "iBackgroundColor", "iSelectionBackgroundColor", "iCurrentCursor.zw",
        "iCursorVisible", "iTime",
    ))
    assert "fragColor = vec4(color, center.a)" in SHADER
    assert not re.search(r"\b(?:for|while|do|sin|cos|tan|pow|sqrt|exp)\s*\(", SHADER)

    # The character wave must not jump as the cursor moves horizontally.
    for width in (17.0, 20.5, 21.333):
        for col in (0, 1, 8, 32, 79):
            x = 24.0 + (col + 0.5) * width
            expected = grid_column(x, 24.0, width)
            for cursor_col in (0, 1, 16, 48):
                assert grid_column(x, 24.0 + cursor_col * width, width) == expected
            assert grid_column(x + width, 24.0, width) == expected + 1

    background = rgb(re.search(r"^background = (#[a-f0-9]{6})$", THEME, re.M).group(1))
    selection = rgb(re.search(r"^selection-background = (#[a-f0-9]{6})$", THEME, re.M).group(1))

    def gate(hex_color: str) -> float:
        color = rgb(hex_color)
        return (
            smoothstep(number("BG_MIN"), number("BG_FULL"), delta(color, background))
            * smoothstep(number("SEL_MIN"), number("SEL_FULL"), delta(color, selection))
        )

    assert gate("#0b0f12") == 0.0  # Ordinary terminal cells
    assert gate("#435158") == 0.0  # Native mouse selection
    assert gate("#1b2225") > 0.1  # ANSI black, distinct from theme background
    for color in ("#f09386", "#c4e891", "#344f6d", "#eaf0e7"):
        assert gate(color) > 0.9  # ANSI, truecolor, and reversed video

    period = number("PULSE_PERIOD_S")
    assert 3.0 < period < 5.0
    assert 0.1 < number("PULSE_STRENGTH") < 0.25
    assert max(pulse(i * period / 20, 3, 0) for i in range(20)) > 0.95
    assert min(pulse(i * period / 20, 3, 0) for i in range(20)) == 0.0
    assert abs(pulse(2.0, 3, 0) - pulse(2.0, 4, 0)) > 0.05
    assert abs(pulse(2.0, 3, 0) - pulse(2.0, 3, 1)) > 0.05
    assert abs(pulse(2.0, 3, 0) - pulse(2.0 + period, 3, 0)) < 1e-10
    print("Ghostty CRT pulse: static and synthetic checks passed.")


if __name__ == "__main__":
    main()
