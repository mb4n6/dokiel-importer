"""Command-line entry point for the Dokiel converter.

Usage:
    python3 -m converter.cli INPUT.pptx OUTPUT_DIR \
        --course-title "Mac Advanced" --day "Day 3" \
        --session-code 3-1 --session-name "Hashcat Results" [--translate --source-lang de]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from . import (classify, emit, extract_docx, extract_pdf, extract_pptx, package,
               translate, verify)
from .ir import Deck

SUPPORTED = (".pptx", ".ppt", ".pdf", ".docx")

def load_deck(input_path: str, log=print, command_mode: str = "auto",
              terms: bool = False, order: str = "document") -> Deck:
    ext = Path(input_path).suffix.lower()
    if ext in (".pptx", ".ppt"):
        return extract_pptx.extract(input_path, command_mode=command_mode, terms=terms, order=order)
    if ext == ".pdf":
        log("[warn] PDF is a lossy source, prefer the .pptx when available")
        return extract_pdf.extract(input_path)
    if ext == ".docx":
        return extract_docx.extract(input_path)
    raise ValueError(f"Unsupported input type: {ext}")

def _report_verify(deck: Deck, files: dict, log) -> tuple[list, dict]:
    wf = verify.check_wellformed(files)
    fid = verify.check_fidelity(deck, files)
    if wf:
        for e in wf:
            log(f"[verify] NOT well-formed: {e}")
    else:
        log("[verify] XML well-formed: OK")
    log(f"[verify] fidelity: {fid['total_tokens'] - len(fid['missing_tokens'])}/"
        f"{fid['total_tokens']} tokens present; "
        f"code byte-exact: {'OK' if fid['code_ok'] else 'MISSING ' + str(len(fid['code_missing']))}")
    if fid["missing_tokens"]:
        log(f"[verify] missing tokens (first 20): {fid['missing_tokens'][:20]}")
    if fid["code_missing"]:
        log(f"[verify] missing code lines (first 5): {fid['code_missing'][:5]}")
    return wf, fid

def convert(input_path: str, output_dir: str, *, course_title: str, day: str,
            session_code: str, session_name: str, do_translate: bool = False,
            source_lang: str = "de", model: str = "gemma4:latest",
            host: str = "http://localhost:11434", make_scwsp: bool = True,
            target: str = "basic", exercises: bool = False, make_pub: bool = False,
            command_mode: str = "auto", terms: bool = False, order: str = "document",
            log=print) -> dict:
    deck = load_deck(input_path, log, command_mode, terms, order)
    log(f"[extract] {len(deck.slides)} slides, {len(deck.all_images())} images")
    for w in deck.warnings:
        log(f"[warn] {w}")

    classify.classify(deck)

    bilingual: list = []
    if do_translate:
        deck.source_lang = source_lang
        deck, bilingual = translate.translate_deck(deck, source_lang, model, host, log=log)

    files = emit.build_workspace(deck, course_title, day, session_code, session_name,
                                 target=target, exercises=exercises, make_pub=make_pub)

    wf, fid = _report_verify(deck, files, log)

    course_safe = emit.safe(course_title)
    ws, scwsp = package.write_workspace(files, output_dir, course_safe, make_scwsp=make_scwsp)
    log(f"[write] workspace: {ws}")
    if scwsp:
        log(f"[write] archive:   {scwsp}")

    if bilingual:
        blog = os.path.join(output_dir, course_safe + ".translation.md")
        with open(blog, "w", encoding="utf-8") as f:
            f.write(f"# Translation log ({source_lang} -> en)\n\n")
            for srct, en in bilingual:
                f.write(f"- **{source_lang}:** {srct}\n  - **en:** {en}\n")
        log(f"[write] bilingual log: {blog}")

    return {"workspace": ws, "scwsp": scwsp, "wellformed": not wf, "fidelity": fid}

def list_inputs(input_dir: str) -> list[Path]:
    return sorted(p for p in Path(input_dir).iterdir()
                  if p.is_file() and p.suffix.lower() in SUPPORTED)

def convert_batch(input_dir: str, output_dir: str, *, course_title: str, day: str,
                  do_translate: bool = False, source_lang: str = "de",
                  model: str = "gemma4:latest", host: str = "http://localhost:11434",
                  make_scwsp: bool = True, target: str = "basic",
                  exercises: bool = False, make_pub: bool = False,
                  command_mode: str = "auto", terms: bool = False,
                  order: str = "document", log=print) -> dict:
    """Convert every file in a folder into ONE workspace (one session per file)."""
    inputs = list_inputs(input_dir)
    if not inputs:
        raise ValueError(f"No {', '.join(SUPPORTED)} files in {input_dir}")
    m = re.search(r"\d+", day)
    day_no = m.group() if m else "1"

    files: dict[str, object] = {}
    combined = Deck(title=course_title)
    bilingual_all: list = []
    log(f"[batch] {len(inputs)} files -> workspace '{course_title}' / {day}")

    for i, path in enumerate(inputs, 1):
        log(f"[batch] ({i}/{len(inputs)}) {path.name}")
        deck = load_deck(str(path), log, command_mode, terms, order)
        for w in deck.warnings:
            log(f"[warn] {path.name}: {w}")
        classify.classify(deck)
        if do_translate:
            deck.source_lang = source_lang
            deck, bl = translate.translate_deck(deck, source_lang, model, host, log=log)
            bilingual_all += bl
        session_code = f"{day_no}-{i}"
        files.update(emit.build_session(deck, day, session_code, path.stem,
                                        target=target, exercises=exercises, make_pub=make_pub))
        combined.slides.extend(deck.slides)
        log(f"[batch]   -> {session_code} ({len(deck.slides)} slides)")

    files.update(emit.workspace_meta(course_title, [day]))
    wf, fid = _report_verify(combined, files, log)

    course_safe = emit.safe(course_title)
    ws, scwsp = package.write_workspace(files, output_dir, course_safe, make_scwsp=make_scwsp)
    log(f"[write] workspace: {ws}")
    if scwsp:
        log(f"[write] archive:   {scwsp}")
    if bilingual_all:
        blog = os.path.join(output_dir, course_safe + ".translation.md")
        with open(blog, "w", encoding="utf-8") as f:
            f.write(f"# Translation log ({source_lang} -> en)\n\n")
            for srct, en in bilingual_all:
                f.write(f"- **{source_lang}:** {srct}\n  - **en:** {en}\n")
        log(f"[write] bilingual log: {blog}")

    return {"workspace": ws, "scwsp": scwsp, "wellformed": not wf,
            "fidelity": fid, "sessions": len(inputs)}

def main(argv=None):
    p = argparse.ArgumentParser(description="Convert PPTX, PDF and DOCX into a Dokiel workspace")
    p.add_argument("--gui", action="store_true", help="launch the desktop GUI")
    p.add_argument("input", nargs="?")
    p.add_argument("output", nargs="?")
    p.add_argument("--course-title", default=None)
    p.add_argument("--day", default="Day 1")
    p.add_argument("--session-code", default="1-1")
    p.add_argument("--session-name", default=None)
    p.add_argument("--translate", action="store_true")
    p.add_argument("--source-lang", default="de")
    p.add_argument("--model", default="gemma4:latest")
    p.add_argument("--host", default="http://localhost:11434")
    p.add_argument("--no-scwsp", action="store_true")
    p.add_argument("--target", choices=("basic", "advanced"), default="basic",
                   help="basic: all slides inline in one submodule; "
                        "advanced: one .unit per slide, referenced from the index")
    p.add_argument("--exercises", action="store_true",
                   help="map exercise-titled slides to dk:exercise (exposition-only, order-preserving)")
    p.add_argument("--pub", action="store_true",
                   help="also emit a dk:trainingRoot .pub publication descriptor")
    p.add_argument("--commands", choices=("auto", "color", "font", "both"), default="auto",
                   help="how to detect commands: auto (colour if the deck uses it, else font), "
                        "color (only the command colour), font, or both")
    p.add_argument("--terms", action="store_true",
                   help="mark monospace text in the default colour as term (role=term)")
    p.add_argument("--reading-order", choices=("document", "position"), default="document",
                   help="document: shape order in the file (default); "
                        "position: sort shapes top-to-bottom, left-to-right")
    p.add_argument("--batch", action="store_true",
                   help="input is a FOLDER; convert every file into one workspace "
                        "(one session per file: .pptx/.pdf/.docx)")
    a = p.parse_args(argv)

    if a.gui:
        from . import gui
        gui.launch()
        return 0
    if not a.input or not a.output:
        p.error("input and output are required (or use --gui)")

    if a.batch:
        res = convert_batch(
            a.input, a.output,
            course_title=a.course_title or Path(a.input).name,
            day=a.day, do_translate=a.translate, source_lang=a.source_lang,
            model=a.model, host=a.host, make_scwsp=not a.no_scwsp,
            target=a.target, exercises=a.exercises, make_pub=a.pub,
            command_mode=a.commands, terms=a.terms, order=a.reading_order,
        )
    else:
        stem = Path(a.input).stem
        res = convert(
            a.input, a.output,
            course_title=a.course_title or stem,
            day=a.day, session_code=a.session_code,
            session_name=a.session_name or stem,
            do_translate=a.translate, source_lang=a.source_lang,
            model=a.model, host=a.host, make_scwsp=not a.no_scwsp,
            target=a.target, exercises=a.exercises, make_pub=a.pub,
            command_mode=a.commands, terms=a.terms, order=a.reading_order,
        )
    return 0 if res["wellformed"] else 1

if __name__ == "__main__":
    sys.exit(main())
