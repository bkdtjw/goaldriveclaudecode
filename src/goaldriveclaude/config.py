"""配置管理 - 从环境变量和默认值加载配置"""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings

# 加载 .env 文件
load_dotenv()


class Config(BaseSettings):
    """GoalDriveClaude 配置"""

    model_config = ConfigDict(
        env_prefix="",
        case_sensitive=False,
    )

    # API 配置
    anthropic_api_key: str = Field(default="", description="Anthropic API Key")
    default_model: str = Field(
        default="claude-3-5-sonnet-20241022", description="默认使用的 Claude 模型"
    )

    # 执行配置
    max_iterations: int = Field(default=50, description="最大迭代次数")
    max_verification_attempts: int = Field(default=3, description="最大验证尝试次数")
    max_consecutive_failures: int = Field(default=3, description="最大连续失败次数")

    # 工具配置
    bash_timeout: int = Field(default=30, description="Bash 命令超时时间（秒）")
    python_timeout: int = Field(default=30, description="Python 代码执行超时时间（秒）")

    # 路径配置
    session_dir: Path = Field(
        default=Path.home() / ".goaldriveclaude" / "sessions",
        description="会话存储目录",
    )
    working_directory: Path = Field(default=Path.cwd(), description="工作目录")

    # 日志配置
    log_level: str = Field(default="INFO", description="日志级别")
    log_file: Optional[Path] = Field(default=None, description="日志文件路径")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 确保会话目录存在
        self.session_dir.mkdir(parents=True, exist_ok=True)


# 全局配置实例
_config: Optional[Config] = None


def get_config() -> Config:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def reload_config() -> Config:
    """重新加载配置"""
    global _config
    _config = Config()
    return _config
