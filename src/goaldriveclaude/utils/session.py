"""会话持久化模块"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from goaldriveclaude.config import get_config
from goaldriveclaude.core.state import AgentState


class SessionManager:
    """会话管理器"""

    def __init__(self):
        config = get_config()
        self.session_dir = config.session_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, goal: str) -> str:
        """创建新会话

        Args:
            goal: 目标

        Returns:
            会话 ID
        """
        session_id = uuid.uuid4().hex[:12]
        session_data = {
            "session_id": session_id,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "goal": goal,
            "state": {},
        }

        self._save_session(session_id, session_data)
        return session_id

    def save_state(self, session_id: str, state: AgentState) -> None:
        """保存状态

        Args:
            session_id: 会话 ID
            state: 状态
        """
        session_data = self._load_session(session_id)
        if session_data:
            # 不保存 messages，太大
            state_to_save = {k: v for k, v in state.items() if k != "messages"}
            session_data["state"] = state_to_save
            session_data["updated_at"] = datetime.now().isoformat()
            self._save_session(session_id, session_data)

    def load_state(self, session_id: str) -> Optional[AgentState]:
        """加载状态

        Args:
            session_id: 会话 ID

        Returns:
            状态或 None
        """
        session_data = self._load_session(session_id)
        if session_data and "state" in session_data:
            return session_data["state"]
        return None

    def list_sessions(self) -> list[dict]:
        """列出所有会话

        Returns:
            会话列表
        """
        sessions = []
        for session_file in self.session_dir.glob("*.json"):
            try:
                with open(session_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    sessions.append({
                        "session_id": data.get("session_id"),
                        "created_at": data.get("created_at"),
                        "updated_at": data.get("updated_at"),
                        "goal": data.get("goal"),
                    })
            except:
                pass

        return sorted(sessions, key=lambda x: x["updated_at"], reverse=True)

    def _get_session_path(self, session_id: str) -> Path:
        """获取会话文件路径"""
        return self.session_dir / f"{session_id}.json"

    def _save_session(self, session_id: str, data: dict) -> None:
        """保存会话数据"""
        session_path = self._get_session_path(session_id)
        with open(session_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _load_session(self, session_id: str) -> Optional[dict]:
        """加载会话数据"""
        session_path = self._get_session_path(session_id)
        if session_path.exists():
            with open(session_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None
