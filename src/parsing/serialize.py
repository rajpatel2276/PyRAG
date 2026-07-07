import json
from pathlib import Path
from dataclasses import asdict
from src.parsing.ast_parser import CodeChunk
from src.config.settings import settings
from src.config.logging_config import setup_logging

logger = setup_logging(__name__)


def save_chunks(chunks: list[CodeChunk], repo_name: str) -> Path:
    out_path = settings.chunks_dir / f"{repo_name}.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(asdict(chunk)) + "\n")
    logger.info(f"Saved {len(chunks)} chunks to {out_path}")
    return out_path


def load_chunks(repo_name: str) -> list[CodeChunk]:
    in_path = settings.chunks_dir / f"{repo_name}.jsonl"
    chunks = []
    with in_path.open("r", encoding="utf-8") as f:
        for line in f:
            data = json.loads(line)
            chunks.append(CodeChunk(**data))
    logger.info(f"Loaded {len(chunks)} chunks from {in_path}")
    return chunks