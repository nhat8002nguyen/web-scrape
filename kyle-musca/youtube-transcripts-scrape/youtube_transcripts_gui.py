#!/usr/bin/env python3
"""
Simple desktop shell for download_channel_transcripts.py — paste channel URL and Webshare
credentials, choose output folder, run. Intended for PyInstaller macOS .app bundles.
"""

from __future__ import annotations

import queue
import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, scrolledtext, ttk

import download_channel_transcripts as scraper


class _QueueWriter:
    """Send print()/logging writes into a queue consumed by the Tk main thread."""

    def __init__(self, q: queue.Queue[str | None]) -> None:
        self._q = q

    def write(self, s: str) -> int:
        if s:
            self._q.put(s)
        return len(s)

    def flush(self) -> None:
        pass


def _default_output_dir() -> Path:
    base = Path.home() / "Documents" / "YouTubeTranscripts"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _focus_widget_after_click(event: tk.Event) -> None:
    """
    Tk/macOS often mishandles first click into ttk.Entry (needs extra clicks).
    Deferring focus_set until idle fixes ordering vs Tk's default bindings.
    """
    widget = event.widget

    def apply_focus() -> None:
        try:
            widget.focus_set()
        except tk.TclError:
            pass

    widget.after_idle(apply_focus)


class TranscriptApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("YouTube channel transcripts")
        self.minsize(640, 620)
        self.geometry("760x680")

        self._log_queue: queue.Queue[str | None] = queue.Queue()
        self._worker: threading.Thread | None = None

        pad = {"padx": 12, "pady": 6}

        frm = ttk.Frame(self)
        frm.pack(fill=tk.BOTH, expand=True, **pad)

        ttk.Label(frm, text="Channel URL").grid(row=0, column=0, sticky=tk.W)
        self.channel_var = tk.StringVar()
        self.channel_entry = ttk.Entry(frm, textvariable=self.channel_var, width=72)
        self.channel_entry.grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=(0, 8))

        ttk.Label(frm, text="Webshare proxy username").grid(row=2, column=0, sticky=tk.W)
        self.ws_user_var = tk.StringVar()
        self.ws_user_entry = ttk.Entry(frm, textvariable=self.ws_user_var, width=48)
        self.ws_user_entry.grid(row=3, column=0, columnspan=3, sticky=tk.EW, pady=(0, 8))

        ttk.Label(frm, text="Webshare proxy password").grid(row=4, column=0, sticky=tk.W)
        self.ws_pass_var = tk.StringVar()
        self.ws_pass_entry = ttk.Entry(
            frm, textvariable=self.ws_pass_var, width=48, show="•"
        )
        self.ws_pass_entry.grid(row=5, column=0, columnspan=3, sticky=tk.EW, pady=(0, 8))

        self.out_var = tk.StringVar(value=str(_default_output_dir()))
        row_out = ttk.Frame(frm)
        row_out.grid(row=6, column=0, columnspan=3, sticky=tk.EW, pady=(0, 8))
        ttk.Label(row_out, text="Output folder").pack(side=tk.LEFT)
        ttk.Button(row_out, text="Choose…", command=self._pick_out).pack(
            side=tk.RIGHT, padx=(8, 0)
        )
        self.out_entry = ttk.Entry(row_out, textvariable=self.out_var)
        self.out_entry.pack(fill=tk.X, expand=True, padx=(12, 0))

        videos_frm = ttk.Frame(frm)
        videos_frm.grid(row=7, column=0, columnspan=3, sticky=tk.EW, pady=(0, 10))
        ttk.Label(videos_frm, text="Videos to download").pack(anchor=tk.W)
        self.video_scope_var = tk.StringVar(value="all")
        ttk.Radiobutton(
            videos_frm,
            text="All videos on the channel",
            variable=self.video_scope_var,
            value="all",
            command=self._sync_limit_spin_state,
        ).pack(anchor=tk.W, pady=(4, 0))

        row_lim = ttk.Frame(videos_frm)
        row_lim.pack(fill=tk.X, pady=(2, 0))
        ttk.Radiobutton(
            row_lim,
            text="Only the first",
            variable=self.video_scope_var,
            value="limit",
            command=self._sync_limit_spin_state,
        ).pack(side=tk.LEFT)
        self.limit_n_var = tk.StringVar(value="50")
        # Classic tk Spinbox: more reliable on macOS than ttk.Spinbox with some Tk builds.
        self.limit_spin = tk.Spinbox(
            row_lim,
            from_=1,
            to=999_999,
            width=10,
            textvariable=self.limit_n_var,
            wrap=False,
        )
        self.limit_spin.pack(side=tk.LEFT, padx=(6, 6))
        ttk.Label(row_lim, text="videos (channel upload order)").pack(side=tk.LEFT)
        self._sync_limit_spin_state()

        for entry_like in (
            self.channel_entry,
            self.ws_user_entry,
            self.ws_pass_entry,
            self.out_entry,
            self.limit_spin,
        ):
            entry_like.bind("<Button-1>", _focus_widget_after_click, add="+")

        self.resume_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frm,
            text="Resume — skip videos that already have a .txt file in the output folder",
            variable=self.resume_var,
        ).grid(row=8, column=0, columnspan=3, sticky=tk.W, pady=(0, 8))

        btn_row = ttk.Frame(frm)
        btn_row.grid(row=9, column=0, columnspan=3, sticky=tk.EW, pady=(0, 8))
        self.run_btn = ttk.Button(btn_row, text="Download transcripts", command=self._run)
        self.run_btn.pack(side=tk.LEFT)

        self.progress = ttk.Progressbar(
            btn_row,
            mode="indeterminate",
            length=220,
            takefocus=False,
        )
        self.progress.pack(side=tk.RIGHT)

        ttk.Label(frm, text="Log").grid(row=10, column=0, sticky=tk.W)
        log_font = tkfont.nametofont("TkFixedFont")
        log_font.configure(size=11)
        self.log_text = scrolledtext.ScrolledText(
            frm,
            height=18,
            wrap=tk.WORD,
            font=log_font,
            state=tk.DISABLED,
            takefocus=False,
        )
        self.log_text.grid(row=11, column=0, columnspan=3, sticky=tk.NSEW)

        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(11, weight=1)

        self.after(120, self._drain_log_queue)

    def _sync_limit_spin_state(self) -> None:
        state = (
            tk.NORMAL if self.video_scope_var.get() == "limit" else tk.DISABLED
        )
        self.limit_spin.configure(state=state)

    def _pick_out(self) -> None:
        path = filedialog.askdirectory(
            title="Choose output folder",
            initialdir=self.out_var.get() or str(Path.home()),
        )
        if path:
            self.out_var.set(path)

    def _append_log(self, s: str) -> None:
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, s)
        self.log_text.see(tk.END)
        self.log_text.configure(state=tk.DISABLED)

    def _drain_log_queue(self) -> None:
        finished = False
        try:
            while True:
                chunk = self._log_queue.get_nowait()
                if chunk is None:
                    finished = True
                    break
                self._append_log(chunk)
        except queue.Empty:
            pass
        if finished:
            self._on_worker_finished()
        self.after(120, self._drain_log_queue)

    def _on_worker_finished(self) -> None:
        self.progress.stop()
        self.run_btn.configure(state=tk.NORMAL)
        self._worker = None

    def _run(self) -> None:
        if self._worker is not None and self._worker.is_alive():
            messagebox.showinfo("Busy", "A download is already running.")
            return

        channel = (self.channel_var.get() or "").strip()
        ws_user = (self.ws_user_var.get() or "").strip()
        ws_pass = (self.ws_pass_var.get() or "").strip()
        out_path = Path((self.out_var.get() or "").strip()).expanduser()

        if not channel:
            messagebox.showerror("Missing URL", "Enter the full YouTube channel URL.")
            return
        if not ws_user or not ws_pass:
            messagebox.showerror(
                "Missing Webshare credentials",
                "Enter Webshare proxy username and password from your dashboard.",
            )
            return

        try:
            out_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Output folder", str(exc))
            return

        limit_n: int | None = None
        if self.video_scope_var.get() == "limit":
            raw_n = (self.limit_n_var.get() or "").strip()
            try:
                limit_n = int(raw_n)
            except ValueError:
                messagebox.showerror(
                    "Video count",
                    "Enter a whole number for how many videos to download (1 or more).",
                )
                return
            if limit_n < 1:
                messagebox.showerror(
                    "Video count",
                    "The limit must be at least 1.",
                )
                return

        argv = [
            channel,
            "--out",
            str(out_path.resolve()),
            "--webshare-user",
            ws_user,
            "--webshare-password",
            ws_pass,
        ]
        if limit_n is not None:
            argv.extend(["--limit", str(limit_n)])
        if self.resume_var.get():
            argv.append("--resume")

        self.log_text.configure(state=tk.NORMAL)
        self.log_text.delete("1.0", tk.END)
        self.log_text.configure(state=tk.DISABLED)

        self.run_btn.configure(state=tk.DISABLED)
        self.progress.start(12)

        self._worker = threading.Thread(
            target=self._worker_main,
            args=(argv,),
            daemon=True,
        )
        self._worker.start()

    def _worker_main(self, argv: list[str]) -> None:
        exit_code = 1
        old_out, old_err = sys.stdout, sys.stderr
        qw = _QueueWriter(self._log_queue)
        try:
            sys.stdout = qw
            sys.stderr = qw
            exit_code = scraper.main(argv)
        except BaseException:
            tb = traceback.format_exc()
            self._log_queue.put(tb)
            exit_code = 1
        finally:
            sys.stdout = old_out
            sys.stderr = old_err
            self._log_queue.put(f"\n--- Exit code: {exit_code} ---\n")
            self._log_queue.put(None)


def main() -> None:
    app = TranscriptApp()
    app.mainloop()


if __name__ == "__main__":
    main()
