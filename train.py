#!/usr/bin/env python3
"""
Ralph 渐进式训练循环 - 单任务深挖

核心思路：
1. 一次只运行一个任务
2. 失败后分析原因，从框架层面优化
3. 重新运行同一任务直到成功
4. 成功后才进入下一个任务

任务梯度设计（L1-L6）：
L1: 分析当前项目结构（使用预置工具）
L2: 统计代码行数（需要组合工具）
L3: 搜索特定模式文件（需要工具组合）
L4: 创建新工具解决问题（需要造工具）
L5: 多步骤复杂任务（工具创建+执行）
L6: 端到端项目任务（完整流程）
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent))

from infrastructure.llm.ollama import OllamaRuntime
from agent.ralph_loop import RalphLoop
from infrastructure.task_state import TaskState


@dataclass
class TaskResult:
    success: bool
    goal: str
    iterations: int
    error: str = ""
    duration: float = 0


class RalphSingleTaskTrainer:
    def __init__(self):
        self.runtime_dir = "./Ralph_runtime"
        self.output_dir = "./Ralph_output"
        self.log_file = "./train_log.txt"

        os.makedirs(self.runtime_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        self.llm = OllamaRuntime(
            base_url="http://localhost:11434",
            default_model="qwen3.5:4b"
        )

    def _log(self, msg: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {msg}"
        print(log_line)
        with open(self.log_file, 'a', encoding='utf-8') as f:
            f.write(log_line + "\n")

    def _create_task_pool(self):
        return [
            {
                'id': 1,
                'level': 'L1',
                'goal': '分析当前项目的目录结构，列出所有一级目录和文件'
            },
            {
                'id': 2,
                'level': 'L2',
                'goal': '统计当前项目中所有 Python 文件的数量和总行数'
            },
            {
                'id': 3,
                'level': 'L3',
                'goal': '找出所有包含 "def " 的 Python 文件，并列出每个文件中的函数数量'
            },
            {
                'id': 4,
                'level': 'L4',
                'goal': '创建一个新工具来计算两个数的最大公约数(GCD)，然后使用它计算 36 和 24 的 GCD'
            },
            {
                'id': 5,
                'level': 'L5',
                'goal': '创建一个工具将文本内容写入文件，然后用这个工具在 output.txt 中写入 "Hello Ralph"'
            },
            {
                'id': 6,
                'level': 'L6',
                'goal': '完成一个完整任务：1) 创建 output 目录 2) 统计当前目录文件数 3) 将结果写入 output/summary.txt'
            },
        ]

    def _execute_task(self, task):
        task_id = task['id']
        goal = task['goal']

        try:
            task_state = TaskState(self.runtime_dir)
            task_uuid = task_state.create_task(goal)

            simple_plan = [
                {
                    'step_id': 1,
                    'description': '理解并完成目标',
                    'required_tool': 'auto_tool',
                    'tool_status': 'need_create',
                    'expected_output': '任务完成',
                    'verification_method': '检查目标是否达成'
                }
            ]
            task_state.set_atomic_plan(task_uuid, simple_plan)

            ralph = RalphLoop(
                llm=self.llm,
                state_dir=self.runtime_dir,
                tools_dir='./tools',
                max_iterations=15
            )

            start = time.time()
            result = ralph.run(task_uuid)
            duration = time.time() - start

            return TaskResult(
                success=result.get('success', False),
                goal=goal,
                iterations=result.get('iterations', 0),
                error=result.get('error', ''),
                duration=duration
            )

        except Exception as e:
            return TaskResult(
                success=False,
                goal=goal,
                iterations=0,
                error=str(e)
            )

    def _verify_task_success(self, task, result):
        goal = task['goal']
        task_id = task['id']

        state_file = os.path.join(self.output_dir, f'task_{task_id}_result.json')
        with open(state_file, 'w', encoding='utf-8') as f:
            json.dump({
                'success': result.success,
                'goal': result.goal,
                'iterations': result.iterations,
                'error': result.error,
                'duration': result.duration
            }, f, ensure_ascii=False, indent=2)

        if task_id == 1:
            return os.path.exists(os.path.join(self.output_dir, 'task_1_result.json'))
        elif task_id == 2:
            return os.path.exists(os.path.join(self.output_dir, 'task_2_result.json'))
        elif task_id == 6:
            return os.path.exists('output/summary.txt')

        return result.success

    def _print_summary(self):
        self._log("\n训练总结:")
        tasks = self._create_task_pool()
        passed = 0
        failed = 0

        for task in tasks:
            result_file = os.path.join(self.output_dir, f'task_{task["id"]}_result.json')
            if os.path.exists(result_file):
                with open(result_file, 'r') as f:
                    result = json.load(f)
                    status = "✅" if result['success'] else "❌"
                    self._log(f"  {status} 任务 {task['id']} ({task['level']}): {task['goal'][:40]}...")
                    if result['success']:
                        passed += 1
                    else:
                        failed += 1

        self._log(f"\n通过: {passed}/{len(tasks)}")
        self._log(f"失败: {failed}/{len(tasks)}")

    def train(self):
        tasks = self._create_task_pool()

        for task in tasks:
            task_id = task['id']
            level = task['level']
            goal = task['goal']

            max_attempts = 3
            attempt = 0

            while attempt < max_attempts:
                attempt += 1
                self._log(f"\n{'='*50}")
                self._log(f"任务 {task_id} ({level}): {goal}")
                self._log(f"尝试 {attempt}/{max_attempts}")
                self._log('='*50)

                start = time.time()
                result = self._execute_task(task)
                duration = time.time() - start

                status = "✅" if result.success else "❌"
                self._log(f"{status} 任务 {task_id} - {result.error or '完成'}")
                self._log(f"  耗时: {duration:.1f}秒, 迭代: {result.iterations}")

                if result.success:
                    self._verify_task_success(task, result)
                    self._log(f"  -> 任务 {task_id} 成功！进入下一任务")
                    break
                else:
                    self._log(f"  -> 任务 {task_id} 失败，分析原因...")
                    self._log(f"  错误: {result.error[:200] if result.error else 'Unknown'}")

                    if attempt < max_attempts:
                        self._log(f"  等待 {3*attempt} 秒后重试...")
                        time.sleep(3 * attempt)
                    else:
                        self._log(f"  任务 {task_id} 失败次数过多，跳过")
                        break

            time.sleep(2)

        self._print_summary()

    def run(self):
        print("="*50)
        print("Ralph 渐进式训练 (单任务深挖)")
        print("="*50)
        self.train()


if __name__ == "__main__":
    trainer = RalphSingleTaskTrainer()
    trainer.run()
