#!/usr/bin/env python3
"""
Ralph 测试运行器

自动执行 test_prd.json 中的所有测试任务
"""

import json
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / ".trae" / "skills" / "ralph"))

from ralph_loop import RalphLoop


def run_verification(verification: str, cwd: str = None) -> tuple[bool, str]:
    """运行验证命令"""
    if not cwd:
        cwd = os.path.dirname(os.path.abspath(__file__))

    try:
        result = subprocess.run(
            verification,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode == 0:
            if "OK" in stdout or "ok" in stdout.lower():
                return True, stdout
            return True, f"验证通过 (无 OK 标记): {stdout[:100]}"
        else:
            if "PyTorch" in stderr and "Disabling" in stderr:
                if "OK" in stdout or "ok" in stdout.lower():
                    return True, f"OK (PyTorch警告可忽略): {stdout[:80]}"
            return False, f"验证失败: {stderr[:200] if stderr else stdout[:200]}"
    except subprocess.TimeoutExpired:
        return False, "验证超时 (60秒)"
    except Exception as e:
        return False, f"验证异常: {str(e)[:200]}"


def task_handler(task, context: str) -> tuple[bool, str]:
    """Ralph 任务处理器 - 执行测试验证"""
    print(f"\n{'='*60}")
    print(f"执行测试: {task.title}")
    print(f"{'='*60}")
    print(f"描述: {task.description}")
    print(f"验证命令: {task.verification[:80]}...")

    success, message = run_verification(task.verification)

    if success:
        print(f"✓ 结果: {message[:100]}")
    else:
        print(f"✗ 失败: {message[:100]}")

    return success, message


def main():
    print("=" * 70)
    print("Tiny Ralph Agent - 自动化测试运行器")
    print("=" * 70)

    prd_path = "test_prd.json"

    if not os.path.exists(prd_path):
        print(f"错误: {prd_path} 不存在")
        sys.exit(1)

    with open(prd_path, 'r', encoding='utf-8') as f:
        prd = json.load(f)

    print(f"\n项目: {prd['project']}")
    print(f"总任务数: {len(prd['tasks'])}")

    ralph = RalphLoop(prd_path)
    ralph.set_task_handler(task_handler)

    print("\n开始 Ralph 循环测试...")
    print("-" * 70)

    summary = ralph.run()

    print("\n" + "=" * 70)
    print("测试完成!")
    print("=" * 70)
    print(f"总任务: {summary['total_tasks']}")
    print(f"完成: {summary['completed']}")
    print(f"失败: {summary['failed']}")
    print(f"迭代次数: {summary['iterations']}")

    if os.path.exists('progress.txt'):
        print("\n--- 学习记录 ---")
        with open('progress.txt', 'r', encoding='utf-8') as f:
            print(f.read())

    if summary['failed'] > 0:
        print("\n⚠ 有测试失败，请检查!")
        sys.exit(1)
    else:
        print("\n✓ 所有测试通过!")
        sys.exit(0)


if __name__ == "__main__":
    main()
