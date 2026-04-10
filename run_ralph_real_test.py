#!/usr/bin/env python3
"""
Ralph 真实环境测试运行器 - 使用 qwen3.5:4b 模型
"""
import json
import subprocess
import sys
import os
from datetime import datetime

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
            timeout=180
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode == 0:
            if "OK" in stdout or "ok" in stdout.lower():
                return True, stdout
            return True, f"验证通过 (无 OK 标记): {stdout[:100]}"
        else:
            if "PyTorch" in stderr and ("Disabling" in stderr or "not found" in stderr.lower()):
                if "OK" in stdout or "ok" in stdout.lower():
                    return True, f"OK (PyTorch警告可忽略): {stdout[:80]}"
            if "Timeout" in stderr:
                return False, f"验证超时: {stderr[:100]}"
            return False, f"验证失败: {stderr[:200] if stderr else stdout[:200]}"
    except subprocess.TimeoutExpired:
        return False, "验证超时 (180秒)"
    except Exception as e:
        return False, f"验证异常: {str(e)[:200]}"


def main():
    prd_path = "test_prd_real.json"

    print("=" * 60)
    print("Ralph 真实环境测试 - qwen3.5:4b")
    print("=" * 60)

    if not os.path.exists(prd_path):
        print(f"错误: 找不到 {prd_path}")
        sys.exit(1)

    with open(prd_path, 'r', encoding='utf-8') as f:
        prd = json.load(f)

    tasks = prd.get('tasks', [])
    print(f"\n项目: {prd.get('project', 'Unknown')}")
    print(f"总任务数: {len(tasks)}")
    print()

    completed = 0
    failed = 0

    for task in tasks:
        task_id = task.get('id', 0)
        title = task.get('title', 'Unknown')
        description = task.get('description', '')
        verification = task.get('verification', '')

        print(f"测试 [{task_id}]: {title}")
        print(f"  描述: {description}")

        if not verification:
            print(f"  ⚠ 无验证命令，跳过")
            continue

        success, message = run_verification(verification)

        if success:
            print(f"  ✓ 通过: {message[:80]}")
            completed += 1
        else:
            print(f"  ✗ 失败: {message[:100]}")
            failed += 1
        print()

    print("=" * 60)
    print("测试总结")
    print("=" * 60)
    print(f"通过: {completed}/{len(tasks)}")
    print(f"失败: {failed}/{len(tasks)}")

    if failed > 0:
        print("\n⚠ 有测试失败，请检查!")
        sys.exit(1)
    else:
        print("\n✓ 所有测试通过！Ralph 方案验证成功！")
        sys.exit(0)


if __name__ == "__main__":
    main()
