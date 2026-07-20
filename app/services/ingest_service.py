import os
from typing import List

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_core.documents import Document

from langchain_community.vectorstores import SupabaseVectorStore
from supabase.client import Client
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings


class IngestService:
    def __init__(self, supabase: Client, embeddings: OpenAIEmbeddings):
        self.vector_store = SupabaseVectorStore(
            client=supabase,
            embedding=embeddings,
            table_name=settings.supabase_table,
            query_name=settings.supabase_match_fn,
        )

    def _split(self, docs: List[Document], chunk_size: int, chunk_overlap: int) -> List[Document]:
        splitter = CharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        return splitter.split_documents(docs)

    def ingest_pdf_path(self, pdf_path: str, chunk_size: int, chunk_overlap: int) -> int:
        loader = PyPDFLoader(pdf_path)
        raw_docs = loader.load()
        chunks = self._split(raw_docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.vector_store.add_documents(chunks)
        return len(chunks)

    def save_upload_to_tmp(self, filename: str, content: bytes) -> str:
        os.makedirs(settings.tmp_dir, exist_ok=True)
        safe_name = os.path.basename(filename)
        tmp_path = os.path.join(settings.tmp_dir, safe_name)
        with open(tmp_path, "wb") as f:
            f.write(content)
        return tmp_path