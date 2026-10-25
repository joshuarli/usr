"""Bounded GitHub Actions expression analyzer.

Lexer + Pratt parser for the documented subset, `${{ }}` interpolation
scanner that respects single/double quotes, conservative context table,
twelve common builtins with case-insensitivity, and an explicit four-way
outcome: valid, valid-unknown, unsupported, syntax-error, semantic-error.

Only high-confidence errors are reported; everything dynamic stays silent.
"""

from __future__ import annotations

from dataclasses import dataclass, field


FUNCTIONS = {
    "contains": (2, 2),
    "startswith": (2, 2),
    "endswith": (2, 2),
    "format": (1, None),
    "join": (1, 2),
    "tojson": (1, 1),
    "fromjson": (1, 1),
    "hashfiles": (1, None),
    "success": (0, 0),
    "failure": (0, 0),
    "cancelled": (0, 0),
    "always": (0, 0),
}

TOP_CONTEXTS = frozenset({
    "github", "env", "vars", "secrets", "job", "jobs", "steps",
    "needs", "matrix", "inputs", "outputs", "strategy", "runner",
})


@dataclass(frozen=True, slots=True)
class Token:
    kind: str
    value: str
    pos: int


def lex(source: str) -> tuple[list[Token], str | None]:
    tokens: list[Token] = []
    i = 0
    n = len(source)
    while i < n:
        c = source[i]
        if c in " \t\r\n":
            i += 1
            continue
        if c == "(" or c == ")" or c == "," or c == "[" or c == "]" or c == ".":
            tokens.append(Token(c, c, i))
            i += 1
            continue
        if c == "*":
            tokens.append(Token("*", "*", i))
            i += 1
            continue
        if c == "!":
            if source[i + 1:i + 2] == "=":
                tokens.append(Token("op", "!=", i))
                i += 2
            else:
                tokens.append(Token("!", "!", i))
                i += 1
            continue
        if c == "&" and source[i + 1:i + 2] == "&":
            tokens.append(Token("op", "&&", i))
            i += 2
            continue
        if c == "|" and source[i + 1:i + 2] == "|":
            tokens.append(Token("op", "||", i))
            i += 2
            continue
        if c == "=" and source[i + 1:i + 2] == "=":
            tokens.append(Token("op", "==", i))
            i += 2
            continue
        if c in "<>":
            if source[i + 1:i + 2] == "=":
                tokens.append(Token("op", c + "=", i))
                i += 2
            else:
                tokens.append(Token("op", c, i))
                i += 1
            continue
        if c == "'":
            j = i + 1
            buf = []
            while j < n:
                if source[j] == "'":
                    if source[j + 1:j + 2] == "'":
                        buf.append("'")
                        j += 2
                        continue
                    break
                buf.append(source[j])
                j += 1
            if j >= n:
                return [], f"unterminated string at offset {i}"
            tokens.append(Token("string", "".join(buf), i))
            i = j + 1
            continue
        if c == '"':
            j = i + 1
            buf = []
            closed = False
            while j < n:
                if source[j] == "\\" and j + 1 < n:
                    buf.append(source[j + 1])
                    j += 2
                    continue
                if source[j] == '"':
                    closed = True
                    break
                buf.append(source[j])
                j += 1
            if not closed:
                return [], f"unterminated string at offset {i}"
            tokens.append(Token("string", "".join(buf), i))
            i = j + 1
            continue
        if c.isdigit() or (c == "-" and source[i + 1:i + 2].isdigit()):
            j = i + (1 if c == "-" else 0)
            while j < n and (source[j].isdigit() or source[j] in "._xXaAbBcCdDeEfF"):
                j += 1
            tokens.append(Token("number", source[i:j], i))
            i = j
            continue
        if c.isalpha() or c == "_" or c == "$":
            j = i
            while j < n and (source[j].isalnum() or source[j] in "_-$"):
                j += 1
            word = source[i:j]
            low = word.lower()
            if low in ("true", "false"):
                tokens.append(Token("bool", low, i))
            elif low in ("null",):
                tokens.append(Token("null", low, i))
            else:
                tokens.append(Token("ident", word, i))
            i = j
            continue
        return [], f"unexpected character {c!r} at offset {i}"
    return tokens, None


@dataclass
class Node:
    kind: str
    value: str = ""
    children: list["Node"] = field(default_factory=list)


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.pos = 0
        self.error: str | None = None

    def peek(self) -> Token | None:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def next(self) -> Token | None:
        tok = self.peek()
        if tok is not None:
            self.pos += 1
        return tok

    def parse(self) -> Node | None:
        if not self.tokens:
            self.error = "empty expression"
            return None
        node = self._or()
        if self.error:
            return None
        if self.peek() is not None:
            self.error = f"unexpected {self.peek().value!r} at offset {self.peek().pos}"
            return None
        return node

    def _or(self) -> Node | None:
        left = self._and()
        while (t := self.peek()) and t.kind == "op" and t.value == "||":
            self.next()
            right = self._and()
            left = Node("or", "||", [left, right])
        return left

    def _and(self) -> Node | None:
        left = self._equality()
        while (t := self.peek()) and t.kind == "op" and t.value == "&&":
            self.next()
            right = self._equality()
            left = Node("and", "&&", [left, right])
        return left

    def _equality(self) -> Node | None:
        left = self._comparison()
        while (t := self.peek()) and t.kind == "op" and t.value in ("==", "!="):
            op = self.next().value
            right = self._comparison()
            left = Node("cmp", op, [left, right])
        return left

    def _comparison(self) -> Node | None:
        left = self._unary()
        while (t := self.peek()) and t.kind == "op" and t.value in ("<", "<=", ">", ">="):
            op = self.next().value
            right = self._unary()
            left = Node("cmp", op, [left, right])
        return left

    def _unary(self) -> Node | None:
        t = self.peek()
        if t and t.kind == "!":
            self.next()
            operand = self._unary()
            return Node("not", "!", [operand] if operand else [])
        return self._postfix()

    def _postfix(self) -> Node | None:
        node = self._primary()
        if node is None:
            return None
        while True:
            t = self.peek()
            if t is None:
                return node
            if t.kind == ".":
                self.next()
                nxt = self.peek()
                if nxt is None:
                    self.error = "expected property after '.'"
                    return None
                if nxt.kind == "*":
                    self.next()
                    node = Node("deref", "*", [node])
                    continue
                if nxt.kind in ("ident", "string", "number"):
                    self.next()
                    node = Node("prop", nxt.value, [node])
                    continue
                self.error = f"expected property after '.' at offset {t.pos}"
                return None
            if t.kind == "[":
                self.next()
                inner = self.peek()
                if inner and inner.kind == "*":
                    self.next()
                    expect = self.peek()
                    if not expect or expect.kind != "]":
                        self.error = "expected ']' after '[*'"
                        return None
                    self.next()
                    node = Node("deref", "*", [node])
                    continue
                expr = self._or()
                if self.error:
                    return None
                expect = self.peek()
                if not expect or expect.kind != "]":
                    self.error = "expected ']'"
                    return None
                self.next()
                node = Node("index", "[]", [node, expr])
                continue
            if t.kind == "(" and node.kind == "ident":
                self.next()
                args: list[Node] = []
                nxt = self.peek()
                if nxt and nxt.kind == ")":
                    self.next()
                    node = Node("call", node.value, args)
                    continue
                while True:
                    arg = self._or()
                    if self.error:
                        return None
                    args.append(arg)
                    nxt = self.peek()
                    if nxt and nxt.kind == ",":
                        self.next()
                        continue
                    if nxt and nxt.kind == ")":
                        self.next()
                        break
                    self.error = "expected ',' or ')' in call"
                    return None
                node = Node("call", node.value, args)
                continue
            return node

    def _primary(self) -> Node | None:
        t = self.peek()
        if t is None:
            self.error = "unexpected end of expression"
            return None
        if t.kind in ("ident", "string", "number", "bool", "null"):
            self.next()
            return Node(t.kind, t.value)
        if t.kind == "(":
            self.next()
            inner = self._or()
            if self.error:
                return None
            expect = self.peek()
            if not expect or expect.kind != ")":
                self.error = "expected ')'"
                return None
            self.next()
            return inner
        if t.kind == "*":
            self.next()
            return Node("deref", "*")
        self.error = f"unexpected {t.value!r} at offset {t.pos}"
        return None


def parse_expression(source: str) -> tuple[Node | None, str | None]:
    tokens, err = lex(source)
    if err is not None:
        return None, err
    parser = _Parser(tokens)
    node = parser.parse()
    if parser.error is not None:
        return None, parser.error
    return node, None


@dataclass(frozen=True, slots=True)
class Interpolation:
    inner: str
    line: int
    column: int
    start: int
    end: int


def scan_interpolations(text: str, base_line: int = 1) -> tuple[list[Interpolation], list[tuple[int, int, str]]]:
    found: list[Interpolation] = []
    errors: list[tuple[int, int, str]] = []
    i = 0
    n = len(text)
    line = base_line
    col_base = 0
    while i < n:
        start = text.find("${{", i)
        if start < 0:
            break
        line += text.count("\n", i, start)
        last_nl = text.rfind("\n", i, start)
        if last_nl < 0:
            column = start - col_base + 1
        else:
            column = start - last_nl
        j = start + 3
        quote: str | None = None
        depth = 0
        end = -1
        k = j
        while k < n:
            c = text[k]
            if quote is not None:
                if quote == "'" and c == "'" and text[k + 1:k + 2] == "'":
                    k += 2
                    continue
                if c == "\\" and quote == '"' and k + 1 < n:
                    k += 2
                    continue
                if c == quote:
                    quote = None
                k += 1
                continue
            if c in ("'", '"'):
                quote = c
                k += 1
                continue
            if c == "(":
                depth += 1
                k += 1
                continue
            if c == ")":
                if depth > 0:
                    depth -= 1
                k += 1
                continue
            if c == "}" and text[k + 1:k + 2] == "}":
                end = k + 2
                break
            k += 1
        if end < 0:
            errors.append((line, column, "missing closing '}}' in expression"))
            i = start + 3
            continue
        inner = text[j:k]
        found.append(Interpolation(inner=inner, line=line, column=column, start=start, end=end))
        i = end
    return found, errors


@dataclass
class Context:
    job_ids: set[str] = field(default_factory=set)
    step_ids_by_job: dict[str, set[str]] = field(default_factory=dict)
    needs_by_job: dict[str, set[str]] = field(default_factory=dict)
    matrix_keys: dict[str, set[str]] = field(default_factory=dict)
    matrix_jobs: set[str] = field(default_factory=set)
    inputs: set[str] = field(default_factory=set)
    outputs: set[str] = field(default_factory=set)
    location: str = ""


unsupported_count = 0


def _bump_unsupported() -> None:
    global unsupported_count
    unsupported_count += 1


def reset_unsupported_count() -> None:
    global unsupported_count
    unsupported_count = 0


def get_unsupported_count() -> int:
    return unsupported_count


def _root_name(node: Node) -> str | None:
    cur = node
    while cur.kind in ("prop", "index", "deref") and cur.children:
        cur = cur.children[0]
    if cur.kind == "ident":
        return cur.value
    return None


def check_semantics(node: Node, ctx: Context) -> tuple[str, str | None]:
    if node.kind == "call":
        low = node.value.lower()
        if low not in FUNCTIONS:
            _bump_unsupported()
            return ("valid-unknown", None)
        min_args, max_args = FUNCTIONS[low]
        got = len(node.children)
        if got < min_args or (max_args is not None and got > max_args):
            return ("semantic-error", f"function '{node.value}' expects {min_args}" +
                    (f"..{max_args}" if max_args != min_args else "") +
                    f" argument(s), got {got}")
        for child in node.children:
            status, msg = check_semantics(child, ctx)
            if status in ("semantic-error", "syntax-error"):
                return status, msg
            if status == "unsupported":
                return status, msg
        return ("valid", None) if low not in ("fromjson",) else ("valid-unknown", None)
    if node.kind in ("prop", "index", "deref"):
        root = _root_name(node)
        if root is None:
            return ("valid-unknown", None)
        if root.lower() not in {c.lower() for c in TOP_CONTEXTS}:
            _bump_unsupported()
            return ("unsupported", None)
        if node.kind == "deref":
            _bump_unsupported()
            return ("unsupported", None)
        low_root = root.lower()
        if low_root == "needs":
            parts = _prop_chain(node)
            if len(parts) >= 2:
                job = parts[1]
                if ctx.job_ids:
                    if job not in ctx.job_ids:
                        return ("semantic-error", f"unknown job '{job}' in 'needs' context")
                    if job not in ctx.needs_by_job.get(ctx.location, set()):
                        return ("semantic-error", f"job '{job}' is not a dependency in 'needs' context")
            _bump_unsupported()
            return ("valid-unknown", None)
        if low_root == "matrix":
            parts = _prop_chain(node)
            if len(parts) >= 2:
                key = parts[1]
                known = ctx.matrix_keys.get(ctx.location, set())
                if ctx.location in ctx.matrix_keys and key not in known:
                    return ("semantic-error", f"unknown matrix key '{key}'")
                if ctx.job_ids and ctx.location not in ctx.matrix_jobs:
                    return ("semantic-error", f"matrix context is unavailable in job '{ctx.location}'")
            _bump_unsupported()
            return ("valid-unknown", None)
        if low_root == "steps":
            parts = _prop_chain(node)
            if len(parts) >= 2:
                sid = parts[1]
                known = ctx.step_ids_by_job.get(ctx.location, set())
                if ctx.location in ctx.step_ids_by_job and sid not in known:
                    return ("semantic-error", f"unknown step '{sid}'")
            _bump_unsupported()
            return ("valid-unknown", None)
        if low_root == "inputs":
            parts = _prop_chain(node)
            if len(parts) >= 2 and ctx.inputs and parts[1] not in ctx.inputs:
                return ("semantic-error", f"unknown input '{parts[1]}'")
            _bump_unsupported()
            return ("valid-unknown", None)
        _bump_unsupported()
        return ("valid-unknown", None)
    if node.kind in ("or", "and", "cmp", "not"):
        for child in node.children:
            status, msg = check_semantics(child, ctx)
            if status in ("semantic-error", "syntax-error"):
                return status, msg
            if status == "unsupported":
                return status, msg
        return ("valid", None)
    if node.kind in ("ident", "string", "number", "bool", "null"):
        if node.kind == "ident" and node.value.lower() not in {c.lower() for c in TOP_CONTEXTS}:
            _bump_unsupported()
            return ("valid-unknown", None)
        return ("valid", None)
    _bump_unsupported()
    return ("unsupported", None)


def _prop_chain(node: Node) -> list[str]:
    parts: list[str] = []
    cur: Node | None = node
    while cur is not None and cur.kind in ("prop", "index", "deref"):
        if cur.kind == "prop":
            parts.append(cur.value)
        elif cur.kind == "index":
            parts.append("<index>")
        else:
            parts.append("*")
        cur = cur.children[0] if cur.children else None
    if cur is not None and cur.kind == "ident":
        parts.append(cur.value)
    parts.reverse()
    return parts


def analyze_expression(inner: str, ctx: Context) -> tuple[str, str | None]:
    node, err = parse_expression(inner)
    if err is not None:
        return ("syntax-error", err)
    assert node is not None
    return check_semantics(node, ctx)
