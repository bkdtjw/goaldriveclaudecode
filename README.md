# GoalDriveClaude - 基于 LangGraph 的目标驱动型终端 Agent

## 核心理念

普通 Agent 的工作方式：执行步骤 → 步骤完了 → 结束。

GoalDriveClaude 的工作方式：理解目标 → 分解子目标 → 执行 → **验证目标是否真正达成** → 没达成就继续 → 达成了才结束。

**类比**：普通 Agent 像一个只管做菜不管味道的厨师；GoalDriveClaude 像一个做完菜还要亲自品尝确认达标的厨师。

## 安装

```bash
pip install -e .
```

## 配置

复制 `.env.example` 到 `.env` 并填写你的配置：

```bash
cp .env.example .env
# 编辑 .env 文件，添加 ANTHROPIC_API_KEY
```

## 使用

### 命令行模式

```bash
# 执行单个目标
goaldriveclaude "创建一个 Flask 博客应用"

# 交互模式
goaldriveclaude -i

# 恢复会话
goaldriveclaude --resume abc123

# 查看历史
goaldriveclaude --history
```

### Python API

```python
from goaldriveclaude.core.graph import build_graph
from goaldriveclaude.core.state import AgentState

graph = build_graph()
result = graph.invoke({
    "original_goal": "创建一个 FastAPI 项目",
    "messages": [],
    "subgoals": [],
    "current_subgoal_index": 0,
    "goal_verified": False,
})
```

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│  GoalDriveClaude                                            │
│  ╭──────────────╮    ╭──────────╮    ╭──────────────╮       │
│  │ Goal Analyzer│───►│ Planner  │───►│ Executor     │       │
│  │ (目标分解)    │    │ (规划)    │    │ (执行工具)    │       │
│  ╰──────────────╯    ╰──────────╯    ╰──────────────╯       │
│                                              │              │
│  ╭──────────────╮    ╭──────────╮    ╭───────▼──────╮       │
│  │ Verifier ⭐   │◄───│ Evaluator│◄───│ Tools        │       │
│  │ (目标验证)    │    │ (评估)    │    │ (工具调用)    │       │
│  ╰──────────────╯    ╰──────────╯    ╰──────────────╯       │
│         │                                                    │
│         └──────────────────────────────────┐                │
│              验证失败 → 重新规划            │                │
│              验证通过 → 任务完成            ▼                │
│                                    ╭──────────────╮         │
│                                    │ END          │         │
│                                    ╰──────────────╯         │
└─────────────────────────────────────────────────────────────┘
```

## 核心差异

| 特性 | 普通 Agent | GoalDriveClaude |
|-----|-----------|-----------------|
| 完成判断 | 步骤执行完即结束 | 验证目标真正达成 |
| 错误恢复 | 简单重试 | 结构化错误恢复 + 人工介入 |
| 目标追踪 | 无 | 子目标分解 + 依赖管理 |
| 验证机制 | 无 | 可执行的验证标准 |

## 项目结构

```
goaldriveclaude/
├── src/goaldriveclaude/
│   ├── cli.py              # CLI 入口
│   ├── config.py           # 配置管理
│   ├── core/
│   │   ├── state.py        # AgentState 定义
│   │   ├── graph.py        # LangGraph 图定义
│   │   └── models.py       # Pydantic 模型
│   ├── nodes/
│   │   ├── goal_analyzer.py    # 目标分解
│   │   ├── planner.py          # 动态规划
│   │   ├── executor.py         # 工具执行
│   │   ├── evaluator.py        # 结果评估
│   │   ├── verifier.py         # ⭐ 目标验证
│   │   ├── error_recovery.py   # 错误恢复
│   │   └── human_input.py      # 人机交互
│   ├── tools/              # 工具系统
│   ├── prompts/            # Prompt 模板
│   └── utils/              # 工具函数
└── tests/                  # 测试
```

## License

MIT
