"""
DLSS 5 One-Click  -  apply Neural Rendering to the games that can take it.

Tkinter UI, no dependencies. Run:  python dlss5.py
"""

from __future__ import annotations

import os
import queue
import threading
import traceback
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import dlss5_scan as scan
import dlss5_apply as apply_mod
import dlss5_model as model_mod
from dlss5_editor import Editor

BG      = "#14161a"
PANEL   = "#1b1e24"
FG      = "#e8eaed"
MUTED   = "#93999f"
ACCENT  = "#76b900"          # NVIDIA green, since we are here
TIER_COLOR = {"A": "#76b900", "B": "#9ecf3a", "C": "#e07b25", "D": "#7a8087"}
TIER_TEXT = {
    "A": "Yes  (DLSS)",
    "B": "Yes  (FSR/XeSS)",
    "C": "Limited",
    "D": "No",
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DLSS 5 One-Click")
        self.geometry("1080x680")
        self.minsize(940, 600)
        self.configure(bg=BG)

        self.games: dict[str, scan.Game] = {}
        self.sysinfo: dict = {}
        self.model: dict = {}
        self.harvest: dict = {}
        self.q: queue.Queue = queue.Queue()
        self.busy = False

        self._style()
        self._build()
        self.after(80, self._pump)
        self._bg(self._check_system)

    # -- style ------------------------------------------------------------
    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure(".", background=BG, foreground=FG, fieldbackground=PANEL,
                    bordercolor="#2a2e35", lightcolor=PANEL, darkcolor=PANEL)
        s.configure("TFrame", background=BG)
        s.configure("Panel.TFrame", background=PANEL)
        s.configure("TLabel", background=BG, foreground=FG)
        s.configure("Muted.TLabel", background=BG, foreground=MUTED)
        s.configure("Panel.TLabel", background=PANEL, foreground=FG)
        s.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED)
        s.configure("Head.TLabel", background=BG, foreground=FG,
                    font=("Segoe UI Semibold", 15))
        s.configure("TButton", background="#272b32", foreground=FG,
                    borderwidth=0, padding=(12, 7), focuscolor=BG)
        s.map("TButton", background=[("active", "#333842"),
                                     ("disabled", "#1e2127")],
              foreground=[("disabled", "#5b6067")])
        s.configure("Go.TButton", background=ACCENT, foreground="#0d1200",
                    font=("Segoe UI Semibold", 10))
        s.map("Go.TButton", background=[("active", "#8ad100"),
                                        ("disabled", "#2c3a12")],
              foreground=[("disabled", "#6a7a52")])
        s.configure("Treeview", background=PANEL, fieldbackground=PANEL,
                    foreground=FG, rowheight=27, borderwidth=0)
        s.configure("Treeview.Heading", background="#22262d", foreground=MUTED,
                    borderwidth=0, padding=(8, 6))
        s.map("Treeview.Heading", background=[("active", "#2a2f37")])
        s.map("Treeview", background=[("selected", "#2f3a1c")],
              foreground=[("selected", FG)])
        s.configure("TCombobox", fieldbackground=PANEL, background=PANEL,
                    foreground=FG, arrowcolor=MUTED)
        s.configure("TProgressbar", background=ACCENT, troughcolor="#22262d",
                    borderwidth=0)

    # -- layout ------------------------------------------------------
    def _build(self):
        pad = dict(padx=14)

        head = ttk.Frame(self)
        head.pack(fill="x", pady=(14, 0), **pad)
        ttk.Label(head, text="DLSS 5 One-Click", style="Head.TLabel").pack(side="left")
        self.sys_lbl = ttk.Label(head, text="checking system...",
                                 style="Muted.TLabel")
        self.sys_lbl.pack(side="right")

        self.warn_lbl = ttk.Label(self, text="", style="Muted.TLabel",
                                  wraplength=1020, justify="left")
        self.warn_lbl.pack(fill="x", pady=(6, 0), **pad)

        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=(12, 8), **pad)
        self.btn_scan = ttk.Button(bar, text="Scan installed games",
                                   command=lambda: self._bg(self._scan_library))
        self.btn_scan.pack(side="left")
        self.btn_add = ttk.Button(bar, text="Add folder...",
                                  command=self._add_folder)
        self.btn_add.pack(side="left", padx=(8, 0))
        self.btn_sys = ttk.Button(bar, text="Recheck system",
                                  command=lambda: self._bg(self._check_system))
        self.btn_sys.pack(side="left", padx=(8, 0))
        self.btn_model = ttk.Button(bar, text="Find model",
                                    command=lambda: self._bg(self._get_model))
        self.btn_model.pack(side="left", padx=(8, 0))

        self.prog = ttk.Progressbar(bar, mode="determinate", length=220)
        self.prog.pack(side="right")
        self.prog_lbl = ttk.Label(bar, text="", style="Muted.TLabel")
        self.prog_lbl.pack(side="right", padx=(0, 10))

        # table
        cols = ("tier", "api", "ups", "state")
        self.tree = ttk.Treeview(self, columns=cols, show="tree headings",
                                 selectmode="browse", height=11)
        self.tree.heading("#0", text="Game")
        self.tree.heading("tier", text="DLSS 5")
        self.tree.heading("api", text="API")
        self.tree.heading("ups", text="Upscalers found")
        self.tree.heading("state", text="State")
        self.tree.column("#0", width=330, anchor="w")
        self.tree.column("tier", width=110, anchor="w")
        self.tree.column("api", width=110, anchor="w")
        self.tree.column("ups", width=230, anchor="w")
        self.tree.column("state", width=190, anchor="w")
        for t, c in TIER_COLOR.items():
            self.tree.tag_configure("tier" + t, foreground=c)
        self.tree.tag_configure("pending", foreground=MUTED)
        self.tree.pack(fill="both", expand=True, **pad)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # bottom panel
        low = ttk.Frame(self, style="Panel.TFrame")
        low.pack(fill="x", pady=(10, 0), **pad)

        self.detail = ttk.Label(low, text="Select a game.",
                                style="Panel.TLabel", wraplength=700,
                                justify="left")
        self.detail.pack(side="left", fill="x", expand=True, padx=12, pady=12)

        right = ttk.Frame(low, style="Panel.TFrame")
        right.pack(side="right", padx=12, pady=12)

        ttk.Label(right, text="Preset", style="PanelMuted.TLabel").grid(
            row=0, column=0, sticky="w")
        self.preset = tk.StringVar(value="balanced")
        combo = ttk.Combobox(right, textvariable=self.preset, state="readonly",
                             width=38,
                             values=[apply_mod.PRESETS[k]["label"]
                                     for k in apply_mod.PRESETS])
        combo.grid(row=1, column=0, columnspan=2, sticky="we", pady=(2, 8))
        combo.set(apply_mod.PRESETS["balanced"]["label"])
        self._combo = combo

        self.btn_apply = ttk.Button(right, text="Apply DLSS 5",
                                    style="Go.TButton", state="disabled",
                                    command=self._start_install)
        self.btn_apply.grid(row=2, column=0, sticky="we")
        self.btn_revert = ttk.Button(right, text="Revert", state="disabled",
                                     command=self._start_revert)
        self.btn_revert.grid(row=2, column=1, sticky="we", padx=(8, 0))
        self.btn_opts = ttk.Button(right, text="Settings...", state="disabled",
                                   command=self._open_editor)
        self.btn_opts.grid(row=3, column=0, sticky="we", pady=(8, 0))
        self.btn_open = ttk.Button(right, text="Open folder", state="disabled",
                                   command=self._open_folder)
        self.btn_open.grid(row=3, column=1, sticky="we", padx=(8, 0), pady=(8, 0))

        # log
        self.log_box = tk.Text(self, height=7, bg="#101216", fg="#b9bfc6",
                               insertbackground=FG, relief="flat",
                               font=("Consolas", 9), wrap="word")
        self.log_box.pack(fill="x", pady=(10, 14), **pad)
        self.log_box.configure(state="disabled")

    # -- threading helpers ------------------------------------------------
    def _bg(self, fn):
        if self.busy:
            return
        self.busy = True
        self._buttons(False)

        def runner():
            try:
                fn()
            except Exception as e:                    # noqa: BLE001
                self.q.put(("log", "ERROR: " + str(e)))
                self.q.put(("log", traceback.format_exc(limit=3)))
                self.q.put(("error", str(e)))
            finally:
                self.q.put(("done", None))

        threading.Thread(target=runner, daemon=True).start()

    def _buttons(self, on: bool):
        state = "normal" if on else "disabled"
        for b in (self.btn_scan, self.btn_add, self.btn_sys, self.btn_model):
            b.configure(state=state)
        if on:
            self._on_select()
        else:
            for b in (self.btn_apply, self.btn_revert, self.btn_open,
                      self.btn_opts):
                b.configure(state="disabled")

    def log(self, msg: str):
        self.q.put(("log", msg))

    def _pump(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "log":
                    self.log_box.configure(state="normal")
                    self.log_box.insert("end", str(payload) + "\n")
                    self.log_box.see("end")
                    self.log_box.configure(state="disabled")
                elif kind == "sys":
                    self._render_system(payload)
                elif kind == "row":
                    self._render_row(payload)
                elif kind == "prog":
                    frac, text = payload
                    self.prog["value"] = frac * 100
                    self.prog_lbl.configure(text=text)
                elif kind == "error":
                    messagebox.showerror("DLSS 5 One-Click", str(payload))
                elif kind == "info":
                    messagebox.showinfo("DLSS 5 One-Click", str(payload))
                elif kind == "modelhelp":
                    messagebox.showwarning(
                        "Neural Rendering model missing",
                        model_mod.help_text(payload))
                elif kind == "done":
                    self.busy = False
                    self._buttons(True)
                    self.prog["value"] = 0
                    self.prog_lbl.configure(text="")
        except queue.Empty:
            pass
        self.after(80, self._pump)

    # -- system -----------------------------------------------------------
    def _get_model(self):
        """Find the model, extracting it from a driver installer if needed."""
        self.log("")
        self.log("Looking for nvngx_dlssnr.dll...")
        res = model_mod.obtain(log=self.log)
        if res["path"]:
            cached = model_mod.cache_model(res["path"], log=self.log)
            self.log(f"Model ready ({res['source']}): {cached}")
            self.q.put(("info", "Model found and cached.\n\n"
                                f"Source: {res['detail']}\n\n"
                                "Re-apply on games you already set up to copy it "
                                "into each one."))
        else:
            self.log("Not found: " + res["detail"])
            self.q.put(("modelhelp", scan.gpu_info().get("driver")))
        self._check_system()

    def _check_system(self):
        self.log("Checking GPU, driver and Neural Rendering model...")
        info = scan.gpu_info()
        model = model_mod.find_existing()
        self.q.put(("sys", (info, model)))
        self.log(f"GPU: {info.get('name') or 'unknown'}   "
                 f"driver {info.get('driver') or '?'}")
        if model["path"]:
            self.log(f"NR model: {model['path']}  "
                     f"({model['size'] >> 20} MB, v{model['version']})")
        elif model["misnamed"]:
            self.log(f"Possible renamed NR model: {model['misnamed']}")
        else:
            self.log("NR model: not on disk. NVIDIA puts it in the driver "
                     "installer but never copies it out.")

        self.log("Looking for the newest nvngx_dlss*.dll on this PC...")
        self.harvest = scan.harvest_dlss_dlls()
        for name, (path, ver) in sorted(self.harvest.items()):
            self.log(f"  {name}  v{ver}")

    def _render_system(self, payload):
        info, model = payload
        self.sysinfo, self.model = info, model

        gpu = info.get("name") or "unknown GPU"
        drv = info.get("driver") or "?"
        ok50 = info.get("rtx50")
        has_model = bool(model["path"] or model["misnamed"])

        marks = ("RTX 50: " + ("yes" if ok50 else "NO") +
                 "   NR model: " + ("yes" if has_model else "NO"))
        self.sys_lbl.configure(text=f"{gpu}  ·  driver {drv}  ·  {marks}")

        problems = []
        if not ok50:
            problems.append("The official model only runs on RTX 50. Other "
                            "cards need a modified nvngx_dlssnr.dll.")
        if model_mod.driver_ok(drv) is False:
            problems.append(f"Driver {drv}: below the 616.56 minimum.")
        if not has_model:
            problems.append(
                "nvngx_dlssnr.dll missing (~158 MB). If you have it, drop it "
                "next to this program and it is picked up. Otherwise it ships with "
                + ", ".join(model_mod.SHIPPING_GAMES)
                + " in data\\streamline: install it and press \"Find model\".")
        self.warn_lbl.configure(
            text=("  ".join(problems) if problems else
                  "System ready: RTX 50, current driver, model present."),
            foreground=("#e0a325" if problems else ACCENT))

    # -- library --------------------------------------------------------
    def _scan_library(self):
        self.log("Scanning Steam, Epic and GOG libraries...")
        found = scan.installed_games()
        self.log(f"{len(found)} games found. Analysing...")

        for entry in found:
            g = scan.Game(name=entry["name"], root=entry["path"],
                          store=entry["store"])
            g.verdict = "queued"
            self.games[g.key] = g
            self.q.put(("row", g))

        total = len(found) or 1
        for i, entry in enumerate(found, 1):
            try:
                g = scan.analyze(entry["path"], entry["name"], entry["store"])
            except Exception as e:                    # noqa: BLE001
                self.log(f"  failed to analyse {entry['name']}: {e}")
                continue
            self.games[g.key] = g
            self.q.put(("row", g))
            self.q.put(("prog", (i / total, f"{i}/{total}")))

        usable = sum(1 for g in self.games.values() if g.tier in "AB")
        self.log(f"Done. {usable} games can take DLSS 5 in some form.")

    def _add_folder(self):
        path = filedialog.askdirectory(title="Game folder")
        if not path:
            return

        def work():
            self.log(f"Analysing {path}...")
            g = scan.analyze(path)
            self.games[g.key] = g
            self.q.put(("row", g))
            self.log(f"  {g.name}: {g.verdict}")

        self._bg(work)

    def _render_row(self, g: scan.Game):
        api = " ".join(sorted(g.apis)).upper() or "-"
        if apply_mod.read_manifest(g.exe_dir or g.root):
            state = "instalado"
        elif g.anticheat:
            state = "anti-cheat: " + ", ".join(sorted(g.anticheat))
        else:
            state = "-" if g.tier != "D" else ""
        values = (TIER_TEXT.get(g.tier, "?") if g.exe else "...",
                  api, scan.summary_upscalers(g), state)
        tag = ("tier" + g.tier) if g.exe else "pending"
        if self.tree.exists(g.key):
            self.tree.item(g.key, text=g.name, values=values, tags=(tag,))
        else:
            self.tree.insert("", "end", iid=g.key, text=g.name, values=values,
                             tags=(tag,))

    # -- selection ---------------------------------------------------------
    def _current(self) -> scan.Game | None:
        sel = self.tree.selection()
        if not sel:
            return None
        return self.games.get(sel[0])

    def _on_select(self, _evt=None):
        g = self._current()
        if not g:
            self.detail.configure(text="Select a game.")
            for b in (self.btn_apply, self.btn_revert, self.btn_open,
                      self.btn_opts):
                b.configure(state="disabled")
            return

        installed = bool(apply_mod.read_manifest(g.exe_dir or g.root))
        lines = [g.verdict or "not analysed"]
        if g.exe:
            lines.append(f"Executable: {os.path.basename(g.exe)}  ({g.arch or '?'})"
                         + (f"   Engine: {g.engine}" if g.engine else ""))
        if g.dlss_version:
            lines.append(f"DLSS installed: v{g.dlss_version}")
        lines += g.notes
        if installed:
            lines.append("Already installed by this tool. "
                         "Press Revert to put it back as it was.")
        self.detail.configure(text="\n".join(lines))

        can_install = (not self.busy and g.tier in ("A", "B", "C")
                       and not installed and bool(g.exe_dir))
        self.btn_apply.configure(state="normal" if can_install else "disabled")
        self.btn_revert.configure(state="normal" if (installed and not self.busy)
                                  else "disabled")
        self.btn_open.configure(state="normal" if g.exe_dir else "disabled")
        # Settings only make sense when there is an OptiScaler.ini to edit.
        self.btn_opts.configure(
            state="normal" if (installed and not self.busy) else "disabled")

    def _open_editor(self):
        """Open the settings editor for the selected game."""
        g = self._current()
        if not g or not g.exe_dir:
            return
        Editor(self, g, on_saved=self.log)

    def _open_folder(self):
        g = self._current()
        if g and g.exe_dir:
            subprocess.Popen(["explorer", os.path.normpath(g.exe_dir)])

    # -- actions ----------------------------------------------------------
    def _preset_key(self) -> str:
        label = self._combo.get()
        for k, v in apply_mod.PRESETS.items():
            if v["label"] == label:
                return k
        return "balanced"

    def _start_install(self):
        """Se lee el estado de los widgets aqui, en el hilo de Tk.

        Tkinter no es reentrante desde otros hilos: consultar la seleccion o el
        combo desde el hilo de trabajo cuelga la ventana antes o despues.
        """
        g = self._current()
        if not g:
            return
        preset = self._preset_key()

        if g.anticheat:
            if not messagebox.askyesno(
                    "Anti-cheat detected",
                    f"{g.name} uses {', '.join(sorted(g.anticheat))}.\n\n"
                    "Dropping a DLL next to the executable is exactly what "
                    "these systems hunt for. In a game with competitive "
                    "multiplayer this can end in an account ban.\n\n"
                    "Continue anyway?"):
                return

        self._bg(lambda: self._install(g, preset))

    def _start_revert(self):
        g = self._current()
        if g and g.exe_dir:
            self._bg(lambda: self._revert(g))

    def _install(self, g: scan.Game, preset: str):
        neural = g.tier in ("A", "B")

        self.log("")
        self.log(f"=== {g.name} ===")
        self.log(f"Target: {g.exe_dir}")

        # The model is resolved once and reused from the cache instead of
        # searching the whole disk again for every game.
        model_path = None
        if neural:
            found = model_mod.find_existing()
            model_path = found["path"] or found["misnamed"]
            if model_path:
                model_path = model_mod.cache_model(model_path, log=self.log)

        kind = "dlssnr" if neural else "stable"

        def prog(frac, text):
            self.q.put(("prog", (frac, text)))

        manifest = apply_mod.install(g, preset=preset, kind=kind, neural=neural,
                                     model_path=model_path,
                                     progress=prog, log=self.log)

        if self.harvest and g.dll_paths:
            self.log("Checking whether the game's DLSS DLLs are outdated...")
            if apply_mod.upgrade_dlss_dll(g, self.harvest, log=self.log):
                self.log("  upgraded.")
            else:
                self.log("  already current.")

        g2 = scan.analyze(g.root, g.name, g.store)
        self.games[g2.key] = g2
        self.q.put(("row", g2))

        if manifest.get("modelo"):
            tail = ("Start the game and press F8 for the overlay, then look "
                    "for \"DLSS Neural Rendering\".\n\n"
                    "F10 toggles the pass without opening the menu: it is the "
                    "honest way to see whether it is doing anything.\n\n"
                    "In the overlay, try Colour -> \"Hybrid proxy + composed\". "
                    "It is the best of v0.2.0 and cannot be preset from here "
                    "because it does not exist as an INI key.")
        else:
            tail = ("OptiScaler is installed and working, but the neural pass "
                    "is off: nvngx_dlssnr.dll is missing.\n\n"
                    "Press \"Find model\", then apply here again.")
        self.q.put(("info", f"Done.\n\n{tail}"))

    def _revert(self, g: scan.Game):
        self.log(f"Reverting {g.name}...")
        apply_mod.revert(g.exe_dir, log=self.log)
        g2 = scan.analyze(g.root, g.name, g.store)
        self.games[g2.key] = g2
        self.q.put(("row", g2))


if __name__ == "__main__":
    App().mainloop()
