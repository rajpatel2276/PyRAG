import networkx as nx
from src.parsing.ast_parser import CodeChunk
from src.graph.schema import NodeType, EdgeType
from src.config.logging_config import setup_logging

logger = setup_logging(__name__)


def add_chunk_nodes_and_edges(graph: nx.MultiDiGraph, chunks: list[CodeChunk]) -> nx.MultiDiGraph:
    """Mutates and returns the graph: adds a node per chunk, plus
    contains edges (file->chunk, class->method) and inherits edges (class->class).
    Assumes file nodes already exist in the graph (from build_import_graph).
    """
    # index: (file_path, class_name) -> chunk_id, needed to resolve inherits edges,
    # since base_classes are stored as bare names ("SessionRedirectMixin"), not chunk_ids
    class_name_to_chunk_id: dict[tuple[str, str], str] = {}

    # Pass 1: add all chunk nodes, and file->chunk / class->method containment edges
    for chunk in chunks:
        graph.add_node(
            chunk.chunk_id,
            node_type=NodeType.CHUNK.value,
            chunk_type=chunk.chunk_type,
            name=chunk.name,
            file_path=chunk.file_path,
            start_line=chunk.start_line,
            end_line=chunk.end_line,
        )

        if chunk.chunk_type == "class":
            class_name_to_chunk_id[(chunk.file_path, chunk.name)] = chunk.chunk_id

        if chunk.parent_class is None:
            # top-level chunk (function, class, or module) -> belongs to its file
            graph.add_edge(chunk.file_path, chunk.chunk_id, relation=EdgeType.CONTAINS.value)
        # methods are handled in pass 2, since we need the parent class's chunk_id,
        # and pass 1 may not have visited that class chunk yet

    # Pass 2: method -> class containment edges (needs class_name_to_chunk_id fully built)
    for chunk in chunks:
        if chunk.chunk_type == "method" and chunk.parent_class is not None:
            parent_id = class_name_to_chunk_id.get((chunk.file_path, chunk.parent_class))
            if parent_id:
                graph.add_edge(parent_id, chunk.chunk_id, relation=EdgeType.CONTAINS.value)
            else:
                logger.warning(
                    f"Could not find parent class chunk for method {chunk.chunk_id} "
                    f"(parent_class={chunk.parent_class})"
                )

    # Pass 3: inherits edges (class -> base class), same-file resolution only for now
    for chunk in chunks:
        if chunk.chunk_type == "class":
            for base_name in chunk.base_classes:
                base_id = class_name_to_chunk_id.get((chunk.file_path, base_name))
                if base_id:
                    graph.add_edge(chunk.chunk_id, base_id, relation=EdgeType.INHERITS.value)
                else:
                    # base class defined in a different file, or is an external class
                    # (e.g. built-in, or from an imported library) — known limitation, logged not crashed
                    logger.debug(
                        f"Could not resolve base class '{base_name}' for {chunk.chunk_id} "
                        f"(likely defined in another file or external)"
                    )

    logger.info(
        f"After adding chunks: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges"
    )
    return graph