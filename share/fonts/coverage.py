from __future__ import annotations

from fontTools.ttLib.tables._g_l_y_f import Glyph
from fontTools.ttLib.tables._g_l_y_f import GlyphCoordinates

ROWS = [-150, -50, 50, 150, 250, 350, 450, 550, 650, 750]
CX = 200
CY = 375

LIGHT_V = (150, 250)
HEAVY_V = (100, 300)
DOUBLE_V = ((0, 100), (300, 400))

LIGHT_H = (350, 400)
HEAVY_H = (325, 425)
DOUBLE_H = ((250, 300), (450, 500))

FULL_W = (0, 500)


def _vbrick(x0: int, x1: int, y0: int) -> tuple[list[tuple[int, int]], list[int]]:
    y1 = y0 + 50
    w = x1 - x0
    ix = 19 if w <= 120 else 32
    pts = [
        (x0, y0 + 9),
        (x0, y0 + 41),
        (x0 + ix, y1),
        (x1 - ix, y1),
        (x1, y1 - 9),
        (x1, y0 + 9),
        (x1 - ix, y0),
        (x0 + ix, y0),
    ]
    return pts, [0] * 8


def _rect(x0: int, y0: int, x1: int, y1: int) -> tuple[list[tuple[int, int]], list[int]]:
    pts = [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]
    return pts, [1] * 4


def _new_glyph() -> Glyph:
    from fontTools.ttLib.tables.ttProgram import Program
    g = Glyph()
    g.program = Program()
    g.program.fromBytecode(b"")
    return g


def _commit(font, name: str, parts: list[tuple[list[tuple[int, int]], list[int]]], advance: int = 500) -> None:
    coords: list[tuple[int, int]] = []
    flags: list[int] = []
    ends: list[int] = []
    for pts, fl in parts:
        base = len(coords)
        coords.extend(pts)
        flags.extend(fl)
        ends.append(base + len(pts) - 1)
    g = _new_glyph()
    g.coordinates = GlyphCoordinates(coords)
    g.endPtsOfContours = ends
    g.flags = flags
    g.numberOfContours = len(ends)
    glyf = font["glyf"]
    glyf.glyphs[name] = g
    g.recalcBounds(glyf)
    xmin = g.xMin if g.numberOfContours > 0 else 0
    font["hmtx"].metrics[name] = (advance, xmin)


def _v_bricks(x0: int, x1: int, skip: set[int] | None = None) -> list[tuple[list[tuple[int, int]], list[int]]]:
    skip = skip or set()
    out = []
    for y0 in ROWS:
        if y0 in skip:
            continue
        out.append(_vbrick(x0, x1, y0))
    return out


def _h_bars(y_ranges: list[tuple[int, int]], x0: int = 0, x1: int = 500) -> list[tuple[list[tuple[int, int]], list[int]]]:
    return [_rect(x0, y0, x1, y1) for (y0, y1) in y_ranges]


def _parse_box(name: str) -> dict[str, str] | None:
    n = name.replace("BOX DRAWINGS ", "")
    if "DASH" in n or "ARC" in n or "DIAGONAL" in n:
        return None
    edges = {"up": " ", "down": " ", "left": " ", "right": " "}
    if n in ("LIGHT HORIZONTAL", "HEAVY HORIZONTAL", "DOUBLE HORIZONTAL"):
        style = "l" if n.startswith("LIGHT") else "h" if n.startswith("HEAVY") else "d"
        edges["left"] = style
        edges["right"] = style
        return edges
    if n in ("LIGHT VERTICAL", "HEAVY VERTICAL", "DOUBLE VERTICAL"):
        style = "l" if n.startswith("LIGHT") else "h" if n.startswith("HEAVY") else "d"
        edges["up"] = style
        edges["down"] = style
        return edges
    groups = n.split(" AND ")
    current = "l"
    for gi, g in enumerate(groups):
        toks = g.split(" ")
        style = None
        for t in toks:
            tl = t.lower()
            if tl == "heavy":
                style = "h"
            elif tl == "double":
                style = "d"
            elif tl in ("light", "single"):
                style = "l"
        if style is None:
            if gi == 0:
                style = "l"
            else:
                style = current
        current = style
        found = False
        for t in toks:
            tl = t.lower()
            if tl == "vertical":
                edges["up"] = style
                edges["down"] = style
                found = True
            elif tl == "horizontal":
                edges["left"] = style
                edges["right"] = style
                found = True
            elif tl in edges:
                edges[tl] = style
                found = True
        if not found:
            return None
    if all(v == " " for v in edges.values()):
        return None
    return edges


def _box_parts(edges: dict[str, str]) -> list[tuple[list[tuple[int, int]], list[int]]]:
    parts: list[tuple[list[tuple[int, int]], list[int]]] = []
    up, down, left, right = edges["up"], edges["down"], edges["left"], edges["right"]
    h_present = left != " " or right != " "
    v_present = up != " " or down != " "
    if h_present:
        if left == right or right == " " or left == " ":
            style = left if right == " " else right if left == " " else left
            if style == "l":
                y0, y1 = LIGHT_H
                x0 = 0 if left != " " else CX
                x1 = 500 if right != " " else CX
                if left == " " or right == " ":
                    x0 = 0 if left != " " else CX
                    x1 = CX if left != " " and right == " " else (500 if right != " " and left == " " else 500)
                    if left != " " and right == " ":
                        x0, x1 = 0, CX
                    elif right != " " and left == " ":
                        x0, x1 = CX, 500
                    else:
                        x0, x1 = 0, 500
                parts.append(_rect(x0, y0, x1, y1))
            elif style == "h":
                y0, y1 = HEAVY_H
                if left != " " and right == " ":
                    x0, x1 = 0, CX
                elif right != " " and left == " ":
                    x0, x1 = CX, 500
                else:
                    x0, x1 = 0, 500
                parts.append(_rect(x0, y0, x1, y1))
            elif style == "d":
                for dy0, dy1 in DOUBLE_H:
                    if left != " " and right == " ":
                        x0, x1 = 0, CX
                    elif right != " " and left == " ":
                        x0, x1 = CX, 500
                    else:
                        x0, x1 = 0, 500
                    parts.append(_rect(x0, dy0, x1, dy1))
        else:
            for side, style in (("left", left), ("right", right)):
                if style == " ":
                    continue
                if style == "l":
                    y0, y1 = LIGHT_H
                elif style == "h":
                    y0, y1 = HEAVY_H
                else:
                    continue
                if side == "left":
                    parts.append(_rect(0, y0, CX, y1))
                    if style == "d":
                        pass
                else:
                    parts.append(_rect(CX, y0, CX + (500 - CX), y1))
            if left == "d" or right == "d":
                for dy0, dy1 in DOUBLE_H:
                    if left == "d":
                        parts.append(_rect(0, dy0, CX, dy1))
                    if right == "d":
                        parts.append(_rect(CX, dy0, 500, dy1))
    if v_present:
        skip: set[int] = set()
        if h_present:
            if left == right or True:
                has_light_h = left in ("l", "d") or right in ("l", "d")
                has_heavy_h = left == "h" or right == "h"
                if has_light_h or has_heavy_h:
                    skip.add(350)
                if left == "d" or right == "d":
                    skip.add(250)
                    skip.add(450)
        if up == down or up == " " or down == " ":
            style = up if down == " " else down if up == " " else up
            if style == "l":
                x0, x1 = LIGHT_V
                for y0 in ROWS:
                    if y0 in skip:
                        continue
                    if up != " " and down == " " and y0 < CY - 25:
                        continue
                    if down != " " and up == " " and y0 > CY - 25:
                        continue
                    parts.append(_vbrick(x0, x1, y0))
            elif style == "h":
                x0, x1 = HEAVY_V
                for y0 in ROWS:
                    if y0 in skip:
                        continue
                    if up != " " and down == " " and y0 < CY - 25:
                        continue
                    if down != " " and up == " " and y0 > CY - 25:
                        continue
                    parts.append(_vbrick(x0, x1, y0))
            elif style == "d":
                for (x0, x1) in DOUBLE_V:
                    for y0 in ROWS:
                        if y0 in skip:
                            continue
                        if up != " " and down == " " and y0 < CY - 25:
                            continue
                        if down != " " and up == " " and y0 > CY - 25:
                            continue
                        parts.append(_vbrick(x0, x1, y0))
        else:
            for side, style in (("up", up), ("down", down)):
                if style == " ":
                    continue
                xs = [LIGHT_V] if style == "l" else [HEAVY_V] if style == "h" else list(DOUBLE_V)
                for (x0, x1) in xs:
                    for y0 in ROWS:
                        if y0 in skip:
                            continue
                        if side == "up" and y0 < CY - 25:
                            continue
                        if side == "down" and y0 > CY - 25:
                            continue
                        parts.append(_vbrick(x0, x1, y0))
    return parts


def _dash_parts(cp: int, font) -> list[tuple[list[tuple[int, int]], list[int]]] | None:
    import unicodedata
    try:
        name = unicodedata.name(chr(cp))
    except ValueError:
        return None
    if "LIGHT TRIPLE DASH HORIZONTAL" in name:
        return [_rect(0, 350, 120, 400), _rect(190, 350, 310, 400), _rect(380, 350, 500, 400)]
    if "HEAVY TRIPLE DASH HORIZONTAL" in name:
        return [_rect(0, 325, 120, 425), _rect(190, 325, 310, 425), _rect(380, 325, 500, 425)]
    if "LIGHT TRIPLE DASH VERTICAL" in name:
        out = []
        for y0 in (-150, -50, 50):
            out.append(_vbrick(150, 250, y0))
        for y0 in (250, 350, 450):
            if y0 == 350:
                out.append(_rect(150, 350, 250, 400))
            else:
                out.append(_vbrick(150, 250, y0))
        for y0 in (550, 650, 750):
            out.append(_vbrick(150, 250, y0))
        return out
    if "HEAVY TRIPLE DASH VERTICAL" in name:
        out = []
        for y0 in (-150, -50, 50, 250, 350, 450, 550, 650, 750):
            if y0 == 350:
                out.append(_rect(100, 325, 300, 425))
            else:
                out.append(_vbrick(100, 300, y0))
        return out
    if "LIGHT QUADRUPLE DASH HORIZONTAL" in name:
        return [_rect(0, 350, 80, 400), _rect(140, 350, 220, 400), _rect(280, 350, 360, 400), _rect(420, 350, 500, 400)]
    if "HEAVY QUADRUPLE DASH HORIZONTAL" in name:
        return [_rect(0, 325, 80, 425), _rect(140, 325, 220, 425), _rect(280, 325, 360, 425), _rect(420, 325, 500, 425)]
    if "LIGHT QUADRUPLE DASH VERTICAL" in name:
        out = []
        for y0 in (-150, 50, 250, 550, 650):
            out.append(_vbrick(150, 250, y0))
        out.append(_rect(150, 350, 250, 400))
        return out
    if "HEAVY QUADRUPLE DASH VERTICAL" in name:
        out = []
        for y0 in (-150, 50, 250, 550, 650):
            out.append(_vbrick(100, 300, y0))
        out.append(_rect(100, 325, 300, 425))
        return out
    if "LIGHT DOUBLE DASH HORIZONTAL" in name:
        return [_rect(0, 350, 200, 400), _rect(300, 350, 500, 400)]
    if "HEAVY DOUBLE DASH HORIZONTAL" in name:
        return [_rect(0, 325, 200, 425), _rect(300, 325, 500, 425)]
    if "LIGHT DOUBLE DASH VERTICAL" in name:
        out = []
        for y0 in (-150, -50, 50, 150, 250):
            out.append(_vbrick(150, 250, y0))
        for y0 in (450, 550, 650, 750):
            out.append(_vbrick(150, 250, y0))
        return out
    if "HEAVY DOUBLE DASH VERTICAL" in name:
        out = []
        for y0 in (-150, -50, 50, 150, 250):
            out.append(_vbrick(100, 300, y0))
        for y0 in (450, 550, 650, 750):
            out.append(_vbrick(100, 300, y0))
        return out
    return None


def _diagonal_parts(cp: int) -> list[tuple[list[tuple[int, int]], list[int]]] | None:
    if cp == 0x2571:
        xs = [300, 250, 200, 150, 100, 50, 0, -50, -100, -150]
        out = []
        for y0, x0 in zip(ROWS, xs):
            out.append(_vbrick(max(0, x0), max(100, x0 + 100), y0))
        return [p for p in out if p[0][0][0] < 500 and p[0][0][0] >= -100]
    if cp == 0x2572:
        xs = [-150, -100, -50, 0, 50, 100, 150, 200, 250, 300]
        out = []
        for y0, x0 in zip(ROWS, xs):
            out.append(_vbrick(max(0, x0), max(100, x0 + 100), y0))
        return [p for p in out if p[0][0][0] < 500]
    if cp == 0x2573:
        a = _diagonal_parts(0x2571) or []
        b = _diagonal_parts(0x2572) or []
        return a + b
    if cp in (0x2574, 0x2575, 0x2576, 0x2577, 0x2578, 0x2579, 0x257A, 0x257B, 0x257C, 0x257D, 0x257E, 0x257F):
        mapping = {
            0x2574: {"left": "l"},
            0x2575: {"up": "l"},
            0x2576: {"right": "l"},
            0x2577: {"down": "l"},
            0x2578: {"left": "h"},
            0x2579: {"up": "h"},
            0x257A: {"right": "h"},
            0x257B: {"down": "h"},
            0x257C: {"left": "l", "right": "h"},
            0x257D: {"up": "l", "down": "h"},
            0x257E: {"left": "h", "right": "l"},
            0x257F: {"up": "h", "down": "l"},
        }
        e = {"up": " ", "down": " ", "left": " ", "right": " "}
        e.update(mapping[cp])
        return _box_parts(e)
    return None


def _arc_parts(cp: int) -> list[tuple[list[tuple[int, int]], list[int]]] | None:
    if cp == 0x256D:
        return _v_bricks(150, 250, skip={350, 450, 550, 650, 750}) + [_rect(0, 350, 500, 400), _vbrick(250, 350, 250)]
    if cp == 0x256E:
        return _v_bricks(150, 250, skip={350, 450, 550, 650, 750}) + [_rect(0, 350, 500, 400), _vbrick(50, 150, 250)]
    if cp == 0x256F:
        return _v_bricks(150, 250, skip={-150, -50, 50, 150, 250, 350}) + [_rect(0, 350, 500, 400), _vbrick(50, 150, 450)]
    if cp == 0x2570:
        return _v_bricks(150, 250, skip={-150, -50, 50, 150, 250, 350}) + [_rect(0, 350, 500, 400), _vbrick(250, 350, 450)]
    return None


def _block_parts(cp: int) -> list[tuple[list[tuple[int, int]], list[int]]] | None:
    if cp == 0x2588:
        return [_rect(0, y0, 500, y0 + 50) for y0 in ROWS]
    if cp == 0x2580:
        return [_rect(0, y0, 500, y0 + 50) for y0 in (350, 450, 550, 650, 750)]
    if cp == 0x2584:
        return [_rect(0, y0, 500, y0 + 50) for y0 in (-150, -50, 50, 150, 250)]
    if cp == 0x258C:
        return [_rect(0, y0, 250, y0 + 50) for y0 in ROWS]
    if cp == 0x2590:
        return [_rect(250, y0, 500, y0 + 50) for y0 in ROWS]
    if cp == 0x2581:
        return [_rect(0, -150, 500, -100)]
    if cp == 0x2582:
        return [_rect(0, -150, 500, -50), _rect(0, -50, 500, 0)]
    if cp == 0x2583:
        return [_rect(0, -150, 500, 0), _rect(0, 50, 500, 100)]
    if cp == 0x2585:
        return [_rect(0, -150, 500, 100), _rect(0, 150, 500, 200), _rect(0, 250, 500, 300)]
    if cp == 0x2586:
        return [_rect(0, -150, 500, 200), _rect(0, 250, 500, 300)]
    if cp == 0x2587:
        return [_rect(0, -150, 500, 300), _rect(0, 350, 500, 400)]
    if cp == 0x258F:
        return [_rect(0, y0, 62, y0 + 50) for y0 in ROWS]
    if cp == 0x258E:
        return [_rect(0, y0, 125, y0 + 50) for y0 in ROWS]
    if cp == 0x258D:
        return [_rect(0, y0, 187, y0 + 50) for y0 in ROWS]
    if cp == 0x258B:
        return [_rect(0, y0, 312, y0 + 50) for y0 in ROWS]
    if cp == 0x258A:
        return [_rect(0, y0, 375, y0 + 50) for y0 in ROWS]
    if cp == 0x2589:
        return [_rect(0, y0, 437, y0 + 50) for y0 in ROWS]
    if cp == 0x2595:
        return [_rect(437, y0, 500, y0 + 50) for y0 in ROWS]
    if cp == 0x2594:
        return [_rect(0, 750, 500, 800)]
    quad = {
        0x2596: (False, False, True, False),
        0x2597: (False, False, False, True),
        0x2598: (True, False, False, False),
        0x259D: (False, True, False, False),
        0x2599: (True, False, True, True),
        0x259A: (True, False, False, True),
        0x259B: (True, True, True, False),
        0x259C: (True, True, False, True),
        0x259E: (False, True, True, False),
        0x259F: (False, True, True, True),
    }
    if cp in (0x2596, 0x2597, 0x2598, 0x259D, 0x2599, 0x259A, 0x259B, 0x259C, 0x259E, 0x259F):
        ul, ur, ll, lr = quad[cp]
        out = []
        top_rows = [350, 450, 550, 650, 750]
        bot_rows = [-150, -50, 50, 150, 250]
        if ul:
            out += [_rect(0, y0, 250, y0 + 50) for y0 in top_rows]
        if ur:
            out += [_rect(250, y0, 500, y0 + 50) for y0 in top_rows]
        if ll:
            out += [_rect(0, y0, 250, y0 + 50) for y0 in bot_rows]
        if lr:
            out += [_rect(250, y0, 500, y0 + 50) for y0 in bot_rows]
        return out
    if cp == 0x2591:
        out = []
        for i, y0 in enumerate(ROWS):
            if i % 2 == 0:
                out.append(_rect(0, y0, 250, y0 + 50))
            else:
                out.append(_rect(250, y0, 500, y0 + 50))
        return out
    if cp == 0x2592:
        out = []
        for i, y0 in enumerate(ROWS):
            if i % 2 == 0:
                out.append(_rect(0, y0, 250, y0 + 50))
                out.append(_rect(250, y0, 375, y0 + 50))
            else:
                out.append(_rect(125, y0, 500, y0 + 50))
        return out
    if cp == 0x2593:
        out = []
        for i, y0 in enumerate(ROWS):
            if i % 3 == 2:
                out.append(_rect(250, y0, 500, y0 + 50))
            else:
                out.append(_rect(0, y0, 500, y0 + 50))
        return out
    return None


def _symbol_parts(cp: int) -> list[tuple[list[tuple[int, int]], list[int]]] | None:
    if cp == 0x2190:
        return [_rect(0, 350, 300, 400), _vbrick(50, 150, 250), _vbrick(50, 150, 450), _vbrick(150, 250, 150), _vbrick(150, 250, 550)]
    if cp == 0x2192:
        return [_rect(200, 350, 500, 400), _vbrick(350, 450, 250), _vbrick(350, 450, 450), _vbrick(250, 350, 150), _vbrick(250, 350, 550)]
    if cp == 0x2191:
        return [_vbrick(150, 250, -150), _vbrick(150, 250, -50), _vbrick(150, 250, 50), _vbrick(150, 250, 150), _vbrick(150, 250, 250), _vbrick(150, 250, 350), _vbrick(50, 150, 450), _vbrick(250, 350, 450), _vbrick(100, 200, 550), _vbrick(200, 300, 550), _vbrick(150, 250, 650)]
    if cp == 0x2193:
        return [_vbrick(150, 250, 650), _vbrick(150, 250, 550), _vbrick(150, 250, 450), _vbrick(150, 250, 350), _vbrick(150, 250, 250), _vbrick(150, 250, 150), _vbrick(50, 150, 50), _vbrick(250, 350, 50), _vbrick(100, 200, -50), _vbrick(200, 300, -50), _vbrick(150, 250, -150)]
    if cp == 0x25A0:
        return [_rect(0, y0, 400, y0 + 50) for y0 in (150, 250, 350, 450, 550)]
    if cp == 0x25A1:
        return [_rect(0, 550, 400, 600), _rect(0, 150, 400, 200), _vbrick(0, 100, 250), _vbrick(0, 100, 350), _vbrick(0, 100, 450), _vbrick(300, 400, 250), _vbrick(300, 400, 350), _vbrick(300, 400, 450)]
    if cp == 0x25B2:
        return [_vbrick(150, 250, 550), _vbrick(100, 300, 450), _vbrick(100, 300, 350), _vbrick(50, 350, 250), _vbrick(50, 350, 150)]
    if cp == 0x25B3:
        return [_vbrick(150, 250, 550), _vbrick(100, 200, 450), _vbrick(200, 300, 450), _vbrick(50, 150, 350), _vbrick(250, 350, 350), _vbrick(50, 150, 250), _vbrick(250, 350, 250), _vbrick(50, 150, 150), _vbrick(250, 350, 150)]
    if cp == 0x25B6:
        return [_vbrick(0, 100, 250), _vbrick(0, 100, 350), _vbrick(0, 100, 450), _vbrick(100, 200, 250), _vbrick(100, 200, 350), _vbrick(100, 200, 450), _vbrick(200, 300, 350)]
    if cp == 0x25BC:
        return [_vbrick(50, 350, 450), _vbrick(50, 350, 550), _vbrick(100, 300, 350), _vbrick(100, 300, 250), _vbrick(150, 250, 150)]
    if cp == 0x25C0:
        return [_vbrick(300, 400, 250), _vbrick(300, 400, 350), _vbrick(300, 400, 450), _vbrick(200, 300, 250), _vbrick(200, 300, 350), _vbrick(200, 300, 450), _vbrick(100, 200, 350)]
    if cp == 0x25CB:
        return [_rect(100, 550, 300, 600), _rect(100, 150, 300, 200), _vbrick(50, 150, 250), _vbrick(50, 150, 350), _vbrick(50, 150, 450), _vbrick(250, 350, 250), _vbrick(250, 350, 350), _vbrick(250, 350, 450)]
    if cp == 0x25CF:
        return [_rect(100, 550, 300, 600), _rect(100, 150, 300, 200), _rect(50, 450, 350, 500), _rect(50, 250, 350, 300), _rect(50, 350, 350, 400)]
    if cp == 0x2022:
        return [_vbrick(125, 275, 250), _vbrick(125, 275, 350), _vbrick(125, 275, 450)]
    if cp == 0x2026:
        return [_vbrick(0, 100, 150), _vbrick(0, 100, 250), _vbrick(150, 250, 150), _vbrick(150, 250, 250), _vbrick(300, 400, 150), _vbrick(300, 400, 250)]
    if cp == 0x2039:
        return [_vbrick(200, 300, 250), _vbrick(200, 300, 350), _vbrick(200, 300, 450), _vbrick(100, 200, 350)]
    if cp == 0x203A:
        return [_vbrick(100, 200, 250), _vbrick(100, 200, 350), _vbrick(100, 200, 450), _vbrick(200, 300, 350)]
    if cp == 0x276E:
        return [_vbrick(250, 350, 150), _vbrick(250, 350, 250), _vbrick(250, 350, 450), _vbrick(250, 350, 550), _vbrick(150, 250, 350), _vbrick(50, 150, 250), _vbrick(50, 150, 450)]
    if cp == 0x276F:
        return [_vbrick(50, 150, 150), _vbrick(50, 150, 250), _vbrick(50, 150, 450), _vbrick(50, 150, 550), _vbrick(150, 250, 350), _vbrick(250, 350, 250), _vbrick(250, 350, 450)]
    if cp == 0x2713:
        return [_vbrick(50, 150, 250), _vbrick(150, 250, 350), _vbrick(250, 350, 450), _vbrick(250, 350, 550)]
    if cp == 0x2716:
        return [_vbrick(50, 150, 250), _vbrick(250, 350, 250), _vbrick(150, 250, 350), _vbrick(50, 150, 450), _vbrick(250, 350, 450)]
    if cp == 0xE0B0:
        out = []
        widths = [500, 450, 400, 350, 300, 250, 200, 150, 100, 50]
        for y0, w in zip(ROWS, widths):
            out.append(_rect(0, y0, w, y0 + 50))
        return out
    if cp == 0xE0B2:
        out = []
        widths = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500]
        for y0, w in zip(ROWS, widths):
            out.append(_rect(500 - w, y0, 500, y0 + 50))
        return out
    if cp == 0xE0B1:
        return [_vbrick(150, 250, 150), _vbrick(150, 250, 250), _vbrick(150, 250, 350), _vbrick(150, 250, 450), _vbrick(150, 250, 550)]
    if cp == 0xE0B3:
        return [_vbrick(250, 350, 150), _vbrick(250, 350, 250), _vbrick(250, 350, 350), _vbrick(250, 350, 450), _vbrick(250, 350, 550)]
    return None


def build_parts(cp: int, font) -> list[tuple[list[tuple[int, int]], list[int]]] | None:
    import unicodedata
    try:
        name = unicodedata.name(chr(cp))
    except ValueError:
        name = ""
    if 0x2500 <= cp <= 0x257F:
        d = _dash_parts(cp, font)
        if d is not None:
            return d
        d = _diagonal_parts(cp)
        if d is not None:
            return d
        d = _arc_parts(cp)
        if d is not None:
            return d
        if "DIAGONAL" in name:
            return None
        edges = _parse_box(name)
        if edges is None:
            return None
        return _box_parts(edges)
    if 0x2580 <= cp <= 0x259F:
        return _block_parts(cp)
    s = _symbol_parts(cp)
    if s is not None:
        return s
    return None


TARGETS = (
    list(range(0x2500, 0x2580))
    + list(range(0x2580, 0x25A0))
    + [0x2190, 0x2191, 0x2192, 0x2193]
    + [0x25A0, 0x25A1, 0x25B2, 0x25B3, 0x25B6, 0x25BC, 0x25C0, 0x25CB, 0x25CF]
    + [0x2022, 0x2026, 0x2039, 0x203A, 0x276E, 0x276F, 0x2713, 0x2716]
    + [0xE0B0, 0xE0B1, 0xE0B2, 0xE0B3]
)


def add_coverage(font) -> int:
    order = font.getGlyphOrder()
    cmap_best = font.getBestCmap()
    added = 0
    for cp in TARGETS:
        if cp in cmap_best:
            continue
        parts = build_parts(cp, font)
        if not parts:
            continue
        name = f"uni{cp:04X}"
        _commit(font, name, parts)
        order.append(name)
        for table in font["cmap"].tables:
            if table.format == 4:
                table.cmap[cp] = name
        added += 1
    font.setGlyphOrder(order)
    font["maxp"].numGlyphs = len(order)
    try:
        font["OS/2"].recalcUnicodeRanges(font)
    except Exception:
        pass
    try:
        font["OS/2"].recalcCodePageRanges(font)
    except Exception:
        pass
    return added
