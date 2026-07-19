"""Turn the IR into Dokiel XML.

One deck becomes one session: an index .scen, a submodule with the slides as
sp:theory, and dk:code units in Outputs/ and SQL Queries/ for code and SQL.
The XML is built as strings so the Dokiel namespace prefixes stay exactly as
Scenari expects them. Code text is passed through unchanged.
"""

from __future__ import annotations

import re
from xml.sax.saxutils import escape

from .ir import Block, Deck, Segment, Slide

NS = ('xmlns:dk="kelis.fr:dokiel" '
      'xmlns:sc="http://www.utc.fr/ics/scenari/v3/core" '
      'xmlns:sp="http://www.utc.fr/ics/scenari/v3/primitive"')
NS_NK = ('xmlns:dk="kelis.fr:dokiel" '
         'xmlns:sc="http://www.utc.fr/ics/scenari/v3/core"')
HDR = '<?xml version="1.0" encoding="UTF-8"?>\n'
HDR10 = '<?xml version="1.0"?>\n'

DEFAULT_SKIN = "~ECTEG2025MacOS"
DEFAULT_USER = "dokiel-importer"

_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

def _sanitize(t: str) -> str:
    return _ILLEGAL_XML.sub(lambda m: "\n" if m.group() in "\x0b\x0c" else "", t)

def _x(t: str) -> str:
    return escape(_sanitize(t))

def safe(text: str, maxlen: int = 60) -> str:
    s = re.sub(r"[^\w\s\-]", "", text).strip()
    return re.sub(r"\s+", "_", s)[:maxlen] or "untitled"

def _seg_inline(seg: Segment) -> str:
    t = _x(seg.text)
    if seg.kind in ("code", "inline_cmd"):
        return f'<sc:inlineStyle role="cmd">{t}</sc:inlineStyle>'
    if seg.kind == "term":
        return f'<sc:inlineStyle role="term">{t}</sc:inlineStyle>'
    if seg.kind == "path":
        return f'<sc:inlineStyle role="filePath">{t}</sc:inlineStyle>'
    if seg.emphasis:
        return f'<sc:inlineStyle role="emphasis">{t}</sc:inlineStyle>'
    return t

def _para(segs: list[Segment]) -> str:
    inner = "".join(_seg_inline(s) for s in segs)
    return f'<sc:para xml:space="preserve">{inner}</sc:para>'

def _para_text(text: str) -> str:
    return f'<sc:para xml:space="preserve">{_x(text)}</sc:para>'

def _rtitle(text: str) -> str:
    return f'<dk:richTitle>{_para_text(text)}</dk:richTitle>'

def _simplelist(members: list[Segment]) -> str:
    li = "".join(f'<sc:member xml:space="preserve">{_seg_inline(m)}</sc:member>' for m in members)
    return f'<sc:simpleList>{li}</sc:simpleList>'

def _table(rows: list[list[list[Segment]]]) -> str:
    if not rows:
        return ""
    ncol = max(len(r) for r in rows)
    cols = "".join(f'<sc:column width="{100 // ncol}"/>' for _ in range(ncol))
    out = [f'<sc:table role="table">{cols}']
    for i, row in enumerate(rows):
        role = ' role="rowTi"' if i == 0 else ""
        cells = "".join(
            (f"<sc:cell>{_para(cell)}</sc:cell>"
             if "".join(s.text for s in cell).strip() else "<sc:cell/>")
            for cell in row)
        out.append(f'<sc:row{role}>{cells}</sc:row>')
    out.append("</sc:table>")
    return "".join(out)

def _render_type(seg: Segment) -> str:
    if seg.kind in ("code", "inline_cmd"):
        return "cmd"
    if seg.kind == "term":
        return "term"
    if seg.kind == "path":
        return "path"
    return "em" if seg.emphasis else "plain"

def _line_inline(segs: list[Segment]) -> str:
    """Inline rendering of one flow line.

    Adjacent runs of the same render type are merged into one span, so a command
    split across several PPTX runs (e.g. "?" + "d?d?d") becomes a single
    role="cmd" span instead of several. Leading/trailing whitespace is trimmed.
    """
    segs = [Segment(text=s.text, kind=s.kind, emphasis=s.emphasis) for s in segs]
    if segs:
        segs[0].text = segs[0].text.lstrip()
        segs[-1].text = segs[-1].text.rstrip()
    merged: list[list[str]] = []
    for s in segs:
        if not s.text:
            continue
        rt = _render_type(s)
        if merged and merged[-1][0] == rt:
            merged[-1][1] += s.text
        else:
            merged.append([rt, s.text])
    out: list[str] = []
    for rt, text in merged:
        t = _x(text)
        if rt == "cmd":
            out.append(f'<sc:inlineStyle role="cmd">{t}</sc:inlineStyle>')
        elif rt == "term":
            out.append(f'<sc:inlineStyle role="term">{t}</sc:inlineStyle>')
        elif rt == "path":
            out.append(f'<sc:inlineStyle role="filePath">{t}</sc:inlineStyle>')
        elif rt == "em":
            out.append(f'<sc:inlineStyle role="emphasis">{t}</sc:inlineStyle>')
        else:
            out.append(t)
    return "".join(out)

def _nested_list(items: list[tuple[int, list[Segment]]], i: int, level: int) -> tuple[str, int]:
    """Build a (possibly nested) itemizedList from (level, segments) lines."""
    parts: list[str] = []
    while i < len(items):
        lvl, segs = items[i]
        if lvl < level:
            break
        if lvl > level:
            child, i = _nested_list(items, i, level + 1)
            if parts:
                parts[-1] = parts[-1][:-len("</sc:listItem>")] + child + "</sc:listItem>"
            else:
                parts.append(f"<sc:listItem>{child}</sc:listItem>")
            continue
        content = f'<sc:para xml:space="preserve">{_line_inline(segs)}</sc:para>'
        i += 1
        child, i = _nested_list(items, i, level + 1)
        parts.append(f"<sc:listItem>{content}{child}</sc:listItem>")
    xml = f'<sc:itemizedList>{"".join(parts)}</sc:itemizedList>' if parts else ""
    return xml, i

def _flow(lines: list[tuple[int, list[Segment]]]) -> str:
    """One source text frame -> one infobloc. Flat frames use simpleList, nested
    frames use a nested itemizedList; commands render inline as role="cmd"."""
    if not lines:
        return ""
    if all(lvl == 0 for lvl, _ in lines):
        if len(lines) == 1:
            return _infobloc(f'<sc:para xml:space="preserve">{_line_inline(lines[0][1])}</sc:para>')
        members = "".join(f'<sc:member xml:space="preserve">{_line_inline(segs)}</sc:member>'
                          for _, segs in lines)
        return _infobloc(f"<sc:simpleList>{members}</sc:simpleList>")
    xml, _ = _nested_list(lines, 0, 0)
    return _infobloc(xml)

def _extblock(ref: str) -> str:
    return f'<sc:extBlock role="fig" sc:refUri="{_x(ref)}"/>'

def _infobloc(inner: str) -> str:
    return (f'<sp:infobloc><dk:blocTi/>'
            f'<dk:flowAll><sp:txt><dk:text>{inner}</dk:text></sp:txt></dk:flowAll>'
            f'</sp:infobloc>')

def code_unit(content: str, mime: str = "text/plain") -> str:
    return (HDR10 + f'<sc:item {NS_NK}>'
            f'<dk:code><dk:codeM/>'
            f'<sc:code mimeType="{mime}" xml:space="preserve">{_x(content)}</sc:code>'
            f'</dk:code></sc:item>')

def image_meta(alt: str) -> str:
    return (HDR + '<sfm:image version="1" '
            'xmlns:dk="kelis.fr:dokiel" '
            'xmlns:sc="http://www.utc.fr/ics/scenari/v3/core" '
            'xmlns:sfm="http://www.utc.fr/ics/scenari/v3/filemeta" '
            'xmlns:sp="http://www.utc.fr/ics/scenari/v3/primitive">'
            f'<dk:imageM><sp:title>{_rtitle(alt)}</sp:title>'
            '<sp:accessibility/></dk:imageM></sfm:image>')

def _train_note(notes: str) -> str:
    if not notes.strip():
        return ""
    note_blk = (f'<sp:note><dk:blocTi><sp:rTitle>{_rtitle("Notes")}</sp:rTitle></dk:blocTi>'
                f'<dk:flowAll><sp:txt><dk:text>{_para_text(notes)}</dk:text></sp:txt></dk:flowAll>'
                f'</sp:note>')
    return (f'<sp:trainNote><dk:trainNote><dk:trainNoteM/>'
            f'<sp:note><dk:comment>{note_blk}</dk:comment></sp:note>'
            f'</dk:trainNote></sp:trainNote>')

_EXERCISE_RE = re.compile(r"\b(exercise|task|practical)\b", re.I)

def is_exercise(slide: Slide) -> bool:
    return bool(_EXERCISE_RE.search(slide.title or ""))

def _content_xml(slide: Slide, code_refs: dict[int, str]) -> str:
    """Blocks of a slide as ordered Dokiel content (shared by theory & exercise).

    Order is preserved exactly. Prose, code and images stay in source order, so
    an exercise's instructions and commands are never reshuffled.
    """
    parts: list[str] = []
    for b in slide.blocks:
        if b.kind == "flow":
            parts.append(_flow(b.lines))
        elif b.kind == "para":
            parts.append(_infobloc(_para(b.segments)))
        elif b.kind == "list":
            parts.append(_infobloc(_simplelist(b.segments)))
        elif b.kind == "olist":
            li = "".join(f'<sc:listItem>{_para([s])}</sc:listItem>' for s in b.segments)
            parts.append(_infobloc(f'<sc:orderedList>{li}</sc:orderedList>'))
        elif b.kind == "table":
            parts.append(_infobloc(_table(b.rows)))
        elif b.kind == "code":
            ref = code_refs.get(id(b))
            if ref:
                parts.append(_infobloc(_extblock(ref)))
    for img in slide.images:
        parts.append(_infobloc(_extblock(f"Resources/{img.filename}")))
    body = "".join(parts)
    if body:
        return body
    return _infobloc(_para_text(slide.title)) if (slide.title or "").strip() else ""

def _theory_core(slide: Slide, code_refs: dict[int, str]) -> str:
    title = slide.title or f"Slide {slide.index + 1}"
    return (f'<dk:theory><dk:theoryM><sp:title>{_rtitle(title)}</sp:title></dk:theoryM>'
            f'{_train_note(slide.notes)}'
            f'<sp:content><dk:content>{_content_xml(slide, code_refs)}</dk:content></sp:content>'
            f'</dk:theory>')

def _exercise_core(slide: Slide, code_refs: dict[int, str]) -> str:
    """Exercise: the whole slide, in order, becomes the exposition.

    No solution is synthesised. The source does not delineate one, and inventing
    or reordering content would break fidelity.
    """
    title = slide.title or f"Exercise {slide.index + 1}"
    return (f'<dk:exercise><dk:exerciseM><sp:title>{_rtitle(title)}</sp:title></dk:exerciseM>'
            f'{_train_note(slide.notes)}'
            f'<sp:exposition><dk:content>{_content_xml(slide, code_refs)}</dk:content></sp:exposition>'
            f'</dk:exercise>')

def _slide_core(slide: Slide, code_refs: dict[int, str], exercises: bool) -> tuple[str, str]:
    """Return (wrapper_tag, core_xml); wrapper is 'theory' or 'exercise'."""
    if exercises and is_exercise(slide):
        return "exercise", _exercise_core(slide, code_refs)
    return "theory", _theory_core(slide, code_refs)

def build_session(deck: Deck, day: str, session_code: str, session_name: str,
                  target: str = "basic", exercises: bool = False,
                  make_pub: bool = False) -> dict[str, object]:
    """Session-scoped files only (no .wspmeta/.wsporigin). Keys are relative to
    the workspace root, so several sessions can be merged into one workspace.

    target: "basic"    -> one submodule .scen with all slides inline
            "advanced" -> one .unit per slide, referenced from the index
    make_pub: also emit a dk:trainingRoot .pub publication descriptor
    """
    files: dict[str, object] = {}
    sess_folder = f"{session_code} - {safe(session_name)}"
    base = f"{day}/{sess_folder}"

    code_refs: dict[int, str] = {}
    code_n = sql_n = 0
    for slide in deck.slides:
        for b in slide.blocks:
            if b.kind != "code":
                continue
            if b.mime == "text/x-sql":
                sql_n += 1
                fname = f"SQL-{session_code}_{sql_n}.unit"
                files[f"{base}/SQL Queries/{fname}"] = code_unit(b.text(), "text/x-sql")
                code_refs[id(b)] = f"SQL Queries/{fname}"
            else:
                code_n += 1
                fname = f"{session_code}-cmd{code_n}.unit"
                files[f"{base}/Outputs/{fname}"] = code_unit(b.text(), "text/plain")
                code_refs[id(b)] = f"Outputs/{fname}"

    for img in deck.all_images():
        d = f"{base}/Resources/{img.filename}"
        files[f"{d}/{img.filename}"] = img.data
        files[f"{d}/meta.xml"] = image_meta(img.alt or img.filename.rsplit(".", 1)[0])

    sub_name = safe(session_name)
    index_fname = f"{session_code}-{sub_name}.scen"

    if target == "advanced":
        refs: list[str] = []
        for p, slide in enumerate(deck.slides):
            tag, core = _slide_core(slide, code_refs, exercises)
            uname = f"{session_code}-{p}-{safe(slide.title or f'slide{p}')}.unit"
            files[f"{base}/{uname}"] = HDR + f'<sc:item {NS}>{core}</sc:item>'
            refs.append(f'<sp:{tag} sc:refUri="{_x(uname)}"/>')
        body = "".join(refs)
    else:
        slides_xml = "".join(
            f'<sp:{tag}>{core}</sp:{tag}>'
            for tag, core in (_slide_core(s, code_refs, exercises) for s in deck.slides)
        )
        sub_fname = f"{session_code}-0-{sub_name}.scen"
        module = (f'<dk:module><dk:moduleM><sp:title>{_rtitle(session_name)}</sp:title></dk:moduleM>'
                  f'{slides_xml}</dk:module>')
        files[f"{base}/{sub_fname}"] = HDR + f'<sc:item {NS}>{module}</sc:item>'
        body = f'<sp:subModule sc:refUri="{_x(sub_fname)}"/>'

    files[f"{base}/{index_fname}"] = _session_index(session_code, session_name, body)

    if make_pub:
        files[f"{day}/{session_code}-{sub_name}.pub"] = _pub(sess_folder, index_fname)

    return files

def workspace_meta(course_title: str, days: list[str]) -> dict[str, object]:
    """The workspace-level metadata files, listing every Day root."""
    return {".wspmeta": _wspmeta(course_title), ".wsporigin": _wsporigin(days)}

def build_workspace(deck: Deck, course_title: str, day: str,
                    session_code: str, session_name: str,
                    target: str = "basic", exercises: bool = False,
                    make_pub: bool = False) -> dict[str, object]:
    """Single-session workspace = one session + workspace metadata."""
    files = build_session(deck, day, session_code, session_name,
                          target=target, exercises=exercises, make_pub=make_pub)
    files.update(workspace_meta(course_title, [day]))
    return files

def _advice(title: str, inner: str) -> str:
    return (f'<sp:advice><dk:blocTi><sp:rTitle>{_rtitle(title)}</sp:rTitle></dk:blocTi>'
            f'<dk:flowAll><sp:txt><dk:text>{inner}</dk:text></sp:txt></dk:flowAll></sp:advice>')

def _session_index(session_code: str, session_name: str, body: str) -> str:
    """body = subModule ref (basic) or a run of sp:theory/sp:exercise refs (advanced)."""
    train = ('<sp:trainNote><dk:trainNote>'
             f'<dk:trainNoteM><sp:title>Trainer\'s Notes: {_x(session_name)}</sp:title>'
             '<sp:time>[to be completed]</sp:time></dk:trainNoteM>'
             '<sp:note><dk:comment>'
             + _advice("Session Overview", _para_text(f"This session covers {session_name}."))
             + '</dk:comment></sp:note>'
             '</dk:trainNote></sp:trainNote>')
    start = ('<sp:start><dk:startTrain><dk:rTitle/>'
             f'<sp:agenda><dk:blocTi><sp:rTitle>{_rtitle("Duration")}</sp:rTitle></dk:blocTi>'
             f'<dk:flowAll><sp:txt><dk:text>{_para_text("[to be completed]")}</dk:text></sp:txt></dk:flowAll></sp:agenda>'
             f'<sp:objectives><dk:blocTi><sp:rTitle>{_rtitle("Learning Objectives")}</sp:rTitle></dk:blocTi>'
             f'<dk:flowAll><sp:txt><dk:text>{_para_text("[to be completed (not present in source)]")}</dk:text></sp:txt></dk:flowAll></sp:objectives>'
             '</dk:startTrain></sp:start>')
    synth = ('<sp:synthesis><dk:rTitle/><dk:content>'
             + _infobloc(_para_text(f"This concludes the session: {session_name}."))
             + '</dk:content></sp:synthesis>')
    module = (f'<dk:module><dk:moduleM><sp:title>{_rtitle(f"{session_code}: {session_name}")}</sp:title></dk:moduleM>'
              f'{train}{start}{body}{synth}</dk:module>')
    return HDR + f'<sc:item {NS}>{module}</sc:item>'

def _pub(sess_folder: str, index_fname: str) -> str:
    """Minimal web-training publication descriptor (dk:trainingRoot)."""
    ref = f"{sess_folder}/{index_fname}"
    return (HDR + f'<sc:item version="1" {NS}>'
            '<dk:trainingRoot><dk:trainingRootM><sp:info><dk:rootM/></sp:info>'
            '<sp:settingsTrainer/></dk:trainingRootM>'
            f'<sp:module sc:refUri="{_x(ref)}"/></dk:trainingRoot></sc:item>')

def _wspmeta(course_title: str) -> str:
    return (f'<wspMeta><title>{_x(course_title)}</title>'
            '<wspType key="dokiel" version="25.0.6" lang="en-US" '
            'uri="dokiel_en-US_25-0-6" title="Dokiel 25">'
            '<wspOption key="dokielRefDoc" version="25.0.6" lang="en-US" '
            'uri="dokielRefDoc_en-US_25-0-6" title="Dokiel – reference documentation 25"/>'
            '<wspOption key="dokielTraining" version="25.0.6" lang="en-US" '
            'uri="dokielTraining_en-US_25-0-6" title="Dokiel – Training 25"/>'
            f'</wspType><skin>white</skin><skin>{DEFAULT_SKIN}</skin>'
            '<feature>extIt</feature></wspMeta>')

def _wsporigin(days: list[str]) -> str:
    import uuid
    code = uuid.uuid4().hex[:22]
    roots = "".join(
        f'<root srcUri="/{_x(d)}" srcId="id:{uuid.uuid4().hex[:22]}"/>'
        for d in dict.fromkeys(days)
    )
    return (HDR + '<wspOrigin scChainUrl="https://scenari.local/'
            'scenarichain-server/~~chain" '
            f'wspCode="{code}" user="{DEFAULT_USER}" timestamp="0">'
            f'{roots}</wspOrigin>')
