"""
执行系统命令工具
"""

import os
import subprocess
from langchain_core.tools import tool

ALLOWED_COMMANDS = {'dir', 'ls', 'echo', 'cat', 'head', 'tail', 'find', 'grep', 'pwd', 'cd', 'type', 'wc'}

ENABLE_SHELL = os.getenv("ENABLE_SHELL_COMMAND", "false").lower() == "true"


@tool
def execute_command(command: str) -> str:
    """执行系统命令（安全限制）

    注意：默认禁用，需设置 ENABLE_SHELL_COMMAND=true 开启

    Args:
        command: 要执行的命令（仅允许特定命令）

    Returns:
        命令输出或错误信息
    """
    if not ENABLE_SHELL:
        return "Shell command is disabled. Set ENABLE_SHELL_COMMAND=true to enable."

    cmd_parts = command.split()
    if not cmd_parts:
        return "Empty command."

    cmd_name = cmd_parts[0]

    if cmd_name not in ALLOWED_COMMANDS:
        return f"Command '{cmd_name}' not allowed. Allowed: {', '.join(sorted(ALLOWED_COMMANDS))}"

    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=os.getcwd()
        )
        if result.stdout:
            return result.stdout
        elif result.stderr:
            return f"Error: {result.stderr}"
        else:
            return "Command executed successfully (no output)."
    except subprocess.TimeoutExpired:
        return "Command timed out (30s limit)."
    except Exception as e:
        return f"Error executing command: {str(e)}"
