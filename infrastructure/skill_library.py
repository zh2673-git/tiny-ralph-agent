"""
技能沉淀库 - Hermes-Agent 风格

核心思想：
1. 成功的工具/模式 → 沉淀到技能库
2. 技能可被后续任务复用
3. 技能可迭代优化（v1, v2, v3...）
4. 跨任务、跨会话累积
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
import shutil


class SkillLibrary:
    """
    技能沉淀库

    核心职责：
    1. add_skill - 添加技能
    2. get_skill - 获取技能
    3. search_skills - 搜索相关技能
    4. improve_skill - 改进技能
    5. get_best_skill - 获取最优版本
    """

    def __init__(self, library_dir: str = "./skills/library"):
        self.library_dir = Path(library_dir)
        self.library_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.library_dir / "index.json"
        self._ensure_index()

    def _ensure_index(self):
        """确保索引文件存在"""
        if not self.index_file.exists():
            self._save_index({})

    def _load_index(self) -> Dict:
        with open(self.index_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_index(self, index: Dict):
        with open(self.index_file, 'w', encoding='utf-8') as f:
            json.dump(index, f, ensure_ascii=False, indent=2)

    def add_skill(
        self,
        name: str,
        description: str,
        code: str,
        metadata: Optional[Dict] = None,
        success: bool = True
    ) -> str:
        """
        添加技能到库

        Args:
            name: 技能名称
            description: 技能描述
            code: 技能代码
            metadata: 元数据（用途、参数等）
            success: 是否成功使用过

        Returns:
            skill_id
        """
        index = self._load_index()

        if name not in index:
            index[name] = {
                "name": name,
                "description": description,
                "versions": [],
                "best_version": None,
                "total_uses": 0,
                "successful_uses": 0
            }

        skill_data = {
            "version": f"v{len(index[name]['versions']) + 1}",
            "code": code,
            "metadata": metadata or {},
            "added_at": datetime.now().isoformat(),
            "last_used_at": None,
            "use_count": 0,
            "success_count": 0
        }

        index[name]["versions"].append(skill_data)
        index[name]["total_uses"] += 1
        if success:
            index[name]["successful_uses"] += 1
            skill_data["success_count"] += 1

        if index[name]["best_version"] is None or success:
            index[name]["best_version"] = skill_data["version"]

        self._save_index(index)

        skill_dir = self.library_dir / name.replace(" ", "_")
        skill_dir.mkdir(exist_ok=True)
        version_file = skill_dir / f"{skill_data['version']}.py"
        with open(version_file, 'w', encoding='utf-8') as f:
            f.write(code)

        return f"{name}:{skill_data['version']}"

    def get_skill(
        self,
        name: str,
        version: Optional[str] = None
    ) -> Optional[Dict]:
        """获取技能"""
        index = self._load_index()

        if name not in index:
            return None

        if version is None:
            version = index[name]["best_version"]

        skill_dir = self.library_dir / name.replace(" ", "_")
        version_file = skill_dir / f"{version}.py"

        if not version_file.exists():
            return None

        with open(version_file, 'r', encoding='utf-8') as f:
            code = f.read()

        skill_info = index[name].copy()
        for v in skill_info["versions"]:
            if v["version"] == version:
                skill_info.update(v)
                break

        skill_info["code"] = code
        return skill_info

    def search_skills(self, query: str) -> List[Dict]:
        """
        搜索相关技能

        基于名称和描述匹配
        """
        index = self._load_index()
        query_lower = query.lower()
        results = []

        for name, skill_info in index.items():
            score = 0

            if query_lower in name.lower():
                score += 10

            if query_lower in skill_info.get("description", "").lower():
                score += 5

            if score > 0:
                results.append({
                    "name": name,
                    "description": skill_info["description"],
                    "score": score,
                    "best_version": skill_info["best_version"],
                    "total_uses": skill_info["total_uses"],
                    "success_rate": (
                        skill_info["successful_uses"] / skill_info["total_uses"]
                        if skill_info["total_uses"] > 0 else 0
                    )
                })

        results.sort(key=lambda x: (x["score"], x["success_rate"]), reverse=True)
        return results

    def improve_skill(
        self,
        name: str,
        improved_code: str,
        reason: str,
        metadata: Optional[Dict] = None
    ) -> Optional[str]:
        """
        改进已有技能

        Args:
            name: 技能名称
            improved_code: 改进后的代码
            reason: 改进原因
            metadata: 元数据

        Returns:
            new_skill_id 或 None
        """
        index = self._load_index()

        if name not in index:
            return None

        improvement_note = f"""
# 改进版本
# 改进原因: {reason}
# 改进时间: {datetime.now().isoformat()}
"""

        new_code = improvement_note + "\n" + improved_code

        return self.add_skill(
            name=name,
            description=index[name]["description"],
            code=new_code,
            metadata={
                **(metadata or {}),
                "improvement_reason": reason,
                "improved_from": index[name].get("best_version")
            },
            success=True
        )

    def record_skill_usage(
        self,
        name: str,
        version: Optional[str] = None,
        success: bool = True
    ):
        """记录技能使用情况"""
        index = self._load_index()

        if name not in index:
            return

        if version is None:
            version = index[name]["best_version"]

        for v in index[name]["versions"]:
            if v["version"] == version:
                v["use_count"] += 1
                v["last_used_at"] = datetime.now().isoformat()
                if success:
                    v["success_count"] += 1
                    index[name]["successful_uses"] += 1

        index[name]["total_uses"] += 1

        success_rate = index[name]["successful_uses"] / index[name]["total_uses"]
        if success and (
            index[name]["best_version"] is None or
            success_rate > self._get_success_rate(name, index[name]["best_version"])
        ):
            index[name]["best_version"] = version

        self._save_index(index)

    def _get_success_rate(self, name: str, version: str) -> float:
        """获取技能成功率"""
        skill = self.get_skill(name, version)
        if not skill or skill["use_count"] == 0:
            return 0
        return skill["success_count"] / skill["use_count"]

    def get_best_skill(self, name: str) -> Optional[Dict]:
        """获取最优版本技能"""
        index = self._load_index()
        if name not in index:
            return None

        best_version = index[name].get("best_version")
        if best_version is None:
            return None

        return self.get_skill(name, best_version)

    def list_skills(self) -> List[Dict]:
        """列出所有技能"""
        index = self._load_index()
        return [
            {
                "name": name,
                "description": info["description"],
                "version_count": len(info["versions"]),
                "best_version": info["best_version"],
                "total_uses": info["total_uses"],
                "success_rate": (
                    info["successful_uses"] / info["total_uses"]
                    if info["total_uses"] > 0 else 0
                )
            }
            for name, info in index.items()
        ]

    def export_learnings(self, task_id: str, learnings: List[str]):
        """导出学习到技能库"""
        for learning in learnings:
            self.add_skill(
                name=f"learning_{task_id}",
                description=f"从任务 {task_id} 学到的经验",
                code=f"# Learning from task {task_id}\n# {learning}",
                metadata={"type": "learning", "task_id": task_id},
                success=True
            )
