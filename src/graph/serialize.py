from pathlib import Path
import networkx as nx
from networkx.readwrite import json_graph
import json
from src.config.settings import settings
from src.config.logging_config import setup_logging

logger = setup_logging(__name__)


def save_graph(graph: nx.MultiDiGraph, repo_name: str) -> Path:
    out_path = settings.chunks_dir / f"{repo_name}_graph.json"
    data = json_graph.node_link_data(graph, edges="edges")
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f)
    logger.info(f"Saved graph ({graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges) to {out_path}")
    return out_path


def load_graph(repo_name: str) -> nx.MultiDiGraph:
    in_path = settings.chunks_dir / f"{repo_name}_graph.json"
    with in_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    graph = json_graph.node_link_graph(data, edges="edges")
    logger.info(f"Loaded graph ({graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges) from {in_path}")
    return graph