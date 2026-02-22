#!/usr/bin/env python3
import re
import sys
from datetime import timedelta

TIME_PATTERN = re.compile(r"(\d\d:\d\d:\d\d,\d\d\d) --> (\d\d:\d\d:\d\d,\d\d\d)")
TAG_PATTERN = re.compile(r"<[^>]+>")

def parse_timestamp(ts: str) -> timedelta:
    h, m, s_ms = ts.split(":")
    s, ms = s_ms.split(",")
    return timedelta(hours=int(h), minutes=int(m), seconds=int(s), milliseconds=int(ms))

def format_timestamp(td: timedelta) -> str:
    total_ms = max(0, int(td.total_seconds() * 1000))
    h = total_ms // 3_600_000
    m = (total_ms % 3_600_000) // 60_000
    s = (total_ms % 60_000) // 1_000
    ms = total_ms % 1_000
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def strip_html(text: str) -> str:
    return TAG_PATTERN.sub("", text)

def parse_blocks(text: str):
    """Yield blocks as lists of lines."""
    block = []
    for line in text.splitlines():
        if line.strip():
            block.append(line)
        else:
            if block:
                yield block
            block = []
    if block:
        yield block

def shift_block(block, shift: timedelta):
    """Return a shifted block or None if invalid/negative start."""
    if len(block) < 2:
        return None

    index = block[0].strip()
    m = TIME_PATTERN.match(block[1])
    if not m:
        return None

    start = parse_timestamp(m.group(1)) - shift
    end   = parse_timestamp(m.group(2)) - shift

    if start.total_seconds() < 0:
        return None

    new_time = f"{format_timestamp(start)} --> {format_timestamp(end)}"
    text_lines = [strip_html(line) for line in block[2:]]

    return [index, new_time] + text_lines

def shift_srt(input_file: str, output_file: str, shift_seconds: float):
    shift = timedelta(seconds=shift_seconds)

    with open(input_file, "r", encoding="utf-8") as f:
        input_text = f.read()

    blocks = [shift_block(b, shift) for b in parse_blocks(input_text)]
    blocks = [b for b in blocks if b is not None]  # filter removed blocks

    with open(output_file, "w", encoding="utf-8") as f:
        for i, block in enumerate(blocks, start=1):
            f.write(f"{i}\n")
            for line in block[1:]:
                f.write(line + "\n")
            f.write("\n")

    print(f"Done. Wrote shifted subtitles to {output_file}")

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python shift_srt.py input.srt output.srt 3.5")
        sys.exit(1)

    shift_srt(sys.argv[1], sys.argv[2], float(sys.argv[3]))
