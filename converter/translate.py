"""Translate prose to English through a local Ollama, one segment at a time.

Only prose is translated, code and paths stay as they are. A result that looks
like a summary (very different length, collapsed line count) is dropped and the
original kept. If Ollama is not reachable the deck comes back unchanged.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .ir import Deck, Segment

LANG_NAMES = {
    "de": "German", "fr": "French", "es": "Spanish", "it": "Italian",
    "nl": "Dutch", "pl": "Polish", "pt": "Portuguese", "sv": "Swedish",
}

def _ollama(prompt: str, model: str, host: str, timeout: int = 120) -> str:
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0},
    }).encode("utf-8")
    req = urllib.request.Request(f"{host}/api/generate", data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8")).get("response", "").strip()

def _reachable(host: str) -> bool:
    try:
        urllib.request.urlopen(f"{host}/api/tags", timeout=5)
        return True
    except Exception:
        return False

def _translate_text(text: str, lang: str, model: str, host: str) -> str:
    if not text.strip():
        return text
    src = LANG_NAMES.get(lang, lang.upper())
    prompt = (
        f"Translate the following {src} text to English.\n"
        "Rules: return ONLY the translation, exactly one output for the one input. "
        "Do NOT summarise, add, omit, or reorder anything. Keep numbers, proper "
        "nouns, tool names, file names, commands and paths unchanged. Preserve line "
        "breaks.\n\n"
        f"TEXT:\n{text}\n\nTRANSLATION:"
    )
    try:
        out = _ollama(prompt, model, host)
    except Exception:
        return text
    if not out:
        return text
    if len(out) < len(text) * 0.4 or len(out) > len(text) * 3:
        return text
    if text.count("\n") and out.count("\n") == 0 and text.count("\n") > 2:
        return text
    return out

def translate_deck(deck: Deck, source_lang: str, model: str = "gemma4:latest",
                   host: str = "http://localhost:11434",
                   log=lambda *a: None) -> tuple[Deck, list[tuple[str, str]]]:
    """Translate prose in place. Returns (deck, bilingual_log[(src, en)])."""
    if source_lang == "en":
        return deck, []
    if not _reachable(host):
        log(f"[translate] Ollama not reachable at {host}, translation skipped")
        return deck, []

    bilingual: list[tuple[str, str]] = []

    def do(seg: Segment):
        if not seg.translatable:
            return
        en = _translate_text(seg.text, source_lang, model, host)
        if en != seg.text:
            bilingual.append((seg.text, en))
            seg.text = en

    for slide in deck.slides:
        if slide.title:
            en = _translate_text(slide.title, source_lang, model, host)
            if en != slide.title:
                bilingual.append((slide.title, en))
                slide.title = en
        if slide.notes:
            slide.notes = _translate_text(slide.notes, source_lang, model, host)
        for b in slide.blocks:
            if b.kind == "flow":
                for _lvl, segs in b.lines:
                    for seg in segs:
                        do(seg)
            elif b.kind in ("para", "list", "olist"):
                for seg in b.segments:
                    do(seg)
            elif b.kind == "table":
                for row in b.rows:
                    for cell in row:
                        for seg in cell:
                            do(seg)
    log(f"[translate] {len(bilingual)} segments translated from {source_lang}")
    return deck, bilingual
