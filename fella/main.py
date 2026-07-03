"""Fella — the tray companion. Run with:  python -m fella.main

Sits in your KDE system tray showing Fella's face. Click to chat.
Detects problems you describe, offers a recipe, and only acts with your OK.
"""

import re
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QByteArray
from PySide6.QtGui import QIcon, QPixmap, QAction, QTextCursor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QMessageBox,
)

from . import brain, memory, hardware
from .face import face_svg
from .recipes import load_recipes, recipe_hint, run_recipe

ACCENT_BODY = "#A79FF0"
ACCENT_EYE = "#26215C"
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



def svg_icon(mood: str) -> QIcon:
    svg = face_svg(mood, ACCENT_BODY, ACCENT_EYE).encode()
    renderer = QSvgRenderer(QByteArray(svg))
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    from PySide6.QtGui import QPainter
    p = QPainter(pm)
    renderer.render(p)
    p.end()
    return QIcon(pm)


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


class ChatWindow(QWidget):
    def __init__(self, model, recipes):
        super().__init__()
        self.model, self.recipes = model, recipes
        self.history = memory.recent()
        self.pending_recipe = None

        self.setWindowTitle("Fella")
        self.resize(440, 560)
        layout = QVBoxLayout(self)

        name = memory.get_name()
        hello = f"Hi {name}! What's up?" if name else "Hi! I'm Fella. What should I call you?"
        header = QLabel("🔒 Running locally · 0 bytes sent")
        header.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(header)

        self.log = QTextEdit(readOnly=True)
        self.log.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.log, 1)
        self._append("Fella", hello)

        row = QHBoxLayout()
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Tell me what's going on...")
        self.entry.returnPressed.connect(self.send)
        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.send)
        row.addWidget(self.entry, 1)
        row.addWidget(send_btn)
        layout.addLayout(row)

        self.action_row = QHBoxLayout()
        layout.addLayout(self.action_row)

    def _append(self, who: str, text: str):
        color = "#7F77DD" if who == "Fella" else "#333"
        self.log.append(f'<b style="color:{color}">{who}:</b> {text}')
        self.log.moveCursor(QTextCursor.MoveOperation.End)

    def _set_stream_text(self, text: str):
        cursor = self.log.textCursor()
        cursor.setPosition(self._stream_anchor)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        cursor.removeSelectedText()
        cursor.insertText(text)
        self.log.setTextCursor(cursor)
        self.log.ensureCursorVisible()

    def send(self):
        text = self.entry.text().strip()
        if not text:
            return
        if text.lower() in ("specs", "my specs", "what pc do i have", "my pc"):
            self._append("You", text)
            self._append("Fella", "Here's what I can see on your machine:")
            self._append("Fella", "<pre>" + hardware.full_report() + "</pre>")
            self.entry.clear()
            return
        self.entry.clear()
        self._append("You", text)
        memory.log("user", text)

        # naive name capture: "my name is X" / "call me X"
        m = re.search(r"(?:my name is|call me|i'm|i am)\s+([A-Za-z][\w-]{1,20})", text, re.I)
        if m and not memory.get_name():
            memory.set_name(m.group(1))

        self.history.append({"role": "user", "content": text})
        hw = hardware.summary_for_model()
        msgs = [{'role': 'system', 'content': hw}] + self.history[-12:]
        self.worker = ChatWorker(self.model, msgs, recipe_hint(self.recipes))
        self._buf = ""
        self._append("Fella", "")
        self._stream_anchor = self.log.textCursor().position()
        self.worker.chunk.connect(self._on_chunk)
        self.worker.done.connect(self._on_done)
        self.worker.start()

    def _on_chunk(self, c):
        self._buf += c
        # Strip the recipe tag from view as it streams in so it never flashes on screen.
        self._set_stream_text(RECIPE_RE.sub("", self._buf))

    def _on_done(self, full):
        clean = RECIPE_RE.sub("", full).strip()
        self._set_stream_text(clean)
        memory.log("assistant", clean)
        self.history.append({"role": "assistant", "content": full})

        m = RECIPE_RE.search(full)
        if m and m.group(1) in self.recipes:
            self._offer_recipe(self.recipes[m.group(1)])
        else:
            last_user = next((msg["content"] for msg in reversed(self.history)
                              if msg["role"] == "user"), "")
            rec = match_recipe(last_user, self.recipes)
            if rec:
                self._offer_recipe(rec)

    def _offer_recipe(self, recipe):
        # clear old buttons
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

    def _run(self, recipe):
        self._clear_actions()
        self._append("Fella", f"Okay, working on: {recipe.title}")
        for line in run_recipe(recipe):
            self._append("Fella", line)
            QApplication.processEvents()


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
    FellaTray(app)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
