"""Desktop GUI for the Dokiel converter.

Left panel: pick a .pptx/.pdf and an export folder, set course/session metadata
and options. Right panel: a notebook with the scan result (slide plan + the Dokiel
elements that will be produced), and a live log.

Scan  = dry run (extract -> classify -> emit in memory -> verify), writes nothing.
Convert = the full pipeline, writes the workspace folder + .scwsp.

Both run on a background thread; log lines flow through a queue.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import cli, plan

class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Dokiel Importer")
        root.geometry("1080x680")

        self.log_q: "queue.Queue[str]" = queue.Queue()
        self._busy = False

        self.v_input = tk.StringVar()
        self.v_output = tk.StringVar()
        self.v_course = tk.StringVar(value="Course")
        self.v_day = tk.StringVar(value="Day 1")
        self.v_code = tk.StringVar(value="1-1")
        self.v_session = tk.StringVar(value="Session")
        self.v_target = tk.StringVar(value="basic")
        self.v_exercises = tk.BooleanVar(value=False)
        self.v_pub = tk.BooleanVar(value=False)
        self.v_scwsp = tk.BooleanVar(value=True)
        self.v_batch = tk.BooleanVar(value=False)
        self.v_translate = tk.BooleanVar(value=False)
        self.v_srclang = tk.StringVar(value="de")
        self.v_model = tk.StringVar(value="gemma4:latest")
        self.v_host = tk.StringVar(value="http://localhost:11434")
        self.v_status = tk.StringVar(value="Ready.")

        self._build()
        self.root.after(120, self._poll_log)

    def _build(self):
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill="both", expand=True)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 8))
        self._build_left(left)

        right = ttk.Frame(main)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)
        self._build_right(right)

        status = ttk.Label(self.root, textvariable=self.v_status, relief="sunken",
                           anchor="w", padding=(6, 2))
        status.pack(fill="x", side="bottom")

    def _section(self, parent, text):
        ttk.Label(parent, text=text, font=("", 11, "bold")).pack(
            anchor="w", pady=(10, 2))

    def _row(self, parent, label, var, width=26):
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=1)
        ttk.Label(f, text=label, width=13).pack(side="left")
        ttk.Entry(f, textvariable=var, width=width).pack(side="left", fill="x", expand=True)

    def _build_left(self, p):
        self._section(p, "1 · Source & output")
        ttk.Checkbutton(p, text="Batch: input is a folder (one session per file)",
                        variable=self.v_batch).pack(anchor="w")
        fin = ttk.Frame(p); fin.pack(fill="x", pady=1)
        ttk.Label(fin, text="Input", width=13).pack(side="left")
        ttk.Entry(fin, textvariable=self.v_input).pack(side="left", fill="x", expand=True)
        ttk.Button(fin, text="…", width=3, command=self._pick_input).pack(side="left")
        fout = ttk.Frame(p); fout.pack(fill="x", pady=1)
        ttk.Label(fout, text="Export dir", width=13).pack(side="left")
        ttk.Entry(fout, textvariable=self.v_output).pack(side="left", fill="x", expand=True)
        ttk.Button(fout, text="…", width=3, command=self._pick_output).pack(side="left")

        self._section(p, "2 · Course metadata")
        self._row(p, "Course title", self.v_course)
        self._row(p, "Day", self.v_day)
        self._row(p, "Session code", self.v_code)
        self._row(p, "Session name", self.v_session)

        self._section(p, "3 · Structure")
        fr = ttk.Frame(p); fr.pack(fill="x")
        ttk.Radiobutton(fr, text="Basic (inline)", value="basic",
                        variable=self.v_target).pack(side="left")
        ttk.Radiobutton(fr, text="Advanced (.unit)", value="advanced",
                        variable=self.v_target).pack(side="left")
        ttk.Checkbutton(p, text="Map exercise-titled slides to dk:exercise",
                        variable=self.v_exercises).pack(anchor="w")
        ttk.Checkbutton(p, text="Emit .pub publication descriptor",
                        variable=self.v_pub).pack(anchor="w")
        ttk.Checkbutton(p, text="Also build .scwsp archive",
                        variable=self.v_scwsp).pack(anchor="w")

        self._section(p, "4 · Translation (optional)")
        ttk.Checkbutton(p, text="Translate prose to English",
                        variable=self.v_translate).pack(anchor="w")
        self._row(p, "Source lang", self.v_srclang, width=10)
        self._row(p, "Ollama model", self.v_model)
        self._row(p, "Ollama host", self.v_host)
        ttk.Label(p, text="Commands, hashes and paths stay unchanged.",
                  foreground="#666").pack(anchor="w", pady=(2, 0))

        self._section(p, "5 · Run")
        fb = ttk.Frame(p); fb.pack(fill="x", pady=(2, 0))
        self.btn_scan = ttk.Button(fb, text="Scan", command=self._scan)
        self.btn_scan.pack(side="left", expand=True, fill="x", padx=(0, 4))
        self.btn_conv = ttk.Button(fb, text="Convert", command=self._convert)
        self.btn_conv.pack(side="left", expand=True, fill="x")

    def _build_right(self, p):
        nb = ttk.Notebook(p)
        nb.grid(row=0, column=0, sticky="nsew")

        ov = ttk.Frame(nb, padding=6); nb.add(ov, text="Overview")
        ov.columnconfigure(0, weight=1); ov.rowconfigure(2, weight=1)
        self.lbl_summary = ttk.Label(ov, text="Run a scan to see the plan.",
                                     font=("", 11, "bold"))
        self.lbl_summary.grid(row=0, column=0, sticky="w")
        self.lbl_fidelity = ttk.Label(ov, text="")
        self.lbl_fidelity.grid(row=1, column=0, sticky="w", pady=(0, 6))
        cols = ("count", "element", "meaning")
        self.tv_el = ttk.Treeview(ov, columns=cols, show="headings", height=12)
        for c, w, t in (("count", 60, "Count"), ("element", 150, "Dokiel element"),
                        ("meaning", 340, "Meaning")):
            self.tv_el.heading(c, text=t); self.tv_el.column(c, width=w,
                                                             anchor="w" if c != "count" else "e")
        self.tv_el.grid(row=2, column=0, sticky="nsew")
        sb1 = ttk.Scrollbar(ov, orient="vertical", command=self.tv_el.yview)
        sb1.grid(row=2, column=1, sticky="ns"); self.tv_el.configure(yscroll=sb1.set)

        sp = ttk.Frame(nb, padding=6); nb.add(sp, text="Slide plan")
        sp.columnconfigure(0, weight=1); sp.rowconfigure(0, weight=1)
        cols2 = ("nr", "type", "blocks", "notes", "title")
        self.tv_sl = ttk.Treeview(sp, columns=cols2, show="headings")
        for c, w, t in (("nr", 40, "#"), ("type", 80, "Type"),
                        ("blocks", 220, "Blocks"), ("notes", 60, "Notes"),
                        ("title", 380, "Title")):
            self.tv_sl.heading(c, text=t); self.tv_sl.column(c, width=w)
        self.tv_sl.grid(row=0, column=0, sticky="nsew")
        sb2 = ttk.Scrollbar(sp, orient="vertical", command=self.tv_sl.yview)
        sb2.grid(row=0, column=1, sticky="ns"); self.tv_sl.configure(yscroll=sb2.set)

        fl = ttk.Frame(nb, padding=6); nb.add(fl, text="Files")
        fl.columnconfigure(0, weight=1); fl.rowconfigure(0, weight=1)
        self.txt_files = tk.Text(fl, wrap="none", font=("Menlo", 10))
        self.txt_files.grid(row=0, column=0, sticky="nsew")
        sb3 = ttk.Scrollbar(fl, orient="vertical", command=self.txt_files.yview)
        sb3.grid(row=0, column=1, sticky="ns"); self.txt_files.configure(yscroll=sb3.set)

        lg = ttk.Frame(nb, padding=6); nb.add(lg, text="Log")
        lg.columnconfigure(0, weight=1); lg.rowconfigure(0, weight=1)
        self.txt_log = tk.Text(lg, wrap="word", font=("Menlo", 10), background="#111",
                               foreground="#ddd", insertbackground="#ddd")
        self.txt_log.grid(row=0, column=0, sticky="nsew")
        sb4 = ttk.Scrollbar(lg, orient="vertical", command=self.txt_log.yview)
        sb4.grid(row=0, column=1, sticky="ns"); self.txt_log.configure(yscroll=sb4.set)
        self.nb = nb

    def _pick_input(self):
        if self.v_batch.get():
            d = filedialog.askdirectory(title="Select folder of PPTX/PDF/DOCX files")
            if d:
                self.v_input.set(d)
                if self.v_course.get() in ("", "Course"):
                    self.v_course.set(Path(d).name)
            return
        f = filedialog.askopenfilename(
            title="Select PPTX, PDF or DOCX",
            filetypes=[("Slides / documents", "*.pptx *.ppt *.pdf *.docx"), ("All files", "*.*")])
        if f:
            self.v_input.set(f)
            stem = Path(f).stem
            if self.v_session.get() in ("", "Session"):
                self.v_session.set(stem)
            if self.v_course.get() in ("", "Course"):
                self.v_course.set(stem)

    def _pick_output(self):
        d = filedialog.askdirectory(title="Select export directory")
        if d:
            self.v_output.set(d)

    def _log(self, *args):
        self.log_q.put(" ".join(str(a) for a in args))

    def _poll_log(self):
        while not self.log_q.empty():
            self.txt_log.insert("end", self.log_q.get() + "\n")
            self.txt_log.see("end")
        self.root.after(120, self._poll_log)

    def _set_busy(self, busy: bool, status: str = ""):
        self._busy = busy
        state = "disabled" if busy else "normal"
        self.btn_scan.config(state=state)
        self.btn_conv.config(state=state)
        if status:
            self.v_status.set(status)

    def _opts(self) -> dict:
        return dict(
            course_title=self.v_course.get() or "Course",
            day=self.v_day.get() or "Day 1",
            session_code=self.v_code.get() or "1-1",
            session_name=self.v_session.get() or "Session",
            target=self.v_target.get(),
            exercises=self.v_exercises.get(),
            make_pub=self.v_pub.get(),
        )

    def _scan(self):
        inp = self.v_input.get().strip()
        batch = self.v_batch.get()
        if not inp or (batch and not Path(inp).is_dir()) or (not batch and not Path(inp).is_file()):
            messagebox.showerror("No input", "Choose a %s first."
                                 % ("folder" if batch else ".pptx / .pdf / .docx file"))
            return
        self._set_busy(True, "Scanning …")
        self._log(f"[scan] {inp}")
        threading.Thread(target=self._scan_worker, args=(inp, batch), daemon=True).start()

    def _scan_worker(self, inp, batch):
        try:
            if batch:
                opts = self._opts()
                opts.pop("session_code", None)
                opts.pop("session_name", None)
                report = plan.scan_batch(inp, **opts)
            else:
                report = plan.scan(inp, **self._opts())
            self.root.after(0, lambda: self._show_scan(report))
        except Exception as e:
            self._log(f"[scan] ERROR: {e}")
            self.root.after(0, lambda: self._set_busy(False, "Scan failed."))

    def _show_scan(self, r: dict):
        t = r["totals"]
        self.lbl_summary.config(
            text=(f"{r['source_type']} · {t['slides']} slides "
                  f"({t['theory']} theory, {t['exercise']} exercise) · "
                  f"{t['code_units']} code units · {t['images']} images · "
                  f"{t['files']} files"))
        fid = r["fidelity"]
        ok = fid["present_tokens"] == fid["total_tokens"] and fid["code_ok"] and r["wellformed"]
        self.lbl_fidelity.config(
            text=(f"Fidelity: {fid['present_tokens']}/{fid['total_tokens']} tokens · "
                  f"code byte-exact: {'yes' if fid['code_ok'] else 'NO'} · "
                  f"well-formed: {'yes' if r['wellformed'] else 'NO'}"),
            foreground="#1a7f37" if ok else "#b00020")

        self.tv_el.delete(*self.tv_el.get_children())
        for e in r["elements"]:
            self.tv_el.insert("", "end", values=(e["count"], e["element"], e["meaning"]))

        self.tv_sl.delete(*self.tv_sl.get_children())
        for s in r["slides"]:
            parts = []
            for k, lbl in (("flow", "box"), ("para", "para"), ("list", "list"),
                           ("olist", "olist"), ("code", "code"), ("sql", "sql"),
                           ("table", "table")):
                if s.get(k):
                    parts.append(f"{s[k]}×{lbl}")
            if s["images"]:
                parts.append(f"{s['images']}×img")
            self.tv_sl.insert("", "end", values=(
                s["index"], s["type"], ", ".join(parts) or "-",
                "yes" if s["has_notes"] else "", s["title"]))

        self.txt_files.delete("1.0", "end")
        self.txt_files.insert("end", "\n".join(r["files"]))

        if not ok:
            self._log("[scan] WARNING: fidelity or well-formedness check failed, see Overview")
            if fid["missing_tokens"]:
                self._log(f"[scan] missing tokens: {fid['missing_tokens'][:20]}")
        for w in r.get("warnings", []):
            self._log(f"[warn] {w}")
        self._log(f"[scan] done: {t['slides']} slides, {len(r['elements'])} distinct elements")
        self._set_busy(False, "Scan complete.")

    def _convert(self):
        inp = self.v_input.get().strip()
        out = self.v_output.get().strip()
        batch = self.v_batch.get()
        if not inp or (batch and not Path(inp).is_dir()) or (not batch and not Path(inp).is_file()):
            messagebox.showerror("No input", "Choose a %s first."
                                 % ("folder" if batch else ".pptx / .pdf / .docx file"))
            return
        if not out:
            messagebox.showerror("No export dir", "Please choose an export directory.")
            return
        self._set_busy(True, "Converting …")
        opts = self._opts()
        if batch:
            opts.pop("session_code", None)
            opts.pop("session_name", None)
        opts.update(do_translate=self.v_translate.get(), source_lang=self.v_srclang.get(),
                    model=self.v_model.get(), host=self.v_host.get(),
                    make_scwsp=self.v_scwsp.get())
        self.nb.select(3)
        threading.Thread(target=self._conv_worker, args=(inp, out, opts, batch), daemon=True).start()

    def _conv_worker(self, inp, out, opts, batch):
        try:
            res = (cli.convert_batch if batch else cli.convert)(inp, out, log=self._log, **opts)
            fid = res["fidelity"]
            ok = res["wellformed"] and not fid["missing_tokens"] and fid["code_ok"]
            msg = ("Conversion complete." if ok else
                   "Conversion done with warnings, check the log.")
            self.root.after(0, lambda: self._set_busy(False, msg))
            self.root.after(0, lambda: messagebox.showinfo("Done",
                f"{msg}\n\nWorkspace:\n{res['workspace']}"
                + (f"\n\nArchive:\n{res['scwsp']}" if res.get('scwsp') else "")))
        except Exception as e:
            self._log(f"[convert] ERROR: {e}")
            self.root.after(0, lambda: self._set_busy(False, "Conversion failed."))

def launch():
    root = tk.Tk()
    App(root)
    root.mainloop()

if __name__ == "__main__":
    launch()
