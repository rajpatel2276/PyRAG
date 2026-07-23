from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer
import numpy as np
from src.parsing.ast_parser import CodeChunk
from src.config.logging_config import setup_logging

logger = setup_logging(__name__)

MODEL_NAME = "jinaai/jina-embeddings-v2-base-code"
MAX_TOKENS = 8192
SAFE_TOKEN_LIMIT = 2000 

class CodeEmbedder:
    def __init__(self):
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        self.model = SentenceTransformer(MODEL_NAME, trust_remote_code=True, device="cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        logger.info(f"Model loaded, embedding dim = {self.model.get_embedding_dimension()}")

    def _text_for_embedding(self, chunk: CodeChunk) -> str:
        token_count = len(self.tokenizer.encode(chunk.source_code))

        header = f"# {chunk.chunk_type}: "
        if chunk.parent_class:
            header += f"{chunk.parent_class}.{chunk.name}"
        else:
            header += chunk.name
        header += f"\n# file: {chunk.file_path}"

        if token_count <= SAFE_TOKEN_LIMIT:
            parts = [header]
            if chunk.docstring:
                parts.append(f'"""{chunk.docstring}"""')
            parts.append(chunk.source_code)
            return "\n".join(parts)

        logger.warning(
            f"Chunk {chunk.chunk_id} has {token_count} tokens (safe limit {SAFE_TOKEN_LIMIT}); "
            f"falling back to name+docstring only for embedding"
        )
        parts = [header]
        if chunk.docstring:
            parts.append(f'"""{chunk.docstring}"""')
        parts.append(f"[Content too large to embed in full: {token_count} tokens]")
        return "\n".join(parts)

    def embed_chunks(self, chunks: list[CodeChunk], batch_size: int = 8) -> np.ndarray:
        texts = [self._text_for_embedding(c) for c in chunks]
        logger.info(f"Embedding {len(texts)} chunks (batch_size={batch_size})")
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=True,
            convert_to_numpy=True,
        )
        return embeddings

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a search query — same model, single string, no batching needed."""
        return self.model.encode(query, convert_to_numpy=True)