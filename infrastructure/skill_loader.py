"""
SkillLoader - Anthropic Style Skill 系统实现

参考 https://github.com/anthropics/skills 设计
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import re
import yaml


class Skill:
    """Anthropic Style Skill"""

    def __init__(
        self,
        name: str,
        description: str,
        instructions: str,
        scripts: Optional[Dict[str, str]] = None,
        references: Optional[List[str]] = None,
        assets: Optional[List[Path]] = None,
        version: Optional[str] = None,
    ):
        self.name = name
        self.description = description
        self.instructions = instructions
        self.scripts = scripts or {}
        self.references = references or []
        self.assets = assets or []
        self.version = version

    def to_prompt(self) -> str:
        """将 Skill 转换为系统提示"""
        prompt = f"# {self.name}\n\n{self.instructions}"

        if self.references:
            prompt += "\n\n## References\n"
            for ref in self.references:
                prompt += f"- {ref}\n"

        return prompt

    def get_script(self, script_name: str) -> Optional[str]:
        """获取指定脚本内容"""
        return self.scripts.get(script_name)

    def __repr__(self) -> str:
        return f"Skill(name={self.name}, description={self.description[:50]}...)"


class SkillLoader:
    """Skill 加载器 - 模拟 Anthropic Skill 系统"""

    def __init__(self, skills_dir: str = "./skills"):
        self.skills_dir = Path(skills_dir)
        self.skills: Dict[str, Skill] = {}
        self._loaded = False

    def load_skill(self, skill_path: Path) -> Skill:
        """加载单个 Skill"""
        if not skill_path.is_dir():
            raise ValueError(f"Skill path must be a directory: {skill_path}")

        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            raise ValueError(f"SKILL.md not found in {skill_path}")

        content = skill_md.read_text(encoding="utf-8")

        frontmatter_match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        if not frontmatter_match:
            raise ValueError(f"Invalid SKILL.md format in {skill_path}: missing frontmatter")

        frontmatter = yaml.safe_load(frontmatter_match.group(1))
        instructions = content[frontmatter_match.end() :].strip()

        name = frontmatter.get("name")
        description = frontmatter.get("description", "")
        version = frontmatter.get("version")

        if not name:
            raise ValueError(f"SKILL.md must have a 'name' field in {skill_path}")

        scripts = {}
        scripts_dir = skill_path / "scripts"
        if scripts_dir.exists():
            for script_file in scripts_dir.glob("*"):
                if script_file.is_file():
                    scripts[script_file.name] = script_file.read_text(encoding="utf-8")

        references = []
        references_dir = skill_path / "references"
        if references_dir.exists():
            for ref_file in references_dir.glob("*"):
                if ref_file.is_file():
                    references.append(ref_file.read_text(encoding="utf-8"))

        assets = []
        assets_dir = skill_path / "assets"
        if assets_dir.exists():
            for asset_file in assets_dir.glob("*"):
                if asset_file.is_file():
                    assets.append(asset_file)

        return Skill(
            name=name,
            description=description,
            instructions=instructions,
            scripts=scripts,
            references=references,
            assets=assets,
            version=version,
        )

    def load_all_skills(self) -> Dict[str, Skill]:
        """加载所有 Skills"""
        self.skills = {}

        if not self.skills_dir.exists():
            return self.skills

        for item in self.skills_dir.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                try:
                    skill = self.load_skill(item)
                    self.skills[skill.name] = skill
                except Exception as e:
                    print(f"Warning: Failed to load skill from {item}: {e}")

        self._loaded = True
        return self.skills

    def get_skill(self, name: str) -> Optional[Skill]:
        """获取指定 Skill"""
        if not self._loaded:
            self.load_all_skills()
        return self.skills.get(name)

    def match_skill(self, query: str, top_k: int = 3) -> List[Skill]:
        """根据查询匹配相关 Skill"""
        if not self._loaded:
            self.load_all_skills()

        query_lower = query.lower()
        matched = []

        for skill in self.skills.values():
            score = 0

            if query_lower in skill.description.lower():
                score += 10

            if query_lower in skill.name.lower():
                score += 5

            words = query_lower.split()
            for word in words:
                if word in skill.description.lower():
                    score += 2
                if word in skill.name.lower():
                    score += 1

            if score > 0:
                matched.append((score, skill))

        matched.sort(key=lambda x: x[0], reverse=True)
        return [skill for _, skill in matched[:top_k]]

    def list_skills(self) -> List[str]:
        """列出所有已加载的 Skill 名称"""
        if not self._loaded:
            self.load_all_skills()
        return list(self.skills.keys())

    def create_skill(
        self,
        name: str,
        description: str,
        instructions: str,
        scripts: Optional[Dict[str, str]] = None,
        references: Optional[List[str]] = None,
    ) -> Skill:
        """创建新 Skill 并保存"""
        skill = Skill(
            name=name,
            description=description,
            instructions=instructions,
            scripts=scripts or {},
            references=references or [],
        )

        skill_dir = self.skills_dir / name
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_md_content = f"""---
name: {name}
description: {description}
---

{instructions}
"""
        (skill_dir / "SKILL.md").write_text(skill_md_content, encoding="utf-8")

        if scripts:
            scripts_dir = skill_dir / "scripts"
            scripts_dir.mkdir(exist_ok=True)
            for script_name, script_content in scripts.items():
                (scripts_dir / script_name).write_text(script_content, encoding="utf-8")

        if references:
            references_dir = skill_dir / "references"
            references_dir.mkdir(exist_ok=True)
            for i, ref_content in enumerate(references):
                (references_dir / f"ref_{i}.md").write_text(ref_content, encoding="utf-8")

        self.skills[name] = skill
        return skill


def create_template_skill() -> str:
    """返回模板 Skill 的 SKILL.md 内容"""
    return """---
name: my-template-skill
description: 当用户需要[具体任务]时触发此技能。描述这个技能做什么以及何时使用。
version: 1.0.0
---

# My Template Skill

你是一个[角色描述]。当这个技能被激活时，你应该：

## 职责
- [职责1]
- [职责2]
- [职责3]

## 执行流程
1. [步骤1]
2. [步骤2]
3. [步骤3]

## 输出格式
```json
{
  "result": "...",
  "confidence": 0.0-1.0
}
```

## 示例
用户说："[示例输入]"
你应该：[执行什么操作]

## 注意事项
- [注意1]
- [注意2]
"""


if __name__ == "__main__":
    loader = SkillLoader("./skills")
    loader.load_all_skills()

    print(f"Loaded {len(loader.skills)} skills:")
    for name, skill in loader.skills.items():
        print(f"  - {name}: {skill.description[:60]}...")
