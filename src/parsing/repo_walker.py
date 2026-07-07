from pathlib import Path
from dataclasses import dataclass
from src.parsing.ast_parser import parse_file, CodeChunk
from src.config.settings import settings
from src.config.logging_config import setup_logging

logger = setup_logging(__name__)

# Directories we never want to walk into
EXCLUDED_DIRS = {
    ".git", "venv", "env", ".venv", "__pycache__", "node_modules",
    ".tox", "build", "dist", ".eggs", "*.egg-info", ".mypy_cache",
    ".pytest_cache", "site-packages",
}


@dataclass
class WalkStats:
    files_found: int = 0
    files_parsed: int = 0
    files_skipped_size: int = 0
    files_failed: int = 0
    total_chunks: int = 0


def should_skip_dir(dir_name: str) -> bool:
    return dir_name in EXCLUDED_DIRS or dir_name.endswith(".egg-info")


def walk_repo(repo_path: Path) -> tuple[list[CodeChunk], WalkStats]:
    """Walk a repo, parse every .py file, return all chunks + run stats."""
    all_chunks: list[CodeChunk] = []
    stats = WalkStats()

    py_files = _collect_python_files(repo_path)
    stats.files_found = len(py_files)
    logger.info(f"Found {len(py_files)} Python files under {repo_path}")

    for file_path in py_files:
        try:
            file_size = file_path.stat().st_size
        except OSError as e:
            logger.warning(f"Could not stat {file_path}: {e}")
            stats.files_failed += 1
            continue

        if file_size > settings.max_file_size_bytes:
            logger.warning(f"Skipping oversized file ({file_size} bytes): {file_path}")
            stats.files_skipped_size += 1
            continue

        chunks = parse_file(file_path)
        chunks = parse_file(file_path)
        if chunks is None:
            # real failure — already logged inside parse_file
            stats.files_failed += 1
        elif len(chunks) == 0:
            # valid file, genuinely empty (0 bytes) — not an error
            stats.files_parsed += 1
        else:
            all_chunks.extend(chunks)
            stats.files_parsed += 1
            stats.total_chunks += len(chunks)
            
    logger.info(
        f"Walk complete: {stats.files_parsed}/{stats.files_found} parsed, "
        f"{stats.files_skipped_size} skipped (size), {stats.files_failed} failed, "
        f"{stats.total_chunks} total chunks"
    )
    return all_chunks, stats


def _collect_python_files(repo_path: Path) -> list[Path]:
    py_files = []
    for path in repo_path.rglob("*.py"):
        if any(should_skip_dir(part) for part in path.parts):
            continue
        py_files.append(path)
    return py_files
