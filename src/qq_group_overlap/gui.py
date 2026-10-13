from __future__ import annotations

import argparse
import threading
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
from .models import Membership
from .onebot import OneBotClient, OneBotError
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
        api_url: str,
        token_environment: str,
        timeout: float,
    ) -> None:
        super().__init__(master, padding=20, style="App.TFrame")
        self.master = master
        self.snapshot_path = snapshot_path
        self.api_url = api_url
        self.token_environment = token_environment
        self.timeout = timeout

        self.memberships: list[Membership] = []
        self.groups: list[GroupSummary] = []
        self.selected_group_ids: set[str] = set()
        self.excluded_users: set[str] = set()
        self.ranked: list[WeightedOverlap] = []
        self.page_index = 0
        self.busy = False
        self.updating_group_tree = False

        self.search_var = tk.StringVar()
        self.selection_var = tk.StringVar(value="已选择 0 个群")
        self.page_size_var = tk.StringVar(value="100")
        self.page_var = tk.StringVar(value="第 0 / 0 页")
        self.min_groups_var = tk.StringVar(value="2")
        self.formula_preset_var = tk.StringVar(value="对数等级（默认）")
        self.formula_var = tk.StringVar(value=DEFAULT_SCORE_FORMULA)
        self.status_var = tk.StringVar(value="正在读取本地快照…")
        self.status_color = MUTED
        self.formula_var.trace_add("write", self._formula_changed)

        self._configure_window()
        self._configure_styles()
        self._build_ui()
        self._bind_shortcuts()
        self._load_snapshot()

    def _configure_window(self) -> None:
        self.master.title("QQ 群同好线索")
        self.master.geometry("1220x760")
        self.master.minsize(980, 640)
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

    def _build_ui(self) -> None:
        header = ttk.Frame(self, style="App.TFrame")
        header.pack(fill="x", pady=(0, 16))
        ttk.Label(header, text="QQ 群同好线索", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="选择多个群，寻找其中重复出现的人；结果无人数上限，按页查看并可完整导出。",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        body = ttk.Panedwindow(self, orient="horizontal")
        body.pack(fill="both", expand=True)

        left = ttk.Frame(body, padding=16, style="Panel.TFrame")
        right = ttk.Frame(body, padding=16, style="Panel.TFrame")
        body.add(left, weight=2)
        body.add(right, weight=4)
        self._build_group_panel(left)
        self._build_result_panel(right)

        status = tk.Label(
            self,
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
            text="例如搜“自动化”。单击选一个群；按住 Ctrl 增减，Shift 连选一段。",
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
        widths = {"rank": 42, "name": 130, "qq": 100, "groups": 68, "score": 78, "coverage": 82, "levels": 340}
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

    def _load_snapshot(self) -> None:
        try:
            self.memberships = load_memberships(self.snapshot_path)
            self.groups = summarize_groups(self.memberships)
        except InputError as exc:
            self.memberships = []
            self.groups = []
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
                coverage = f"{group.level_coverage:.0%}" if group.level_count else "缺失"
                self.group_tree.insert(
                    "",
                    "end",
                    iid=group.group_id,
                    values=("✓" if chosen else "", group.group_name, group.group_id, group.member_count, coverage),
                    tags=("chosen",) if chosen else (),
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
            values[0] = "✓" if group_id in self.selected_group_ids else ""
            self.group_tree.item(
                group_id,
                values=values,
                tags=("chosen",) if group_id in self.selected_group_ids else (),
            )

    def _select_all_visible(self, _event: tk.Event | None = None) -> str:
        visible = self.group_tree.get_children()
        if visible:
            self.group_tree.selection_set(visible)
            self._group_selection_changed()
        return "break"

    def _clear_selection(self) -> None:
        self.selected_group_ids.clear()
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
        self.selection_var.set(
            f"已选择 {len(selected_names)} 个群" + (f"：{preview}" if preview else "")
        )

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
                    format_level_summary(person.levels),
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
                client = OneBotClient.from_environment(
                    self.api_url,
                    self.token_environment,
                    self.timeout,
                )
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
            "无法连接 NapCat",
            f"{concise}\n\n请先运行 ./scripts/start-napcat.sh，确认 QQ 已登录，再重试。",
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
        default="runtime/data/members.private.json",
        help="本地成员快照路径",
    )
    parser.add_argument("--api", default="http://127.0.0.1:3000", help="OneBot HTTP 地址")
    parser.add_argument("--token-env", default="ONEBOT_ACCESS_TOKEN", help="Token 环境变量名")
    parser.add_argument("--timeout", type=float, default=20, help="OneBot 请求超时秒数")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    snapshot = Path(args.snapshot).expanduser().resolve()
    root = tk.Tk()
    OverlapApp(
        root,
        snapshot_path=snapshot,
        api_url=args.api,
        token_environment=args.token_env,
        timeout=args.timeout,
    )
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
