#!/usr/bin/env python3
"""
Ralph 循环测试脚本

验证完整流程：
1. 创建任务
2. 执行 Ralph 循环
3. 验证结果
"""

import sys
import shutil
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from agent.ralph_loop import RalphLoop
from infrastructure.llm.ollama import OllamaRuntime


def main():
    print("=" * 60)
    print("Tiny Ralph Agent - 端到端测试")
    print("=" * 60)

    print("\n[1] 初始化 Ollama...")
    try:
        llm = OllamaRuntime(default_model="qwen3.5:4b")
        print("    ✓ Ollama 初始化成功")
    except Exception as e:
        print(f"    ✗ Ollama 初始化失败: {e}")
        print("    提示: 确保 Ollama 服务已启动")
        return False

    print("\n[2] 初始化 Ralph 循环...")
    ralph = RalphLoop(
        llm=llm,
        state_dir="./runtime",
        tools_dir="./tools/custom",
        max_iterations=10
    )
    print("    ✓ Ralph 循环初始化成功")

    print("\n[3] 执行测试任务...")
    task = "用 Python 列出当前目录的所有 .py 文件"
    print(f"    任务: {task}")

    result = ralph.create_and_run(task)

    print("\n[4] 结果:")
    print(f"    成功: {result.get('success', False)}")

    if 'iterations' in result:
        print(f"    迭代次数: {result['iterations']}")

    if 'learnings' in result:
        print(f"    学习记录: {len(result['learnings'])} 条")

    if 'error' in result:
        print(f"    错误: {result['error']}")

    print("\n[5] 清理...")
    shutil.rmtree('./runtime', ignore_errors=True)
    shutil.rmtree('./tools/custom', ignore_errors=True)
    print("    ✓ 清理完成")

    print("\n" + "=" * 60)

    return result.get('success', False)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
