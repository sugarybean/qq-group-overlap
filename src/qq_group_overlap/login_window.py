from __future__ import annotations

import argparse
import os
import tkinter as tk
from pathlib import Path


PAPER = "#F6F5F1"
PANEL = "#FFFFFF"
INK = "#171A18"
MUTED = "#676B66"
BORDER = "#C9C7BE"
ACCENT = "#0C756B"
ACCENT_SOFT = "#DCECE8"
POLL_MS = 300


def qr_is_current(path: Path, *, not_before: float) -> bool:
    try:
        stat = path.stat()
    except OSError:
        return False
    return stat.st_size > 0 and stat.st_mtime >= not_before


class LoginWindow:
    def __init__(self, root: tk.Tk, *, qr_path: Path, not_before: float) -> None:
        self.root = root
        self.qr_path = qr_path
        self.not_before = not_before
        self.parent_pid = os.getppid()
        self.loaded_mtime_ns: int | None = None
        self.qr_image: tk.PhotoImage | None = None

        root.title("登录 QQ")
        root.geometry("420x510")
        root.resizable(False, False)
        root.configure(background=PAPER)
        root.protocol("WM_DELETE_WINDOW", root.destroy)

        main = tk.Frame(root, background=PAPER, padx=28, pady=24)
        main.pack(fill="both", expand=True)

        tk.Label(
            main,
            text="登录 QQ",
            anchor="w",
            background=PAPER,
            foreground=INK,
            font=("TkDefaultFont", 20, "bold"),
        ).pack(fill="x")
        tk.Label(
            main,
            text="用手机 QQ 扫描下方二维码。以你扫码确认的账号为准。",
            anchor="w",
            justify="left",
            wraplength=350,
            background=PAPER,
            foreground=MUTED,
            font=("TkDefaultFont", 10),
        ).pack(fill="x", pady=(6, 18))

        qr_panel = tk.Frame(
            main,
            width=320,
            height=320,
            background=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        qr_panel.pack()
        qr_panel.pack_propagate(False)
        self.qr_label = tk.Label(
            qr_panel,
            text="正在等待二维码…",
            background=PANEL,
            foreground=MUTED,
            font=("TkDefaultFont", 11),
        )
        self.qr_label.pack(fill="both", expand=True, padx=12, pady=12)

        self.status_label = tk.Label(
            main,
            text="二维码只显示在本机，不会写入报告。",
            anchor="w",
            background=PAPER,
            foreground=MUTED,
            font=("TkDefaultFont", 9),
        )
        self.status_label.pack(fill="x", pady=(14, 10))

        close_button = tk.Button(
            main,
            text="已扫码，关闭窗口",
            command=root.destroy,
            background=ACCENT,
            foreground="#FFFFFF",
            activebackground="#095F57",
            activeforeground="#FFFFFF",
            relief="flat",
            borderwidth=0,
            highlightbackground=ACCENT_SOFT,
            highlightthickness=2,
            padx=16,
            pady=9,
            font=("TkDefaultFont", 10, "bold"),
            cursor="hand2",
        )
        close_button.pack(fill="x")

        root.lift()
        root.attributes("-topmost", True)
        root.after(1000, lambda: root.attributes("-topmost", False))
        root.after(50, self._poll)

    def _poll(self) -> None:
        if os.getppid() != self.parent_pid:
            self.root.destroy()
            return

        if qr_is_current(self.qr_path, not_before=self.not_before):
            try:
                mtime_ns = self.qr_path.stat().st_mtime_ns
                if mtime_ns != self.loaded_mtime_ns:
                    image = tk.PhotoImage(file=str(self.qr_path))
                    if image.width() <= 160 and image.height() <= 160:
                        image = image.zoom(2, 2)
                    self.qr_image = image
                    self.qr_label.configure(image=image, text="")
                    self.loaded_mtime_ns = mtime_ns
                    self.status_label.configure(
                        text="扫码确认后，点击下方按钮。NapCat 会继续运行。"
                    )
            except (OSError, tk.TclError):
                self.status_label.configure(text="二维码正在生成，请稍候…")

        if self.root.winfo_exists():
            self.root.after(POLL_MS, self._poll)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Show the local NapCat login QR.")
    parser.add_argument("--qr-path", required=True, type=Path)
    parser.add_argument("--not-before", required=True, type=float)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    root = tk.Tk()
    LoginWindow(root, qr_path=args.qr_path, not_before=args.not_before)
    root.mainloop()


if __name__ == "__main__":
    main()
