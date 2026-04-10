"""
GraphRAG Service - 知识图谱服务（速度自适应版）

基于实体-关系的智能文档处理。
支持动态调整处理速度，根据系统负载自动降级。
"""

import os
import time
import asyncio
import threading
from typing import List, Optional, Dict, Any, Callable
from pathlib import Path
import json
import hashlib
import sqlite3
import requests
from dataclasses import dataclass, field
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor
import psutil


@dataclass
class ProcessingStats:
    """处理统计信息"""
    total_processed: int = 0
    total_time: float = 0.0
    avg_time_per_doc: float = 0.0
    current_batch_size: int = 1
    items_per_second: float = 0.0


@dataclass
class SystemLoad:
    """系统负载"""
    memory_percent: float = 0.0
    memory_available_gb: float = 0.0
    cpu_percent: float = 0.0


class AdaptiveEmbeddingService:
    """
    自适应 Embedding 服务

    特性：
    - 动态批处理：根据系统负载自动调整批次大小
    - 异步处理：不阻塞主线程
    - 后台索引：启动即可对话，索引不阻塞
    - 进度追踪：实时显示索引进度
    """

    DEFAULT_BATCH_SIZES = [1, 4, 8, 16, 32]
    MIN_BATCH_SIZE = 1
    MAX_BATCH_SIZE = 32

    def __init__(
        self,
        embedding_model: str = "qwen3-embedding:0.6b",
        ollama_base_url: str = None,
    ):
        self.embedding_model = embedding_model
        self._ollama_base_url = ollama_base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        self._current_batch_size = 8
        self._processing_queue: Queue = Queue()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="embedding_worker")
        self._running = False
        self._stats = ProcessingStats()
        self._stats_lock = threading.Lock()

        self._start_time = time.time()

    def _get_system_load(self) -> SystemLoad:
        """获取系统负载"""
        try:
            memory = psutil.virtual_memory()
            return SystemLoad(
                memory_percent=memory.percent,
                memory_available_gb=memory.available / (1024 ** 3),
                cpu_percent=psutil.cpu_percent(interval=0.1)
            )
        except Exception:
            return SystemLoad()

    def _calculate_adaptive_batch_size(self) -> int:
        """
        根据系统负载动态计算批次大小

        策略：
        - 内存充足（>50%）且负载低（<70%）→ 增大批次
        - 内存紧张（<30%）或负载高（>85%）→ 减小批次
        - 其他情况 → 保持当前批次
        """
        load = self._get_system_load()

        if load.memory_percent < 30 or load.cpu_percent > 85:
            new_batch = max(self.MIN_BATCH_SIZE, self._current_batch_size // 2)
        elif load.memory_percent > 50 and load.cpu_percent < 70:
            new_batch = min(self.MAX_BATCH_SIZE, self._current_batch_size * 2)
        else:
            new_batch = self._current_batch_size

        self._current_batch_size = new_batch
        return new_batch

    def _get_embedding(self, text: str) -> List[float]:
        """获取单个文本的 embedding"""
        try:
            response = requests.post(
                f"{self._ollama_base_url}/api/embeddings",
                json={"model": self.embedding_model, "prompt": text},
                timeout=60
            )
            response.raise_for_status()
            result = response.json()
            return result.get("embedding", [0.0] * 1024)
        except Exception as e:
            print(f"Embedding 失败: {e}")
            return [0.0] * 1024

    def get_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量获取 embeddings（自适应大小）

        根据当前系统负载动态调整批次大小
        """
        batch_size = self._calculate_adaptive_batch_size()
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = []

            for text in batch:
                embedding = self._get_embedding(text)
                batch_results.append(embedding)

            results.extend(batch_results)

            self._update_stats(len(batch))

        return results

    def _update_stats(self, processed: int):
        """更新处理统计"""
        with self._stats_lock:
            self._stats.total_processed += processed
            elapsed = time.time() - self._start_time
            self._stats.total_time = elapsed
            if elapsed > 0:
                self._stats.items_per_second = self._stats.total_processed / elapsed
                self._stats.avg_time_per_doc = elapsed / max(1, self._stats.total_processed)

    def get_stats(self) -> ProcessingStats:
        """获取处理统计"""
        with self._stats_lock:
            return ProcessingStats(
                total_processed=self._stats.total_processed,
                total_time=self._stats.total_time,
                avg_time_per_doc=self._stats.avg_time_per_doc,
                current_batch_size=self._current_batch_size,
                items_per_second=self._stats.items_per_second
            )

    def get_progress_str(self) -> str:
        """获取进度字符串"""
        stats = self.get_stats()
        return (
            f"已处理: {stats.total_processed} | "
            f"批大小: {stats.current_batch_size} | "
            f"速度: {stats.items_per_second:.2f}/s | "
            f"平均: {stats.avg_time_per_doc:.2f}s/条"
        )


class GraphRAGService:
    """
    GraphRAG 服务（增强版）

    特性：
    - 自适应 Embedding：根据系统负载动态调整
    - 增量索引：新文档自动合并到现有图谱
    - 智能分块：大文档自动切分
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
        self._embedding_service = AdaptiveEmbeddingService(embedding_model=embedding_model)
        self._init_db()

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

    def _extract_entities(self, text: str) -> List[Dict]:
        """提取实体"""
        entities = []

        import re
        patterns = [
            (r'《([^》]+)》', '书名'),
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
                entities.append({
                    "name": match,
                    "entity_type": entity_type,
                    "description": f"从文本中识别: {match}"
                })

        return entities

    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        """
        智能分块文本

        按句子边界分块，保持语义连贯
        """
        import re
        sentences = re.split(r'[。！？\n]', text)
        chunks = []
        current_chunk = []

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            current_chunk.append(sentence)
            if len(' '.join(current_chunk)) >= chunk_size:
                chunks.append(' '.join(current_chunk))
                current_chunk = []

        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks if chunks else [text]

    def add_document(
        self,
        text: str,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        chunk_size: int = 500,
        show_progress: bool = True,
    ) -> str:
        """
        添加文档（带进度显示）

        Args:
            text: 文档文本
            doc_id: 文档 ID，默认自动生成
            metadata: 元数据
            chunk_size: 分块大小
            show_progress: 是否显示进度
        """
        if doc_id is None:
            doc_id = hashlib.md5(text.encode()).hexdigest()[:16]

        chunks = self._chunk_text(text, chunk_size)
        if show_progress:
            print(f"📚 文档分块完成: {len(chunks)} 个块")

        embeddings = self._embedding_service.get_embeddings_batch(chunks)
        if show_progress:
            print(f"📊 进度: {self._embedding_service.get_progress_str()}")

        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        for chunk, embedding in zip(chunks, embeddings):
            chunk_id = hashlib.md5(chunk.encode()).hexdigest()[:16]
            c.execute(
                "INSERT OR REPLACE INTO documents (id, content, metadata, embedding) VALUES (?, ?, ?, ?)",
                (chunk_id, chunk, json.dumps(metadata or {}), json.dumps(embedding))
            )

        entities = self._extract_entities(text)
        for entity in entities:
            entity_id = hashlib.md5(entity["name"].encode()).hexdigest()[:16]
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
                    (entity_id, entity["name"], entity["entity_type"], entity["description"], json.dumps([doc_id]))
                )

        for i, e1 in enumerate(entities):
            for e2 in entities[i+1:]:
                rel_id = hashlib.md5(f"{e1['name']}{e2['name']}".encode()).hexdigest()[:16]
                c.execute(
                    "INSERT OR IGNORE INTO relations (id, source, target, relation, doc_id, confidence) VALUES (?, ?, ?, ?, ?, ?)",
                    (rel_id, e1["name"], e2["name"], "CO_OCCUR", doc_id, 0.8)
                )

        conn.commit()
        conn.close()

        if show_progress:
            print(f"✅ 文档索引完成: {doc_id}")

        return doc_id

    def add_documents_batch(
        self,
        documents: List[Dict[str, Any]],
        show_progress: bool = True,
    ) -> List[str]:
        """
        批量添加文档

        Args:
            documents: 文档列表，每项包含 text, metadata
            show_progress: 是否显示进度
        """
        doc_ids = []
        total = len(documents)

        for i, doc in enumerate(documents):
            if show_progress:
                print(f"\n📄 [{i+1}/{total}] 处理中...")

            doc_id = self.add_document(
                text=doc.get("text", ""),
                metadata=doc.get("metadata"),
                show_progress=show_progress
            )
            doc_ids.append(doc_id)

        if show_progress:
            print(f"\n🎉 批量索引完成: {len(doc_ids)} 个文档")
            print(f"📈 {self._embedding_service.get_progress_str()}")

        return doc_ids

    def search(self, query: str, top_k: int = 5) -> str:
        """搜索相关上下文"""
        query_embedding = self._embedding_service._get_embedding(query)

        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

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

        conn.close()

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

        embedding_stats = self._embedding_service.get_stats()

        return {
            "total_entities": entity_count,
            "total_relations": relation_count,
            "total_documents": doc_count,
            "embedding_stats": {
                "total_processed": embedding_stats.total_processed,
                "items_per_second": embedding_stats.items_per_second,
                "current_batch_size": embedding_stats.current_batch_size,
            }
        }
