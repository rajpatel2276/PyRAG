from dataclasses import dataclass
import networkx as nx
from src.embedding.embedder import CodeEmbedder
from src.embedding.vector_store import VectorStore
from src.retrieval.graph_expand import expand_from_seeds
from src.retrieval.chunk_lookup import ChunkLookup
from src.config.logging_config import setup_logging

logger = setup_logging(__name__)


@dataclass
class RetrievedChunk:
    chunk_id: str
    name: str
    parent_class: str | None
    file_path: str
    source_code: str
    source: str          # "vector" or "graph"
    reason: str          # human-readable: "vector match" or "calls Session.send" etc.
    score: float          # lower = better; vector distance for vector hits, a fixed penalty for graph hits


class HybridRetriever:
    def __init__(self, repo_name: str, graph: nx.MultiDiGraph):
        self.embedder = CodeEmbedder()
        self.store = VectorStore(repo_name)
        self.lookup = ChunkLookup(repo_name)
        self.graph = graph

    def retrieve(self, query: str, n_vector_results: int = 5, graph_penalty: float = 0.15) -> list[RetrievedChunk]:
        """graph_penalty: added to a graph-expanded chunk's implicit score so
        it ranks below direct vector matches by default, unless it's clearly
        structurally central. Simple, tunable, and transparent — not a black box.
        """
        query_vec = self.embedder.embed_query(query)
        vector_results = self.store.query(query_vec, n_results=n_vector_results)

        results: dict[str, RetrievedChunk] = {}
        seed_ids = []

        for chunk_id, distance, meta in zip(
            vector_results["ids"][0], vector_results["distances"][0], vector_results["metadatas"][0]
        ):
            seed_ids.append(chunk_id)
            chunk = self.lookup.get(chunk_id)
            if chunk is None:
                logger.warning(f"Vector hit {chunk_id} not found in chunk lookup, skipping")
                continue
            results[chunk_id] = RetrievedChunk(
                chunk_id=chunk_id,
                name=chunk.name,
                parent_class=chunk.parent_class,
                file_path=chunk.file_path,
                source_code=chunk.source_code,
                source="vector",
                reason="semantic match",
                score=distance,
            )

        related = expand_from_seeds(self.graph, seed_ids, max_hops=1)
        for rel in related:
            if rel.chunk_id in results:
                continue  # already have it as a direct vector hit, don't downgrade it
            chunk = self.lookup.get(rel.chunk_id)
            if chunk is None:
                continue  # e.g. a file node, or a chunk not in this repo's chunk file

            seed_chunk = self.lookup.get(rel.via_seed)
            seed_label = seed_chunk.name if seed_chunk else rel.via_seed
            reason_map = {
                "calls": f"called by {seed_label}",
                "called_by": f"calls into {seed_label}",
                "contains": f"member of {seed_label}",
                "contained_by": f"contains {seed_label}",
                "inherits": f"base class of {seed_label}",
            }

            # base score: worst vector distance among seeds + fixed penalty,
            # so graph hits rank after vector hits by default but stay comparable
            base_score = max((r.score for r in results.values()), default=1.0) + graph_penalty

            results[rel.chunk_id] = RetrievedChunk(
                chunk_id=rel.chunk_id,
                name=chunk.name,
                parent_class=chunk.parent_class,
                file_path=chunk.file_path,
                source_code=chunk.source_code,
                source="graph",
                reason=reason_map.get(rel.relation, rel.relation),
                score=base_score,
            )

        return sorted(results.values(), key=lambda r: r.score)