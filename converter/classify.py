"""Split prose from code without an LLM.

Extraction already marks monospace and coloured runs as code. This pass also
catches commands written in a normal font (tool names, flags, masks, hashes,
SQL). It only reclassifies and regroups text, it never changes it.
"""

from __future__ import annotations

import re

from .ir import Block, Deck, Segment

_TOOLS = (r"hashcat|john|sqlite3?|plutil|PlistBuddy|mdls|mdfind|log|"
          r"ls|cd|cat|head|tail|grep|awk|sed|echo|cp|mv|rm|chmod|chown|sudo|"
          r"find|xxd|hexdump|strings|file|dd|mount|hdiutil|diskutil|"
          r"python3?|pip3?|git|curl|wget|unzip|tar|openssl|base64|jq")

_RE_CMD_START = re.compile(rf"^\s*(?:\$\s*)?(?:{_TOOLS})\b")
_RE_FLAG      = re.compile(r"(?:^|\s)--?[A-Za-z][\w-]*")
_RE_MASK      = re.compile(r"\?[dluasb]")
_RE_HASHLINE  = re.compile(r"^[0-9a-fA-F]{16,}:")
_RE_REDIRECT  = re.compile(r"[^<>]\s(?:>|>>|\|)\s|~/|\$\(")
_RE_SQL       = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE|CREATE|PRAGMA)\b.*", re.I)
_RE_SQL_END   = re.compile(r";\s*$")

def is_sql_line(text: str) -> bool:
    t = text.strip()
    return bool(_RE_SQL.match(t) and (_RE_SQL_END.search(t) or True))

def is_code_line(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    if _RE_HASHLINE.match(t):
        return True
    if _RE_CMD_START.search(t):
        return True
    if _RE_MASK.search(t):
        return True
    if _RE_FLAG.search(t) and (_RE_CMD_START.search(t) or _RE_MASK.search(t) or "hash" in t.lower()):
        return True
    if _RE_REDIRECT.search(t):
        return True
    return False

def _norm_prose(text: str) -> str:
    """Collapse authoring line-breaks/spaces in prose (formatting only, not content)."""
    return re.sub(r"\s+", " ", text).strip()

def _classify_lines(lines: list[str]) -> list[Block]:
    """Turn a sequence of text lines into alternating prose/code blocks."""
    out: list[Block] = []
    prose_buf: list[str] = []
    code_buf: list[str] = []
    sql = False

    def flush_prose():
        if not prose_buf:
            return
        members = [Segment(text=_norm_prose(l), kind="prose") for l in prose_buf if l.strip()]
        if len(members) == 1:
            out.append(Block(kind="para", segments=members))
        elif members:
            out.append(Block(kind="list", segments=members))
        prose_buf.clear()

    def flush_code():
        nonlocal sql
        if not code_buf:
            return
        mime = "text/x-sql" if sql else "text/plain"
        out.append(Block(kind="code", mime=mime,
                         segments=[Segment(text="\n".join(code_buf), kind="code")]))
        code_buf.clear()
        sql = False

    for line in lines:
        if is_sql_line(line):
            flush_prose()
            sql = True
            code_buf.append(line.rstrip())
        elif is_code_line(line):
            flush_prose()
            code_buf.append(line.rstrip())
        else:
            flush_code()
            prose_buf.append(line)
    flush_code()
    flush_prose()
    return out

def _block_to_lines(block: Block) -> list[str]:
    """Explode a prose/list block into individual lines for reclassification."""
    lines: list[str] = []
    for seg in block.segments:
        lines.extend(seg.text.split("\n"))
    return lines

def classify(deck: Deck) -> Deck:
    for slide in deck.slides:
        new_blocks: list[Block] = []
        for block in slide.blocks:
            if block.kind == "flow":
                new_blocks.append(block)
            elif block.kind in ("para", "list"):
                new_blocks.extend(_classify_lines(_block_to_lines(block)))
            elif block.kind == "code":
                txt = "\n".join(l.rstrip() for l in block.text().split("\n"))
                block.segments = [Segment(text=txt, kind="code")]
                new_blocks.append(block)
            else:
                new_blocks.append(block)
        slide.blocks = new_blocks
    return deck
