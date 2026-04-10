# Tiny Ralph Agent

> Ralph Is Learning And Repeating From Humble Tasks
>
> 专为小模型优化的自主智能体框架，基于第一性原理的感知-决策-执行-反馈四层闭环架构

## 核心特性

- **四层闭环架构**：感知 → 决策 → 执行 → 反馈
- **原子化任务拆解**：每步只做一件事，避免小模型上下文溢出
- **工具自造能力**：没有可用工具时自动创建
- **Ralph 循环**：每次迭代全新上下文，状态持久化
- **小模型友好**：极度结构化 Prompt，三要素清单式输入

## 快速开始

### 1. 安装依赖

```bash
pip install langchain-core langgraph ollama requests python-dotenv
```

### 2. 启动 Ollama

```bash
ollama run qwen3.5:4b
```

### 3. 运行示例

```python
from agent.ralph_loop import RalphLoop
from infrastructure.llm.ollama import OllamaRuntime

# 初始化
llm = OllamaRuntime(default_model="qwen3.5:4b")
ralph = RalphLoop(llm=llm)

# 执行任务
result = ralph.create_and_run("列出当前目录的 Python 文件")

print(f"成功: {result['success']}")
print(f"迭代次数: {result['iterations']}")
```

## 项目结构

```
├── agent/                      # 智能体核心
│   ├── ralph_loop.py          # Ralph 循环核心
│   ├── graph.py               # LangGraph 集成
│   └── assembly.py            # 智能体组装
├── middleware/                 # 中间件层
│   ├── decision_small.py      # 决策层（小模型版）
│   ├── execution_small.py     # 执行层（小模型版）
│   └── feedback_small.py      # 反馈层（小模型版）
├── infrastructure/            # 基础设施
│   ├── task_state.py         # 任务状态管理
│   ├── tool_verifier.py      # 工具验证器
│   └── skill_library.py      # 技能沉淀库
└── .trae/skills/ralph/       # Ralph Skill
```

## Ralph 循环工作流程

```
┌─────────────────────────────────────────────────────────┐
│                     Ralph 循环                          │
│                                                          │
│  ┌─────────┐    ┌──────────┐    ┌─────────────┐          │
│  │ prd.json │ → │  Ralph   │ → │  Task Handler│          │
│  │ (任务池) │    │   Loop   │    │   (AI/Func) │          │
│  └─────────┘    └──────────┘    └─────────────┘          │
│       ↑                                    │              │
│       └──────── progress.txt (learnings) ←┘              │
└─────────────────────────────────────────────────────────┘
```

## 架构设计

### 四层闭环

```
感知层 (Perception)
    ↓
决策层 (Decision) ← 原子化拆解 + 工具绑定
    ↓
执行层 (Execution) ← 分步执行 + 验证
    ↓
反馈层 (Feedback) ← 规则判断 + 学习记录
    ↓
    ↺ (循环直到完成)
```

### 与 LangGraph 集成

```python
from agent.graph import build_ralph_graph

# 构建 Ralph 图
app = build_ralph_graph(llm=llm)

# 运行
result = app.invoke({"task": "分析代码结构"})
```

## 许可证

MIT License
