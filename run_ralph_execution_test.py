#!/usr/bin/env python3
"""
Ralph 真实执行测试 - 使用 RalphLoop 让 qwen3.5:4b 真实执行任务

本测试让 RalphLoop 使用 qwen3.5:4b 模型真实执行每个任务：
- RalphLoop.run() 内部会调用模型
- 模型自己决定如何执行步骤
- 记录完整执行过程
"""
import json
import os
import sys
import time
import shutil
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from infrastructure.llm.ollama import OllamaRuntime
from agent.ralph_loop import RalphLoop
from infrastructure.task_state import TaskState


def setup():
    """清理并创建运行时目录"""
    if os.path.exists('./ralph_runtime'):
        shutil.rmtree('./ralph_runtime')
    os.makedirs('./ralph_runtime', exist_ok=True)

    if os.path.exists('./ralph_execution_log.txt'):
        os.remove('./ralph_execution_log.txt')


def run_ralph_task(task_id: str, goal: str, llm) -> dict:
    """使用 RalphLoop 真实执行单个任务"""
    print(f"\n{'='*60}")
    print(f"开始任务: {goal}")
    print(f"{'='*60}")

    start_time = time.time()

    ralph = RalphLoop(
        llm=llm,
        state_dir="./ralph_runtime",
        tools_dir="./tools/custom",
        max_iterations=10
    )

    task_state = TaskState("./ralph_runtime")
    created_task_id = task_state.create_task(goal)

    result = ralph.run(created_task_id)

    duration = time.time() - start_time

    return {
        'task_id': task_id,
        'goal': goal,
        'success': result.get('success', False),
        'duration': duration,
        'iterations': result.get('iterations', 0),
        'learnings': result.get('learnings', []),
        'reason': result.get('reason', '')
    }


def main():
    print("="*60)
    print("Ralph 真实执行测试")
    print("使用 qwen3.5:4b 模型真实执行每个任务")
    print("="*60)

    setup()

    llm = OllamaRuntime(default_model='qwen3.5:4b')

    tasks = [
        {
            'id': 1,
            'goal': '列出当前目录下所有 Python 文件，保存到 output/list_files.txt'
        },
        {
            'id': 2,
            'goal': '统计当前项目的代码行数，保存到 output/line_count.txt'
        },
        {
            'id': 3,
            'goal': '分析当前项目结构，生成报告到 output/structure_report.txt'
        },
    ]

    results = []

    for task in tasks:
        result = run_ralph_task(task['id'], task['goal'], llm)
        results.append(result)

        status = "✅" if result['success'] else "❌"
        print(f"\n{status} 任务 {task['id']} 完成")
        print(f"   耗时: {result['duration']:.1f}秒")
        print(f"   迭代次数: {result['iterations']}")
        if result['learnings']:
            print(f"   学习点: {len(result['learnings'])}")
        if result['reason']:
            print(f"   原因: {result['reason']}")

        time.sleep(2)

    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    passed = sum(1 for r in results if r['success'])
    print(f"总任务: {len(results)}")
    print(f"通过: {passed}")
    print(f"失败: {len(results) - passed}")

    if results:
        with open('ralph_execution_log.txt', 'a', encoding='utf-8') as f:
            f.write(f"\n\n{'='*60}\n")
            f.write(f"测试完成时间: {datetime.now()}\n")
            f.write(f"通过率: {passed}/{len(results)}\n")
            f.write("="*60 + "\n\n")
            for r in results:
                f.write(json.dumps(r, ensure_ascii=False, indent=2) + "\n\n")

    if passed == len(results):
        print("\n🎉 所有任务通过！")
        return 0
    else:
        print("\n⚠️  有任务失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
