"""Prompt 上下文管理"""

from typing import Dict


class PromptContext:
    """
    Prompt 上下文管理

    Prompt 属于 Context 的范畴，
    作为系统上下文的一部分进行管理
    """

    def __init__(self):
        self.templates: Dict[str, str] = {
            "decompose": """你是一个目标拆解专家。
请将用户的目标拆解为具体的、可执行的子目标。
请用简单的列表格式返回，每行一个子目标。""",

            "plan": """你是一个规划专家。
请根据子目标生成详细的执行计划。""",

            "evaluate": """你是一个结果评估专家。
请评估任务执行结果的质量。
请给出质量分数(0-1)、是否可以调整、以及改进建议。""",

            "system": """你是一个智能助手，可以帮助用户分析文件、执行命令和解决问题。
你可以访问文件系统，分析代码结构，并根据用户的需求提供建议。

你可以使用以下工具：
- read_project_file: 读取项目文件内容
- list_directory: 列出目录内容
- search_files: 搜索文件
- analyze_code_structure: 分析代码结构
- execute_command: 执行系统命令（受限）

请根据用户的需求，合理使用这些工具来完成任务。"""
        }

    def get(self, template_name: str) -> str:
        """获取 prompt 模板"""
        return self.templates.get(template_name, "")

    def render(self, template_name: str, **kwargs) -> str:
        """渲染 prompt"""
        template = self.templates.get(template_name, "")
        return template.format(**kwargs)

    def add_template(self, name: str, template: str):
        """添加新模板"""
        self.templates[name] = template
