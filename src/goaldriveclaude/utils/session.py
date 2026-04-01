"""会话持久化模块"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from goaldriveclaude.config import get_config
from goaldriveclaude.core.state import AgentState


def _serialize_messages(messages: list[Any]) -> list[dict]:
    """将 messages 序列化为可 JSON 存储的格式。"""
    from langchain_core.messages import message_to_dict

    serialized: list[dict] = []
    for m in messages[-20:]:
        if isinstance(m, tuple):
            role = str(m[0]) if len(m) > 0 else "unknown"
            content = str(m[1]) if len(m) > 1 else ""
            type_map = {
                "human": "human",
                "user": "human",
                "ai": "ai",
                "assistant": "ai",
                "system": "system",
                "tool": "tool",
            }
            lc_type = type_map.get(role, role)
            serialized.append({"type": lc_type, "data": {"content": content}})
        else:
            try:
                serialized.append(message_to_dict(m))
            except Exception:
                pass
    return serialized


def _deserialize_messages(serialized: list[dict]) -> list[Any]:
    """将序列化后的 messages 还原为 LangChain 消息对象或元组。"""
    from langchain_core.messages import messages_from_dict

    # 若序列化格式来自 tuple，其结构为 {"type": "human", "data": {"content": "..."}}
    # 这与 message_to_dict 的输出一致（LangChain dict 格式）
    try:
        return messages_from_dict(serialized)
    except Exception:
        # 降级：返回空列表
        return []


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
        if not session_data:
            # 文件损坏时兜底重建
            session_data = {
                "session_id": session_id,
                "created_at": datetime.now().isoformat(),
                "goal": state.get("original_goal", ""),
                "state": {},
            }
        # 保留最近 20 条 messages 以支持 waiting_for_user 恢复
        state_to_save = dict(state)
        messages = state_to_save.get("messages", [])
        state_to_save["messages"] = _serialize_messages(messages)
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
            state = session_data["state"]
            serialized_messages = state.get("messages", [])
            if serialized_messages:
                state["messages"] = _deserialize_messages(serialized_messages)
            return state
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
            except Exception:
                pass

        return sorted(sessions, key=lambda x: x["updated_at"], reverse=True)

    def _get_session_path(self, session_id: str) -> Path:
        """获取会话文件路径"""
        return self.session_dir / f"{session_id}.json"

    def _save_session(self, session_id: str, data: dict) -> None:
        """保存会话数据（原子写入，防止半写文件）。"""
        session_path = self._get_session_path(session_id)
        temp_path = session_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        temp_path.replace(session_path)

    def _load_session(self, session_id: str) -> Optional[dict]:
        """加载会话数据"""
        session_path = self._get_session_path(session_id)
        if session_path.exists():
            try:
                with open(session_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return None
        return None
