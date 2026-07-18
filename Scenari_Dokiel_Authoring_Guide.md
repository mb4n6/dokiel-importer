# Scenari / Dokiel Authoring Guide

## Reference standard, Dokiel 25.0.6

This guide describes the XML structure of Dokiel content as used in real Scenari/Dokiel courses and the course skeleton. Every example is verified against those
exports. Sections marked **present in the model, not used in the reference exports** describe Dokiel
components that exist but are currently unused in the reference courses; their markup is described there
conceptually, and such an item should be authored once in the tool and exported before it is relied
on.

---

## 1. Overview

Scenari is an open-source platform for structured authoring. **Dokiel** is the schema for e-learning
and documentation built on top of it (a *document model*, `wsppack`). All content is stored as XML
files with the extensions `.scen`, `.unit`, or `.pub`. Scenari uses a workspace model: a folder tree
on disk that the desktop application or the server reads and publishes to HTML, SCORM, or PDF.

The reference courses use Dokiel version **25.0.6** with a project-specific skin and the English locale
(`en-US`).

### 1.1 Two authoring patterns

The two reference courses are built differently. A converter or author has to know which pattern applies:

| | **Inline pattern** (Mac Basic) | **Reference pattern** (Mac Advanced) |
|---|---|---|
| Session index | `N-M-Name.scen` = `dk:module` | `N-M-Name.scen` = `dk:module` |
| Location of slides | **inside** the submodule `.scen` | in **separate `.unit` files**, one item each |
| Slide attachment | `<sp:subModule sc:refUri="…​.scen"/>` to a submodule `.scen` with inline `<sp:theory>` | `<sp:theory sc:refUri="…​.unit"/>`, `<sp:exercise sc:refUri="…​.unit"/>`, `<sp:part sc:refUri="…​.unit"/>` directly in the index |
| Publication | training module | training module plus `.pub` web/training publication |

The basic rule: `sp:theory`, `sp:exercise`, and `sp:part` can either **contain** their content or
**reference** an external `.unit` through `sc:refUri`. Both are valid. A `.unit` therefore holds not
only code or SQL; in the Advanced course it holds every slide.

### 1.2 How content reaches Scenari (import)

A loose folder does not become a course on its own, and the Scenari chain-server API is not available.
The supported routes are:

1. **Import a workspace**: the workspace is packaged as a **`.scwsp`** archive (a ZIP of the whole
   content tree including `.wspmeta`) and read in through *Workspaces ▸ Import a workspace…* in
   SCENARIchain-desktop or MyScenari. This creates a new workspace.
2. **Import an archive**: a **`.scar`** archive (a *fragment*: one item, an item network, or a loose
   set) through *WorkspaceName ▾ ▸ Content ▸ Import an archive…* into an **existing** workspace, with
   three modes (new sub-space, direct non-destructive import, direct import with replacement).
3. **Placement in the source folder**: a correctly formed source folder is placed directly into the
   desktop application's source store (the exported folder has exactly this form).

The hard condition is **model compatibility**: the document model of the target workspace must match
the source. The `.wspmeta` therefore has to be reproduced exactly (Dokiel **25.0.6**, the project skin,
`en-US`), otherwise Scenari warns with *"content may not be usable, readable"* and
forces a migration.

On `.scar`: a `.scar` carries the internal **code or ID** of each item in its manifest ("items have
the same code and are stored at the same place"). A hand-written `.scar` manifest is correspondingly
error-prone. For a whole course the **`.scwsp`** or source-folder route is preferable, since it only
reproduces the known content tree.

> Automated generation exists (SCENARIbatch or the SCENARIserver batch API, the `scenari/lti-suite`
> Docker image), but it requires server access that is not available here. For offline authoring it
> stays out of scope.

---

## 2. XML namespaces

Every `.scen`, `.unit`, and `.pub` file uses three namespaces:

```xml
xmlns:dk="kelis.fr:dokiel"
xmlns:sc="http://www.utc.fr/ics/scenari/v3/core"
xmlns:sp="http://www.utc.fr/ics/scenari/v3/primitive"
```

A resource `meta.xml` additionally uses `sfm` and a **type-specific root element**:

| Resource | Root element | Metadata block |
|---|---|---|
| Image (PNG/JPG/GIF/SVG) | `<sfm:image>` | `<dk:imageM>` |
| Video / audio (MP4, podcast) | `<sfm:video>` | `<dk:mediaM>` |

```xml
xmlns:sfm="http://www.utc.fr/ics/scenari/v3/filemeta"
```

Every `.scen` file begins with:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<sc:item xmlns:dk="kelis.fr:dokiel"
         xmlns:sc="http://www.utc.fr/ics/scenari/v3/core"
         xmlns:sp="http://www.utc.fr/ics/scenari/v3/primitive">
  ...
</sc:item>
```

`.unit` files use the same `sc:item` root and the same namespaces.

---

## 3. Workspace layout

```
WorkspaceRoot/
├── .wspmeta                          Metadata (title, model, skin)
├── .wsporigin                        Root declarations + Scenari server configuration
├── &/                                Shared resource POOL (logos, EU funding banner, …),
│                                     referenced as "../&/file.png"
├── Day 0 - Online Module/
│   ├── 0-1 - Session Name/
│   │   ├── 0-1-Session Name.scen     Session index (dk:module: notes + submodule refs)
│   │   ├── 0-1-0-Intro.scen          Inline submodule (Basic) …
│   │   ├── 0-1-1-Theory.unit         … or standalone item unit (Advanced)
│   │   ├── 0-1-2-Exercises.scen
│   │   ├── Resources/                Images / videos, each in its own subfolder
│   │   │   ├── diagram.png/
│   │   │   │   ├── diagram.png
│   │   │   │   └── meta.xml           (sfm:image)
│   │   │   └── demo.mp4/
│   │   │       ├── demo.mp4
│   │   │       └── meta.xml           (sfm:video)
│   │   ├── Outputs/                  Command-line / tool output as .unit
│   │   ├── SQL Queries/             SQL queries as .unit (separate from Outputs/)
│   │   ├── Podcast/                  Audio resources (Advanced)
│   │   └── Export Versions/         Author's local publication output, NOT content
│   └── 0-2 - Another Session/
├── Day 1/ … Day 5/
└── N-M-Name.pub                      Publication descriptor(s), see §17 (Advanced)
```

**Naming conventions:**
- Day folders: `Day N` or `Day N - Label`
- Session folders: `N-M - Session Name`
- Session index: `N-M-Session Name.scen`
- Submodule/unit files: `N-M-P-Name.{scen|unit}`, P is `0,1,2,…`; gaps (0, 2, 4) are valid
- Output units: `N-M-P-desc_output.unit` in `Outputs/`
- SQL units: `SQL-N-M_0.unit` in `SQL Queries/`

> **Pool folder `&`**: Scenari stores workspace-wide resources in a folder named `&`. Content
> references them relatively, for example `sc:refUri="../&/logo.png"` (XML-escaped as
> `../&amp;/…`). The logo and the EU banner belong here.
>
> `Export Versions/` and the output produced by `.pub` are **not source content** and are not fed
> back as items.

---

## 4. Workspace metadata files

### .wspmeta

Plain XML (no XML declaration). Defines model version, skin, and features. Reproduce it **verbatim**
for import compatibility:

```xml
<wspMeta>
  <title>Course Title</title>
  <wspType key="dokiel" version="25.0.6" lang="en-US"
           uri="dokiel_en-US_25-0-6" title="Dokiel 25">
    <wspOption key="dokielRefDoc" version="25.0.6" lang="en-US"
               uri="dokielRefDoc_en-US_25-0-6"
               title="Dokiel – reference documentation 25"/>
    <wspOption key="dokielTraining" version="25.0.6" lang="en-US"
               uri="dokielTraining_en-US_25-0-6"
               title="Dokiel – Training 25"/>
  </wspType>
  <skin>white</skin>
  <skin>~YourSkin</skin>
  <feature>extIt</feature>
</wspMeta>
```

### .wsporigin

Registers the workspace with the chain server and declares the root folders (the days). `wspCode` and
`srcId` are identifiers assigned by the server; offline any unique string works. Example:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<wspOrigin scChainUrl="https://scenari.local/scenarichain-server/~~chain"
           wspCode="qoV5enuDzfunK69M2vo3rw" user="AuthorName" timestamp="0">
  <root srcUri="/Day 0 - Online Module" srcId="id:…"/>
  <root srcUri="/Day 1" srcId="id:…"/>
  ...
</wspOrigin>
```

---

## 5. Item types at a glance

| `sp:` wrapper | `dk:` item | Purpose | Used |
|---|---|---|---|
| `sp:module` / `sp:subModule` | `dk:module` | course/session container, ordered slide list | yes, both |
| `sp:part` | `dk:part` | titled content section (lighter than a module) | yes, Advanced |
| `sp:theory` | `dk:theory` | content slide (explanation, media, tables, code) | yes, both (the default) |
| `sp:exercise` | `dk:exercise` | hands-on task with a hidden solution | yes, Advanced and parts of Basic |
| *(step list)* | `dk:stepList` / `dk:step` | numbered procedure or walkthrough | yes, Basic |
| *(screen)* | `dk:screen` | annotated image with clickable zones | yes, both (rare) |
| *(code)* | `dk:code` | verbatim code or terminal output | yes, both |
| *(media meta)* | `sfm:image` / `sfm:video` | resource metadata | yes, both |
| *(publication)* | `dk:trainingRoot` / `dk:tutorialRoot` | `.pub` output descriptor | yes, Advanced |

`sp:theory`, `sp:exercise`, and `sp:part` appear **inline** (with a contained `dk:…` item) or as a
**reference** (`sc:refUri="file.unit"`, empty element).

---

## 6. Session index (`dk:module`)

One per session folder, named `N-M-Session Name.scen`. It contains the trainer notes, an
`<sp:start>` block (duration and objectives), and the ordered slide list. Slides attach **either** as
`sp:subModule` references to neighbouring `.scen` (Basic) **or** as `sp:theory`/`sp:exercise`/`sp:part`
included inline or through `refUri` (Advanced).

```xml
<?xml version="1.0" encoding="UTF-8"?>
<sc:item xmlns:dk="kelis.fr:dokiel"
         xmlns:sc="http://www.utc.fr/ics/scenari/v3/core"
         xmlns:sp="http://www.utc.fr/ics/scenari/v3/primitive">
  <dk:module>
    <dk:moduleM>
      <sp:title><dk:richTitle><sc:para xml:space="preserve">2-4: File Types</sc:para></dk:richTitle></sp:title>
    </dk:moduleM>

    <sp:trainNote>
      <dk:trainNote>
        <dk:trainNoteM>
          <sp:title>Trainer's Notes: File Types</sp:title>
          <sp:time>90 minutes</sp:time>
        </dk:trainNoteM>
        <sp:note><dk:comment>
          <sp:advice>
            <dk:blocTi><sp:rTitle><dk:richTitle><sc:para xml:space="preserve">Session Overview</sc:para></dk:richTitle></sp:rTitle></dk:blocTi>
            <dk:flowAll><sp:txt><dk:text><sc:para xml:space="preserve">Describe the session purpose.</sc:para></dk:text></sp:txt></dk:flowAll>
          </sp:advice>
        </dk:comment></sp:note>
      </dk:trainNote>
    </sp:trainNote>

    <sp:start>
      <dk:startTrain>
        <dk:rTitle/>
        <sp:agenda>
          <dk:blocTi><sp:rTitle><dk:richTitle><sc:para xml:space="preserve">Duration</sc:para></dk:richTitle></sp:rTitle></dk:blocTi>
          <dk:flowAll><sp:txt><dk:text><sc:para xml:space="preserve">90 minutes</sc:para></dk:text></sp:txt></dk:flowAll>
        </sp:agenda>
        <sp:objectives>
          <dk:blocTi><sp:rTitle><dk:richTitle><sc:para xml:space="preserve">Learning Objectives</sc:para></dk:richTitle></sp:rTitle></dk:blocTi>
          <dk:flowAll><sp:txt><dk:text>
            <sc:itemizedList>
              <sc:listItem><sc:para xml:space="preserve">Understand plist file formats</sc:para></sc:listItem>
              <sc:listItem><sc:para xml:space="preserve">Query SQLite databases</sc:para></sc:listItem>
            </sc:itemizedList>
          </dk:text></sp:txt></dk:flowAll>
        </sp:objectives>
      </dk:startTrain>
    </sp:start>

    <!-- Basic pattern: references to neighbouring submodule .scen -->
    <sp:subModule sc:refUri="2-4-0-Plist Theory.scen"/>
    <sp:subModule sc:refUri="2-4-1-Plist Exercises.scen"/>

    <!-- Advanced pattern (alternative): each slide an external .unit -->
    <!-- <sp:theory   sc:refUri="advanced-sqlite.unit"/>            -->
    <!-- <sp:exercise sc:refUri="2-3-4-skype_2.unit"/>              -->
    <!-- <sp:part     sc:refUri="2-1-3-relational-databases.unit"/> -->

    <!-- optional session closing (see §12) -->
    <sp:synthesis>
      <dk:rTitle/>
      <dk:content>
        <sp:infobloc><dk:blocTi/><dk:flowAll><sp:txt><dk:text>
          <sc:para xml:space="preserve">This concludes the session on File Types.</sc:para>
        </dk:text></sp:txt></dk:flowAll></sp:infobloc>
      </dk:content>
    </sp:synthesis>
  </dk:module>
</sc:item>
```

A submodule `.scen` (Basic) has the same `sc:item` → `dk:module` wrapper and contains one or more
`<sp:theory>` or `<sp:exercise>` slides.

---

## 7. Theory slide (`sp:theory` / `dk:theory`)

The default case: delivering content through explanations, diagrams, tables, code. Structure: title,
optional trainer note, `sp:content`.

```xml
<sp:theory>
  <dk:theory>
    <dk:theoryM>
      <sp:title><dk:richTitle><sc:para xml:space="preserve">Slide Title</sc:para></dk:richTitle></sp:title>
    </dk:theoryM>
    <sp:trainNote>
      <dk:trainNote>
        <dk:trainNoteM/>
        <sp:note><dk:comment>
          <sp:advice>
            <dk:blocTi><sp:rTitle><dk:richTitle><sc:para xml:space="preserve">Key Talking Points</sc:para></dk:richTitle></sp:rTitle></dk:blocTi>
            <dk:flowAll><sp:txt><dk:text>
              <sc:simpleList>
                <sc:member xml:space="preserve">Point 1</sc:member>
              </sc:simpleList>
            </dk:text></sp:txt></dk:flowAll>
          </sp:advice>
        </dk:comment></sp:note>
      </dk:trainNote>
    </sp:trainNote>
    <sp:content>
      <dk:content>
        <!-- block elements (§13) -->
      </dk:content>
    </sp:content>
  </dk:theory>
</sp:theory>
```

> Style note: inside `dk:text`, the reference courses use `<sc:simpleList>`/`<sc:member>` (a flat list) far
> more often than `<sc:itemizedList>`/`<sc:listItem>`, roughly by a factor of 30:1. For simple lists
> prefer `simpleList`; reserve `itemizedList` for lists with sub-lists or multi-paragraph items.

---

## 8. Exercise slide (`sp:exercise` / `dk:exercise`)

The real structure (verified against `2-3-4-skype_2.unit`). An exercise has a **title**, an
optional **trainer note**, an **`sp:exposition`** (the task statement), and one or more
**`sp:exerciseQ`** question-and-answer pairs, each with `sp:desc` (the question) and `sp:solution`.
An overall `sp:solution` may appear in addition.

```xml
<sc:item xmlns:dk="kelis.fr:dokiel"
         xmlns:sc="http://www.utc.fr/ics/scenari/v3/core"
         xmlns:sp="http://www.utc.fr/ics/scenari/v3/primitive">
  <dk:exercise>
    <dk:exerciseM>
      <sp:title><dk:richTitle><sc:para xml:space="preserve">Parsing the SkypeContent.json</sc:para></dk:richTitle></sp:title>
    </dk:exerciseM>

    <!-- optional: <sp:trainNote>…</sp:trainNote> (same form as elsewhere) -->

    <sp:exposition>
      <dk:content>
        <sp:infobloc>
          <dk:blocTi><sp:rTitle><dk:richTitle><sc:para xml:space="preserve">Find skype names and cids</sc:para></dk:richTitle></sp:rTitle></dk:blocTi>
          <dk:flowAll><sp:txt><dk:text>
            <sc:itemizedList>
              <sc:listItem><sc:para xml:space="preserve">Open the file <sc:inlineStyle role="filePath">~/Desktop/SkypeContent.json</sc:inlineStyle> with Sublime Text.</sc:para></sc:listItem>
            </sc:itemizedList>
            <sc:para xml:space="preserve">Find Paul's skype name and cid?</sc:para>
          </dk:text></sp:txt></dk:flowAll>
        </sp:infobloc>
      </dk:content>
    </sp:exposition>

    <sp:exerciseQ>
      <dk:exerciseQ>
        <sp:desc>
          <dk:para><sc:para xml:space="preserve">Find skype names and cids</sc:para></dk:para>
        </sp:desc>
        <sp:solution>
          <dk:content>
            <sp:infobloc>
              <dk:blocTi><sp:rTitle><dk:richTitle><sc:para xml:space="preserve">Solution</sc:para></dk:richTitle></sp:rTitle></dk:blocTi>
              <dk:flowAll><sp:txt><dk:text>
                <sc:para xml:space="preserve">&quot;displayNameOverride&quot;: &quot;Paul&quot;,</sc:para>
                <sc:para xml:space="preserve">&quot;mri&quot;: &quot;8:live:.cid.6b24f630371f001d&quot;,</sc:para>
              </dk:text></sp:txt></dk:flowAll>
            </sp:infobloc>
          </dk:content>
        </sp:solution>
      </dk:exerciseQ>
    </sp:exerciseQ>
  </dk:exercise>
</sc:item>
```

> Solutions stay hidden until released in the publication, and can be marked as *not visible in the
> pub version* through an author comment. The `sp:desc` uses `dk:para` (a single paragraph), not the
> full `dk:text` flow. An exercise therefore differs from a plain theory slide, so exercises should
> not be flattened into theory slides.

---

## 9. Procedure / step list (`dk:stepList`)

A numbered walkthrough. Each `sp:step` has a short title (`sp:ti` → `dk:para`) and an `sp:detail`
holding a `dk:comment` with block content. Verified against `4-3-3-2.unit`.

```xml
<dk:stepList>
  <dk:stepListM>
    <sp:title><dk:richTitle><sc:para xml:space="preserve">Analysing Manifest.db</sc:para></dk:richTitle></sp:title>
  </dk:stepListM>
  <sp:steps>
    <dk:steps>
      <dk:stepsM/>
      <sp:step>
        <dk:step>
          <dk:stepM>
            <sp:ti><dk:para><sc:para xml:space="preserve">Open Manifest.db</sc:para></dk:para></sp:ti>
          </dk:stepM>
          <sp:detail>
            <dk:comment>
              <sp:infobloc><dk:blocTi/><dk:flowAll><sp:txt><dk:text>
                <sc:orderedList>
                  <sc:listItem><sc:para xml:space="preserve">Launch DB Browser for SQLite</sc:para></sc:listItem>
                  <sc:listItem><sc:para xml:space="preserve">Open Manifest.db from the backup directory</sc:para></sc:listItem>
                </sc:orderedList>
              </dk:text></sp:txt></dk:flowAll></sp:infobloc>
            </dk:comment>
          </sp:detail>
        </dk:step>
      </sp:step>
      <!-- more <sp:step>… -->
    </dk:steps>
  </sp:steps>
</dk:stepList>
```

`dk:stepList` is not a root item; it appears nested inside content, for instance inside an exercise
solution through an `op` element.

---

## 10. Content part (`dk:part`)

The Advanced course renders many slides as lightweight **parts** (a titled content block without the
trainer-note and agenda scaffolding). It is the root of its own `.unit`, referenced from the index
through `<sp:part sc:refUri="…​.unit"/>`.

```xml
<sc:item xmlns:dk="kelis.fr:dokiel"
         xmlns:sc="http://www.utc.fr/ics/scenari/v3/core"
         xmlns:sp="http://www.utc.fr/ics/scenari/v3/primitive">
  <dk:part>
    <dk:rTitle><sp:rTitle><dk:richTitle><sc:para xml:space="preserve">Relational Databases</sc:para></dk:richTitle></sp:rTitle></dk:rTitle>
    <sp:co>
      <dk:content>
        <sp:infobloc><dk:blocTi/><dk:flowAll><sp:txt><dk:text>
          <sc:para xml:space="preserve">A <sc:inlineStyle role="emphasis">table</sc:inlineStyle> is made up of columns.</sc:para>
        </dk:text></sp:txt></dk:flowAll></sp:infobloc>
      </dk:content>
    </sp:co>
  </dk:part>
</sc:item>
```

---

## 11. Annotated image (`dk:screen`)

Places clickable zones over a base image (stored in `Resources/`). The coordinates are
`x1,y1,x2,y2` (floating-point values allowed). Verified against `0-1-1-Methodology Diagram.unit`.

```xml
<sc:item xmlns:dk="kelis.fr:dokiel"
         xmlns:sc="http://www.utc.fr/ics/scenari/v3/core"
         xmlns:sp="http://www.utc.fr/ics/scenari/v3/primitive">
  <dk:screen>
    <dk:screenM>
      <sp:img sc:refUri="Resources/Casey.png"/>
      <sp:publishZoneImages>no</sp:publishZoneImages>
    </dk:screenM>
    <sp:zone>
      <dk:filter/>
      <sc:spatial>
        <sc:shape>rect</sc:shape>
        <sc:coords>168.55,10.77,776.53,102.77</sc:coords>
      </sc:spatial>
      <dk:zone>
        <dk:zoneM>
          <sp:title><dk:richTitle><sc:para xml:space="preserve">Preparation</sc:para></dk:richTitle></sp:title>
        </dk:zoneM>
        <sp:content>
          <dk:content>
            <sp:infobloc><dk:blocTi/><dk:flowAll><sp:txt><dk:text>
              <sc:para xml:space="preserve">This stage affects all other stages…</sc:para>
            </dk:text></sp:txt></dk:flowAll></sp:infobloc>
          </dk:content>
        </sp:content>
      </dk:zone>
    </sp:zone>
    <!-- more <sp:zone>… -->
  </dk:screen>
</sc:item>
```

---

## 12. Session synthesis (`sp:synthesis`)

The real session closing is an `sp:synthesis` block *inside* `dk:module` (not a separate
"Conclusion" submodule). A short closing paragraph, optionally a resource table (§13 / §14.5).

```xml
<sp:synthesis>
  <dk:rTitle/>
  <dk:content>
    <sp:infobloc><dk:blocTi/><dk:flowAll><sp:txt><dk:text>
      <sc:para xml:space="preserve">This concludes our lesson about Introduction to Computer Forensics.</sc:para>
    </dk:text></sp:txt></dk:flowAll></sp:infobloc>
  </dk:content>
</sp:synthesis>
```

---

## 13. Block elements

Blocks sit in `<dk:content>` (slide content) or `<dk:comment>` (trainer notes). Every block has a
`<dk:blocTi>` title header and a `<dk:flowAll>` body. The title is omitted with `<dk:blocTi/>`.

| Element | Purpose | Rendering |
|---|---|---|
| `<sp:infobloc>` | main content block | neutral / white |
| `<sp:advice>` | key points, best practice | blue |
| `<sp:tip>` | short hint | green |
| `<sp:note>` | side note or reminder | yellow |
| `<sp:example>` | example or demo (may contain media) | purple |
| `<sp:complement>` | optional / further reading | grey |
| `<sp:warning>` | warning or caution | red |

**Template (identical for all types):**

```xml
<sp:infobloc>
  <dk:blocTi><sp:rTitle><dk:richTitle><sc:para xml:space="preserve">Block Title</sc:para></dk:richTitle></sp:rTitle></dk:blocTi>
  <dk:flowAll><sp:txt><dk:text>
    <!-- content elements -->
  </dk:text></sp:txt></dk:flowAll>
</sp:infobloc>
```

---

## 14. Content elements

### 14.1 Paragraph
```xml
<sc:para xml:space="preserve">Plain text here.</sc:para>
```

### 14.2 Simple list (flat, the common default)
```xml
<sc:simpleList>
  <sc:member xml:space="preserve">Item A</sc:member>
  <sc:member xml:space="preserve">Item B</sc:member>
</sc:simpleList>
```

### 14.3 Itemized list (nested / multi-paragraph)
```xml
<sc:itemizedList>
  <sc:listItem>
    <sc:para xml:space="preserve">Top-level item</sc:para>
    <sc:simpleList><sc:member xml:space="preserve">Sub-item</sc:member></sc:simpleList>
  </sc:listItem>
</sc:itemizedList>
```

### 14.4 Ordered list
```xml
<sc:orderedList>
  <sc:listItem><sc:para xml:space="preserve">Step one</sc:para></sc:listItem>
</sc:orderedList>
```

### 14.5 Table
```xml
<sc:table role="table">
  <sc:column width="30"/>
  <sc:column width="70"/>
  <sc:row role="rowTi">
    <sc:cell><sc:para xml:space="preserve">Header A</sc:para></sc:cell>
    <sc:cell><sc:para xml:space="preserve">Header B</sc:para></sc:cell>
  </sc:row>
  <sc:row>
    <sc:cell><sc:para xml:space="preserve">Value A</sc:para></sc:cell>
    <sc:cell><sc:para xml:space="preserve">Value B</sc:para></sc:cell>
  </sc:row>
</sc:table>
```
Widths are relative. `role="rowTi"` marks the header row. `rowSpan`/`colSpan` work on `<sc:cell>`.

### 14.6 Inline styles (in `sc:para` / `sc:member`)

| Role | Purpose |
|---|---|
| `emphasis` | bold / highlighted |
| `cmd` | inline command or code, for every command, flag, mask |
| `filePath` | file-system path |
| `menuPath` | GUI menu path |
| `term` | technical term |
| `label` | callout / inline label |

```xml
<sc:para xml:space="preserve">Run <sc:inlineStyle role="cmd">uname -a</sc:inlineStyle> in <sc:inlineStyle role="filePath">/var/log/</sc:inlineStyle>.</sc:para>
```
`<sc:phrase role="alt">(placeholder)</sc:phrase>` marks alt or placeholder text.

### 14.7 Hyperlink
```xml
<sc:phrase role="url">
  <dk:urlM xml:space="default"><sp:url>https://example.com</sp:url></dk:urlM>https://example.com</sc:phrase>
```

### 14.8 Image reference
`sc:refUri` points to the resource **subfolder** (not the file inside it) and must sit in
`<dk:text>`, never as a direct child of `<dk:content>`:
```xml
<sc:extBlock role="fig" sc:refUri="Resources/screenshot.png"/>
```

---

## 15. Code, SQL, and output units (`dk:code`)

Verbatim blocks live in their own `.unit` files and are referenced through `sc:extBlock`. This is the
right place for anything that must be preserved **byte for byte**: commands, hashes, JSON, terminal
output. Use `xml:space="preserve"` and neither summarise nor translate this text.

**Terminal / plain-text output** (`Outputs/`, `mimeType="text/plain"`):
```xml
<?xml version="1.0"?>
<sc:item xmlns:dk="kelis.fr:dokiel" xmlns:sc="http://www.utc.fr/ics/scenari/v3/core">
  <dk:code>
    <dk:codeM/>
    <sc:code mimeType="text/plain" xml:space="preserve">81dc9bdb52d04dc20036dbd8313ed055:1234
1f40e5494d67bacca0d2505b45e607ce:946023</sc:code>
  </dk:code>
</sc:item>
```

**SQL** (`SQL Queries/`, `mimeType="text/x-sql"`, one statement per file):
```xml
<sc:code mimeType="text/x-sql" xml:space="preserve">SELECT url, visit_count FROM history_items ORDER BY visit_count DESC LIMIT 10;</sc:code>
```

Referencing from a slide:
```xml
<sc:extBlock role="fig" sc:refUri="Outputs/11-1-hashcat_potfile.unit"/>
<sc:extBlock role="fig" sc:refUri="SQL Queries/SQL-2-4-3_0.unit"/>
```

> `mimeType` also accepts `text/x-sh`, `application/json`, and similar; the right value produces
> syntax highlighting in the publication.

---

## 16. Media resources (`sfm:image` / `sfm:video`)

Each image or video sits as a **subfolder** in `Resources/`, named after the file, holding the file
itself and a `meta.xml`.

**Image** (`sfm:image` / `dk:imageM`):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<sfm:image version="1"
           xmlns:dk="kelis.fr:dokiel" xmlns:sc="http://www.utc.fr/ics/scenari/v3/core"
           xmlns:sfm="http://www.utc.fr/ics/scenari/v3/filemeta" xmlns:sp="http://www.utc.fr/ics/scenari/v3/primitive">
  <dk:imageM>
    <sp:title><dk:richTitle><sc:para xml:space="preserve">Alt / caption text</sc:para></dk:richTitle></sp:title>
    <sp:accessibility/>
  </dk:imageM>
</sfm:image>
```

**Video / audio** (`sfm:video` / `dk:mediaM`), with a different root and metadata element:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<sfm:video version="1"
           xmlns:dk="kelis.fr:dokiel" xmlns:sc="http://www.utc.fr/ics/scenari/v3/core"
           xmlns:sfm="http://www.utc.fr/ics/scenari/v3/filemeta" xmlns:sp="http://www.utc.fr/ics/scenari/v3/primitive">
  <dk:mediaM>
    <sp:title><dk:richTitle><sc:para xml:space="preserve">Demo video: man sort</sc:para></dk:richTitle></sp:title>
  </dk:mediaM>
</sfm:video>
```

Supported: PNG, JPG, GIF, SVG, MP4 (and audio for podcasts). Each resource needs its own subfolder
and the matching `meta.xml`.

---

## 17. Publication descriptors (`.pub`)

The Advanced course ships `.pub` files that tell Scenari **how** a module is published (web training,
SCORM, and so on). They are `sc:item` roots with `dk:trainingRoot` or `dk:tutorialRoot`. They
reference the module `.scen` and carry logo, author, and slideshow settings. They are not required
for a pure content import, but they are needed to reproduce the original publications.

**Training publication** (`dk:trainingRoot`):
```xml
<?xml version="1.0" encoding="UTF-8"?>
<sc:item version="1" xmlns:dk="kelis.fr:dokiel" xmlns:sc="http://www.utc.fr/ics/scenari/v3/core" xmlns:sp="http://www.utc.fr/ics/scenari/v3/primitive">
  <dk:trainingRoot>
    <dk:trainingRootM>
      <sp:logo sc:refUri="../&amp;/logo.png"/>
      <sp:info><dk:rootM>
        <sp:author><dk:textSimple><sc:para xml:space="preserve">Chris Farrugia, Johan Wallengren, Martin Mink</sc:para></dk:textSimple></sp:author>
      </dk:rootM></sp:info>
      <sp:settingsDiap>
        <sp:img sc:refUri="../&amp;/EN_fundedbyEU_VERTICAL_RGB_Monochrome.png"/>
        <sp:cplts>yes</sp:cplts>
      </sp:settingsDiap>
      <sp:settingsTrainee><sp:cplts>yes</sp:cplts></sp:settingsTrainee>
      <sp:settingsTrainer/>
    </dk:trainingRootM>
    <sp:module sc:refUri="2-1 - Advanced SQLite/2-1-AdvancedSQLite.scen"/>
  </dk:trainingRoot>
</sc:item>
```

**Tutorial / web publication** (`dk:tutorialRoot`), minimal variant referencing a `.scen`:
```xml
<dk:tutorialRoot>
  <dk:tutorialRootM><sp:info><dk:rootM/></sp:info></dk:tutorialRootM>
  <sp:content sc:refUri="1-1-Introduction.scen"/>
</dk:tutorialRoot>
```
`settingsDiap` holds slideshow options; `settingsTrainer`/`settingsTrainee` switch the trainer and
learner build; `sp:cplts` shows complements.

---

## 18. Interactive Dokiel palette (present in the model, not used in the reference exports)

The reference courses use only `theory`, `exercise`, `stepList`, and `screen`. Dokiel offers a much
larger set of **interactive and assessment** components beyond that. These can add value beyond a
1:1 slide import. They do not occur in the present exports, so the exact XML has to be obtained by
authoring and exporting one item in the tool. The following notes come from the Dokiel model
documentation, not from verified samples.

### 18.1 Quiz / question types
- **QCU**: one correct answer (radio).
- **QCM**: several correct answers (checkbox); the statement can be **text or multimedia**.
- **Closed question**: an expected **text** or **numeric** value.
- **Open question**: free-text answer (self-assessed against a model answer).
- **Gap-fill (texte à trous)**: blanks in **text** or **on an image**.
- **Categorisation**: sort items into categories.
- **Ordering**: put **words or images** into the correct sequence.
- **Graphic MCQ / hotspot**: single or multiple choice by clicking regions of an image.

Each question carries a **statement** (may contain image/audio/video), the **solution**, an optional
**explanation** (visible to everyone) and **feedback** (depending on the answer), and **distractors**
for MCQ.

### 18.2 Assessment container
- **Evaluation**: a graded assessment that bundles questions; it connects to **SCORM** tracking when
  published to an LMS (Moodle and similar).

### 18.3 Reference and knowledge components
- **Concept** / **Definition**: reusable explanation items; **definitions feed a glossary
  automatically**.
- **Glossary**, **Index**, **Bibliography**: automatically generated reference sections.
- **Fragment**: a reusable, untitled content block shared across items.

### 18.4 Media and navigation
- **Screen sequence**: several linked `screen`s as a slideshow or animation.
- **Conditions / Questionnaire**: adaptive content shown or hidden per learner **profile** (for
  instance a beginner versus an advanced track).

> Recommendation for the converter: deterministic generation targets `theory`, `code`/`sql` units,
> `stepList`, and real `exercise`. The items from §18 remain an optional, author-driven enrichment. A
> language model should not generate QCM or gap-fill questions from slides, as that would invent
> content. If you want quizzes, capture the real XML of the chosen question type first, then
> template it from explicit author input.

---

## 19. Authoring conventions

- Every session has an index `N-M-Session Name.scen` (`dk:module`).
- Slides attach as `sp:subModule` to neighbouring `.scen` (**Basic**) **or** as `sp:theory`/
  `sp:exercise`/`sp:part` with `sc:refUri` to external `.unit` (**Advanced**). Choose one pattern per
  course and keep it consistent.
- `sp:theory` is the default slide. Prefer `<sc:simpleList>` for lists.
- **Verbatim content** (commands, hashes, JSON, output, SQL) belongs in `dk:code` `.unit` files with
  `xml:space="preserve"`, never summarised, never machine-translated.
- Exercises use the real structure of `exposition` and `exerciseQ` (`desc` plus `solution`, §8), not
  theory slides.
- Procedures use `dk:stepList` (§9); session closings use `sp:synthesis` (§12), not an invented
  "Conclusion" submodule.
- Images → `sfm:image`; video/audio → `sfm:video`; one dedicated `Resources/<file>/` folder with a
  `meta.xml` per resource.
- Shared logos and banners live in the `&` pool, referenced as `../&/file.png`.
- Reproduce the `.wspmeta` exactly (Dokiel 25.0.6, the project skin) for import compatibility.

---

## 20. XML namespace quick reference

| Prefix | URI | Scope |
|---|---|---|
| `sc` | `http://www.utc.fr/ics/scenari/v3/core` | `sc:item`, `sc:para`, `sc:extBlock`, `sc:code`, `sc:table`, lists, inline styles, `sc:refUri` |
| `sp` | `http://www.utc.fr/ics/scenari/v3/primitive` | `sp:module`/`sp:subModule`, `sp:theory`, `sp:exercise`, `sp:part`, `sp:steps`/`sp:step`, `sp:content`/`sp:co`, `sp:exposition`, `sp:exerciseQ`, `sp:solution`, `sp:synthesis`, block types, `sp:trainNote`, `sp:title`, `sp:url`, `sp:img`, `sp:logo`, `sp:settings*` |
| `dk` | `kelis.fr:dokiel` | `dk:module`, `dk:part`, `dk:theory`, `dk:exercise`, `dk:stepList`/`dk:step`, `dk:screen`, `dk:code`, `dk:content`, `dk:comment`, `dk:blocTi`/`dk:flowAll`/`dk:text`, `dk:richTitle`, `dk:urlM`, `dk:trainingRoot`/`dk:tutorialRoot`, `dk:imageM`/`dk:mediaM` |
| `sfm` | `http://www.utc.fr/ics/scenari/v3/filemeta` | root of a resource `meta.xml`: `sfm:image` (images) and `sfm:video` (video/audio) |

---

## 21. Sources

- Scenari, *Import an archive* (SCENARIchain-desktop 6): <https://doc.scenari.software/SCENARIchain-desktop@6/reference/en/co/archive-importer.xhtml>
- Scenari, *Create a workspace from an archive*: <https://doc.scenari.software/SCENARIchain-desktop@6/reference/en/co/archive-importer-creer-migrer-atelier.xhtml>
- Dokiel, *Quiz* (question types): <https://dokiel.fr/fr/co/quiz-edit.html>
- Dokiel 4.4, glossary / model reference: <https://doc.scenari.software/Dokiel@4.4/reference/fr/co/glossary.xhtml>
- Scenari community, *Le format SCAR*: <https://pjacob.scenari-community.org/formation/exploiter_ressources/co/scar.html>
- Verified against real exports (*Mac Basic*, *Mac Advanced*) and the course skeleton.
