# 智能体设计方案 - LangChain 生态架构版（重构版）

> 基于纯逻辑推理 + LangChain v1 Core / LangGraph / DeepAgents 的智能体架构设计
> 
> **核心设计原则**：模块即中间件，基础设施直接使用 LangChain v1 Core，整体使用 DeepAgents Agent API 组装

---

## 一、设计方法论

### 1.1 核心原则

本方案采用**纯逻辑演绎法**结合**LangChain生态最佳实践**进行架构设计：

1. **从本质定义出发**：智能体 = 感知 → 决策 → 执行 → 反馈 → 修正的闭环系统
2. **逻辑必然性推导**：每个环节必然需要什么（属性）和能做什么（方法）
3. **生态优先原则**：优先使用 LangChain/LangGraph/DeepAgents 原生能力，避免重复造轮子
4. **模块即中间件**：模块层封装业务逻辑，作为中间件调用底层基础设施
5. **简洁组装原则**：使用 DeepAgents Agent API 进行整体组装

### 1.2 推导链条

```
智能体本质定义
      ↓
感知→决策→执行→反馈→修正（5个环节）
      ↓
每个环节必然需要什么（纯逻辑）
      ↓
中间件层：4个核心中间件（业务逻辑封装）
      ↓
映射到 LangChain 生态组件
      ↓
LangGraph StateGraph 编排
      ↓
DeepAgents Agent API 组装
```

---

## 二、架构分层设计

### 2.1 架构分层映射（重构后）

```
┌─────────────────────────────────────────────────────────────────┐
│                    DeepAgents Agent API 层                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  • Agent 组装与编排（create_react_agent / AgentGraph）     │  │
│  │  • 上下文管理（自动摘要、大输出保存）                       │  │
│  │  • 多代理协作（Human-in-the-loop）                         │  │
│  │  • MCP 工具集成                                            │  │
│  └───────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                        LangGraph 层                             │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  StateGraph（状态图编排）                                   │  │
│  │  ├── State（TypedDict + Annotated + Reducer）              │  │
│  │  ├── Node（中间件实例作为节点）                             │  │
│  │  ├── Edge（条件边、循环边）                                 │  │
│  │  └── Checkpointer（持久化检查点）                           │  │
│  └───────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                      中间件层（业务逻辑封装）                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐│
│  │ 感知中间件   │ │ 决策中间件   │ │ 执行中间件   │ │ 反馈中间件   ││
│  │Perception   │ │  Decision  │ │  Execution │ │  Feedback   ││
│  │Middleware   │ │ Middleware │ │ Middleware │ │ Middleware  ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘│
├─────────────────────────────────────────────────────────────────┤
│                      LangChain Core 层                          │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Runnable 协议体系                                          │  │
│  │  ├── BaseChatModel（LLM统一接口）                          │  │
│  │  ├── BaseTool / @tool（工具定义）                          │  │
│  │  ├── BaseRetriever（检索器）                               │  │
│  │  ├── RunnableConfig（运行时配置）                          │  │
│  │  └── MemorySaver（检查点持久化）                           │  │
│  └───────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                      基础设施层（直接使用）                       │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  • init_chat_model() - LLM 初始化                          │  │
│  │  • RunnableConfig - 运行时配置                             │  │
│  │  • MemorySaver - 状态持久化                                │  │
│  │  • SystemContext - 系统上下文（保留）                      │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 组件映射对照表（重构后）

| 原设计组件 | 重构后设计 | 映射说明 |
|-----------|-----------|---------|
| **感知模块** | `PerceptionMiddleware` | 继承 `BaseRetriever`，封装业务感知逻辑 |
| **决策模块** | `DecisionMiddleware` | 实现 `__call__(state)`，返回 `Command` |
| **执行模块** | `ExecutionMiddleware` | 管理 `BaseTool` 集合，提供 `ToolNode` |
| **反馈模块** | `FeedbackMiddleware` | 实现 `__call__(state)`，支持 `interrupt` |
| **LLMService** | `init_chat_model()` | 直接使用 LangChain 原生函数 |
| **ContextManager** | `RunnableConfig` + `SystemContext` | 保留 SystemContext，其余用 RunnableConfig |
| **MemoryService** | `MemorySaver` | 使用 LangGraph 原生检查点 |
| **Agent 编排** | `create_react_agent()` / `AgentGraph` | 使用 DeepAgents API 或 LangGraph |

---

## 三、核心设计原则

### 3.1 模块即中间件

```python
# 设计原则：中间件封装业务逻辑，调用底层基础设施

class PerceptionMiddleware(BaseRetriever):
    """
    感知中间件
    
    职责：
    1. 封装业务感知逻辑（从哪些源获取、如何过滤）
    2. 调用 LangChain BaseRetriever 基础设施
    3. 对外提供统一的感知接口
    """
    
    def __init__(self, config_loader, document_processor):
        # 业务依赖
        self.config_loader = config_loader
        self.processor = document_processor
        # 底层基础设施在父类 BaseRetriever 中
    
    def _get_relevant_documents(self, query: str) -> List[Document]:
        # 业务逻辑：从配置加载感知源
        sources = self.config_loader.get_sources()
        
        # 业务逻辑：感知数据
        raw_data = self._sense_from_sources(sources, query)
        
        # 业务逻辑：处理和过滤
        processed = self.processor.process(raw_data)
        
        # 返回 LangChain Document（基础设施格式）
        return processed


class DecisionMiddleware:
    """
    决策中间件
    
    职责：
    1. 封装业务决策逻辑（如何拆解目标、如何规划）
    2. 调用 LangChain BaseChatModel 基础设施
    3. 对外提供 LangGraph Node 接口
    """
    
    def __init__(self, llm: BaseChatModel, prompt_templates):
        # 基础设施：LangChain LLM
        self.llm = llm
        # 业务依赖：prompt 模板
        self.prompts = prompt_templates
    
    def __call__(self, state: Dict) -> Command:
        # 业务逻辑：构建决策 prompt
        decision_prompt = self.prompts.build_decision_prompt(state)
        
        # 基础设施：调用 LLM
        response = self.llm.invoke(decision_prompt)
        
        # 业务逻辑：解析决策结果
        decision = self._parse_decision(response)
        
        # 基础设施：返回 LangGraph Command
        return Command(update={...}, goto=decision.next_step)
```

### 3.2 基础设施直接使用 LangChain v1 Core

```python
# 不再封装，直接使用

from langchain.chat_models import init_chat_model
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

# LLM 初始化 - 直接使用
def get_llm(config: dict) -> BaseChatModel:
    return init_chat_model(
        model=config["model"],
        model_provider=config["provider"],
        temperature=config.get("temperature", 0.7),
    )

# 运行时配置 - 直接使用
runnable_config = RunnableConfig(
    tags=["agent"],
    metadata={"task": "analysis"}
)

# 状态持久化 - 直接使用
checkpointer = MemorySaver()
```

### 3.3 整体使用 DeepAgents Agent API 组装

```python
# 方式1：使用 DeepAgents 高层 API（最简洁）
from deepagents import create_react_agent

agent = create_react_agent(
    model=llm,
    tools=tools,
    prompt=system_prompt,
    interrupt_before=["human_review"],
)

# 方式2：使用 LangGraph 精细控制
from langgraph.graph import StateGraph

workflow = StateGraph(AgentState)
workflow.add_node("perception", perception_middleware)
workflow.add_node("decision", decision_middleware)
# ... 编排边
agent = workflow.compile(checkpointer=checkpointer)
```

---

## 四、中间件层详细设计

### 4.1 感知中间件（PerceptionMiddleware）

```python
# middleware/perception.py
from langchain_core.retrievers import BaseRetriever
from langchain_core.documents import Document
from typing import List, Any, Optional

class PerceptionMiddleware(BaseRetriever):
    """
    感知中间件
    
    逻辑必然性：
    - 必须获取数据 → _get_relevant_documents()
    - 数据是连续的 → raw_data_buffer
    - 不能处理所有数据 → filter_rules
    - 要知道从哪获取 → subscribed_sources
    
    整合方式：继承 BaseRetriever，实现业务感知逻辑
    """
    
    def __init__(
        self,
        subscribed_sources: List[str] = None,
        filter_rules: List[callable] = None,
        perception_window: int = 100
    ):
        self.subscribed_sources = subscribed_sources or []
        self.filter_rules = filter_rules or []
        self.perception_window = perception_window
        self.raw_data_buffer: List[Any] = []
    
    def _get_relevant_documents(self, query: str) -> List[Document]:
        """LangChain Retriever 接口实现"""
        # 1. 感知数据（业务逻辑）
        raw_data = self._sense(query)
        
        # 2. 存储到缓冲区（业务逻辑）
        self._store(raw_data)
        
        # 3. 过滤数据（业务逻辑）
        filtered_data = self._filter(raw_data)
        
        # 4. 转换为 LangChain Document（基础设施格式）
        return [
            Document(page_content=str(d), metadata={"source": "perception"})
            for d in filtered_data
        ]
    
    def _sense(self, query: str) -> List[Any]:
        """业务逻辑：从各源获取数据"""
        results = []
        for source in self.subscribed_sources:
            data = self._fetch_from_source(source, query)
            results.extend(data)
        return results
    
    def _filter(self, data: List[Any]) -> List[Any]:
        """业务逻辑：应用过滤规则"""
        for rule in self.filter_rules:
            data = [d for d in data if rule(d)]
        return data
    
    def _store(self, data: List[Any]):
        """业务逻辑：维护缓冲区"""
        self.raw_data_buffer.extend(data)
        if len(self.raw_data_buffer) > self.perception_window:
            self.raw_data_buffer = self.raw_data_buffer[-self.perception_window:]
```

### 4.2 决策中间件（DecisionMiddleware）

```python
# middleware/decision.py
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import SystemMessage, HumanMessage
from langgraph.types import Command
from typing import Literal, List, Dict, Any

class DecisionMiddleware:
    """
    决策中间件
    
    逻辑必然性：
    - 必须有目标 → goal_state
    - 目标要拆解 → decompose()
    - 需要参考信息 → decision_context
    - 要有备选 → alternative_plans
    
    整合方式：实现 __call__ 作为 LangGraph Node
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        context: Any,
        prompt_templates: Any
    ):
        # 基础设施：LangChain LLM
        self.llm = llm
        # 业务依赖
        self.context = context
        self.prompts = prompt_templates
    
    def __call__(
        self,
        state: Dict[str, Any]
    ) -> Command[Literal["execute", "feedback", "__end__"]]:
        """LangGraph Node 入口"""
        # 1. 获取目标
        goal = state.get("goal", "")
        if not goal:
            return Command(update={"error": "No goal"}, goto="feedback")
        
        # 2. 构建决策上下文（业务逻辑）
        decision_context = self._build_context(state)
        
        # 3. 目标拆解（业务逻辑 + LLM）
        sub_goals = self._decompose_goal(goal, decision_context)
        
        # 4. 生成计划（业务逻辑）
        plan = self._generate_plan(sub_goals)
        
        # 5. 决策下一步（业务逻辑）
        next_step = self._decide_next_action(plan, state)
        
        # 6. 返回 Command（基础设施）
        return Command(
            update={"plan": plan, "sub_goals": sub_goals},
            goto=next_step
        )
    
    def _build_context(self, state: Dict) -> Dict:
        """业务逻辑：构建决策上下文"""
        return {
            "system_info": self.context.get_system_context_for_llm(),
            "history": state.get("messages", []),
            "resources": self.context.get_resource_usage()
        }
    
    def _decompose_goal(self, goal: str, context: Dict) -> List[str]:
        """业务逻辑：使用 LLM 拆解目标"""
        messages = [
            SystemMessage(content=self.prompts.get("decompose")),
            HumanMessage(content=f"目标：{goal}\n上下文：{context}")
        ]
        response = self.llm.invoke(messages)
        return self._parse_sub_goals(response.content)
```

### 4.3 执行中间件（ExecutionMiddleware）

```python
# middleware/execution.py
from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import ToolNode
from typing import List, Dict, Any

class ExecutionMiddleware:
    """
    执行中间件
    
    逻辑必然性：
    - 要知道能力 → skill_registry
    - 能调外部工具 → tool_inventory
    - 任务可能排队 → execution_queue
    - 要知道进度 → execution_state
    
    整合方式：管理 BaseTool 集合，提供 ToolNode
    """
    
    def __init__(self):
        self.skill_registry: List[BaseTool] = []
        self.tool_inventory: Dict[str, BaseTool] = {}
        self.execution_queue: List[Dict] = []
        self.execution_state: Dict = {}
        
        # 注册业务工具
        self._register_business_tools()
    
    def _register_business_tools(self):
        """注册业务相关的工具"""
        
        @tool
        def read_project_file(file_path: str) -> str:
            """读取项目文件 - 业务工具"""
            with open(file_path, 'r') as f:
                return f.read()
        
        @tool
        def analyze_code_structure(code: str) -> dict:
            """分析代码结构 - 业务工具"""
            # 业务逻辑
            return {"structure": "..."}
        
        self.register_skill(read_project_file)
        self.register_skill(analyze_code_structure)
    
    def register_skill(self, skill: BaseTool):
        """注册技能"""
        self.skill_registry.append(skill)
        self.tool_inventory[skill.name] = skill
    
    def get_tool_node(self) -> ToolNode:
        """获取 LangGraph ToolNode（基础设施）"""
        return ToolNode(self.skill_registry)
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """LangGraph Node 入口"""
        plan = state.get("plan", [])
        current_step = state.get("current_step", 0)
        
        if current_step >= len(plan):
            return {"execution_result": {"status": "completed"}}
        
        # 执行当前步骤（业务逻辑）
        step = plan[current_step]
        result = self._execute_step(step, state)
        
        return {
            "execution_result": result,
            "current_step": current_step + 1
        }
```

### 4.4 反馈中间件（FeedbackMiddleware）

```python
# middleware/feedback.py
from langchain_core.language_models import BaseChatModel
from langgraph.types import Command, interrupt
from typing import Literal, Dict, Any

class FeedbackMiddleware:
    """
    反馈中间件
    
    逻辑必然性：
    - 要有评判标准 → evaluation_criteria
    - 要记录历史 → result_log
    - 要知道偏差 → deviation_records
    - 要能学习 → learning_patterns
    
    整合方式：实现 __call__，支持 interrupt
    """
    
    def __init__(
        self,
        llm: BaseChatModel,
        memory: Any,
        context: Any
    ):
        self.llm = llm
        self.memory = memory
        self.context = context
    
    def __call__(
        self,
        state: Dict[str, Any]
    ) -> Command[Literal["decision", "execute", "__end__"]]:
        """LangGraph Node 入口"""
        result = state.get("execution_result", {})
        plan = state.get("plan", [])
        
        # 1. 评估结果（业务逻辑）
        evaluation = self._evaluate(result, plan)
        
        # 2. 对比预期与实际（业务逻辑）
        deviation = self._compare(plan, result)
        
        # 3. 人工介入检查（基础设施：interrupt）
        if evaluation.get("needs_human_review"):
            human_feedback = interrupt({
                "question": "请确认结果",
                "evaluation": evaluation
            })
            evaluation["human_feedback"] = human_feedback
        
        # 4. 学习（业务逻辑）
        self._learn(evaluation, deviation)
        
        # 5. 决策下一步（业务逻辑）
        next_step = self._decide_next_step(state, evaluation, deviation)
        
        return Command(
            update={"evaluation": evaluation, "deviation": deviation},
            goto=next_step
        )
```

---

## 五、基础设施层（直接使用 LangChain v1 Core）

### 5.1 LLM 基础设施

```python
# infrastructure/llm.py
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel

def create_llm(config: dict) -> BaseChatModel:
    """
    创建 LLM 实例
    
    直接使用 LangChain 的 init_chat_model，
    不再封装 LLMService 类
    """
    return init_chat_model(
        model=config.get("model", "qwen3.5:4b"),
        model_provider=config.get("provider", "ollama"),
        temperature=config.get("temperature", 0.7),
        base_url=config.get("base_url", "http://localhost:11434"),
    )
```

### 5.2 Context 基础设施

```python
# infrastructure/context.py
from langchain_core.runnables import RunnableConfig
from typing import Dict, Any

class SystemContext:
    """
    系统上下文（保留）
    
    职责：提供硬件、运行时和资源使用信息
    这是业务相关的上下文，需要保留
    """
    
    def get_hardware_info(self) -> Dict[str, Any]: ...
    def get_runtime_info(self) -> Dict[str, Any]: ...
    def get_resource_usage(self) -> Dict[str, Any]: ...
    def get_system_context_for_llm(self) -> str: ...

def create_runnable_config(context: SystemContext) -> RunnableConfig:
    """
    创建 RunnableConfig
    
    直接使用 LangChain 基础设施
    """
    return RunnableConfig(
        metadata={
            "system_context": context.get_hardware_info(),
        }
    )
```

### 5.3 记忆基础设施

```python
# infrastructure/memory.py
from langgraph.checkpoint.memory import MemorySaver

def create_checkpointer():
    """
    创建检查点存储
    
    直接使用 LangGraph 基础设施
    """
    return MemorySaver()
```

---

## 六、Agent 组装层

### 6.1 使用 DeepAgents API（推荐）

```python
# agent/assembly.py
from deepagents import create_react_agent
from langchain_core.language_models import BaseChatModel
from middleware.perception import PerceptionMiddleware
from middleware.decision import DecisionMiddleware
from middleware.execution import ExecutionMiddleware
from middleware.feedback import FeedbackMiddleware

def assemble_agent_with_deepagents(
    llm: BaseChatModel,
    middleware_config: dict
):
    """
    使用 DeepAgents API 组装 Agent（最简洁）
    
    DeepAgents 自动处理：
    - 状态图编排
    - 上下文管理
    - 人机协作
    - 持久化
    """
    # 创建中间件
    perception = PerceptionMiddleware(**middleware_config.get("perception", {}))
    decision = DecisionMiddleware(llm=llm, **middleware_config.get("decision", {}))
    execution = ExecutionMiddleware(**middleware_config.get("execution", {}))
    feedback = FeedbackMiddleware(llm=llm, **middleware_config.get("feedback", {}))
    
    # 获取工具
    tools = execution.skill_registry
    
    # 使用 DeepAgents 组装
    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=perception.get_system_prompt(),
        interrupt_before=["feedback"],  # 在反馈前允许人工介入
    )
    
    return agent
```

### 6.2 使用 LangGraph（精细控制）

```python
# agent/graph.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from agent.state import AgentState

def assemble_agent_with_langgraph(
    perception,
    decision,
    execution,
    feedback
):
    """
    使用 LangGraph 精细控制编排
    
    适用于需要自定义流程的场景
    """
    workflow = StateGraph(AgentState)
    
    # 添加节点（中间件作为节点）
    workflow.add_node("perception", perception)
    workflow.add_node("decision", decision)
    workflow.add_node("execution", execution.get_tool_node())
    workflow.add_node("feedback", feedback)
    
    # 编排边
    workflow.set_entry_point("perception")
    workflow.add_edge("perception", "decision")
    workflow.add_conditional_edges(
        "decision",
        lambda s: s.get("next_step"),
        {"execute": "execution", "feedback": "feedback", END: END}
    )
    workflow.add_edge("execution", "feedback")
    workflow.add_conditional_edges(
        "feedback",
        lambda s: s.get("next_step"),
        {"decision": "decision", "execute": "execution", END: END}
    )
    
    return workflow.compile(checkpointer=MemorySaver())
```

---

## 七、Prompt 管理

### 7.1 Prompt 作为 Context 的一部分

```python
# context/prompts.py
from typing import Dict

class PromptContext:
    """
    Prompt 上下文管理
    
    Prompt 属于 Context 的范畴，
    作为系统上下文的一部分进行管理
    """
    
    def __init__(self):
        self.templates: Dict[str, str] = {
            "decompose": """你是一个目标拆解专家。
请将用户的目标拆解为具体的、可执行的子目标。
请用简单的列表格式返回，每行一个子目标。""",
            
            "plan": """你是一个规划专家。
请根据子目标生成详细的执行计划。""",
            
            "evaluate": """你是一个结果评估专家。
请评估任务执行结果的质量。
请给出质量分数(0-1)、是否可以调整、以及改进建议。""",
        }
    
    def get(self, template_name: str) -> str:
        """获取 prompt 模板"""
        return self.templates.get(template_name, "")
    
    def render(self, template_name: str, **kwargs) -> str:
        """渲染 prompt"""
        template = self.templates.get(template_name, "")
        return template.format(**kwargs)


# 在 SystemContext 中集成
class SystemContext:
    def __init__(self):
        self.prompt_context = PromptContext()
        # ... 其他初始化
    
    def get_prompt(self, template: str, **vars) -> str:
        return self.prompt_context.render(template, **vars)
```

---

## 八、完整使用示例

```python
# main.py
from infrastructure.llm import create_llm
from infrastructure.context import SystemContext
from infrastructure.memory import create_checkpointer
from middleware.perception import PerceptionMiddleware
from middleware.decision import DecisionMiddleware
from middleware.execution import ExecutionMiddleware
from middleware.feedback import FeedbackMiddleware
from agent.assembly import assemble_agent_with_deepagents

def main():
    # 1. 初始化基础设施（直接使用 LangChain）
    llm = create_llm({
        "provider": "ollama",
        "model": "qwen3.5:4b",
        "base_url": "http://localhost:11434"
    })
    
    context = SystemContext()
    checkpointer = create_checkpointer()
    
    # 2. 创建中间件（封装业务逻辑）
    perception = PerceptionMiddleware(
        subscribed_sources=["user_input", "file_system"],
        filter_rules=[lambda x: len(str(x)) > 0]
    )
    
    decision = DecisionMiddleware(
        llm=llm,
        context=context,
        prompt_templates=context.prompt_context
    )
    
    execution = ExecutionMiddleware()
    
    feedback = FeedbackMiddleware(
        llm=llm,
        memory=checkpointer,
        context=context
    )
    
    # 3. 使用 DeepAgents API 组装 Agent（最简洁）
    agent = assemble_agent_with_deepagents(
        llm=llm,
        middleware_config={
            "perception": {"subscribed_sources": ["file_system"]},
            "decision": {"context": context},
            "execution": {},
            "feedback": {"memory": checkpointer, "context": context}
        }
    )
    
    # 4. 执行
    result = agent.invoke({
        "input": "分析当前目录下的所有 Python 文件"
    })
    
    print(result)

if __name__ == "__main__":
    main()
```

---

## 九、架构优势总结

### 9.1 重构后的优势

| 方面 | 原设计 | 重构后设计 |
|------|--------|-----------|
| **代码量** | 较多封装层 | 直接使用生态组件，代码更少 |
| **维护性** | 需要维护封装层 | 跟随生态更新，维护成本低 |
| **灵活性** | 封装层限制 | 直接使用原生 API，更灵活 |
| **学习成本** | 需要学习封装层 | 学习标准生态，一次学会到处用 |
| **可扩展性** | 受封装层限制 | 直接扩展生态组件 |

### 9.2 核心设计价值保留

| 原设计要素 | 保留方式 |
|-----------|---------|
| **纯逻辑推导** | 中间件层保留逻辑完整性 |
| **模块职责边界** | 中间件封装业务逻辑 |
| **SystemContext** | 保留作为业务上下文 |
| **属性/方法设计** | 在中间件中保留 |

### 9.3 整体架构特点

```
┌─────────────────────────────────────────────────────────────┐
│                    重构后架构特点总结                         │
├─────────────────────────────────────────────────────────────┤
│  1. 简洁性：直接使用 LangChain v1 Core，无额外封装层          │
│  2. 业务聚焦：中间件只封装业务逻辑，不封装基础设施             │
│  3. 生态兼容：完全基于 LangChain 标准接口                    │
│  4. 组装便捷：使用 DeepAgents API 快速组装                   │
│  5. 可观测性：LangSmith 原生支持，全流程追踪                 │
│  6. 生产就绪：DeepAgents 提供开箱即用的生产特性              │
└─────────────────────────────────────────────────────────────┘
```

---

## 十、参考资源

- [LangChain GitHub](https://github.com/langchain-ai/langchain)
- [LangGraph GitHub](https://github.com/langchain-ai/langgraph)
- [DeepAgents GitHub](https://github.com/langchain-ai/deepagents)
- [LangChain 官方文档](https://python.langchain.com/)
- [LangGraph 官方文档](https://langchain-ai.github.io/langgraph/)

---

## 十、SkillLoader 设计（Anthropic Style）

> **设计背景**：LangChain/LangGraph 没有内置 Skill 配置，本项目参考 Anthropic 官方 [skills](https://github.com/anthropics/skills) 设计，实现自定义 SkillLoader

### 10.1 Anthropic Skill 架构

```
skill-name/
├── SKILL.md (必需)
│   ├── YAML frontmatter (name, description 必需)
│   └── Markdown instructions
└── Bundled Resources (可选)
    ├── scripts/    - 可执行脚本
    ├── references/ - 按需加载的文档
    └── assets/     - 模板、图标等
```

**SKILL.md 格式**：
```markdown
---
name: skill-name
description: 清晰描述这个 skill 做什么，什么时候触发
---

# Skill Name

[当 skill 激活时 Claude 遵循的指令]

## Examples
- 示例用法 1
- 示例用法 2
```

### 10.2 SkillLoader 核心设计

```python
# infrastructure/skill_loader.py

class Skill:
    """Anthropic Style Skill"""
    
    def __init__(self, name: str, description: str, instructions: str,
                 scripts: Dict[str, str] = None, references: List[str] = None):
        self.name = name
        self.description = description
        self.instructions = instructions
        self.scripts = scripts or {}
        self.references = references or []
    
    def to_prompt(self) -> str:
        """将 Skill 转换为系统提示"""
        prompt = f"# {self.name}\n\n{self.instructions}"
        if self.references:
            prompt += "\n\n## References\n" + "\n".join(f"- {r}" for r in self.references)
        return prompt

class SkillLoader:
    """Skill 加载器 - 模拟 Anthropic Skill 系统"""
    
    def __init__(self, skills_dir: str = "./skills"):
        self.skills_dir = Path(skills_dir)
        self.skills: Dict[str, Skill] = {}
    
    def load_skill(self, skill_path: Path) -> Skill:
        """加载单个 Skill"""
        # 1. 解析 YAML frontmatter
        # 2. 加载 instructions
        # 3. 加载 scripts/
        # 4. 加载 references/
        return Skill(...)
    
    def match_skill(self, query: str) -> List[Skill]:
        """根据查询匹配相关 Skill"""
        matched = []
        for skill in self.skills.values():
            if query.lower() in skill.description.lower():
                matched.append(skill)
        return matched
```

### 10.3 与 LangChain 集成

```python
# agent/assembly.py 集成

class AgentAssembly:
    def __init__(self):
        self.skill_loader = SkillLoader("./skills")
        self.skill_loader.load_all_skills()
    
    def build_prompt(self, task: str) -> str:
        # 1. 匹配相关 Skills
        matched_skills = self.skill_loader.match_skill(task)
        
        # 2. 构建系统提示
        system_parts = [self.base_system_prompt]
        for skill in matched_skills:
            system_parts.append(skill.to_prompt())
        
        return "\n\n".join(system_parts)
    
    def get_skill_tools(self, task: str) -> List[BaseTool]:
        """获取 Skill 相关的工具"""
        matched_skills = self.skill_loader.match_skill(task)
        tools = []
        for skill in matched_skills:
            for name, code in skill.scripts.items():
                tools.append(self._create_tool_from_script(name, code))
        return tools
```

### 10.4 目录结构

```
skills/
├── skill-creator/
│   ├── SKILL.md
│   ├── scripts/
│   │   └── create_skill.py
│   └── references/
│       └── guide.md
├── brainstorm/
│   ├── SKILL.md
│   └── references/
│       └── techniques.md
└── code-review/
    ├── SKILL.md
    ├── scripts/
    │   └── lint.py
    └── references/
        └── rules.md
```

---

## 十一、实施计划

### 11.1 测试阶段

项目完成后，将按以下步骤进行真实测试：

1. **LLM 集成测试**
   - 使用 Ollama 本地部署
   - 模型：`qwen3.5:4b`
   - 测试目标：验证智能体基础功能在真实 LLM 下的表现

2. **测试配置**
   ```python
   llm = create_llm({
       "provider": "ollama",
       "model": "qwen3.5:4b",
       "base_url": "http://localhost:11434",
       "temperature": 0.7
   })
   ```

3. **测试内容**
   - 感知模块：数据获取与过滤
   - 决策模块：目标拆解与计划生成
   - 执行模块：工具调用与任务执行
   - 反馈模块：结果评估与学习

4. **测试通过后**
   - 正式实施本方案
   - 根据测试结果进行优化调整

---

> 本文档基于纯逻辑推理 + LangChain 生态最佳实践完成，采用"模块即中间件，基础设施直接用，整体 DeepAgents 组装"的设计原则，确保智能体架构的科学性、简洁性和工程可行性。
