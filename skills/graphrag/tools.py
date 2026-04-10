"""
GraphRAG 工具集

提供知识图谱相关的工具函数。
"""

from typing import Optional, List, Dict, Any
from pathlib import Path
import logging

from langchain_core.tools import tool
from PyPDF2 import PdfReader
from docx import Document

from .skill import GraphRAGService, Entity

logger = logging.getLogger("graphrag.tools")

_service: Optional[GraphRAGService] = None


def init_graphrag_services(service: GraphRAGService) -> None:
    """初始化全局服务实例"""
    global _service
    _service = service


def get_graph_service() -> Optional[GraphRAGService]:
    """获取图谱服务实例"""
    return _service


@tool
def upload_document(
    file_path: str,
    category: Optional[str] = None,
) -> str:
    """
    上传文档到知识图谱

    Args:
        file_path: 文档路径
        category: 可选，分类名称
    """
    if _service is None:
        return "GraphRAG 服务未初始化"

    path = Path(file_path)
    if not path.exists():
        return f"文件不存在: {file_path}"

    try:
        ext = path.suffix.lower()
        if ext == ".pdf":
            reader = PdfReader(str(path))
            text = "\n".join([page.extract_text() for page in reader.pages])
        elif ext in [".docx", ".doc"]:
            doc = Document(str(path))
            text = "\n".join([para.text for para in doc.paragraphs])
        elif ext in [".txt", ".md"]:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
        else:
            return f"不支持的文件格式: {ext}"

        metadata = {"file_path": str(path), "category": category or "default"}

        doc_id = _service.add_document(text=text, metadata=metadata)

        return f"文档已上传: {path.name} (ID: {doc_id})"

    except Exception as e:
        return f"上传失败: {str(e)}"


@tool
def add_text(
    text: str,
    doc_id: Optional[str] = None,
    metadata: Optional[Dict] = None,
) -> str:
    """
    添加文本到知识图谱

    Args:
        text: 文本内容
        doc_id: 可选，文档ID
        metadata: 可选，元数据
    """
    if _service is None:
        return "GraphRAG 服务未初始化"

    try:
        doc_id = _service.add_document(text=text, doc_id=doc_id, metadata=metadata or {})
        return f"文本已添加 (ID: {doc_id})"
    except Exception as e:
        return f"添加失败: {str(e)}"


@tool
def search_all_documents(query: str, top_k: int = 5) -> str:
    """
    全局搜索所有文档

    Args:
        query: 查询内容
        top_k: 返回数量
    """
    if _service is None:
        return "GraphRAG 服务未初始化"

    try:
        return _service.search(query=query, top_k=top_k)
    except Exception as e:
        return f"搜索失败: {str(e)}"


@tool
def search_in_category(category: str, query: str, top_k: int = 5) -> str:
    """
    在指定分类中搜索

    Args:
        category: 分类名称
        query: 查询内容
        top_k: 返回数量
    """
    if _service is None:
        return "GraphRAG 服务未初始化"

    import sqlite3
    import json

    try:
        conn_db = sqlite3.connect(str(_service.db_path))
        c = conn_db.cursor()

        c.execute("SELECT id, content, metadata FROM documents WHERE metadata LIKE ?", (f'%"{category}"%',))
        results = c.fetchall()
        conn_db.close()

        if not results:
            return f"分类 '{category}' 中没有找到文档"

        return f"在分类 '{category}' 中找到 {len(results)} 个文档\n\n" + "\n\n---\n\n".join([
            f"### 文档\n{content}" for _, content, _ in results[:top_k]
        ])

    except Exception as e:
        return f"搜索失败: {str(e)}"


@tool
def list_knowledge_categories() -> str:
    """列出所有知识分类"""
    if _service is None:
        return "GraphRAG 服务未初始化"

    import sqlite3
    import json

    try:
        conn_db = sqlite3.connect(str(_service.db_path))
        c = conn_db.cursor()

        c.execute("SELECT metadata FROM documents")
        categories = set()
        for row in c.fetchall():
            if row[0]:
                metadata = json.loads(row[0])
                if "category" in metadata:
                    categories.add(metadata["category"])

        conn_db.close()

        if not categories:
            return "暂无分类"

        return "可用分类:\n" + "\n".join([f"- {cat}" for cat in sorted(categories)])

    except Exception as e:
        return f"获取分类失败: {str(e)}"


@tool
def query_graph_stats() -> str:
    """查询知识图谱统计信息"""
    if _service is None:
        return "GraphRAG 服务未初始化"

    try:
        stats = _service.get_stats()
        return f"""知识图谱统计:
- 实体数量: {stats['total_entities']}
- 关系数量: {stats['total_relations']}
- 文档数量: {stats['total_documents']}
"""
    except Exception as e:
        return f"获取统计失败: {str(e)}"


@tool
def list_entities(entity_type: Optional[str] = None, limit: int = 20) -> str:
    """
    列出实体

    Args:
        entity_type: 可选，实体类型过滤
        limit: 返回数量
    """
    if _service is None:
        return "GraphRAG 服务未初始化"

    import sqlite3
    import json

    try:
        conn_db = sqlite3.connect(str(_service.db_path))
        c = conn_db.cursor()

        if entity_type:
            c.execute("SELECT name, entity_type, description FROM entities WHERE entity_type = ? LIMIT ?", (entity_type, limit))
        else:
            c.execute("SELECT name, entity_type, description FROM entities LIMIT ?", (limit,))

        rows = c.fetchall()
        conn_db.close()

        if not rows:
            return "未找到实体"

        return "实体列表:\n" + "\n".join([
            f"- {name} ({entity_type}): {description[:50] if description else ''}..."
            for name, entity_type, description in rows
        ])

    except Exception as e:
        return f"获取实体失败: {str(e)}"


@tool
def get_entity_relations(entity_name: str) -> str:
    """
    获取实体的关系

    Args:
        entity_name: 实体名称
    """
    if _service is None:
        return "GraphRAG 服务未初始化"

    import sqlite3

    try:
        conn_db = sqlite3.connect(str(_service.db_path))
        c = conn_db.cursor()

        c.execute("""
            SELECT r.source, r.target, r.relation, r.confidence
            FROM relations r
            WHERE r.source = ? OR r.target = ?
        """, (entity_name, entity_name))

        rows = c.fetchall()
        conn_db.close()

        if not rows:
            return f"实体 '{entity_name}' 没有找到关系"

        return f"实体 '{entity_name}' 的关系:\n" + "\n".join([
            f"- {source} --[{relation}]--> {target} (置信度: {confidence:.2f})"
            for source, target, relation, confidence in rows
        ])

    except Exception as e:
        return f"获取关系失败: {str(e)}"
