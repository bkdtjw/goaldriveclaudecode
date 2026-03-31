"""日志模块"""

import logging
import sys
from pathlib import Path
from typing import Optional

from goaldriveclaude.config import get_config


def get_logger(name: str) -> logging.Logger:
    """获取配置好的 logger

    Args:
        name: logger 名称

    Returns:
        配置好的 logger
    """
    config = get_config()
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(getattr(logging, config.log_level.upper()))

        # 控制台处理器
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # 文件处理器（如果配置了）
        if config.log_file:
            file_handler = logging.FileHandler(config.log_file)
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)

    return logger
