"""Read a PDF into the IR. Lossy fallback.

One page becomes one slide. The largest span on a page is taken as the title,
monospace spans become code. Prefer the .pptx when both exist.
"""

from __future__ import annotations

import hashlib
import re

import fitz

from .ir import Block, Deck, Image, Segment, Slide

_MONO_RE = re.compile(r"(mono|courier|consol|menlo|monaco|inconsolata)", re.I)
_PAGENO_RE = re.compile(r"^\s*\d{1,3}\s*$")

def _is_mono(font: str | None) -> bool:
    return bool(font and _MONO_RE.search(font))

def extract(path: str) -> Deck:
    doc = fitz.open(path)
    deck = Deck(title="", source_lang="en")
    seen: dict[str, str] = {}
    for i, page in enumerate(doc):
        data = page.get_text("dict")
        lines: list[tuple[str, float, bool]] = []
        for block in data.get("blocks", []):
            for line in block.get("lines", []):
                text = "".join(sp.get("text", "") for sp in line.get("spans", []))
                if not text.strip():
                    continue
                spans = line.get("spans", [])
                size = max((sp.get("size", 0) for sp in spans), default=0)
                mono = all(_is_mono(sp.get("font")) for sp in spans if sp.get("text", "").strip())
                lines.append((text, size, mono))

        images: list[Image] = []
        for j, img in enumerate(page.get_images(full=True)):
            try:
                base = doc.extract_image(img[0])
                blob = base["image"]
                h = hashlib.sha1(blob).hexdigest()
                if h not in seen:
                    fname = f"page_{i+1}_img_{len(seen)+1}.{base['ext']}"
                    seen[h] = fname
                    images.append(Image(filename=fname, data=blob))
            except Exception:
                pass

        if not lines and not images:
            continue

        title = ""
        if lines:
            maxsize = max(s for _, s, _ in lines)
            for text, size, _ in lines:
                if size == maxsize and not _PAGENO_RE.match(text):
                    title = text.strip()
                    break

        blocks: list[Block] = []
        prose_buf: list[str] = []
        code_buf: list[str] = []

        def flush_prose():
            if not prose_buf:
                return
            members = [Segment(text=l.strip(), kind="prose") for l in prose_buf if l.strip()]
            if len(members) == 1:
                blocks.append(Block(kind="para", segments=members))
            elif members:
                blocks.append(Block(kind="list", segments=members))
            prose_buf.clear()

        def flush_code():
            if not code_buf:
                return
            blocks.append(Block(kind="code",
                                segments=[Segment(text="\n".join(code_buf), kind="code")]))
            code_buf.clear()

        for text, _, mono in lines:
            if text.strip() == title or _PAGENO_RE.match(text):
                continue
            if mono:
                flush_prose()
                code_buf.append(text.rstrip())
            else:
                flush_code()
                prose_buf.append(text)
        flush_code()
        flush_prose()

        deck.slides.append(Slide(index=i, title=title, notes="",
                                 blocks=blocks, images=images))
    return deck
