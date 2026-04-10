"""
搜索引擎注册表 - 统一管理搜索引擎优先级和配置
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import os


@dataclass
class EngineConfig:
    """搜索引擎配置"""
    name: str
    priority: int
    api_required: bool
    base_url: Optional[str] = None
    max_results: int = 10

    def is_available(self, api_keys: Dict[str, str]) -> bool:
        """检查引擎是否可用"""
        if self.api_required:
            return bool(api_keys.get(self.name))
        return True


class SearchEngineRegistry:
    """搜索引擎注册表"""

    ENGINES: List[EngineConfig] = [
        EngineConfig(
            name="tavily",
            priority=1,
            api_required=True,
            max_results=10
        ),
        EngineConfig(
            name="searxng",
            priority=2,
            api_required=False,
            base_url=os.getenv("SEARXNG_URL", "http://localhost:8080"),
            max_results=10
        ),
        EngineConfig(
            name="duckduckgo",
            priority=3,
            api_required=False,
            max_results=10
        ),
        EngineConfig(
            name="bing",
            priority=4,
            api_required=True,
            max_results=10
        ),
        EngineConfig(
            name="github",
            priority=6,
            api_required=False,
            max_results=10
        ),
        EngineConfig(
            name="pubmed",
            priority=7,
            api_required=False,
            max_results=10
        ),
    ]

    @classmethod
    def get_api_keys(cls) -> Dict[str, str]:
        """从环境变量获取 API Keys"""
        return {
            "tavily": os.getenv("TAVILY_API_KEY"),
            "bing": os.getenv("BING_API_KEY"),
            "searxng": os.getenv("SEARXNG_URL"),
            "github": os.getenv("GITHUB_TOKEN"),
            "pubmed": os.getenv("NCBI_API_KEY"),
        }

    @classmethod
    def get_available_engines(cls, api_keys: Dict[str, str] = None) -> List[EngineConfig]:
        """获取所有可用的引擎，按优先级排序"""
        if api_keys is None:
            api_keys = cls.get_api_keys()

        available = []
        for engine in sorted(cls.ENGINES, key=lambda x: x.priority):
            if engine.is_available(api_keys):
                available.append(engine)

        if not available:
            raise ValueError("No search engines available. Please configure at least one engine.")

        return available

    @classmethod
    def get_best_engine(cls, api_keys: Dict[str, str] = None) -> EngineConfig:
        """获取最高优先级的可用引擎"""
        available = cls.get_available_engines(api_keys)
        return available[0]

    @classmethod
    def get_engine(cls, name: str) -> Optional[EngineConfig]:
        """根据名称获取引擎配置"""
        for engine in cls.ENGINES:
            if engine.name == name:
                return engine
        return None

    @classmethod
    def register_engine(cls, config: EngineConfig):
        """注册新引擎"""
        cls.ENGINES.append(config)
        cls.ENGINES.sort(key=lambda x: x.priority)


class QuotaManager:
    """配额管理器 - 跟踪 API 使用情况"""

    def __init__(self):
        self._quotas: Dict[str, Dict[str, int]] = {}

    def init_engine_quotas(self, engine: str, monthly_limit: int):
        """初始化引擎配额"""
        if engine not in self._quotas:
            self._quotas[engine] = {
                "used": 0,
                "limit": monthly_limit,
                "reset_day": 1
            }

    def use(self, engine: str, count: int = 1):
        """使用配额"""
        if engine in self._quotas:
            self._quotas[engine]["used"] += count

    def get_remaining(self, engine: str) -> int:
        """获取剩余配额"""
        if engine not in self._quotas:
            return -1
        quota = self._quotas[engine]
        return max(0, quota["limit"] - quota["used"])

    def is_available(self, engine: str) -> bool:
        """检查配额是否可用"""
        remaining = self.get_remaining(engine)
        return remaining > 0 or remaining == -1

    def load_from_file(self, path: str):
        """从文件加载配额数据"""
        import json
        try:
            with open(path, "r") as f:
                self._quotas = json.load(f)
        except FileNotFoundError:
            pass

    def save_to_file(self, path: str):
        """保存配额数据到文件"""
        import json
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(self._quotas, f, indent=2)
