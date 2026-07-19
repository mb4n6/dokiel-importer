"""Data model shared by the pipeline.

A Deck holds Slides, a Slide holds Blocks and Images, a Block holds Segments.
Extraction fills it, the later stages read it. Nothing here changes the text.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SEGMENT_KINDS = ("prose", "code", "inline_cmd", "path", "term")

BLOCK_KINDS = ("heading", "para", "list", "olist", "flow", "code", "table")

@dataclass
class Segment:
    text: str
    kind: str = "prose"
    emphasis: bool = False

    @property
    def translatable(self) -> bool:
        return self.kind == "prose"

@dataclass
class Block:
    kind: str
    segments: list[Segment] = field(default_factory=list)
    rows: list[list[list[Segment]]] = field(default_factory=list)
    lines: list[tuple[int, list[Segment]]] = field(default_factory=list)
    mime: str = "text/plain"
    ordered: bool = False

    def text(self) -> str:
        """Flattened plain text of this block (for fidelity checks)."""
        if self.kind == "table":
            return "\n".join(
                "\t".join("".join(s.text for s in cell) for cell in row)
                for row in self.rows
            )
        if self.kind == "flow":
            return "\n".join("".join(s.text for s in segs) for _, segs in self.lines)
        return "\n".join(s.text for s in self.segments)

@dataclass
class Image:
    filename: str
    data: bytes
    alt: str = ""

@dataclass
class Slide:
    index: int
    title: str = ""
    notes: str = ""
    blocks: list[Block] = field(default_factory=list)
    images: list[Image] = field(default_factory=list)

    def text(self) -> str:
        parts = [self.title] + [b.text() for b in self.blocks]
        return "\n".join(p for p in parts if p)

@dataclass
class Deck:
    title: str
    source_lang: str = "en"
    slides: list[Slide] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def text(self) -> str:
        return "\n".join(s.text() for s in self.slides)

    def all_images(self) -> list[Image]:
        out: list[Image] = []
        for s in self.slides:
            out.extend(s.images)
        return out
