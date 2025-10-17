# services/index_service.py
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional
import os
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain.docstore.document import Document
from langchain_community.vectorstores import FAISS
from langchain.embeddings.base import Embeddings
import dashscope
from http import HTTPStatus

from dotenv import load_dotenv
load_dotenv(override=True)

class DashScopeEmbeddings(Embeddings):
    """自定义DashScope嵌入类，使用原生SDK"""
    
    def __init__(self, model: str = "text-embedding-v4"):
        self.model = model
        # 设置API密钥
        dashscope.api_key = os.getenv("DASHSCOPE_API_KEY")
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """嵌入文档列表，支持批处理以避免API限制"""
        try:
            all_embeddings = []
            batch_size = 10  # DashScope API限制
            
            for i in range(0, len(texts), batch_size):
                batch = texts[i:i + batch_size]
                resp = dashscope.TextEmbedding.call(
                    model=self.model,
                    input=batch
                )
                
                if resp.status_code == HTTPStatus.OK:
                    batch_embeddings = [record['embedding'] for record in resp.output['embeddings']]
                    all_embeddings.extend(batch_embeddings)
                else:
                    raise Exception(f"DashScope API error: {resp}")
            
            return all_embeddings
        except Exception as e:
            print(f"Error in embed_documents: {e}")
            raise e
    
    def embed_query(self, text: str) -> List[float]:
        """嵌入单个查询"""
        try:
            resp = dashscope.TextEmbedding.call(
                model=self.model,
                input=text
            )
            
            if resp.status_code == HTTPStatus.OK:
                return resp.output['embeddings'][0]['embedding']
            else:
                raise Exception(f"DashScope API error: {resp}")
        except Exception as e:
            print(f"Error in embed_query: {e}")
            raise e

# 复用你已有的数据目录结构
DATA_ROOT = Path("data")

def workdir(file_id: str) -> Path:
    p = DATA_ROOT / file_id
    p.mkdir(parents=True, exist_ok=True)
    return p

def markdown_path(file_id: str) -> Path:
    return workdir(file_id) / "output.md"

def index_dir(file_id: str) -> Path:
    p = workdir(file_id) / "index_faiss"
    p.mkdir(parents=True, exist_ok=True)
    return p

def load_embeddings() -> DashScopeEmbeddings:
    # 使用自定义的DashScope嵌入类
    return DashScopeEmbeddings(model="text-embedding-v4")

def split_markdown(md_text: str) -> List[Document]:
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        # 需要更细可以加 ("###", "Header 3")
    ]
    splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    docs = splitter.split_text(md_text)
    # 可加一点清洗
    cleaned: List[Document] = []
    for d in docs:
        txt = (d.page_content or "").strip()
        if not txt:
            continue
        # 限制太长的段落，避免向量化出错
        if len(txt) > 8000:
            txt = txt[:8000]
        cleaned.append(Document(page_content=txt, metadata=d.metadata))
    return cleaned

def build_faiss_index(file_id: str) -> Dict[str, Any]:
    try:
        md_file = markdown_path(file_id)
        if not md_file.exists():
            return {"ok": False, "error": "MARKDOWN_NOT_FOUND"}
        md_text = md_file.read_text(encoding="utf-8")

        docs = split_markdown(md_text)
        if not docs:
            return {"ok": False, "error": "EMPTY_MD"}

        print(f"Building index for {file_id}, {len(docs)} documents")
        for i, doc in enumerate(docs):
            print(f"Doc {i}: content length={len(doc.page_content)}, metadata={doc.metadata}")
            if not doc.page_content or not isinstance(doc.page_content, str):
                print(f"Warning: Doc {i} has invalid content: {type(doc.page_content)}")

        embeddings = load_embeddings()
        vs = FAISS.from_documents(docs, embedding=embeddings)
        vs.save_local(str(index_dir(file_id)))
        return {"ok": True, "chunks": len(docs)}
    except Exception as e:
        print(f"Error building index: {e}")
        import traceback
        traceback.print_exc()
        return {"ok": False, "error": str(e)}

def search_faiss(file_id: str, query: str, k: int = 5) -> Dict[str, Any]:
    idx = index_dir(file_id)
    if not (idx / "index.faiss").exists():
        return {"ok": False, "error": "INDEX_NOT_FOUND"}

    embeddings = load_embeddings()
    vs = FAISS.load_local(str(idx), embeddings, allow_dangerous_deserialization=True)
    hits = vs.similarity_search_with_score(query, k=k)
    results = []
    for doc, score in hits:
        results.append({
            "text": doc.page_content,
            "score": float(score),
            "metadata": doc.metadata,
        })
    return {"ok": True, "results": results}
