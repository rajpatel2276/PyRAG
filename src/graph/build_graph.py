from pathlib import Path
import networkx as nx
from src.parsing.repo_walker import walk_repo, _collect_python_files
from src.graph.import_graph import build_import_graph
from src.graph.chunk_graph import add_chunk_nodes_and_edges
from src.config.logging_config import setup_logging

logger = setup_logging(__name__)


def build_full_graph(repo_path: Path) -> nx.MultiDiGraph:
    py_files = _collect_python_files(repo_path)
    graph = build_import_graph(repo_path, py_files)

    chunks, stats = walk_repo(repo_path)
    logger.info(f"Chunk walk stats: {stats}")

    graph = add_chunk_nodes_and_edges(graph, chunks)
    return graph