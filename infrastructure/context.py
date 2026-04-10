"""Context 基础设施 - 直接使用 LangChain + 保留 SystemContext"""

import platform
import psutil
from datetime import datetime
from langchain_core.runnables import RunnableConfig
from typing import Dict, Any


class SystemContext:
    """
    系统上下文（保留）

    职责：提供硬件、运行时和资源使用信息
    这是业务相关的上下文，需要保留
    """

    def __init__(self):
        self._hardware_info = None
        self._runtime_info = None

    def get_hardware_info(self) -> Dict[str, Any]:
        """获取硬件信息"""
        if self._hardware_info is None:
            self._hardware_info = {
                "cpu_count": psutil.cpu_count(),
                "cpu_freq": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None,
                "memory_total": psutil.virtual_memory().total,
                "memory_available": psutil.virtual_memory().available,
                "platform": platform.platform(),
                "machine": platform.machine(),
                "processor": platform.processor(),
            }
        return self._hardware_info

    def get_runtime_info(self) -> Dict[str, Any]:
        """获取运行时信息"""
        if self._runtime_info is None:
            self._runtime_info = {
                "python_version": platform.python_version(),
                "python_implementation": platform.python_implementation(),
            }
        return self._runtime_info

    def get_resource_usage(self) -> Dict[str, Any]:
        """获取资源使用情况"""
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_used": psutil.virtual_memory().used,
            "memory_available": psutil.virtual_memory().available,
        }

    def get_current_time(self) -> Dict[str, Any]:
        """获取当前时间信息"""
        now = datetime.now()
        return {
            "datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "weekday": now.strftime("%A"),
            "timezone": "CST"
        }

    def get_system_context_for_llm(self) -> str:
        """获取用于 LLM 的系统上下文字符串"""
        hardware = self.get_hardware_info()
        runtime = self.get_runtime_info()
        resources = self.get_resource_usage()
        current_time = self.get_current_time()

        return f"""系统环境信息：
- 平台：{hardware.get('platform', 'Unknown')}
- 机器类型：{hardware.get('machine', 'Unknown')}
- CPU核心数：{hardware.get('cpu_count', 'Unknown')}
- 内存总量：{hardware.get('memory_total', 0) / (1024**3):.2f} GB
- Python版本：{runtime.get('python_version', 'Unknown')}
- 当前CPU使用率：{resources.get('cpu_percent', 'Unknown')}%
- 当前内存使用率：{resources.get('memory_percent', 'Unknown')}%
- 当前时间：{current_time.get('datetime', 'Unknown')} ({current_time.get('weekday', 'Unknown')})"""


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
