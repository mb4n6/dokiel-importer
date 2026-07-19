# dokiel-importer

This tool converts existing slide decks and documents (PowerPoint, PDF, Word) into a Scenari/Dokiel workspace. The content is carried over unchanged: commands, hashes, output and source code stay byte-for-byte. A language model is used only for translation, never to rephrase, shorten or reorder.

The Scenari authoring API is not available. The workspace is therefore produced as Dokiel XML on disk and imported through the desktop application. The document model and skin are set automatically in the `.wspmeta` to match the target Scenari instance (see `DEFAULT_SKIN` in `converter/emit.py`).

Inputs are PPTX (preferred, because slide, note and font information are kept), PDF (a lossy fallback) and DOCX (headings become slides).

## Installation

```bash
pip install -r requirements.txt          # macOS system Python: add --break-system-packages
```

Translation needs a local [Ollama](https://ollama.com):

```bash
ollama serve && ollama pull gemma4:latest
```

## Usage

Graphical interface:

```bash
python3 -m converter.gui
```

The interface has four areas: an overview with key figures and the table of the Dokiel elements that will be produced, the slide plan (type and block breakdown per slide), the list of files that will be written, and a log. The scan is a dry run and writes nothing. The conversion produces the workspace together with the `.scwsp` archive.

Command line, single file:

```bash
python3 -m converter.cli deck.pptx out/ \
    --course-title "Mac Advanced" --day "Day 3" \
    --session-code 3-1 --session-name "Hashcat Results"
```

Advanced pattern (one `.unit` per slide), with exercises and a publication descriptor:

```bash
python3 -m converter.cli deck.pptx out/ \
    --session-name "Hashcat Results" --target advanced --exercises --pub
```

Translation of a German source (needs Ollama), prose only, commands stay verbatim:

```bash
python3 -m converter.cli input.pdf out/ --translate --source-lang de
```

Batch mode: a folder of `.pptx`/`.pdf`/`.docx` becomes one workspace (one session per file):

```bash
python3 -m converter.cli slides/ out/ --batch --course-title "Mac Advanced" --day "Day 3"
```

The folder `out/<Course>/` holds the Dokiel source structure, `out/<Course>.scwsp` the import archive. Import it through *Workspaces ▸ Import a workspace…* in SCENARIchain-desktop or MyScenari.

## Self-test

The self-test runs the whole pipeline over a single file or a whole folder without writing anything, and checks per file: XML well-formedness, per-segment fidelity, byte-exact code blocks, no empty mandatory fields, no dangling references, source coverage for PPTX, and the element vocabulary:

```bash
python3 -m converter.selftest folder/            # recurse a folder
```

The exit code is 0 when every file is clean. The broadest run so far, over 137 mixed PPTX/PDF/DOCX files, passed with two visible warnings.

## Fidelity

Every run checks XML well-formedness and asserts that each source segment appears in the result and that each code block is carried over byte-for-byte. On a 19-slide reference deck that is full coverage, code byte-exact, without an element outside the known Dokiel vocabulary. One source slide becomes one content box: nested lists keep their levels, commands appear inline in monospace, and only multi-line code blocks become a code figure.

## Known limitations

What `python-pptx` cannot read is reported rather than dropped silently:

- SmartArt and diagrams: the text is imported flat (the layout is lost), with a warning.
- Charts: title, category labels and series names only.
- Embedded video/audio: not imported, with a warning.
- Reading order: document order of the shapes, not the visual position (multi-column slides may reorder).
- Command detection: a run is treated as a command (`role="cmd"`) when its font is monospace or when it is painted in a configured theme colour (`CMD_SCHEME_COLORS` in `converter/extract_pptx.py`, default `tx2`/`dk2`). Commands in an unknown font and default colour render as plain text (content complete, only not styled).
- PDF stays lossy. When both exist, use the `.pptx`.

## Options

| Option | Default | Meaning |
|---|---|---|
| `--course-title` | file name | workspace title |
| `--day` | `Day 1` | day folder |
| `--session-code` | `1-1` | session prefix |
| `--session-name` | file name | session name |
| `--target` | `basic` | `basic` (inline) or `advanced` (one `.unit` per slide) |
| `--exercises` | off | slides with an exercise title become `dk:exercise` (exposition only, order kept) |
| `--pub` | off | also produce a `dk:trainingRoot` publication descriptor |
| `--batch` | off | input is a folder (one session per file) |
| `--commands` | `auto` | command detection: `auto` (colour if the deck uses it, else font), `color`, `font`, `both` |
| `--terms` | off | mark monospace text in the default colour as term (`role="term"`) |
| `--reading-order` | `document` | `document` keeps the file order; `position` sorts shapes top-to-bottom, left-to-right |
| `--translate` | off | translate prose to English (needs Ollama) |
| `--source-lang` | `de` | source language for translation |
| `--model` / `--host` | `gemma4:latest` / localhost | Ollama model and host |
| `--no-scwsp` | off | write only the source folder, no `.scwsp` |

## Layout

| Path | Content |
|---|---|
| `converter/ir.py` | intermediate representation (Deck, Slide, Block, Segment) |
| `converter/extract_pptx.py` | PPTX into the IR (runs/fonts, notes, groups, tables, SmartArt, images) |
| `converter/extract_pdf.py` | PDF into the IR (dict mode, lossy fallback) |
| `converter/extract_docx.py` | DOCX into the IR (headings to slides, lists, tables) |
| `converter/classify.py` | deterministic split of prose and code |
| `converter/translate.py` | optional, guarded translation via local Ollama (prose only) |
| `converter/emit.py` | IR to Dokiel XML (basic/advanced, `sp:theory`, `dk:exercise`, `dk:code`, `.pub`) |
| `converter/package.py` | write source folder and `.scwsp` |
| `converter/verify.py` | well-formedness and fidelity |
| `converter/plan.py` | dry run with slide plan and element usage (drives the GUI) |
| `converter/gui.py` | Tkinter interface |
| `converter/selftest.py` | self-test over many files |
| `Scenari_Dokiel_Authoring_Guide.md` | reference for the Dokiel XML structure, verified against real exports |

## Requirements

Python 3.10 or newer plus `python-pptx`, `python-docx`, `PyMuPDF` and `lxml`. Translation needs Ollama. Details in `requirements.txt`.

## Acknowledgements

Two parts were improved after feedback from an author in Italy who wrote a companion tool for the same slides. Her colour convention for marking commands (theme colour `tx2`) now drives the command detection, and her title handling fixed the reading of wrapped slide titles.
