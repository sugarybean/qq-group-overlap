from __future__ import annotations

import argparse
import os
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .gui_support import (
    filter_group_summaries,
    format_level_summary,
    page_items,
    update_group_selection,
    write_top_csv,
)
from .io import InputError, load_memberships, merge_snapshot_groups
from .login_window import qr_is_current
from .models import Membership
from .napcat_runtime import (
    ONEBOT_HOST,
    ONEBOT_PORT,
    NapCatSession,
    RuntimeBootstrapError,
    ensure_runtime,
    load_or_create_token,
)
from .onebot import OneBotClient, OneBotError
from .paths import default_snapshot_path
from .score import (
    DEFAULT_SCORE_FORMULA,
    SCORE_FORMULA_PRESETS,
    GroupSummary,
    WeightedOverlap,
    rank_selected_groups,
    summarize_groups,
)


PAPER = "#F6F5F1"
PANEL = "#FFFFFF"
INK = "#171A18"
MUTED = "#676B66"
BORDER = "#C9C7BE"
ACCENT = "#0C756B"
ACCENT_SOFT = "#DCECE8"
ERROR = "#B13A34"
WARNING = "#8A5B00"


class OverlapApp(ttk.Frame):
    def __init__(
        self,
        master: tk.Tk,
        *,
        snapshot_path: Path,
        timeout: float,
        integrated: bool = True,
        api_url: str | None = None,
        api_token: str | None = None,
        token_environment: str | None = None,
    ) -> None:
        super().__init__(master, padding=20, style="App.TFrame")
        self.master = master
        self.snapshot_path = snapshot_path
        self.timeout = timeout
        self.integrated = integrated
        self.api_url = api_url or f"http://{ONEBOT_HOST}:{ONEBOT_PORT}"
        if api_token:
            self.api_token = api_token
        elif not integrated and token_environment:
            self.api_token = os.environ.get(token_environment, "")
        else:
            self.api_token = ""
        self.token_environment = token_environment
        self.self_id: str | None = None
        self._session: NapCatSession | None = None
        self._login_start_time = 0.0
        self._progress_pulsing = False
        self.qr_image = None

        self.memberships: list[Membership] = []
        self.groups: list[GroupSummary] = []
        self.selected_group_ids: set[str] = set()
        self.excluded_users: set[str] = set()
        self.ranked: list[WeightedOverlap] = []
        self.page_index = 0
        self.busy = False
        self.updating_group_tree = False
        self.special_group_ids: set[str] = set()
        self.marking_special = False

        self.search_var = tk.StringVar()
        self.selection_var = tk.StringVar(value="已选择 0 个群")
        self.page_size_var = tk.StringVar(value="100")
        self.page_var = tk.StringVar(value="第 0 / 0 页")
        self.min_groups_var = tk.StringVar(value="2")
        self.formula_preset_var = tk.StringVar(value="对数等级（默认）")
        self.formula_var = tk.StringVar(value=DEFAULT_SCORE_FORMULA)
        self.status_var = tk.StringVar(value="正在准备 QQ 连接组件…")
        self.status_color = MUTED
        self.formula_var.trace_add("write", self._formula_changed)

        self._configure_window()
        self._configure_styles()
        self.main_view = ttk.Frame(self, style="App.TFrame")
        self._build_login_view()
        self._start_flow()

    def _configure_window(self) -> None:
        self.master.title("QQ 群同好线索")
        self.master.geometry("480x600")
        self.master.minsize(420, 560)
        self.master.configure(background=PAPER)
        self.pack(fill="both", expand=True)

    def _configure_styles(self) -> None:
        style = ttk.Style(self.master)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("App.TFrame", background=PAPER)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("App.TLabel", background=PAPER, foreground=INK, font=("TkDefaultFont", 10))
        style.configure("Panel.TLabel", background=PANEL, foreground=INK, font=("TkDefaultFont", 10))
        style.configure("Title.TLabel", background=PAPER, foreground=INK, font=("TkDefaultFont", 20, "bold"))
        style.configure("Subtitle.TLabel", background=PAPER, foreground=MUTED, font=("TkDefaultFont", 10))
        style.configure("Section.TLabel", background=PANEL, foreground=INK, font=("TkDefaultFont", 11, "bold"))
        style.configure("Hint.TLabel", background=PANEL, foreground=MUTED, font=("TkDefaultFont", 9))
        style.configure("Target.TLabel", background=ACCENT_SOFT, foreground="#084E48", font=("TkDefaultFont", 10, "bold"), padding=(8, 5))
        style.configure("Primary.TButton", background=ACCENT, foreground="#FFFFFF", bordercolor=ACCENT, focuscolor=ACCENT_SOFT, padding=(16, 8), font=("TkDefaultFont", 10, "bold"))
        style.map("Primary.TButton", background=[("active", "#095F57"), ("disabled", "#9DBCB7")])
        style.configure("Secondary.TButton", background=PANEL, foreground=INK, bordercolor=BORDER, focuscolor=ACCENT_SOFT, padding=(10, 7))
        style.map("Secondary.TButton", background=[("active", "#ECEAE3")])
        style.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=INK, bordercolor=BORDER, rowheight=27, font=("TkDefaultFont", 10))
        style.configure("Treeview.Heading", background="#ECEAE3", foreground=INK, bordercolor=BORDER, font=("TkDefaultFont", 9, "bold"), padding=(6, 6))
        style.map("Treeview", background=[("selected", ACCENT)], foreground=[("selected", "#FFFFFF")])

    # -- login / bootstrap flow -------------------------------------------

    def _build_login_view(self) -> None:
        self.login_view = ttk.Frame(self, padding=28, style="App.TFrame")
        self.login_view.pack(fill="both", expand=True)

        ttk.Label(self.login_view, text="QQ 群同好线索", style="Title.TLabel").pack(anchor="w")
        self.login_subtitle = ttk.Label(
            self.login_view,
            text="首次使用会自动下载并启动 QQ 连接组件（NapCat）。准备好后用手机 QQ 扫码登录。",
            style="Subtitle.TLabel",
        )
        self.login_subtitle.pack(anchor="w", pady=(4, 16))

        self.login_status = ttk.Label(
            self.login_view,
            text="正在准备 QQ 连接组件…",
            style="Panel.TLabel",
            wraplength=400,
            justify="left",
        )
        self.login_status.pack(anchor="w", pady=(0, 8))
        self.login_progress = ttk.Progressbar(
            self.login_view, orient="horizontal", length=380, mode="indeterminate"
        )
        self.login_progress.pack(fill="x", pady=(0, 16))

        self.qr_panel = tk.Frame(
            self.login_view,
            width=320,
            height=320,
            background=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        self.qr_panel.pack()
        self.qr_panel.pack_propagate(False)
        self.qr_label = tk.Label(
            self.qr_panel,
            text="正在等待二维码…",
            background=PANEL,
            foreground=MUTED,
            font=("TkDefaultFont", 11),
        )
        self.qr_label.pack(fill="both", expand=True, padx=12, pady=12)

        self.login_note = ttk.Label(
            self.login_view,
            text="二维码只在本机显示，不会写入任何报告。",
            style="Hint.TLabel",
        )
        self.login_note.pack(anchor="w", pady=(14, 10))

        btn_row = ttk.Frame(self.login_view, style="App.TFrame")
        btn_row.pack(fill="x", pady=(8, 0))
        self.retry_button = ttk.Button(
            btn_row, text="重试", command=self._retry, style="Secondary.TButton"
        )
        self.retry_button.pack(side="right")
        self.retry_button.pack_forget()
        ttk.Button(
            btn_row,
            text="退出",
            command=self.master.destroy,
            style="Secondary.TButton",
        ).pack(side="right", padx=(0, 8))

    def _start_flow(self) -> None:
        if self.integrated:
            self._set_login_status("正在准备 QQ 连接组件（首次使用会下载 NapCat）…")
            threading.Thread(target=self._bootstrap_worker, daemon=True).start()
        else:
            # 连接到已运行的 NapCat：跳过下载 / 扫码，直接进入主界面
            self._enter_main_view()

    def _bootstrap_worker(self) -> None:
        try:
            ensure_runtime(
                progress=lambda msg, frac: self.master.after(
                    0, self._report_progress, msg, frac
                ),
                base=None,
            )
        except RuntimeBootstrapError as exc:
            self.master.after(0, self._login_failed, f"无法准备 QQ 连接组件：{exc}")
            return

        token = load_or_create_token()
        self.api_token = token
        session = NapCatSession(
            token,
            base=None,
            log=lambda msg: self.master.after(0, self._report_progress, msg, None),
        )
        try:
            session.start()
        except RuntimeBootstrapError as exc:
            self.master.after(0, self._login_failed, f"无法启动 QQ 连接组件：{exc}")
            return

        self._session = session
        self._login_start_time = time.time()
        # 复用上次的登录状态：若已登录则直接进入主界面，无需再次扫码
        try:
            uin = session.current_uin()
        except Exception:
            uin = None
        if uin:
            self.master.after(0, self._on_logged_in, uin)
            return
        self.master.after(0, self._begin_scan_phase)

    def _begin_scan_phase(self) -> None:
        self.login_subtitle.configure(
            text="请用手机 QQ 扫描下方二维码登录；扫码确认的账号将作为分析基准。"
        )
        self.login_progress.pack_forget()
        self.qr_label.configure(text="正在生成二维码…")
        self.login_note.configure(
            text="二维码只在本机显示，不会写入任何报告。登录成功后自动进入分析界面。"
        )
        self._poll_login()

    def _poll_login(self) -> None:
        session = self._session
        if session is None:
            return
        if not session.is_running():
            self._login_failed("QQ 连接组件在登录前退出，请点「重试」。")
            return
        uin = session.current_uin()
        if uin:
            self._on_logged_in(uin)
            return
        qr_path = session.qr_path
        if qr_is_current(qr_path, not_before=self._login_start_time):
            try:
                self._display_qr(qr_path)
            except (OSError, tk.TclError):
                self.login_status.configure(text="二维码正在写入，请稍候…")
        else:
            self.login_status.configure(text="正在生成二维码，请稍候…")
        self.master.after(500, self._poll_login)

    def _display_qr(self, path: Path) -> None:
        image = tk.PhotoImage(file=str(path))
        if image.width() <= 160 and image.height() <= 160:
            image = image.zoom(2, 2)
        self.qr_image = image
        self.qr_label.configure(image=image, text="")
        self.login_status.configure(text="二维码已就绪，请用手机 QQ 扫码；确认后自动进入。")

    def _report_progress(self, message: str, fraction: float | None) -> None:
        if not hasattr(self, "login_status"):
            return
        self.login_status.configure(text=message)
        if fraction is None:
            if not self._progress_pulsing:
                self.login_progress.configure(mode="indeterminate")
                self.login_progress.start(20)
                self._progress_pulsing = True
        else:
            if self._progress_pulsing:
                self.login_progress.stop()
                self._progress_pulsing = False
            self.login_progress.configure(mode="determinate", maximum=1.0, value=fraction)

    def _on_logged_in(self, uin: str) -> None:
        self.self_id = uin
        self.excluded_users = {uin}
        if self._session is not None:
            self.api_url = self._session.api_url
        if hasattr(self, "login_view"):
            self.login_view.destroy()
            self.login_view = None
        self._enter_main_view()

    def _enter_main_view(self) -> None:
        if hasattr(self, "login_view") and self.login_view is not None:
            self.login_view.destroy()
            self.login_view = None
        self.master.geometry("1320x760")
        self.master.minsize(980, 640)
        self.main_view.pack(fill="both", expand=True)
        self._build_ui(self.main_view)
        self._bind_shortcuts()
        self._load_snapshot()
        self._populate_groups_from_qq()
        if self.self_id:
            self._set_status(
                f"已登录 QQ {self.self_id}（已自动排除你的账号）。"
                "选群后点「只刷新已选群等级」即可拉取成员并出结果。"
            )
        else:
            self._set_status(
                "已连接 QQ 连接组件。选群后点「只刷新已选群等级」即可拉取成员并出结果。"
            )

    def _populate_groups_from_qq(self) -> None:
        def worker() -> None:
            try:
                client = OneBotClient(self.api_url, self.api_token, self.timeout)
                self_id = client.get_login_user_id()
                available = client.list_groups()
            except (OneBotError, OSError) as exc:
                self.master.after(
                    0,
                    lambda: self._set_status(
                        f"无法获取你的群列表：{exc}（可稍后再试）", kind="warning"
                    ),
                )
                return
            self.master.after(0, self._set_self_id, self_id)
            self.master.after(0, self._merge_catalog, available)

        threading.Thread(target=worker, daemon=True).start()

    def _set_self_id(self, uin: str) -> None:
        self.self_id = uin
        self.excluded_users = {uin}

    def _merge_catalog(self, available: list[dict[str, object]]) -> None:
        existing = {group.group_id: group for group in self.groups}
        merged: list[GroupSummary] = []
        for item in available:
            group_id = str(item.get("group_id") or "")
            if not group_id:
                continue
            name = str(item.get("group_name") or group_id)
            try:
                member_count = int(item.get("member_count") or 0)
            except (TypeError, ValueError):
                member_count = 0
            previous = existing.pop(group_id, None)
            if previous is not None:
                merged.append(
                    GroupSummary(group_id, name, member_count, previous.level_count)
                )
            else:
                merged.append(GroupSummary(group_id, name, member_count, 0))
        merged.extend(existing.values())
        merged.sort(key=lambda group: (group.group_name.casefold(), group.group_id))
        self.groups = merged
        self._refresh_group_tree()
        self._update_selection_labels()

    def _set_login_status(self, message: str) -> None:
        if hasattr(self, "login_status"):
            self.login_status.configure(text=message)

    def _login_failed(self, message: str) -> None:
        self._progress_pulsing = False
        if hasattr(self, "login_progress"):
            try:
                self.login_progress.stop()
            except Exception:
                pass
        if hasattr(self, "login_status"):
            self.login_status.configure(text=f"出错了：{message}")
        if hasattr(self, "qr_label"):
            self.qr_label.configure(image="", text="准备失败，可点「重试」。")
        if hasattr(self, "retry_button"):
            self.retry_button.pack(side="right")

    def _retry(self) -> None:
        if hasattr(self, "retry_button"):
            self.retry_button.pack_forget()
        self._progress_pulsing = False
        self._set_login_status("正在准备 QQ 连接组件…")
        self.login_progress.configure(mode="indeterminate")
        self.login_progress.pack(fill="x", pady=(0, 16))
        threading.Thread(target=self._bootstrap_worker, daemon=True).start()

    def _build_ui(self, parent: ttk.Frame) -> None:
        header = ttk.Frame(parent, style="App.TFrame")
        header.pack(fill="x", pady=(0, 16))
        ttk.Label(header, text="QQ 群同好线索", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="选择多个群，寻找其中重复出现的人；结果无人数上限，按页查看并可完整导出。",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        body = ttk.Panedwindow(parent, orient="horizontal")
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, padding=16, style="Panel.TFrame")
        right = ttk.Frame(body, padding=16, style="Panel.TFrame")
        body.add(left, weight=2)
        body.add(right, weight=4)
        self._build_group_panel(left)
        self._build_result_panel(right)

        status = tk.Label(
            parent,
            textvariable=self.status_var,
            anchor="w",
            background=PAPER,
            foreground=MUTED,
            font=("TkDefaultFont", 9),
            padx=2,
            pady=8,
        )
        status.pack(fill="x")
        self.status_label = status

    def _build_group_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="1  搜索并选群", style="Section.TLabel").pack(anchor="w")
        ttk.Label(
            parent,
            text=(
                "例如搜“自动化”。单击选一个群；按住 Ctrl 增减，Shift 连选一段。\n"
                "按住 Ctrl+X 时点选的群会标为「特别关照」（★），结果必须包含它们。"
            ),
            style="Hint.TLabel",
            wraplength=370,
            justify="left",
        ).pack(anchor="w", pady=(5, 10))

        search_row = ttk.Frame(parent, style="Panel.TFrame")
        search_row.pack(fill="x", pady=(0, 10))
        ttk.Label(search_row, text="群名 / 群号", style="Panel.TLabel").pack(side="left")
        self.search_entry = ttk.Entry(search_row, textvariable=self.search_var)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=(10, 0))
        self.search_var.trace_add("write", lambda *_args: self._refresh_group_tree())

        table_frame = ttk.Frame(parent, style="Panel.TFrame")
        table_frame.pack(fill="both", expand=True)
        columns = ("chosen", "name", "id", "members", "levels")
        self.group_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            selectmode="extended",
            height=10,
        )
        headings = {
            "chosen": "已选",
            "name": "群名",
            "id": "群号",
            "members": "人数",
            "levels": "等级",
        }
        widths = {"chosen": 44, "name": 140, "id": 72, "members": 40, "levels": 44}
        for column in columns:
            self.group_tree.heading(column, text=headings[column])
            self.group_tree.column(
                column,
                width=widths[column],
                minwidth=40,
                anchor="w" if column == "name" else "center" if column == "chosen" else "e",
                stretch=column == "name",
            )
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.group_tree.yview)
        self.group_tree.configure(yscrollcommand=scrollbar.set)
        self.group_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.group_tree.tag_configure("chosen", background=ACCENT_SOFT, foreground="#084E48")
        self.group_tree.tag_configure("special", background=WARNING, foreground="#FFFFFF")
        self.group_tree.bind("<<TreeviewSelect>>", self._group_selection_changed)
        self.group_tree.bind("<Control-a>", self._select_all_visible)
        self.group_tree.bind("<Control-A>", self._select_all_visible)

        action_row = ttk.Frame(parent, style="Panel.TFrame")
        action_row.pack(fill="x", pady=(10, 0))
        ttk.Button(
            action_row,
            text="清空已选",
            command=self._clear_selection,
            style="Secondary.TButton",
        ).pack(side="right")

        selection = ttk.Frame(parent, style="Panel.TFrame")
        selection.pack(fill="x", pady=(12, 0))
        ttk.Label(selection, textvariable=self.selection_var, style="Target.TLabel").pack(fill="x")

    def _build_result_panel(self, parent: ttk.Frame) -> None:
        ttk.Label(parent, text="2  自定义加权评价", style="Section.TLabel").pack(anchor="w")
        ttk.Label(
            parent,
            text="默认分数与原来相同：共同群数 + 各群等级的对数加分。可以选预设，也可以直接改公式。",
            style="Hint.TLabel",
            wraplength=720,
            justify="left",
        ).pack(anchor="w", pady=(5, 10))

        formula_row = ttk.Frame(parent, style="Panel.TFrame")
        formula_row.pack(fill="x", pady=(0, 6))
        ttk.Label(formula_row, text="算法", style="Panel.TLabel").pack(side="left")
        self.formula_preset_box = ttk.Combobox(
            formula_row,
            width=15,
            textvariable=self.formula_preset_var,
            values=(*SCORE_FORMULA_PRESETS.keys(), "自定义"),
            state="readonly",
        )
        self.formula_preset_box.pack(side="left", padx=(8, 8))
        self.formula_preset_box.bind("<<ComboboxSelected>>", self._formula_preset_selected)
        self.formula_entry = ttk.Entry(formula_row, textvariable=self.formula_var)
        self.formula_entry.pack(side="left", fill="x", expand=True)
        ttk.Label(
            parent,
            text=(
                "变量：shared_groups、level_sum、level_avg、level_max、known_levels、"
                "missing_levels、log_level_sum；函数：abs、log2、min、max、sqrt。"
            ),
            style="Hint.TLabel",
            wraplength=720,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))

        controls = ttk.Frame(parent, style="Panel.TFrame")
        controls.pack(fill="x", pady=(0, 12))
        ttk.Label(controls, text="每页", style="Panel.TLabel").pack(side="left")
        self.page_size_box = ttk.Combobox(
            controls,
            width=5,
            textvariable=self.page_size_var,
            values=("50", "100", "200", "500"),
            state="readonly",
        )
        self.page_size_box.pack(side="left", padx=(6, 14))
        self.page_size_box.bind("<<ComboboxSelected>>", self._page_size_changed)
        ttk.Label(controls, text="最少共同群", style="Panel.TLabel").pack(side="left")
        self.min_groups_spin = ttk.Spinbox(
            controls,
            from_=2,
            to=20,
            width=4,
            textvariable=self.min_groups_var,
        )
        self.min_groups_spin.pack(side="left", padx=(6, 14))
        self.refresh_button = ttk.Button(
            controls,
            text="只刷新已选群等级",
            command=self._refresh_selected_from_qq,
            style="Secondary.TButton",
        )
        self.refresh_button.pack(side="right")
        self.evaluate_button = ttk.Button(
            controls,
            text="开始评价",
            command=self._evaluate,
            style="Primary.TButton",
        )
        self.evaluate_button.pack(side="right", padx=(0, 8))

        table_frame = ttk.Frame(parent, style="Panel.TFrame")
        table_frame.pack(fill="both", expand=True)
        columns = ("rank", "name", "qq", "groups", "score", "coverage", "levels")
        self.result_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "rank": "#",
            "name": "昵称",
            "qq": "QQ 号",
            "groups": "共同群",
            "score": "加权分",
            "coverage": "等级覆盖",
            "levels": "等级明细",
        }
        widths = {"rank": 42, "name": 110, "qq": 88, "groups": 60, "score": 72, "coverage": 78, "levels": 520}
        for column in columns:
            self.result_tree.heading(column, text=headings[column])
            self.result_tree.column(
                column,
                width=widths[column],
                minwidth=38,
                anchor="w" if column in {"name", "levels"} else "e",
                stretch=column == "levels",
            )
        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.result_tree.yview)
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=self.result_tree.xview)
        self.result_tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.result_tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        footer = ttk.Frame(parent, style="Panel.TFrame")
        footer.pack(fill="x", pady=(10, 0))
        ttk.Label(
            footer,
            text="排名只是兴趣圈层重合的线索，不代表对方愿意被联系。",
            style="Hint.TLabel",
        ).pack(side="left")
        self.export_button = ttk.Button(
            footer,
            text="导出全部结果",
            command=self._export_all,
            style="Secondary.TButton",
        )
        self.export_button.pack(side="right")
        self.next_page_button = ttk.Button(
            footer,
            text="下一页",
            command=lambda: self._change_page(1),
            style="Secondary.TButton",
        )
        self.next_page_button.pack(side="right", padx=(8, 8))
        ttk.Label(footer, textvariable=self.page_var, style="Hint.TLabel").pack(side="right")
        self.previous_page_button = ttk.Button(
            footer,
            text="上一页",
            command=lambda: self._change_page(-1),
            style="Secondary.TButton",
        )
        self.previous_page_button.pack(side="right", padx=(8, 8))
        self._update_page_controls()

    def _bind_shortcuts(self) -> None:
        self.master.bind("<Control-f>", lambda _event: self.search_entry.focus_set())
        self.master.bind("<Control-F>", lambda _event: self.search_entry.focus_set())
        self.master.bind("<Return>", lambda _event: self._evaluate())
        self.master.bind("<Control-x>", self._special_mark_on)
        self.master.bind("<Control-X>", self._special_mark_on)
        self.master.bind("<Control-KeyRelease-x>", self._special_mark_off)
        self.master.bind("<Control-KeyRelease-X>", self._special_mark_off)
        self.master.bind("<FocusOut>", self._special_mark_off)

    def _load_snapshot(self) -> None:
        try:
            self.memberships = load_memberships(self.snapshot_path)
            self.groups = summarize_groups(self.memberships)
        except InputError as exc:
            self.memberships = []
            self.groups = []
            # First launch: no snapshot yet. Guide the user instead of showing
            # a raw "file not found" error that looks like the app is broken.
            if not self.snapshot_path.exists():
                self._set_status(
                    "还没有成员快照。先选择要分析的群，再点“只刷新已选群等级”从 NapCat 拉取成员。"
                )
            else:
                self._set_status(str(exc), kind="error")
            return
        available = {group.group_id for group in self.groups}
        self.selected_group_ids &= available
        self._refresh_group_tree()
        self._update_selection_labels()
        level_rows = sum(row.level is not None for row in self.memberships)
        if level_rows:
            self._set_status(
                f"已读取 {len(self.groups)} 个群；{level_rows} 条成员记录带群等级。"
            )
        else:
            self._set_status(
                f"已读取 {len(self.groups)} 个群，但旧快照没有等级。选群后点“只刷新已选群等级”。",
                kind="warning",
            )

    def _refresh_group_tree(self) -> None:
        if not hasattr(self, "group_tree"):
            return
        self.updating_group_tree = True
        try:
            self.group_tree.delete(*self.group_tree.get_children())
            for group in filter_group_summaries(self.groups, self.search_var.get()):
                chosen = group.group_id in self.selected_group_ids
                special = group.group_id in self.special_group_ids
                coverage = f"{group.level_coverage:.0%}" if group.level_count else "缺失"
                if special:
                    mark, tags = "★", ("special",)
                else:
                    mark, tags = ("✓" if chosen else ""), (("chosen",) if chosen else ())
                self.group_tree.insert(
                    "",
                    "end",
                    iid=group.group_id,
                    values=(mark, group.group_name, group.group_id, group.member_count, coverage),
                    tags=tags,
                )
            visible_selected = tuple(
                group_id
                for group_id in self.group_tree.get_children()
                if group_id in self.selected_group_ids
            )
            if visible_selected:
                self.group_tree.selection_set(visible_selected)
        finally:
            self.updating_group_tree = False

    def _selected_group_ids(self) -> list[str]:
        return sorted(self.selected_group_ids)

    def _group_selection_changed(self, _event: tk.Event | None = None) -> None:
        if self.updating_group_tree:
            return
        visible = {str(item) for item in self.group_tree.get_children()}
        selected_visible = {str(item) for item in self.group_tree.selection()}
        updated_selection = update_group_selection(
            self.selected_group_ids,
            visible_group_ids=visible,
            selected_visible_group_ids=selected_visible,
        )
        if updated_selection == self.selected_group_ids:
            self._paint_group_selection()
            return
        # 标记模式下：本次新增选中的群，一并记入「特别关照」
        if self.marking_special:
            added = updated_selection - self.selected_group_ids
            self.special_group_ids |= added
        # 普通选择里被移除的群，也要从「特别关照」里清掉，避免残留
        removed = self.selected_group_ids - updated_selection
        if removed:
            self.special_group_ids -= removed
        self.selected_group_ids = updated_selection
        self._paint_group_selection()
        self.ranked = []
        self.page_index = 0
        self._render_results([])
        self.page_var.set("第 0 / 0 页")
        self._update_selection_labels()
        self._update_page_controls()

    def _paint_group_selection(self) -> None:
        for group_id in self.group_tree.get_children():
            values = list(self.group_tree.item(group_id, "values"))
            chosen = group_id in self.selected_group_ids
            special = group_id in self.special_group_ids
            if special:
                values[0] = "★"
                tags = ("special",)
            else:
                values[0] = "✓" if chosen else ""
                tags = ("chosen",) if chosen else ()
            self.group_tree.item(group_id, values=values, tags=tags)

    def _select_all_visible(self, _event: tk.Event | None = None) -> str:
        visible = self.group_tree.get_children()
        if visible:
            self.group_tree.selection_set(visible)
            self._group_selection_changed()
        return "break"

    def _special_mark_on(self, _event: tk.Event | None = None) -> str:
        if self.marking_special:
            return "break"
        self.marking_special = True
        self._paint_group_selection()
        self._set_status(
            "按住 Ctrl+X 期间点选的群将标记为「特别关照」（结果必须包含它们）。松开 Ctrl+X 结束。"
        )
        return "break"

    def _special_mark_off(self, _event: tk.Event | None = None) -> str:
        if not self.marking_special:
            return "break"
        self.marking_special = False
        self._paint_group_selection()
        self._update_selection_labels()
        if self.special_group_ids:
            names = {
                group.group_id: group.group_name for group in self.groups
            }
            preview = "、".join(
                names.get(gid, gid) for gid in sorted(self.special_group_ids)
            )
            self._set_status(
                f"特别关照：{preview}。结果将只保留同时属于这些群的人。"
            )
        else:
            self._set_status("未标记特别关照群。")
        return "break"

    def _clear_selection(self) -> None:
        self.selected_group_ids.clear()
        self.special_group_ids.clear()
        self.ranked = []
        self.page_index = 0
        self._render_results([])
        self.page_var.set("第 0 / 0 页")
        self.updating_group_tree = True
        try:
            self.group_tree.selection_remove(self.group_tree.selection())
        finally:
            self.updating_group_tree = False
        self._paint_group_selection()
        self._update_selection_labels()
        self._update_page_controls()
        self._set_status("已清空选择。")

    def _update_selection_labels(self) -> None:
        names = {group.group_id: group.group_name for group in self.groups}
        selected_names = [names.get(group_id, group_id) for group_id in self._selected_group_ids()]
        preview = "、".join(selected_names[:3])
        if len(selected_names) > 3:
            preview += f" 等 {len(selected_names)} 个"
        label = f"已选择 {len(selected_names)} 个群" + (f"：{preview}" if preview else "")
        if self.special_group_ids:
            special_names = [
                names.get(group_id, group_id)
                for group_id in sorted(self.special_group_ids)
            ]
            label += f"；特别关照 {len(special_names)} 个：{'、'.join(special_names[:3])}"
        self.selection_var.set(label)

    def _validated_min_groups(self) -> int:
        selected_count = len(self.selected_group_ids)
        if selected_count < 2:
            raise ValueError("请至少选择 2 个群")
        try:
            min_groups = int(self.min_groups_var.get())
        except ValueError as exc:
            raise ValueError("最少共同群必须是整数") from exc
        if not 2 <= min_groups <= selected_count:
            raise ValueError(f"最少共同群应在 2–{selected_count} 之间")
        return min_groups

    def _validate_selection(self) -> tuple[int, int, str]:
        min_groups = self._validated_min_groups()
        try:
            page_size = int(self.page_size_var.get())
        except ValueError as exc:
            raise ValueError("每页数量必须是整数") from exc
        if page_size < 1:
            raise ValueError("每页数量必须大于 0")
        return page_size, min_groups, self.formula_var.get()

    def _evaluate(self) -> None:
        if self.busy:
            return
        try:
            _page_size, min_groups, formula = self._validate_selection()
            self.ranked = rank_selected_groups(
                self.memberships,
                selected_group_ids=self.selected_group_ids,
                min_groups=min_groups,
                excluded_users=self.excluded_users,
                score_formula=formula,
                required_group_ids=self.special_group_ids,
            )
        except ValueError as exc:
            messagebox.showinfo("无法开始评价", str(exc), parent=self.master)
            return
        self.page_index = 0
        self._render_current_page()

    def _render_current_page(self) -> None:
        try:
            page_size = int(self.page_size_var.get())
        except ValueError:
            page_size = 100
        page, start, total_pages = page_items(
            self.ranked,
            page_index=self.page_index,
            page_size=page_size,
        )
        self.page_index = start // page_size
        self._render_results(page, start_index=start + 1)
        current_page = self.page_index + 1 if self.ranked else 0
        self.page_var.set(f"第 {current_page} / {total_pages if self.ranked else 0} 页")
        self._update_page_controls()

        known = sum(person.known_level_count for person in page)
        total = sum(person.shared_group_count for person in page)
        if not self.ranked:
            self._set_status("已完成：没有找到符合当前条件的重合成员。")
        elif known == 0:
            self._set_status(
                f"共 {len(self.ranked)} 个结果；当前第 {current_page}/{total_pages} 页，等级全部缺失，请先刷新已选群。",
                kind="warning",
            )
        else:
            self._set_status(
                f"共 {len(self.ranked)} 个结果；当前第 {current_page}/{total_pages} 页，当前页等级覆盖 {known}/{total}。"
            )

    def _render_results(
        self, people: list[WeightedOverlap], *, start_index: int = 1
    ) -> None:
        self.result_tree.delete(*self.result_tree.get_children())
        for index, person in enumerate(people, start=start_index):
            self.result_tree.insert(
                "",
                "end",
                values=(
                    index,
                    person.display_name,
                    person.user_id,
                    person.shared_group_count,
                    f"{person.score:.3f}",
                    f"{person.known_level_count}/{person.shared_group_count}",
                    format_level_summary(person.levels, person.level_aliases),
                ),
            )

    def _change_page(self, offset: int) -> None:
        if self.busy or not self.ranked:
            return
        self.page_index += offset
        self._render_current_page()

    def _page_size_changed(self, _event: tk.Event | None = None) -> None:
        self.page_index = 0
        if self.ranked:
            self._render_current_page()
        else:
            self._update_page_controls()

    def _formula_preset_selected(self, _event: tk.Event | None = None) -> None:
        expression = SCORE_FORMULA_PRESETS.get(self.formula_preset_var.get())
        if expression is not None:
            self.formula_var.set(expression)
            self.formula_entry.focus_set()

    def _formula_changed(self, *_args: object) -> None:
        expression = self.formula_var.get().strip()
        preset = next(
            (
                name
                for name, candidate in SCORE_FORMULA_PRESETS.items()
                if candidate == expression
            ),
            "自定义",
        )
        if self.formula_preset_var.get() != preset:
            self.formula_preset_var.set(preset)
        if hasattr(self, "result_tree"):
            self.ranked = []
            self.page_index = 0
            self._render_results([])
            self.page_var.set("第 0 / 0 页")
            self._update_page_controls()

    def _refresh_selected_from_qq(self) -> None:
        if self.busy:
            return
        try:
            self._validated_min_groups()
        except ValueError as exc:
            messagebox.showinfo("无法刷新", str(exc), parent=self.master)
            return
        selected_ids = self._selected_group_ids()
        self._set_busy(True)
        self._set_status(f"正在从 NapCat 刷新 {len(selected_ids)} 个已选群…")

        def worker() -> None:
            try:
                client = OneBotClient(self.api_url, self.api_token, self.timeout)
                self_id = client.get_login_user_id()
                groups = client.fetch_groups(selected_ids)
                merge_snapshot_groups(self.snapshot_path, groups)
            except (OneBotError, InputError, OSError, ValueError) as exc:
                self.master.after(0, self._refresh_failed, str(exc))
                return
            self.master.after(0, self._refresh_succeeded, self_id, len(groups))

        threading.Thread(target=worker, daemon=True).start()

    def _refresh_succeeded(self, self_id: str, group_count: int) -> None:
        self.excluded_users = {self_id}
        self._set_busy(False)
        self._load_snapshot()
        self._set_status(
            f"已刷新 {group_count} 个已选群，并自动排除当前登录账号。"
        )
        self._evaluate()

    def _refresh_failed(self, message: str) -> None:
        self._set_busy(False)
        concise = message.replace("\n", " ")[:360]
        self._set_status("刷新失败；本地快照没有被改动。", kind="error")
        messagebox.showerror(
            "无法连接 QQ 连接组件",
            f"{concise}\n\n若这是首次使用，请确认网络可以访问 GitHub 以下载组件；"
            "若组件已就绪，请关闭本窗口后重新打开本程序再试。",
            parent=self.master,
        )

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.refresh_button.configure(state=state)
        self.evaluate_button.configure(state=state)
        self._update_page_controls()

    def _update_page_controls(self) -> None:
        if not hasattr(self, "previous_page_button"):
            return
        try:
            page_size = int(self.page_size_var.get())
        except ValueError:
            page_size = 100
        _page, start, total_pages = page_items(
            self.ranked,
            page_index=self.page_index,
            page_size=max(page_size, 1),
        )
        current_index = start // max(page_size, 1)
        self.previous_page_button.configure(
            state="normal" if not self.busy and self.ranked and current_index > 0 else "disabled"
        )
        self.next_page_button.configure(
            state=(
                "normal"
                if not self.busy and self.ranked and current_index + 1 < total_pages
                else "disabled"
            )
        )
        self.export_button.configure(
            state="normal" if not self.busy and self.ranked else "disabled"
        )

    def _export_all(self) -> None:
        if not self.ranked:
            messagebox.showinfo("无可导出结果", "请先完成一次评价。", parent=self.master)
            return
        target = filedialog.asksaveasfilename(
            parent=self.master,
            title="导出全部结果",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv")],
            initialfile=f"qq-group-overlap-all-{len(self.ranked)}.csv",
        )
        if not target:
            return
        try:
            saved = write_top_csv(target, self.ranked, limit=None)
        except (OSError, ValueError) as exc:
            messagebox.showerror("导出失败", str(exc), parent=self.master)
            return
        self._set_status(f"已导出全部 {len(self.ranked)} 个结果：{saved}")

    def _set_status(self, message: str, *, kind: str = "normal") -> None:
        colors = {"normal": MUTED, "warning": WARNING, "error": ERROR}
        self.status_var.set(message)
        self.status_label.configure(foreground=colors.get(kind, MUTED))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QQ 群同好线索本地 GUI")
    parser.add_argument(
        "--snapshot",
        default=str(default_snapshot_path()),
        help="本地成员快照路径（默认在当前用户数据目录，与运行目录无关）",
    )
    parser.add_argument(
        "--api",
        default=None,
        help="连接到已运行的 OneBot 地址；不传则自动下载并启动 NapCat（默认 127.0.0.1:3000）",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="OneBot 访问令牌（配合 --api 使用；不传则自动生成）",
    )
    parser.add_argument(
        "--token-env",
        default="ONEBOT_ACCESS_TOKEN",
        help="从环境变量读取令牌名（配合 --api 使用）",
    )
    parser.add_argument("--timeout", type=float, default=20, help="OneBot 请求超时秒数")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    snapshot = Path(args.snapshot).expanduser().resolve()
    root = tk.Tk()
    OverlapApp(
        root,
        snapshot_path=snapshot,
        timeout=args.timeout,
        integrated=args.api is None,
        api_url=args.api,
        api_token=args.token,
        token_environment=args.token_env,
    )
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
