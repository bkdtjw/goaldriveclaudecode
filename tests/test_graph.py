"""测试图"""

import pytest

from goaldriveclaude.core.graph import build_graph


class TestGraph:
    """测试图"""

    def test_build_graph(self):
        """测试图是否能成功构建"""
        graph = build_graph()
        assert graph is not None
