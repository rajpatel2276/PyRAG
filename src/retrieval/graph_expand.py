import networkx as nx
from dataclasses import dataclass
from src.config.logging_config import setup_logging

logger = setup_logging(__name__)


@dataclass
class RelatedChunk:
    chunk_id: str
    relation: str       # "calls", "called_by", "contains", "contained_by", "inherits"
    hop_distance: int
    via_seed: str        # which seed chunk led us here, useful for debugging/explaining results


def expand_from_seed(graph: nx.MultiDiGraph, seed_chunk_id: str, max_hops: int = 1) -> list[RelatedChunk]:
    """One-hop (by default) structural expansion from a single chunk node.
    Only follows: calls (both directions), contains (both directions), inherits (outgoing).
    Deliberately does NOT follow 'imports' — that's file-granularity, too coarse here.
    """
    if seed_chunk_id not in graph:
        logger.warning(f"Seed chunk_id not found in graph: {seed_chunk_id}")
        return []

    related: dict[str, RelatedChunk] = {}

    # outgoing calls: seed calls these
    for _, target, data in graph.out_edges(seed_chunk_id, data=True):
        if data["relation"] == "calls" and target != seed_chunk_id:
            related[target] = RelatedChunk(target, "calls", 1, seed_chunk_id)

    # incoming calls: these call the seed
    for source, _, data in graph.in_edges(seed_chunk_id, data=True):
        if data["relation"] == "calls" and source != seed_chunk_id:
            related[source] = RelatedChunk(source, "called_by", 1, seed_chunk_id)

    # outgoing contains: seed is a class, these are its methods
    for _, target, data in graph.out_edges(seed_chunk_id, data=True):
        if data["relation"] == "contains" and graph.nodes[target].get("node_type") == "chunk":
            related[target] = RelatedChunk(target, "contains", 1, seed_chunk_id)

    # incoming contains: seed's containing class/file
    for source, _, data in graph.in_edges(seed_chunk_id, data=True):
        if data["relation"] == "contains":
            related[source] = RelatedChunk(source, "contained_by", 1, seed_chunk_id)

    # outgoing inherits: seed's base class
    for _, target, data in graph.out_edges(seed_chunk_id, data=True):
        if data["relation"] == "inherits":
            related[target] = RelatedChunk(target, "inherits", 1, seed_chunk_id)

    return list(related.values())


def expand_from_seeds(graph: nx.MultiDiGraph, seed_chunk_ids: list[str], max_hops: int = 1) -> list[RelatedChunk]:
    """Expand from multiple seeds, deduping by chunk_id (keep first occurrence)."""
    all_related: dict[str, RelatedChunk] = {}
    for seed in seed_chunk_ids:
        for rel in expand_from_seed(graph, seed, max_hops):
            if rel.chunk_id not in all_related and rel.chunk_id not in seed_chunk_ids:
                all_related[rel.chunk_id] = rel
    return list(all_related.values())