"""Fella — the tray companion. Run with:  python -m fella.main

Sits in your KDE system tray showing Fella's face. Click to chat.
Detects problems you describe, offers a recipe, and only acts with your OK.
"""

import os
import re
import sys

# Qt's native "wayland" platform plugin doesn't reliably show the system
# tray icon (StatusNotifierItem support is spottier there); "xcb" (via
# XWayland) does. Set a default but let an explicit user override win.
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

from PySide6.QtCore import Qt, QThread, Signal, QByteArray, QTimer
from PySide6.QtGui import QIcon, QPixmap, QAction, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QWidget, QVBoxLayout, QHBoxLayout,
    QScrollArea, QLineEdit, QPushButton, QLabel, QMessageBox, QDialog,
    QColorDialog,
)

from . import brain, memory, hardware, settings
from . import flatpak_apps
from .apps import APPS, catalog_hint, install_recipe, match_app
from .face import face_svg
from .recipes import load_recipes, recipe_hint, run_recipe

RECIPE_RE = re.compile(r"\[RECIPE:\s*([a-z_]+)\]")

# Map everyday words to a recipe id, so Fella acts on what you ASK for.
KEYWORDS = {
    "restart_audio":    ["sound", "audio", "no sound", "can't hear", "speaker", "headphone", "volume"],
    "free_disk_space":  ["space", "disk full", "storage", "full drive", "clean", "cleanup"],
    "refresh_mirrors":  ["update fail", "slow update", "mirror", "can't update", "update slow"],
    "fix_broken_update":["stuck update", "broken update", "lock", "db.lck", "interrupted update"],
    "nvidia_status":    ["driver", "gpu", "graphics", "nvidia", "game looks", "screen glitch", "2060"],
}


def match_recipe(text, recipes):
    t = text.lower()
    for rid, words in KEYWORDS.items():
        if rid in recipes and any(w in t for w in words):
            return recipes[rid]
    return None


def render_face(mood: str, body: str, eye: str, size: int = 96) -> QPixmap:
    svg = face_svg(mood, body, eye).encode()
    renderer = QSvgRenderer(QByteArray(svg))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    return pm


def face_pixmap(mood: str, size: int = 96) -> QPixmap:
    body, eye = settings.get_colors()
    return render_face(mood, body, eye, size)


def svg_icon(mood: str) -> QIcon:
    return QIcon(face_pixmap(mood, 64))


class ChatWorker(QThread):
    chunk = Signal(str)
    done = Signal(str)

    def __init__(self, model, messages, hint):
        super().__init__()
        self.model, self.messages, self.hint = model, messages, hint

    def run(self):
        full = ""
        try:
            for c in brain.chat_stream(self.model, self.messages, self.hint):
                full += c
                self.chunk.emit(c)
        except Exception as e:
            full = f"(I couldn't reach my brain: {e})"
            self.chunk.emit(full)
        self.done.emit(full)


BUBBLE_FELLA = "background:#EDEBFB; color:#26215C; border-radius:14px; padding:9px 13px; font-size:14px;"
BUBBLE_USER = "background:#A79FF0; color:white; border-radius:14px; padding:9px 13px; font-size:14px;"
BUBBLE_MONO = "background:#EDEBFB; color:#26215C; border-radius:14px; padding:9px 13px; font-family:monospace; font-size:12px;"
ICON_BTN_STYLE = (
    "QPushButton { background: rgba(255,255,255,170); border: none; border-radius: 12px; font-size: 13px; }"
    "QPushButton:hover { background: rgba(255,255,255,230); }"
)

# How long a "happy" reaction lingers before Fella settles back to idle.
REACTION_MS = 1800


def make_bubble(text: str, who: str, mono: bool = False) -> QLabel:
    bubble = QLabel(text)
    bubble.setWordWrap(True)
    bubble.setMaximumWidth(320)
    bubble.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    bubble.setStyleSheet(BUBBLE_MONO if mono else (BUBBLE_FELLA if who == "Fella" else BUBBLE_USER))
    return bubble


def bubble_row(bubble: QLabel, who: str) -> QHBoxLayout:
    row = QHBoxLayout()
    if who == "Fella":
        row.addWidget(bubble)
        row.addStretch()
    else:
        row.addStretch()
        row.addWidget(bubble)
    return row


class AvatarLabel(QLabel):
    """The avatar image, draggable so you can reposition the floating window."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # startSystemMove() hands the drag off to the compositor, which
            # works on both X11 and Wayland - a plain window.move() in
            # mouseMoveEvent only works on X11 and is a silent no-op on
            # Wayland, where clients can't reposition their own windows.
            handle = self.window().windowHandle()
            if handle is not None:
                handle.startSystemMove()
            event.accept()


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Fella Settings")
        self.body, self.eye = settings.get_colors()

        layout = QVBoxLayout(self)

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.preview)
        self._refresh_preview()

        body_row = QHBoxLayout()
        body_row.addWidget(QLabel("Body color:"))
        self.body_btn = QPushButton()
        self.body_btn.setFixedWidth(60)
        self.body_btn.clicked.connect(self._pick_body)
        body_row.addWidget(self.body_btn)
        layout.addLayout(body_row)

        eye_row = QHBoxLayout()
        eye_row.addWidget(QLabel("Eye color:"))
        self.eye_btn = QPushButton()
        self.eye_btn.setFixedWidth(60)
        self.eye_btn.clicked.connect(self._pick_eye)
        eye_row.addWidget(self.eye_btn)
        layout.addLayout(eye_row)

        self._refresh_buttons()

        btn_row = QHBoxLayout()
        reset_btn = QPushButton("Reset to default")
        reset_btn.clicked.connect(self._reset)
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(reset_btn)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _refresh_preview(self):
        self.preview.setPixmap(render_face("idle", self.body, self.eye, 96))

    def _refresh_buttons(self):
        self.body_btn.setStyleSheet(f"background:{self.body}; border-radius:6px;")
        self.eye_btn.setStyleSheet(f"background:{self.eye}; border-radius:6px;")

    def _pick_body(self):
        color = QColorDialog.getColor(QColor(self.body), self, "Choose a body color")
        if color.isValid():
            self.body = color.name()
            self._refresh_buttons()
            self._refresh_preview()

    def _pick_eye(self):
        color = QColorDialog.getColor(QColor(self.eye), self, "Choose an eye color")
        if color.isValid():
            self.eye = color.name()
            self._refresh_buttons()
            self._refresh_preview()

    def _reset(self):
        self.body, self.eye = settings.DEFAULT_BODY, settings.DEFAULT_EYE
        self._refresh_buttons()
        self._refresh_preview()

    def _save(self):
        settings.set_colors(self.body, self.eye)
        self.accept()


class HistoryWindow(QWidget):
    def __init__(self, history: list[dict]):
        super().__init__()
        self.setWindowTitle("Fella — History")
        self.resize(420, 560)
        layout = QVBoxLayout(self)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        host = QWidget()
        vbox = QVBoxLayout(host)
        for msg in history:
            who = "Fella" if msg["role"] == "assistant" else "You"
            vbox.addLayout(bubble_row(make_bubble(msg["content"], who), who))
        vbox.addStretch()
        scroll.setWidget(host)
        layout.addWidget(scroll)

        QTimer.singleShot(0, lambda: scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum()))


class ChatWindow(QWidget):
    def __init__(self, model, recipes):
        super().__init__()
        self.model, self.recipes = model, recipes
        self.history = memory.recent()
        self._history_win = None
        self._settings_win = None

        self.setWindowTitle("Fella")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 10, 14, 14)

        toolbar = QHBoxLayout()
        toolbar.addStretch()
        hist_btn = QPushButton("🕘")
        hist_btn.setToolTip("View chat history")
        hist_btn.clicked.connect(self._open_history)
        settings_btn = QPushButton("⚙")
        settings_btn.setToolTip("Settings")
        settings_btn.clicked.connect(self._open_settings)
        close_btn = QPushButton("✕")
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self.close)
        for b in (hist_btn, settings_btn, close_btn):
            b.setFixedSize(26, 26)
            b.setStyleSheet(ICON_BTN_STYLE)
            toolbar.addWidget(b)
        outer.addLayout(toolbar)

        self.bubble_label = QLabel()
        self.bubble_label.setWordWrap(True)
        self.bubble_label.setMaximumWidth(320)
        self.bubble_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.bubble_label.hide()
        bubble_wrap = QHBoxLayout()
        bubble_wrap.addStretch()
        bubble_wrap.addWidget(self.bubble_label)
        bubble_wrap.addStretch()
        outer.addLayout(bubble_wrap)

        mid = QHBoxLayout()
        avatar_col = QVBoxLayout()
        self.avatar = AvatarLabel()
        self.avatar.setFixedSize(96, 96)
        self.avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar_col.addWidget(self.avatar)
        self.action_row = QHBoxLayout()
        avatar_col.addLayout(self.action_row)
        mid.addLayout(avatar_col)

        entry_col = QVBoxLayout()
        entry_col.addStretch()
        entry_row = QHBoxLayout()
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Tell me what's going on...")
        self.entry.setStyleSheet(
            "background: rgba(255,255,255,230); border-radius: 10px; padding: 7px 10px; font-size: 13px;"
        )
        self.entry.returnPressed.connect(self.send)
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.send)
        entry_row.addWidget(self.entry, 1)
        entry_row.addWidget(send_btn)
        entry_col.addLayout(entry_row)
        mid.addLayout(entry_col, 1)
        outer.addLayout(mid)

        self._set_mood("idle")
        name = memory.get_name()
        hello = f"Hi {name}! What's up?" if name else "Hi! I'm Fella. What should I call you?"
        self._say(hello)

    def _set_mood(self, mood: str):
        self.avatar.setPixmap(face_pixmap(mood, 88))

    def _say(self, text: str, mono: bool = False):
        self.bubble_label.setStyleSheet(BUBBLE_MONO if mono else BUBBLE_FELLA)
        self.bubble_label.setText(text)
        self.bubble_label.show()
        self.adjustSize()

    def _open_history(self):
        self._history_win = HistoryWindow(memory.recent(limit=200))
        self._history_win.show()

    def _open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec():
            self._set_mood("idle")

    def send(self):
        text = self.entry.text().strip()
        if not text:
            return
        if text.lower() in ("specs", "my specs", "what pc do i have", "my pc"):
            self.entry.clear()
            self._say(hardware.full_report(), mono=True)
            return
        self.entry.clear()
        memory.log("user", text)

        # naive name capture: "my name is X" / "call me X"
        m = re.search(r"(?:my name is|call me|i'm|i am)\s+([A-Za-z][\w-]{1,20})", text, re.I)
        if m and not memory.get_name():
            memory.set_name(m.group(1))

        self.history.append({"role": "user", "content": text})
        hw = hardware.summary_for_model()
        msgs = [{'role': 'system', 'content': hw}] + self.history[-12:]
        hint = recipe_hint(self.recipes) + "\n" + catalog_hint()
        self.worker = ChatWorker(self.model, msgs, hint)
        self._buf = ""
        self._set_mood("thinking")
        self._say("...")
        self.worker.chunk.connect(self._on_chunk)
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def _on_chunk(self, c):
        self._buf += c
        # Strip the recipe tag from view as it streams in so it never flashes on screen.
        self._say(RECIPE_RE.sub("", self._buf))

    def _on_done(self, full):
        clean = RECIPE_RE.sub("", full).strip()
        self._say(clean)
        memory.log("assistant", clean)
        self.history.append({"role": "assistant", "content": full})

        m = RECIPE_RE.search(full)
        if m and m.group(1) in self.recipes:
            self._offer_recipe(self.recipes[m.group(1)])
            return
        if m and m.group(1).startswith("install_") and m.group(1)[len("install_"):] in APPS:
            self._offer_recipe(install_recipe(m.group(1)[len("install_"):]))
            return

        last_user = next((msg["content"] for msg in reversed(self.history)
                          if msg["role"] == "user"), "")
        rec = match_recipe(last_user, self.recipes)
        if rec:
            self._offer_recipe(rec)
            return
        app = match_app(last_user)
        if app:
            key, _info = app
            self._offer_recipe(install_recipe(key))
            return
        if flatpak_apps.available():
            query = flatpak_apps.extract_query(last_user)
            if query:
                matches = flatpak_apps.search(query)
                if matches:
                    app_id, name = matches[0]
                    self._offer_recipe(flatpak_apps.install_recipe(app_id, name))
                    return

        self._react_happy()

    def _react_happy(self):
        self._set_mood("happy")
        QTimer.singleShot(REACTION_MS, lambda: self._set_mood("idle"))

    def _offer_recipe(self, recipe):
        self._set_mood("asking")
        while self.action_row.count():
            self.action_row.takeAt(0).widget().deleteLater()
        fix = QPushButton(f"✅ {recipe.title}")
        fix.clicked.connect(lambda: self._run(recipe))
        no = QPushButton("Not now")
        no.clicked.connect(self._clear_actions)
        self.action_row.addWidget(fix)
        self.action_row.addWidget(no)

    def _clear_actions(self):
        while self.action_row.count():
            self.action_row.takeAt(0).widget().deleteLater()
        self._set_mood("idle")

    def _run(self, recipe):
        self._clear_actions()
        self._set_mood("thinking")
        self._say(f"Okay, working on: {recipe.title}")
        for line in run_recipe(recipe):
            self._say(line)
            QApplication.processEvents()
        self._react_happy()


class FellaTray:
    def __init__(self, app):
        self.app = app
        self.recipes = load_recipes()
        models = brain.list_models()
        self.model = models[0] if models else None

        self.tray = QSystemTrayIcon(svg_icon("idle" if brain.is_up() else "sleeping"))
        self.tray.setToolTip("Fella")
        menu = QMenu()
        chat_action = QAction("Talk to Fella")
        chat_action.triggered.connect(self.open_chat)
        menu.addAction(chat_action)
        mem_action = QAction("Open my memory file")
        mem_action.triggered.connect(self.open_memory)
        menu.addAction(mem_action)
        menu.addSeparator()
        quit_action = QAction("Quit")
        quit_action.triggered.connect(app.quit)
        menu.addAction(quit_action)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._activated)
        self.tray.show()

        if not brain.is_up():
            self.tray.showMessage("Fella", "My brain (Ollama) isn't running yet. Start it, then click me.")
        elif not self.model:
            self.tray.showMessage("Fella", "No model found. Run: ollama pull qwen2.5:7b-instruct")

    def _activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.open_chat()

    def open_chat(self):
        if not brain.is_up() or not self.model:
            QMessageBox.information(None, "Fella",
                "I need my brain running first.\n\n"
                "1) sudo systemctl enable --now ollama\n"
                "2) ollama pull qwen2.5:7b-instruct")
            return
        self.win = ChatWindow(self.model, self.recipes)
        self.win.show()

    def open_memory(self):
        memory.load_profile()
        import subprocess
        subprocess.Popen(["xdg-open", str(memory.PROFILE)])


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("No system tray available.")
        return 1
    # Keep a reference - an unassigned FellaTray gets garbage collected almost
    # immediately, silently tearing down the tray icon right after it appears.
    tray = FellaTray(app)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
