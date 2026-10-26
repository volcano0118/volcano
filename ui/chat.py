"""Chat window for the Kuromi desktop pet.

DeepSeek through LangChain (langchain-openai), with streaming answers and a
persistent conversation list on the left (like the DeepSeek web app).
"""

from __future__ import annotations

import html
import json
import time
import uuid
from pathlib import Path

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ui.config import (
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    SYSTEM_PROMPT,
    user_data_path,
)

HISTORY_FILE = user_data_path("chat_history.json")

QSS = """
QWidget {
    background: #fdfbff;
    color: #2a242f;
    font-family: "Microsoft YaHei UI", "Segoe UI";
    font-size: 13px;
}
QLabel#header {
    font-size: 16px;
    font-weight: 600;
    padding: 10px 16px;
    background: #f7accc;
    color: #2a242f;
}
QLabel#section {
    color: #8d7f90;
    font-size: 11px;
    padding: 10px 8px 4px 8px;
    background: transparent;
}
QLabel#hint {
    color: #a99aa4;
    font-size: 11px;
    padding: 0 4px;
}
QListWidget {
    border: none;
    background: #f7f3f9;
    outline: 0;
    padding: 4px;
}
QListWidget::item {
    padding: 8px 10px;
    border-radius: 8px;
    color: #4a4350;
}
QListWidget::item:hover {
    background: #efe6f2;
}
QListWidget::item:selected {
    background: #f7accc;
    color: #2a242f;
}
QTextBrowser {
    border: 1px solid #efe9f2;
    border-radius: 10px;
    background: #ffffff;
    padding: 6px;
}
QLineEdit {
    border: 1px solid #e3dce8;
    border-radius: 16px;
    padding: 8px 14px;
    background: #ffffff;
}
QLineEdit:focus {
    border-color: #f7accc;
}
QPushButton#send {
    background: #f7accc;
    border: none;
    border-radius: 16px;
    padding: 8px 20px;
    font-weight: 600;
}
QPushButton#send:disabled {
    background: #f3e6ec;
    color: #b3a5af;
}
QPushButton#newChat {
    background: transparent;
    border: 1px solid #e3dce8;
    border-radius: 14px;
    padding: 6px 12px;
}
QPushButton#newChat:hover {
    border-color: #f7accc;
}
"""


class ChatStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.chats: list[dict] = []
        self._load()

    def _load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, list):
            return
        for chat in data:
            if (
                isinstance(chat, dict)
                and isinstance(chat.get("id"), str)
                and isinstance(chat.get("messages"), list)
            ):
                chat.setdefault("title", "新对话")
                chat.setdefault("updated", 0.0)
                self.chats.append(chat)

    def save(self) -> None:
        try:
            self.path.write_text(
                json.dumps(self.chats, ensure_ascii=False, indent=1), encoding="utf-8"
            )
        except OSError:
            pass

    def create(self) -> dict:
        chat = {
            "id": uuid.uuid4().hex,
            "title": "新对话",
            "updated": time.time(),
            "messages": [],
        }
        self.chats.append(chat)
        return chat

    def delete(self, chat: dict) -> None:
        self.chats = [c for c in self.chats if c["id"] != chat["id"]]

    def ordered(self) -> list[dict]:
        return sorted(self.chats, key=lambda c: c.get("updated", 0), reverse=True)


def _message_to_lc(role: str, content: str):
    from langchain_core.messages import AIMessage, HumanMessage

    return HumanMessage(content=content) if role == "user" else AIMessage(content=content)


class ChatWorker(QThread):
    chunk = pyqtSignal(str)
    failed = pyqtSignal(str)

    def __init__(self, messages, cancelled, parent=None):
        super().__init__(parent)
        self._messages = messages
        self._cancelled = cancelled

    def run(self) -> None:
        try:
            from langchain_openai import ChatOpenAI

            llm = ChatOpenAI(
                model=DEEPSEEK_MODEL,
                api_key=DEEPSEEK_API_KEY,
                base_url=DEEPSEEK_BASE_URL,
                temperature=0.7,
                streaming=True,
                max_retries=1,
            )
            for piece in llm.stream(self._messages):
                if self._cancelled():
                    return
                content = getattr(piece, "content", "")
                if isinstance(content, list):
                    content = "".join(
                        part.get("text", "") if isinstance(part, dict) else str(part)
                        for part in content
                    )
                if content:
                    self.chunk.emit(content)
        except Exception as exc:  # noqa: BLE001 - surfaced in the UI
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class ChatWindow(QWidget):
    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowTitle("Kuromi")
        self.resize(900, 580)
        self.setMinimumSize(560, 380)
        self.setAttribute(Qt.WidgetAttribute.WA_QuitOnClose, False)
        self.setStyleSheet(QSS)

        self.store = ChatStore(HISTORY_FILE)
        self.current: dict | None = None
        self._worker: ChatWorker | None = None
        self._cancelled = False

        header = QLabel("Kuromi")
        header.setObjectName("header")

        self.new_chat_btn = QPushButton("新对话")
        self.new_chat_btn.setObjectName("newChat")
        self.new_chat_btn.clicked.connect(self.reset)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 12, 0)
        top.addWidget(header, 1)
        top.addWidget(self.new_chat_btn)

        section = QLabel("会话历史")
        section.setObjectName("section")

        self.sessions = QListWidget()
        self.sessions.itemClicked.connect(self._on_session_clicked)
        self.sessions.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sessions.customContextMenuRequested.connect(self._session_menu)

        sidebar = QVBoxLayout()
        sidebar.setContentsMargins(0, 0, 0, 0)
        sidebar.setSpacing(0)
        sidebar.addWidget(section)
        sidebar.addWidget(self.sessions, 1)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(True)

        self.input = QLineEdit()
        self.input.setPlaceholderText("和库洛米说点什么…（Enter 发送）")
        self.input.returnPressed.connect(self.send_message)

        self.send = QPushButton("发送")
        self.send.setObjectName("send")
        self.send.clicked.connect(self.send_message)

        hint = QLabel(f"model: {DEEPSEEK_MODEL}")
        hint.setObjectName("hint")

        row = QHBoxLayout()
        row.setSpacing(8)
        row.addWidget(self.input, 1)
        row.addWidget(self.send)

        chat = QVBoxLayout()
        chat.setContentsMargins(10, 0, 0, 0)
        chat.setSpacing(8)
        chat.addWidget(self.view, 1)
        chat.addLayout(row)
        chat.addWidget(hint)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 12, 0)
        body.setSpacing(0)
        body.addLayout(sidebar)
        body.addLayout(chat, 1)
        self.sessions.setFixedWidth(210)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(8)
        layout.addLayout(top)
        layout.addLayout(body, 1)

        self._load_initial()
        self.input.setFocus()

    # -------------------------------------------------------------- sessions

    def _load_initial(self) -> None:
        chats = self.store.ordered()
        self._refresh_sessions(chats[0]["id"] if chats else None)
        if chats:
            self._open_chat(chats[0])
        else:
            self._render()

    def _refresh_sessions(self, select_id: str | None = None) -> None:
        self.sessions.blockSignals(True)
        self.sessions.clear()
        row = -1
        for index, chat in enumerate(self.store.ordered()):
            item = QListWidgetItem(chat.get("title") or "新对话")
            item.setData(Qt.ItemDataRole.UserRole, chat["id"])
            self.sessions.addItem(item)
            if chat["id"] == select_id:
                row = index
        if row >= 0:
            self.sessions.setCurrentRow(row)
        self.sessions.blockSignals(False)

    def _chat_by_id(self, chat_id: str) -> dict | None:
        for chat in self.store.chats:
            if chat["id"] == chat_id:
                return chat
        return None

    def _on_session_clicked(self, item: QListWidgetItem) -> None:
        if self._worker is not None:
            return
        chat = self._chat_by_id(item.data(Qt.ItemDataRole.UserRole))
        if chat is not None:
            self._open_chat(chat)

    def _open_chat(self, chat: dict) -> None:
        self.current = chat
        self._render(scroll=True)
        self._refresh_sessions(chat["id"])
        self.input.setFocus()

    def _session_menu(self, pos) -> None:
        item = self.sessions.itemAt(pos)
        if item is None or self._worker is not None:
            return
        chat = self._chat_by_id(item.data(Qt.ItemDataRole.UserRole))
        if chat is None:
            return
        menu = QMenu(self)
        delete = menu.addAction("删除会话")
        if menu.exec(self.sessions.viewport().mapToGlobal(pos)) is delete:
            self.store.delete(chat)
            if self.current is chat:
                self.current = None
                self._render()
            self.store.save()
            self._refresh_sessions(None)

    # ------------------------------------------------------------------ chat

    def send_message(self) -> None:
        text = self.input.text().strip()
        if not text or self._worker is not None:
            return
        self.input.clear()

        if self.current is None:
            self.current = self.store.create()
        messages = self.current["messages"]
        messages.append({"role": "user", "content": text})
        messages.append({"role": "assistant", "content": ""})
        if self.current.get("title") in (None, "", "新对话"):
            self.current["title"] = text.replace("\n", " ")[:20]
        self.current["updated"] = time.time()
        self.store.save()
        self._refresh_sessions(self.current["id"])
        self._render(scroll=True)
        self._start_worker()

    def _start_worker(self) -> None:
        from langchain_core.messages import SystemMessage

        assert self.current is not None
        history = [SystemMessage(content=SYSTEM_PROMPT)]
        for message in self.current["messages"][:-1]:
            if message.get("content"):
                history.append(
                    _message_to_lc(message["role"], message["content"])
                )

        self._cancelled = False
        self._worker = ChatWorker(history, lambda: self._cancelled, self)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()
        self._set_busy(True)

    def _on_chunk(self, text: str) -> None:
        if self.current is None or not self.current["messages"]:
            return
        self.current["messages"][-1]["content"] += text
        self._render(scroll=True)

    def _on_failed(self, error: str) -> None:
        if self.current is None or not self.current["messages"]:
            return
        self.current["messages"][-1]["content"] = f"[出错了] {error}"
        self._render(scroll=True)
        self._set_busy(False)

    def _on_finished(self) -> None:
        if self.current is not None:
            self.current["updated"] = time.time()
            self.store.save()
        self._set_busy(False)
        if self._worker is not None:
            self._worker.wait(500)
            self._worker.deleteLater()
            self._worker = None

    def _set_busy(self, busy: bool) -> None:
        self.send.setEnabled(not busy)
        self.send.setText("思考中…" if busy else "发送")
        self.input.setEnabled(not busy)
        self.sessions.setEnabled(not busy)
        self.new_chat_btn.setEnabled(not busy)

    def reset(self) -> None:
        if self._worker is not None:
            return
        self.current = None
        self.sessions.clearSelection()
        self._render()
        self.input.setFocus()

    # ------------------------------------------------------------------- ui

    def _render(self, scroll: bool = False) -> None:
        rows = []
        if self.current is not None:
            for message in self.current["messages"]:
                text = html.escape(message.get("content", "")).replace("\n", "<br/>")
                if not text:
                    text = "…"
                if message.get("role") == "user":
                    side, color = "right", "#f7accc"
                else:
                    side, color = "left", "#f1edf4"
                inner = (
                    f'<table cellspacing="0" cellpadding="9" bgcolor="{color}">'
                    f'<tr><td style="color:#2a242f;">{text}</td></tr></table>'
                )
                rows.append(
                    f'<table width="100%" cellspacing="0" cellpadding="5">'
                    f'<tr><td align="{side}">{inner}</td></tr></table>'
                )
        self.view.setHtml('<div style="padding:6px;">' + "".join(rows) + "</div>")
        if scroll:
            bar = self.view.verticalScrollBar()
            bar.setValue(bar.maximum())

    def open(self) -> None:
        if not self.isVisible():
            from PyQt6.QtGui import QGuiApplication

            screen = QGuiApplication.primaryScreen().availableGeometry()
            self.move(
                screen.center().x() - self.width() // 2,
                screen.center().y() - self.height() // 2,
            )
        self.show()
        self.raise_()
        self.activateWindow()
        self.input.setFocus()

    def shutdown(self) -> None:
        self._cancelled = True
        self.store.save()
        if self._worker is not None:
            self._worker.wait(1500)
