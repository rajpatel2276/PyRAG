import chromadb
from chromadb.config import Settings as ChromaSettings
import numpy as np
from src.parsing.ast_parser import CodeChunk
from src.config.settings import settings
from src.config.logging_config import setup_logging

logger = setup_logging(__name__)

CHROMA_DIR = settings.project_root / "chroma_db"


class VectorStore:
    def __init__(self, collection_name: str):
        self.client = chromadb.PersistentClient(
            path=str(CHROMA_DIR),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},  # cosine similarity — standard for text/code embeddings
        )
        logger.info(f"Connected to Chroma collection '{collection_name}' at {CHROMA_DIR}")

    def add_chunks(self, chunks: list[CodeChunk], embeddings: np.ndarray, batch_size: int = 100):
        """Upsert chunks + their embeddings into the collection.
        Uses chunk_id as the primary key — re-running this with the same
        chunk_id updates the existing entry rather than duplicating it,
        which matters for Phase 7 (incremental re-indexing).
        """
        ids = [c.chunk_id for c in chunks]
        documents = [c.source_code for c in chunks]
        metadatas = [
            {
                "file_path": c.file_path,
                "chunk_type": c.chunk_type,
                "name": c.name,
                "parent_class": c.parent_class or "",  # Chroma metadata can't store None
                "start_line": c.start_line,
                "end_line": c.end_line,
            }
            for c in chunks
        ]

        for i in range(0, len(ids), batch_size):
            end = i + batch_size
            self.collection.upsert(
                ids=ids[i:end],
                embeddings=embeddings[i:end].tolist(),
                documents=documents[i:end],
                metadatas=metadatas[i:end],
            )
            logger.info(f"Upserted chunks {i}-{min(end, len(ids))}/{len(ids)}")

        logger.info(f"Total chunks in collection: {self.collection.count()}")

    def query(self, query_embedding: np.ndarray, n_results: int = 5) -> dict:
        return self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=n_results,
        )