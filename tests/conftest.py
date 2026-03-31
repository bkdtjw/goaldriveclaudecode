"""测试配置"""

import pytest

from goaldriveclaude.config import get_config


class TestConfig:
    """测试配置"""

    def test_config_exists(self):
        config = get_config()
        assert config is not None
        assert hasattr(config, "max_iterations")
