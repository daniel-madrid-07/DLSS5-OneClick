"""
Per-game visual settings editor.

Opens on an already-installed game, reads its OptiScaler.ini and exposes
everything the file accepts. Saves only what you change: keys you do not touch
stay as they are, comments intact.

Deliberately minimal: one column, collapsible groups, and each setting's help
underneath in grey. No tabs, no grid of 336 boxes.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox

import dlss5_apply as apply_mod
import dlss5_opts as opts

BG     = "#14161a"
PANEL  = "#1b1e24"
CARD   = "#20242b"
FG     = "#e8eaed"
MUTED  = "#8b9198"
DIM    = "#5f666e"
ACCENT = "#76b900"


class Editor(tk.Toplevel):
    def __init__(self, parent, game, on_saved=None):
        super().__init__(parent)
        self.game = game
        self.on_saved = on_saved
        self.title(f"Settings  ·  {game.name}")
        self.geometry("620x760")
        self.minsize(560, 520)
        self.configure(bg=BG)
        self.transient(parent)

        self.ini_path = apply_mod.game_ini_path(game.exe_dir or game.root)
        if not self.ini_path:
            messagebox.showerror("Settings",
                                 "This game has no OptiScaler.ini.\n\n"
                                 "Apply DLSS 5 first.", parent=parent)
            self.destroy()
            return

        self.data = apply_mod.read_ini(self.ini_path)
        self.vars: dict[tuple, tk.Variable] = {}
        self.open_groups: set[str] = {"nr"}      # only the first group open

        self._style()
        self._build()

    # ------------------------------------------------------------------
    def _style(self):
        s = ttk.Style(self)
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("E.TFrame", background=BG)
        s.configure("Card.TFrame", background=CARD)
        s.configure("E.TLabel", background=BG, foreground=FG)
        s.configure("Card.TLabel", background=CARD, foreground=FG)
        s.configure("Help.TLabel", background=CARD, foreground=DIM,
                    font=("Segoe UI", 8))
        s.configure("Title.TLabel", background=BG, foreground=FG,
                    font=("Segoe UI Semibold", 11))
        s.configure("Sub.TLabel", background=BG, foreground=MUTED,
                    font=("Segoe UI", 8))
        s.configure("E.TButton", background="#272b32", foreground=FG,
                    borderwidth=0, padding=(14, 8))
        s.map("E.TButton", background=[("active", "#333842")])
        s.configure("Save.TButton", background=ACCENT, foreground="#0d1200",
                    borderwidth=0, padding=(14, 8),
                    font=("Segoe UI Semibold", 10))
        s.map("Save.TButton", background=[("active", "#8ad100")])
        s.configure("E.TCheckbutton", background=CARD, foreground=FG,
                    focuscolor=CARD)
        s.map("E.TCheckbutton", background=[("active", CARD)])
        s.configure("E.TCombobox", fieldbackground=PANEL, background=PANEL,
                    foreground=FG, arrowcolor=MUTED)
        s.configure("E.Horizontal.TScale", background=CARD, troughcolor="#2a2f37")

    # ------------------------------------------------------------------
    def _build(self):
        head = ttk.Frame(self, style="E.TFrame")
        head.pack(fill="x", padx=16, pady=(14, 8))
        ttk.Label(head, text=self.game.name, style="Title.TLabel").pack(anchor="w")
        ttk.Label(head, text=os.path.basename(os.path.dirname(self.ini_path))
                  + "  ·  OptiScaler.ini", style="Sub.TLabel").pack(anchor="w")

        # scrollable area
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="both", expand=True, padx=10)
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0, bd=0)
        bar = ttk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas, style="E.TFrame")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.bind("<Configure>",
                         lambda e: self.canvas.itemconfig(self.win, width=e.width))
        self.canvas.configure(yscrollcommand=bar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        bar.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", self._wheel)

        self._render()

        foot = ttk.Frame(self, style="E.TFrame")
        foot.pack(fill="x", padx=16, pady=12)
        ttk.Button(foot, text="Save", style="Save.TButton",
                   command=self._save).pack(side="right")
        ttk.Button(foot, text="Close", style="E.TButton",
                   command=self.destroy).pack(side="right", padx=(0, 8))
        ttk.Button(foot, text="Reset", style="E.TButton",
                   command=self._reset).pack(side="left")

    def _wheel(self, event):
        try:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    def _render(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.vars.clear()

        for gid, title, subtitle, items in opts.GROUPS:
            self._group(gid, title, subtitle, items)

        self._overlay_note()

    def _group(self, gid, title, subtitle, items):
        opened = gid in self.open_groups

        head = tk.Frame(self.inner, bg=BG, cursor="hand2")
        head.pack(fill="x", pady=(10, 0))
        arrow = "▾" if opened else "▸"
        lbl = tk.Label(head, text=f"{arrow}  {title}", bg=BG, fg=FG,
                       font=("Segoe UI Semibold", 10), anchor="w")
        lbl.pack(fill="x")
        sub = tk.Label(head, text="     " + subtitle, bg=BG, fg=DIM,
                       font=("Segoe UI", 8), anchor="w")
        sub.pack(fill="x")

        def toggle(_e=None):
            if gid in self.open_groups:
                self.open_groups.discard(gid)
            else:
                self.open_groups.add(gid)
            self._render()

        for w in (head, lbl, sub):
            w.bind("<Button-1>", toggle)

        if not opened:
            return

        body = ttk.Frame(self.inner, style="Card.TFrame")
        body.pack(fill="x", pady=(6, 2))
        for sect, key, label, kind, extra, help_ in items:
            self._row(body, sect, key, label, kind, extra, help_)

    # ------------------------------------------------------------------
    def _current(self, sect: str, key: str) -> str:
        return self.data.get(sect, {}).get(key, "auto")

    def _row(self, parent, sect, key, label, kind, extra, help_):
        row = tk.Frame(parent, bg=CARD)
        row.pack(fill="x", padx=12, pady=(9, 0))

        top = tk.Frame(row, bg=CARD)
        top.pack(fill="x")
        tk.Label(top, text=label, bg=CARD, fg=FG, anchor="w",
                 font=("Segoe UI", 9)).pack(side="left")

        raw = self._current(sect, key)
        ident = (sect, key)

        if kind == "bool":
            var = tk.StringVar(value=raw)
            self.vars[ident] = var
            box = ttk.Combobox(top, textvariable=var, state="readonly", width=12,
                               values=["auto", "true", "false"], style="E.TCombobox")
            box.pack(side="right")

        elif kind == "choice":
            labels = ["auto"] + [f"{v}  {t}" for v, t in extra]
            var = tk.StringVar()
            match = next((f"{v}  {t}" for v, t in extra if v == raw), None)
            var.set(match or ("auto" if raw == "auto" else raw))
            self.vars[ident] = var
            box = ttk.Combobox(top, textvariable=var, state="readonly", width=22,
                               values=labels, style="E.TCombobox")
            box.pack(side="right")

        else:  # float / int
            lo, hi, step = extra
            var = tk.StringVar(value=raw)
            self.vars[ident] = var
            shown = tk.Label(top, text=raw, bg=CARD, fg=ACCENT, width=7,
                             anchor="e", font=("Consolas", 9))
            shown.pack(side="right")

            try:
                start = float(raw)
            except ValueError:
                start = lo

            # ttk.Scale.set() fires the callback, so without this guard merely
            # building the control would mark the setting as changed -- and
            # saving would overwrite everything left at 'auto' with the slider
            # minimum. Only a real drag counts.
            state = {"armed": False}

            def on_move(v, var=var, shown=shown, kind=kind, step=step,
                        state=state):
                if not state["armed"]:
                    return
                x = round(float(v) / step) * step
                txt = str(int(x)) if kind == "int" else f"{x:.2f}"
                var.set(txt)
                shown.configure(text=txt, fg=ACCENT)

            sc = ttk.Scale(row, from_=lo, to=hi, orient="horizontal",
                           command=on_move, style="E.Horizontal.TScale")
            sc.set(start)
            sc.pack(fill="x", pady=(4, 0))
            if raw == "auto":
                shown.configure(text="auto", fg=MUTED)
            sc.after_idle(lambda s=state: s.__setitem__("armed", True))

            def to_auto(_e=None, var=var, shown=shown):
                var.set("auto")
                shown.configure(text="auto", fg=MUTED)
            shown.bind("<Button-1>", to_auto)

        if help_:
            tk.Label(row, text=help_, bg=CARD, fg=DIM, anchor="w",
                     justify="left", wraplength=520,
                     font=("Segoe UI", 8)).pack(fill="x", pady=(3, 6))
        else:
            tk.Frame(row, bg=CARD, height=4).pack()

    # ------------------------------------------------------------------
    def _overlay_note(self):
        box = ttk.Frame(self.inner, style="Card.TFrame")
        box.pack(fill="x", pady=(16, 14))
        tk.Label(box, text="In-game only  (F8)", bg=CARD, fg=FG,
                 font=("Segoe UI Semibold", 9), anchor="w").pack(
                     fill="x", padx=12, pady=(10, 2))
        tk.Label(box, text="These are not INI keys, so no external window can "
                           "touch them. Change them in the overlay, live.",
                 bg=CARD, fg=MUTED, anchor="w", justify="left", wraplength=520,
                 font=("Segoe UI", 8)).pack(fill="x", padx=12)
        for name, desc in opts.OVERLAY_ONLY:
            tk.Label(box, text="·  " + name, bg=CARD, fg=ACCENT, anchor="w",
                     font=("Segoe UI", 9)).pack(fill="x", padx=12, pady=(8, 0))
            tk.Label(box, text="   " + desc, bg=CARD, fg=DIM, anchor="w",
                     justify="left", wraplength=510,
                     font=("Segoe UI", 8)).pack(fill="x", padx=12)
        tk.Frame(box, bg=CARD, height=10).pack()

    # ------------------------------------------------------------------
    def _collect(self) -> dict[str, dict[str, str]]:
        """Only what differs from what the file already holds."""
        changes: dict[str, dict[str, str]] = {}
        for (sect, key), var in self.vars.items():
            value = var.get().strip()
            if "  " in value:                     # "11  K (transformer)"
                value = value.split("  ", 1)[0]
            if value != self._current(sect, key):
                changes.setdefault(sect, {})[key] = value
        return changes

    def _save(self):
        changes = self._collect()
        if not changes:
            messagebox.showinfo("Settings", "Nothing changed.", parent=self)
            return
        n = sum(len(v) for v in changes.values())
        try:
            apply_mod.set_ini(self.ini_path, changes)
        except OSError as e:
            messagebox.showerror("Settings", f"Could not write the INI:\n{e}",
                                 parent=self)
            return
        self.data = apply_mod.read_ini(self.ini_path)
        if self.on_saved:
            self.on_saved(f"{n} settings saved to {self.game.name}")
        messagebox.showinfo("Settings",
                            f"{n} settings saved.\n\n"
                            "Changes take effect when the game starts. "
                            "For live tweaks, press F8 in game.",
                            parent=self)

    def _reset(self):
        if not messagebox.askyesno(
                "Reset",
                "Return every setting here to 'auto'?\n\n"
                "Auto is OptiScaler's default, not necessarily what "
                "you had before.", parent=self):
            return
        changes: dict[str, dict[str, str]] = {}
        for gid, _t, _s, items in opts.GROUPS:
            for sect, key, *_ in items:
                changes.setdefault(sect, {})[key] = "auto"
        apply_mod.set_ini(self.ini_path, changes)
        self.data = apply_mod.read_ini(self.ini_path)
        self._render()
        if self.on_saved:
            self.on_saved(f"Settings reset in {self.game.name}")
