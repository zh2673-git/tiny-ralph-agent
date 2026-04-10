"""
GraphRAG Skill - 知识图谱检索增强

基于实体-关系的智能文档问答 Skill。
适配本项目架构，使用 SQLite 存储和 Ollama Embedding。
"""

import os
from typing import List, Optional, Dict, Any
from pathlib import Path
import json
import hashlib
import sqlite3
import requests
from dataclasses import dataclass, asdict

from infrastructure.skill_loader import Skill


@dataclass
class Entity:
    """实体"""
    name: str
    entity_type: str
    description: str = ""
    doc_ids: List[str] = None

    def __post_init__(self):
        if self.doc_ids is None:
            self.doc_ids = []


@dataclass
class Relation:
    """关系"""
    source: str
    target: str
    relation: str
    doc_id: str
    confidence: float = 1.0


class GraphRAGService:
    """
    GraphRAG 服务

    提供基于实体-关系的知识图谱存储和检索。
    使用 SQLite 存储，无需额外依赖。
    """

    def __init__(
        self,
        persist_dir: str = "./data/graphrag",
        embedding_model: str = "qwen3-embedding:0.6b",
    ):
        self.persist_dir = Path(persist_dir)
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_model = embedding_model

        self.db_path = self.persist_dir / "graphrag.db"
        self._init_db()

        self._ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                description TEXT,
                embedding BLOB,
                doc_ids TEXT
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS relations (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                target TEXT NOT NULL,
                relation TEXT NOT NULL,
                doc_id TEXT,
                confidence REAL DEFAULT 1.0
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                metadata TEXT,
                embedding BLOB
            )
        """)

        c.execute("CREATE INDEX IF NOT EXISTS idx_entity_name ON entities(name)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_relation_source ON relations(source)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_relation_target ON relations(target)")

        conn.commit()
        conn.close()

    def _get_embedding(self, text: str) -> List[float]:
        """获取文本 embedding"""
        try:
            response = requests.post(
                f"{self._ollama_base_url}/api/embeddings",
                json={"model": self.embedding_model, "prompt": text},
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            return result.get("embedding", [0.0] * 1024)
        except Exception as e:
            print(f"Embedding 失败: {e}")
            return [0.0] * 1024

    def add_document(
        self,
        text: str,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """添加文档"""
        if doc_id is None:
            doc_id = hashlib.md5(text.encode()).hexdigest()[:16]

        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        embedding = self._get_embedding(text)

        c.execute(
            "INSERT OR REPLACE INTO documents (id, content, metadata, embedding) VALUES (?, ?, ?, ?)",
            (doc_id, text, json.dumps(metadata or {}), json.dumps(embedding))
        )

        entities = self._extract_entities(text)
        for entity in entities:
            self._add_entity(entity, doc_id, conn)

        self._infer_relations(entities, doc_id, conn)

        conn.commit()
        conn.close()

        return doc_id

    def _extract_entities(self, text: str) -> List[Entity]:
        """提取实体（简单规则版）"""
        entities = []

        import re
        patterns = [
            (r'《([^》]+)》', '书名'),
            (r'《([^》]+)》', '书籍'),
            (r'([\u4e00-\u9fa5]{2,4})说', '人物'),
            (r'([\u4e00-\u9fa5]{2,4})提出', '人物'),
            (r'([\u4e00-\u9fa5]{2,4})认为', '人物'),
            (r'([\u4e00-\u9fa5]+)病', '疾病'),
            (r'([\u4e00-\u9fa5]+)证', '证型'),
            (r'([\u4e00-\u9fa5]+)汤', '方剂'),
        ]

        for pattern, entity_type in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) >= 2:
                    entities.append(Entity(
                        name=match,
                        entity_type=entity_type,
                        description=f"从文本中识别: {match}"
                    ))

        return entities

    def _add_entity(self, entity: Entity, doc_id: str, conn: sqlite3.Connection):
        """添加实体"""
        c = conn.cursor()
        entity_id = hashlib.md5(entity.name.encode()).hexdigest()[:16]

        c.execute("SELECT doc_ids FROM entities WHERE id = ?", (entity_id,))
        row = c.fetchone()

        if row:
            doc_ids = json.loads(row[0])
            if doc_id not in doc_ids:
                doc_ids.append(doc_id)
            c.execute(
                "UPDATE entities SET doc_ids = ? WHERE id = ?",
                (json.dumps(doc_ids), entity_id)
            )
        else:
            c.execute(
                "INSERT INTO entities (id, name, entity_type, description, doc_ids) VALUES (?, ?, ?, ?, ?)",
                (entity_id, entity.name, entity.entity_type, entity.description, json.dumps([doc_id]))
            )

    def _infer_relations(self, entities: List[Entity], doc_id: str, conn: sqlite3.Connection):
        """推断实体间关系"""
        c = conn.cursor()

        for i, e1 in enumerate(entities):
            for e2 in entities[i+1:]:
                rel_id = hashlib.md5(f"{e1.name}{e2.name}".encode()).hexdigest()[:16]
                c.execute(
                    "INSERT OR IGNORE INTO relations (id, source, target, relation, doc_id, confidence) VALUES (?, ?, ?, ?, ?, ?)",
                    (rel_id, e1.name, e2.name, "CO_OCCUR", doc_id, 0.8)
                )

    def search(self, query: str, top_k: int = 5) -> str:
        """搜索相关上下文"""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        query_embedding = self._get_embedding(query)

        c.execute("SELECT id, embedding FROM documents")
        docs = []
        for doc_id, emb_str in c.fetchall():
            doc_emb = json.loads(emb_str)
            sim = self._cosine_sim(query_embedding, doc_emb)
            docs.append((doc_id, sim))

        docs.sort(key=lambda x: x[1], reverse=True)

        results = []
        for doc_id, score in docs[:top_k]:
            c.execute("SELECT content, metadata FROM documents WHERE id = ?", (doc_id,))
            row = c.fetchone()
            if row:
                results.append(f"### 文档 (相似度: {score:.2f})\n{row[0]}")

        if not results:
            return "未找到相关文档"

        return "\n\n---\n\n".join(results)

    def _cosine_sim(self, v1: List[float], v2: List[float]) -> float:
        """余弦相似度"""
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = sum(a * a for a in v1) ** 0.5
        norm2 = sum(b * b for b in v2) ** 0.5
        return dot / (norm1 * norm2 + 1e-8)

    def get_stats(self) -> Dict[str, int]:
        """获取统计信息"""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM entities")
        entity_count = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM relations")
        relation_count = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM documents")
        doc_count = c.fetchone()[0]

        conn.close()

        return {
            "total_entities": entity_count,
            "total_relations": relation_count,
            "total_documents": doc_count,
        }


class GraphRAGSkill(Skill):
    """
    GraphRAG Skill

    提供知识图谱检索增强能力。
    """

    name = "graphrag"
    description = "知识图谱检索增强 - 基于实体-关系的智能文档问答"
    version = "1.0.0"
    triggers = [
        "知识图谱", "文档问答", "知识库",
        "检索", "实体", "关系",
        "添加文档", "上传文档", "搜索知识",
    ]

    def __init__(
        self,
        embedding_model: str = "qwen3-embedding:0.6b",
        persist_dir: str = "./data/graphrag",
        knowledge_base_dir: str = "./knowledge_base",
    ):
        super().__init__(
            name=self.name,
            description=self.description,
            instructions=self._get_instructions(),
        )

        self.embedding_model = embedding_model
        self.persist_dir = persist_dir
        self.knowledge_base_dir = knowledge_base_dir
        self._service: Optional[GraphRAGService] = None

    def _get_instructions(self) -> str:
        return """你是知识库管理助手。

## 搜索范围规则

### 用户指定了分类
只在用户指定的分类中搜索。

### 用户没说分类
使用全局搜索。

### 用户问有哪些分类
列出所有可用分类。

## 工具说明
- search_in_category(category, query) - 在指定分类中搜索
- search_all_documents(query) - 全局搜索
- list_knowledge_categories() - 查看分类
- upload_document(file_path) - 上传文档
"""

    def initialize(self):
        """初始化服务"""
        if self._service is None:
            self._service = GraphRAGService(
                persist_dir=self.persist_dir,
                embedding_model=self.embedding_model,
            )

    def get_service(self) -> GraphRAGService:
        if self._service is None:
            self.initialize()
        return self._service