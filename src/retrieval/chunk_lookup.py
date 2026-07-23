from src.parsing.ast_parser import CodeChunk
from src.parsing.serialize import load_chunks
from src.config.logging_config import setup_logging

logger = setup_logging(__name__)


class ChunkLookup:
    """In-memory index of chunk_id -> CodeChunk for a repo, built once and reused
    across many retrieval calls rather than re-loading from disk every query.
    """
    def __init__(self, repo_name: str):
        chunks = load_chunks(repo_name)
        self._index: dict[str, CodeChunk] = {c.chunk_id: c for c in chunks}
        logger.info(f"ChunkLookup loaded {len(self._index)} chunks for '{repo_name}'")

    def get(self, chunk_id: str) -> CodeChunk | None:
        return self._index.get(chunk_id)