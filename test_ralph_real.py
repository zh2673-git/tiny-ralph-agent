"""Ralph Loop 真实集成测试 - 使用 qwen3.5:4b 模型"""
import sys
import shutil
from pathlib import Path

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent))

from infrastructure.llm.ollama import OllamaRuntime
from infrastructure.task_state import TaskState
from infrastructure.tool_verifier import ToolVerifier
from middleware.decision import DecisionMiddleware
from middleware.execution import ExecutionMiddleware
from middleware.feedback import FeedbackMiddleware
from langchain_core.messages import HumanMessage

def test_ollama_chat():
    """测试 Ollama chat 功能"""
    print("\n" + "="*60)
    print("测试 1: Ollama Runtime Chat")
    print("="*60)

    runtime = OllamaRuntime(default_model='qwen3.5:4b')

    try:
        response = runtime.chat([
            HumanMessage(content='请用一句话介绍自己')
        ], temperature=0.7)

        content = response.generations[0].message.content
        print(f"✓ Chat 成功: {content[:100]}...")
        return True
    except Exception as e:
        print(f"✗ Chat 失败: {e}")
        return False


def test_decision_decompose():
    """测试决策中间件 - 任务拆解"""
    print("\n" + "="*60)
    print("测试 2: 决策中间件 - 任务拆解")
    print("="*60)

    runtime = OllamaRuntime(default_model='qwen3.5:4b')
    decision = DecisionMiddleware(llm=runtime)

    task = "列出当前目录的所有 Python 文件"

    try:
        steps = decision.decompose_to_atomic_steps(task)
        print(f"✓ 任务拆解成功: {len(steps)} 个原子步骤")
        for i, step in enumerate(steps[:3], 1):
            print(f"  [{i}] {step.description} (tool: {step.required_tool})")
        return True
    except Exception as e:
        print(f"✗ 任务拆解失败: {e}")
        return False


def test_ralph_loop_simple():
    """测试 Ralph 循环 - 简单任务"""
    print("\n" + "="*60)
    print("测试 3: Ralph 循环 - 简单任务执行")
    print("="*60)

    runtime = OllamaRuntime(default_model='qwen3.5:4b')
    task_state = TaskState('./runtime_test')
    tool_verifier = ToolVerifier('./tools/custom')
    decision = DecisionMiddleware(llm=runtime)
    execution = ExecutionMiddleware(tool_verifier, './tools/custom')
    feedback = FeedbackMiddleware()

    task_id = task_state.create_task("用 list_dir 列出当前目录文件")
    print(f"创建任务: {task_id}")

    # 模拟 Ralph 循环一次迭代
    state = task_state.load_task(task_id)
    print(f"加载状态: {state['status']}")

    # 构建上下文
    context = {
        'task': state['goal'],
        'available_tools': ['list_dir', 'read_file', 'execute_command'],
        'current_step': 0,
        'iterations': 0
    }
    print(f"上下文: {context}")

    # 调用小模型
    print("\n调用 qwen3.5:4b 模型...")
    try:
        response = runtime.chat([
            HumanMessage(content=f"""你是一个任务执行助手。当前任务: {context['task']}
可用工具: {', '.join(context['available_tools'])}
当前步骤: {context['current_step']}

请输出一个 JSON 格式的执行计划，格式如下:
{{"step": 1, "tool": "工具名", "action": "具体动作描述"}}

只输出 JSON，不要其他内容。""")
        ], temperature=0.3)

        plan_text = response.generations[0].message.content
        print(f"模型响应: {plan_text[:200]}...")

        task_state.complete_task(task_id, {'plan': plan_text})
        print("✓ Ralph 循环迭代成功")
        return True
    except Exception as e:
        print(f"✗ Ralph 循环迭代失败: {e}")
        return False
    finally:
        shutil.rmtree('./runtime_test', ignore_errors=True)
        shutil.rmtree('./tools/custom', ignore_errors=True)


def test_end_to_end():
    """端到端测试"""
    print("\n" + "="*60)
    print("测试 4: 端到端测试 - 完整流程")
    print("="*60)

    runtime = OllamaRuntime(default_model='qwen3.5:4b')
    task_state = TaskState('./runtime_e2e')

    # 创建任务
    task_id = task_state.create_task("分析当前目录结构并输出报告")
    print(f"创建任务: {task_id}")

    # 加载状态
    state = task_state.load_task(task_id)
    print(f"任务状态: {state['status']}")

    # 决策
    decision = DecisionMiddleware(llm=runtime)
    steps = decision.decompose_to_atomic_steps(state['goal'])
    print(f"拆解步骤: {len(steps)}")

    # 执行
    tool_verifier = ToolVerifier('./tools/custom')
    execution = ExecutionMiddleware(tool_verifier, './tools/custom')

    for step in steps[:2]:
        print(f"执行步骤: {step.description}")
        result = execution.execute_step({'tool': step.required_tool, 'params': {}}, state)
        print(f"  结果: {result.get('status')}")

    # 反馈
    feedback = FeedbackMiddleware()
    state = task_state.load_task(task_id)
    evaluation = feedback.evaluate(state)
    print(f"反馈评估: {evaluation['reason']}")

    # 清理
    shutil.rmtree('./runtime_e2e', ignore_errors=True)
    shutil.rmtree('./tools/custom', ignore_errors=True)

    print("✓ 端到端测试完成")
    return True


if __name__ == "__main__":
    print("="*60)
    print("Ralph Loop 真实集成测试 - qwen3.5:4b")
    print("="*60)

    results = []

    # 测试 1: Ollama Chat
    results.append(("Ollama Chat", test_ollama_chat()))

    # 测试 2: 决策拆解
    results.append(("决策拆解", test_decision_decompose()))

    # 测试 3: Ralph 循环迭代
    results.append(("Ralph 循环", test_ralph_loop_simple()))

    # 测试 4: 端到端
    results.append(("端到端", test_end_to_end()))

    # 总结
    print("\n" + "="*60)
    print("测试总结")
    print("="*60)
    passed = sum(1 for _, r in results if r)
    total = len(results)
    for name, result in results:
        status = "✓" if result else "✗"
        print(f"  {status} {name}")
    print(f"\n通过: {passed}/{total}")

    if passed == total:
        print("\n✓ 所有测试通过！Ralph 方案验证成功！")
        sys.exit(0)
    else:
        print("\n✗ 部分测试失败，需要修复")
        sys.exit(1)
