"""
智能体主入口

基于 LangChain 生态架构的智能体实现
统一使用 LangGraph 中间件链模式
"""

import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

from infrastructure.llm import create_llm, TokenManager
from infrastructure.llm.ollama import OllamaRuntime
from infrastructure.context import SystemContext
from infrastructure.context_manager import init_context_manager, get_context_manager
from middleware.perception import PerceptionMiddleware
from middleware.decision import DecisionMiddleware
from middleware.execution import ExecutionMiddleware
from middleware.feedback import FeedbackMiddleware
from agent.assembly import assemble_agent_with_langgraph_main
from agent.graph import assemble_agent_with_langgraph


def get_ollama_context_window() -> int:
    """从 Ollama 获取模型上下文窗口"""
    try:
        runtime = OllamaRuntime()
        return runtime.get_context_window()
    except Exception:
        return 4096


def create_agent():
    """创建智能体（统一使用 LangGraph 中间件链）"""
    llm_config = {
        "provider": "ollama",
        "model": "qwen3.5:4b",
        "base_url": "http://localhost:11434",
        "temperature": 0.7
    }

    ollama_runtime = OllamaRuntime()
    context_window = ollama_runtime.get_context_window(llm_config["model"])
    model_name = llm_config["model"]
    token_manager = TokenManager(context_window=context_window, model=model_name)

    context_mgr = init_context_manager(
        ollama_runtime=ollama_runtime,
        warning_threshold=0.7,
        danger_threshold=0.9,
    )
    context_mgr.set_max_tokens(context_window)

    print(f"正在初始化 LLM: {llm_config['model']}...")
    try:
        llm = create_llm(llm_config)
        print(f"✓ LLM 初始化成功 (上下文窗口: {context_window})")
    except Exception as e:
        print(f"✗ LLM 初始化失败: {e}")
        print("提示: 请确保 Ollama 服务已启动，并且已下载 qwen3.5:4b 模型")
        return None, None

    context = SystemContext()
    print("✓ 系统上下文初始化成功")

    print(f"✓ 上下文管理器初始化成功 (警告: {context_mgr._warning_threshold}, 危险: {context_mgr._danger_threshold})")

    print("\n使用 LangGraph 中间件链模式...")
    print("  - 完整中间件链: perception → decision → execute → feedback")
    print("  - 任务复杂度由决策模块自动判断")

    agent, _ = assemble_agent_with_langgraph_main(
        llm=llm,
        middleware_config={
            "perception": {"subscribed_sources": ["user_input"]},
            "execution": {}
        }
    )

    print("✓ Agent 组装成功\n")
    return agent, token_manager


def invoke_agent(agent, token_manager, user_input: str):
    """调用智能体并追踪执行时间和 Token 消耗"""
    token_manager.reset()
    start_time = time.time()

    result = agent.invoke(
        {"messages": [{"role": "user", "content": user_input}]},
        config={
            "configurable": {"thread_id": "default"},
            "recursion_limit": 50
        }
    )

    elapsed_time = time.time() - start_time

    if "messages" in result and result["messages"]:
        last = result["messages"][-1]
        if hasattr(last, 'content') and last.content:
            input_tokens = token_manager.estimate_tokens(user_input)
            output_tokens = token_manager.estimate_tokens(last.content)
            token_manager.update(prompt_tokens=input_tokens, completion_tokens=output_tokens)
        else:
            input_tokens = token_manager.estimate_tokens(user_input)
            token_manager.update(prompt_tokens=input_tokens, completion_tokens=0)

    return result, elapsed_time


def format_token_info(token_manager: TokenManager) -> str:
    """格式化 Token 信息"""
    warning = ""
    level = token_manager.warning_level()
    if level == "warning":
        warning = " ⚠️"
    elif level == "danger":
        warning = " 🔴"

    return f"{token_manager}{warning}"


def run_interactive(agent, token_manager):
    """运行交互式会话"""
    print("=" * 50)
    print("智能体已启动，输入 'exit' 或 'quit' 退出")
    print("=" * 50)

    while True:
        try:
            user_input = input("\n用户: ").strip()

            if user_input.lower() in ['exit', 'quit', '退出']:
                print("再见！")
                break

            if not user_input:
                continue

            print("\n智能体思考中...")

            result, elapsed = invoke_agent(agent, token_manager, user_input)

            if "messages" in result and result["messages"]:
                last = result["messages"][-1]
                if hasattr(last, 'content') and last.content:
                    print(f"\n智能体: {last.content}")

            print(f"\n⏱️ 耗时: {elapsed:.2f}s | 📊 上下文: {format_token_info(token_manager)}")

        except KeyboardInterrupt:
            print("\n\n再见！")
            break
        except Exception as e:
            import traceback
            print(f"\n错误: {e}")
            traceback.print_exc()


def run_single_task(agent, token_manager, task):
    """运行单个任务"""
    print(f"\n任务: {task}")
    print("智能体思考中...")

    try:
        result, elapsed = invoke_agent(agent, token_manager, task)

        if "messages" in result and result["messages"]:
            last = result["messages"][-1]
            if hasattr(last, 'content') and last.content:
                print(f"\n最终回复: {last.content}")

        print(f"\n⏱️ 耗时: {elapsed:.2f}s | 📊 上下文: {format_token_info(token_manager)}")

    except Exception as e:
        import traceback
        print(f"\n错误: {e}")
        traceback.print_exc()


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="智能体主入口")
    parser.add_argument("--task", type=str, help="运行单个任务")
    args = parser.parse_args()

    print("=" * 50)
    print("LangChain 智能体启动")
    print("=" * 50)

    agent, token_manager = create_agent()
    if not agent:
        return

    if args.task:
        run_single_task(agent, token_manager, args.task)
    else:
        run_interactive(agent, token_manager)


if __name__ == "__main__":
    main()
