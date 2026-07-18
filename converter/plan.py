"""Dry run: analyse a source and report what the conversion would produce.

Runs extract, classify and emit in memory, writing nothing, and counts the
Dokiel elements. Used by the GUI for the scan result and the slide plan.
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree

from . import classify, emit, extract_docx, extract_pdf, extract_pptx, verify
from .ir import Deck

ELEMENT_LABELS = {
    "dk:module": "Module / session container",
    "dk:theory": "Theory slide (content)",
    "dk:exercise": "Exercise (task + exposition)",
    "sp:exposition": "Exercise task statement",
    "dk:code": "Code / output unit",
    "sp:subModule": "Submodule reference",
    "sp:theory": "Theory reference / wrapper",
    "sp:exercise": "Exercise reference / wrapper",
    "sp:synthesis": "Session synthesis (closing)",
    "sp:trainNote": "Trainer note",
    "sp:infobloc": "Content block",
    "sc:simpleList": "Bullet list",
    "sc:orderedList": "Numbered list",
    "sc:table": "Table",
    "sc:extBlock": "Embedded figure / unit ref",
    "sc:inlineStyle": "Inline style (cmd / path / emphasis)",
    "dk:trainingRoot": "Publication descriptor (.pub)",
    "sfm:image": "Image resource metadata",
}

_NS = {
    "dk": "kelis.fr:dokiel",
    "sc": "http://www.utc.fr/ics/scenari/v3/core",
    "sp": "http://www.utc.fr/ics/scenari/v3/primitive",
    "sfm": "http://www.utc.fr/ics/scenari/v3/filemeta",
}
_URI2PFX = {v: k for k, v in _NS.items()}

def _extract(input_path: str) -> Deck:
    ext = Path(input_path).suffix.lower()
    if ext in (".pptx", ".ppt"):
        return extract_pptx.extract(input_path)
    if ext == ".pdf":
        return extract_pdf.extract(input_path)
    if ext == ".docx":
        return extract_docx.extract(input_path)
    raise ValueError(f"Unsupported input type: {ext}")

def _slide_plan(deck: Deck, exercises: bool) -> list[dict]:
    rows = []
    for s in deck.slides:
        kinds = {"flow": 0, "para": 0, "list": 0, "olist": 0, "code": 0, "sql": 0, "table": 0}
        for b in s.blocks:
            if b.kind == "code":
                kinds["sql" if b.mime == "text/x-sql" else "code"] += 1
            elif b.kind in kinds:
                kinds[b.kind] += 1
        rows.append({
            "index": s.index + 1,
            "title": s.title or f"Slide {s.index + 1}",
            "type": "exercise" if (exercises and emit.is_exercise(s)) else "theory",
            "has_notes": bool(s.notes.strip()),
            "images": len(s.images),
            **kinds,
        })
    return rows

def _count_elements(files: dict[str, object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for rel, content in files.items():
        if not rel.endswith((".scen", ".unit", ".pub")) and rel not in ("meta.xml",):
            if not rel.endswith("meta.xml"):
                continue
        data = content.encode("utf-8") if isinstance(content, str) else content
        try:
            root = etree.fromstring(data)
        except Exception:
            continue
        for el in root.iter():
            if not isinstance(el.tag, str) or "}" not in el.tag:
                continue
            uri, local = el.tag[1:].split("}", 1)
            pfx = _URI2PFX.get(uri)
            if not pfx:
                continue
            key = f"{pfx}:{local}"
            counts[key] = counts.get(key, 0) + 1
    return counts

def scan_batch(input_dir: str, *, course_title: str = "Course", day: str = "Day 1",
               target: str = "basic", exercises: bool = False, make_pub: bool = False) -> dict:
    """Aggregate scan over every supported file in a folder (one session each)."""
    import re
    from pathlib import Path
    exts = (".pptx", ".ppt", ".pdf", ".docx")
    inputs = sorted(p for p in Path(input_dir).iterdir()
                    if p.is_file() and p.suffix.lower() in exts)
    if not inputs:
        raise ValueError(f"No {', '.join(exts)} files in {input_dir}")
    m = re.search(r"\d+", day)
    day_no = m.group() if m else "1"

    slides: list[dict] = []
    el_counts: dict[str, int] = {}
    tot = {"slides": 0, "theory": 0, "exercise": 0, "code_units": 0, "images": 0, "files": 0}
    fid_present = fid_total = 0
    code_ok = wellformed = True
    warnings: list[str] = []
    for i, path in enumerate(inputs, 1):
        r = scan(str(path), course_title=course_title, day=day,
                 session_code=f"{day_no}-{i}", session_name=path.stem,
                 target=target, exercises=exercises, make_pub=make_pub)
        warnings += [f"{path.name}: {w}" for w in r.get("warnings", [])]
        for s in r["slides"]:
            s = dict(s); s["title"] = f"[{path.name}] {s['title']}"
            slides.append(s)
        for e in r["elements"]:
            el_counts[e["element"]] = el_counts.get(e["element"], 0) + e["count"]
        for k in tot:
            tot[k] += r["totals"][k]
        fid_present += r["fidelity"]["present_tokens"]
        fid_total += r["fidelity"]["total_tokens"]
        code_ok = code_ok and r["fidelity"]["code_ok"]
        wellformed = wellformed and r["wellformed"]

    elements = [{"element": k, "count": el_counts[k], "meaning": ELEMENT_LABELS.get(k, "")}
                for k in sorted(el_counts, key=lambda k: (0 if k in ELEMENT_LABELS else 1,
                                                          -el_counts[k], k))]
    return {
        "source": input_dir, "source_type": f"BATCH ({len(inputs)} files)",
        "slides": slides, "totals": tot, "elements": elements,
        "files": [f"{p.name}" for p in inputs],
        "fidelity": {"total_tokens": fid_total, "present_tokens": fid_present,
                     "missing_tokens": [], "code_ok": code_ok, "code_missing": []},
        "wellformed": wellformed, "wellformed_errors": [],
        "warnings": warnings,
    }

def scan(input_path: str, *, course_title: str = "Course", day: str = "Day 1",
         session_code: str = "1-1", session_name: str = "Session",
         target: str = "basic", exercises: bool = False, make_pub: bool = False) -> dict:
    deck = _extract(input_path)
    classify.classify(deck)

    files = emit.build_workspace(deck, course_title, day, session_code, session_name,
                                 target=target, exercises=exercises, make_pub=make_pub)
    counts = _count_elements(files)
    fid = verify.check_fidelity(deck, files)
    wf = verify.check_wellformed(files)

    slides = _slide_plan(deck, exercises)
    n_theory = sum(1 for s in slides if s["type"] == "theory")
    n_exercise = sum(1 for s in slides if s["type"] == "exercise")

    elements = []
    for key in sorted(counts, key=lambda k: (0 if k in ELEMENT_LABELS else 1, -counts[k], k)):
        elements.append({"element": key, "count": counts[key],
                         "meaning": ELEMENT_LABELS.get(key, "")})

    return {
        "source": input_path,
        "source_type": Path(input_path).suffix.lstrip(".").upper(),
        "slides": slides,
        "totals": {
            "slides": len(slides),
            "theory": n_theory,
            "exercise": n_exercise,
            "code_units": counts.get("dk:code", 0),
            "images": len(deck.all_images()),
            "files": len(files),
        },
        "elements": elements,
        "files": sorted(files.keys()),
        "fidelity": {
            "total_tokens": fid["total_tokens"],
            "present_tokens": fid["total_tokens"] - len(fid["missing_tokens"]),
            "missing_tokens": fid["missing_tokens"],
            "code_ok": fid["code_ok"],
            "code_missing": fid["code_missing"],
        },
        "wellformed": not wf,
        "wellformed_errors": wf,
        "warnings": list(deck.warnings),
    }
