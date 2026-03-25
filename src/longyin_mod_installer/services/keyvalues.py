from __future__ import annotations

import re
from collections import deque
from typing import Iterator

TOKEN_PATTERN = re.compile(r'"((?:\\.|[^"\\])*)"|([{}])', re.DOTALL)
COMMENT_PATTERN = re.compile(r"//.*?$", re.MULTILINE)


def parse_keyvalues(text: str) -> dict[str, object]:
    sanitized = COMMENT_PATTERN.sub("", text)
    tokens = deque(_tokenize(sanitized))
    return _parse_object(tokens)


def _tokenize(text: str) -> Iterator[str]:
    for match in TOKEN_PATTERN.finditer(text):
        quoted, brace = match.groups()
        if brace:
            yield brace
        elif quoted is not None:
            yield bytes(quoted, "utf-8").decode("unicode_escape")


def _parse_object(tokens: deque[str]) -> dict[str, object]:
    result: dict[str, object] = {}
    while tokens:
        token = tokens.popleft()
        if token == "}":
            return result

        key = token
        if not tokens:
            raise ValueError(f"键 {key} 缺少值。")

        next_token = tokens.popleft()
        if next_token == "{":
            value = _parse_object(tokens)
        else:
            value = next_token
        result[key] = value
    return result
