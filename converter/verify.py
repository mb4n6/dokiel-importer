"""Check the output: XML well-formedness and content fidelity.

Fidelity is checked per source segment: its non-space characters must appear in
the emitted XML. Code blocks are checked as an exact substring. Comparing
segments rather than whitespace tokens survives inline styling and re-wrapping
without false alarms.
"""

from __future__ import annotations

import re

from lxml import etree

from .ir import Deck

_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

def _norm(text: str) -> str:
    return re.sub(r"\s+", "", _ILLEGAL_XML.sub("", text))

def check_wellformed(files: dict[str, object]) -> list[str]:
    errors: list[str] = []
    for rel, content in files.items():
        if not (rel.endswith((".scen", ".unit", ".xml")) or rel in (".wspmeta", ".wsporigin")):
            continue
        data = content.encode("utf-8") if isinstance(content, str) else content
        try:
            etree.fromstring(data)
        except Exception as e:
            errors.append(f"{rel}: {e}")
    return errors

def _emitted_text(files: dict[str, object]) -> str:
    """Concatenate all text nodes of every .scen/.unit with NO separator.

    itertext() already returns text nodes decoded (&amp; -> &), so this matches
    the source characters. No separator is inserted, so a run split across
    adjacent inline spans stays contiguous (e.g. <em>SEGB</em>-Container).
    """
    chunks: list[str] = []
    for rel, content in files.items():
        if not rel.endswith((".scen", ".unit")):
            continue
        data = content.encode("utf-8") if isinstance(content, str) else content
        try:
            root = etree.fromstring(data)
        except Exception:
            continue
        chunks.append("".join(root.itertext()))
    return "".join(chunks)

def _atoms(deck: Deck):
    """Yield (kind, text) for every atomic piece of source content."""
    for s in deck.slides:
        if s.title.strip():
            yield "seg", s.title
        if s.notes.strip():
            yield "seg", s.notes
        for b in s.blocks:
            if b.kind == "code":
                yield "code", b.text()
            elif b.kind == "flow":
                for _lvl, segs in b.lines:
                    for seg in segs:
                        if seg.text.strip():
                            yield "seg", seg.text
            elif b.kind == "table":
                for row in b.rows:
                    for cell in row:
                        for seg in cell:
                            if seg.text.strip():
                                yield "seg", seg.text
            else:
                for seg in b.segments:
                    if seg.text.strip():
                        yield "seg", seg.text

def check_fidelity(deck: Deck, files: dict[str, object]) -> dict:
    """Return {total_tokens, missing_tokens, code_ok, code_missing}.

    (Keys keep the historical names; a "token" here is a source segment.)
    """
    emitted_raw = _emitted_text(files)
    emitted_ns = _norm(emitted_raw)

    total = 0
    missing: list[str] = []
    code_missing: list[str] = []
    for kind, text in _atoms(deck):
        ns = _norm(text)
        if not ns:
            continue
        total += 1
        if kind == "code":
            if text not in emitted_raw and ns not in emitted_ns:
                code_missing.append(text[:80])
        else:
            if ns not in emitted_ns:
                missing.append(text[:80])

    return {
        "total_tokens": total,
        "missing_tokens": missing,
        "code_ok": not code_missing,
        "code_missing": code_missing,
    }
