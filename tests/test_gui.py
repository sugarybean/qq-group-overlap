from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# A tiny fake Tk / ttk so the GUI can be exercised without a display server.
# Every widget is a no-op shell; ``after(0, cb, *a)`` runs the callback
# synchronously (to drive the startup state machine), while ``after(>0, ...)``
# is a no-op so the login poll loop does not recurse during a test.
# ---------------------------------------------------------------------------

class _W:
    def __init__(self, *args, **kwargs) -> None:
        self._children: list = []
        self._props: dict = {}
        self._value = kwargs.get("value", "")
        self.children: list = []

    def configure(self, *args, **kw) -> None:
        self._props.update(kw)

    config = configure

    def pack(self, *a, **k) -> None:
        pass

    def pack_propagate(self, *a, **k) -> None:
        pass

    def pack_forget(self, *a, **k) -> None:
        pass

    def grid(self, *a, **k) -> None:
        pass

    def place(self, *a, **k) -> None:
        pass

    def destroy(self, *a, **k) -> None:
        pass

    def after(self, ms, cb, *args, **kwargs):
        if ms == 0:
            cb(*args, **kwargs)
        return 0

    def bind(self, *a, **k) -> None:
        pass

    def lift(self, *a, **k) -> None:
        pass

    def attributes(self, *a, **k) -> None:
        pass

    def protocol(self, *a, **k) -> None:
        pass

    def winfo_exists(self, *a, **k) -> int:
        return 1

    def winfo_screenwidth(self, *a, **k) -> int:
        return 1280

    def rowconfigure(self, *a, **k) -> None:
        pass

    def columnconfigure(self, *a, **k) -> None:
        pass

    def focus_set(self, *a, **k) -> None:
        pass

    def selection_set(self, *a, **k) -> None:
        pass

    def selection_remove(self, *a, **k) -> None:
        pass

    def selection(self, *a, **k):
        return []

    def get_children(self, *a, **k):
        return []

    def delete(self, *a, **k) -> None:
        pass

    def insert(self, *a, **k):
        return "iid"

    def item(self, *a, **k):
        return {"values": []}

    def set(self, *a, **k) -> None:
        pass

    def get(self, *a, **k):
        return self._value

    def set_value(self, v) -> None:
        self._value = v

    def trace_add(self, *a, **k):
        return "id"

    def width(self, *a, **k) -> int:
        return 320

    def height(self, *a, **k) -> int:
        return 320

    def zoom(self, *a, **k):
        return self

    def start(self, *a, **k) -> None:
        pass

    def stop(self, *a, **k) -> None:
        pass

    def theme_names(self, *a, **k):
        return ["clam"]

    def theme_use(self, *a, **k) -> None:
        pass

    def map(self, *a, **k) -> None:
        pass

    def heading(self, *a, **k) -> None:
        pass

    def column(self, *a, **k) -> None:
        pass

    def tag_configure(self, *a, **k) -> None:
        pass

    def yview(self, *a, **k) -> None:
        pass

    def xview(self, a, **k) -> None:
        pass

    def add(self, *a, **k) -> None:
        pass

    def geometry(self, *a, **k) -> None:
        pass

    def title(self, *a, **k) -> None:
        pass

    def minsize(self, *a, **k) -> None:
        pass

    def mainloop(self, *a, **k) -> None:
        pass

    def update_idletasks(self, *a, **k) -> None:
        pass

    def update(self, *a, **k) -> None:
        pass


def _make_module(name: str, attrs: dict) -> types.ModuleType:
    module = types.ModuleType(name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


_tk_attrs = {
    "Tk": _W,
    "Frame": _W,
    "Label": _W,
    "PhotoImage": _W,
    "StringVar": _W,
    "TclError": Exception,
    "END": "end",
}
_ttk_attrs = {
    "Frame": _W,
    "Label": _W,
    "Panedwindow": _W,
    "Treeview": _W,
    "Entry": _W,
    "Combobox": _W,
    "Spinbox": _W,
    "Progressbar": _W,
    "Scrollbar": _W,
    "Button": _W,
    "Style": _W,
}
_filedialog_attrs = {"asksaveasfilename": lambda *a, **k: ""}
_messagebox_attrs = {"showinfo": lambda *a, **k: None, "showerror": lambda *a, **k: None}

_fake_tk = _make_module("tkinter", _tk_attrs)
_fake_ttk = _make_module("tkinter.ttk", _ttk_attrs)
_fake_filedialog = _make_module("tkinter.filedialog", _filedialog_attrs)
_fake_messagebox = _make_module("tkinter.messagebox", _messagebox_attrs)
_fake_tk.ttk = _fake_ttk
_fake_tk.filedialog = _fake_filedialog
_fake_tk.messagebox = _fake_messagebox


# Inject the fake Tk *before* importing the GUI module, then restore the real
# one so other test modules that import tkinter afterwards are unaffected.
_original_modules = {}
for _name, _mod in (
    ("tkinter", _fake_tk),
    ("tkinter.ttk", _fake_ttk),
    ("tkinter.filedialog", _fake_filedialog),
    ("tkinter.messagebox", _fake_messagebox),
):
    if _name in sys.modules:
        _original_modules[_name] = sys.modules[_name]
    sys.modules[_name] = _mod

try:
    from qq_group_overlap import gui
finally:
    for _name in ("tkinter", "tkinter.ttk", "tkinter.filedialog", "tkinter.messagebox"):
        if _name in _original_modules:
            sys.modules[_name] = _original_modules[_name]
        else:
            sys.modules.pop(_name, None)


class _CatalogHolder:
    """A stand-in for OverlapApp carrying only what _merge_catalog touches."""

    groups: list = []
    selected_group_ids = set()

    def _refresh_group_tree(self) -> None:
        self.refreshed = True

    def _update_selection_labels(self) -> None:
        self.labels_updated = True


class MergeCatalogTests(unittest.TestCase):
    def test_merge_keeps_snapshot_levels_and_adds_live_groups(self) -> None:
        holder = _CatalogHolder()
        holder.groups = [
            gui.GroupSummary("1001", "老群", 30, 12),  # has levels from snapshot
            gui.GroupSummary("1002", "消失的群", 5, 5),  # only in snapshot
        ]
        live = [
            {"group_id": "1001", "group_name": "老群(改名)", "member_count": 40},
            {"group_id": "1003", "group_name": "新群", "member_count": 88},
        ]
        gui.OverlapApp._merge_catalog(holder, live)

        by_id = {g.group_id: g for g in holder.groups}
        self.assertEqual(by_id["1001"].member_count, 40)
        self.assertEqual(by_id["1001"].level_count, 12)  # preserved
        self.assertIn("1002", by_id)  # snapshot-only kept
        self.assertIn("1003", by_id)  # live-only added
        # sorted by name case-insensitively
        names = [g.group_name for g in holder.groups]
        self.assertEqual(names, sorted(names, key=str.casefold))
        self.assertTrue(holder.refreshed)
        self.assertTrue(holder.labels_updated)

    def test_merge_skips_empty_group_id(self) -> None:
        holder = _CatalogHolder()
        holder.groups = []
        gui.OverlapApp._merge_catalog(holder, [{"group_id": "", "member_count": 3}])
        self.assertEqual(holder.groups, [])


class _GuiHarness:
    def __init__(self, integrated: bool, api_url: str | None = None) -> None:
        self.root = gui.tk.Tk()
        self.app = gui.OverlapApp(
            self.root,
            snapshot_path=Path("/tmp/does-not-exist-members.private.json"),
            timeout=5,
            integrated=integrated,
            api_url=api_url,
        )

    def destroy(self) -> None:
        if getattr(self.app, "login_view", None) is not None:
            self.app.login_view.destroy()
        self.root.destroy()


class ExternalModeTests(unittest.TestCase):
    def test_external_mode_enters_main_view_without_bootstrap(self) -> None:
        harness = _GuiHarness(integrated=False, api_url="http://127.0.0.1:3000")
        try:
            app = harness.app
            # No bootstrap worker should have started in external mode.
            self.assertIsNone(app._session)
            self.assertFalse(app.integrated)
            # Main view is built immediately (group_tree only exists after that).
            self.assertTrue(hasattr(app, "group_tree"))
        finally:
            harness.destroy()

    def test_external_mode_populates_groups_from_qq(self) -> None:
        harness = _GuiHarness(integrated=False, api_url="http://127.0.0.1:3000")
        try:
            app = harness.app
            client = MagicMock()
            client.get_login_user_id.return_value = "123456"
            client.list_groups.return_value = [
                {"group_id": "2001", "group_name": "测试群A", "member_count": 10},
                {"group_id": "2002", "group_name": "测试群B", "member_count": 20},
            ]
            with patch.object(gui, "OneBotClient", return_value=client):
                app._populate_groups_from_qq()
            app._set_self_id("123456")
            app._merge_catalog(client.list_groups())
            self.assertEqual(app.self_id, "123456")
            self.assertEqual({g.group_id for g in app.groups}, {"2001", "2002"})
        finally:
            harness.destroy()


class IntegratedModeTests(unittest.TestCase):
    def test_integrated_flow_logged_in_reaches_main_view(self) -> None:
        harness = _GuiHarness(integrated=True)
        try:
            app = harness.app
            self.assertTrue(hasattr(app, "qr_label"))  # login view built
            session = MagicMock()
            session.start.return_value = None
            session.current_uin.return_value = "999888"
            session.is_running.return_value = True
            session.api_url = "http://127.0.0.1:3000"
            with patch.object(gui, "ensure_runtime", return_value=None), patch.object(
                gui, "load_or_create_token", return_value="tok-123"
            ), patch.object(gui, "NapCatSession", return_value=session):
                app._bootstrap_worker()
            # after(0, ...) is synchronous in the fake Tk, so the transition fires.
            self.assertEqual(app.self_id, "999888")
            self.assertEqual(app.api_token, "tok-123")
            self.assertTrue(hasattr(app, "group_tree"))  # main view built
            self.assertIsNone(app.login_view)  # login view destroyed
        finally:
            harness.destroy()

    def test_integrated_flow_not_logged_in_shows_qr_phase(self) -> None:
        harness = _GuiHarness(integrated=True)
        try:
            app = harness.app
            session = MagicMock()
            session.start.return_value = None
            session.current_uin.return_value = None
            session.is_running.return_value = True
            session.qr_path = Path("/tmp/nonexistent-qrcode.png")
            with patch.object(gui, "ensure_runtime", return_value=None), patch.object(
                gui, "load_or_create_token", return_value="tok-123"
            ), patch.object(gui, "NapCatSession", return_value=session):
                app._bootstrap_worker()
            self.assertIsNotNone(app._session)
            # begin_scan_phase ran: progress hidden, QR label reset
            self.assertFalse(hasattr(app, "group_tree"))
            self.assertTrue(hasattr(app, "qr_label"))
        finally:
            harness.destroy()

    def test_bootstrap_failure_shows_retry(self) -> None:
        harness = _GuiHarness(integrated=True)
        try:
            app = harness.app
            with patch.object(
                gui, "ensure_runtime", side_effect=gui.RuntimeBootstrapError("下载失败")
            ):
                app._bootstrap_worker()
            self.assertTrue(hasattr(app, "retry_button"))
        finally:
            harness.destroy()


class ParserTests(unittest.TestCase):
    def test_default_is_integrated(self) -> None:
        args = gui.build_parser().parse_args([])
        self.assertIsNone(args.api)
        self.assertTrue(args.api is None)  # drives integrated mode

    def test_api_flag_switches_to_external(self) -> None:
        args = gui.build_parser().parse_args(["--api", "http://127.0.0.1:9999"])
        self.assertEqual(args.api, "http://127.0.0.1:9999")


if __name__ == "__main__":
    unittest.main()
