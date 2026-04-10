"""
Tools 模块 - 独立工具集

结构:
tools/
├── __init__.py          # 统一导出
├── base.py              # 引擎注册表、配额管理
├── web_search/          # 网络搜索
│   ├── __init__.py
│   ├── engine.py        # 引擎基类
│   ├── main.py          # 统一入口
│   └── engines/
│       ├── __init__.py
│       ├── tavily.py
│       ├── searxng.py
│       ├── duckduckgo.py
│       ├── bing.py
│       ├── github.py
│       └── pubmed.py
├── file_ops/            # 文件操作
│   ├── __init__.py
│   ├── read_file.py
│   ├── list_dir.py
│   ├── search_files.py
│   └── analyze_code.py
└── shell/                # Shell 命令
    ├── __init__.py
    └── execute_command.py
"""

from .web_search import web_search
from .file_ops import read_project_file, list_directory, search_files, analyze_code_structure
from .shell import execute_command

__all__ = [
    "web_search",
    "read_project_file",
    "list_directory",
    "search_files",
    "analyze_code_structure",
    "execute_command",
]
