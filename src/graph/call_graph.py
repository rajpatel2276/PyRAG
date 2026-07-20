import ast
from pathlib import Path
import networkx as nx
from src.graph.schema import EdgeType
from src.config.logging_config import setup_logging

logger = setup_logging(__name__)


def add_call_edges(graph: nx.MultiDiGraph, repo_path: Path, py_files: list[Path]) -> nx.MultiDiGraph:
    """Best-effort call graph: resolves direct function calls and self.method()
    calls. Does NOT attempt type inference for arbitrary obj.method() calls.
    """
    # index: (file_path, function_or_method_name) -> chunk_id
    # built from existing chunk nodes already in the graph
    name_index: dict[tuple[str, str], str] = {}
    class_methods: dict[tuple[str, str], str] = {}  # (file_path, "ClassName.method") -> chunk_id

    for node_id, data in graph.nodes(data=True):
        if data.get("node_type") != "chunk":
            continue
        file_path = data["file_path"]
        name = data["name"]
        if data["chunk_type"] in ("function", "module"):
            name_index[(file_path, name)] = node_id
        elif data["chunk_type"] == "method":
            class_methods[(file_path, name)] = node_id  # ambiguous if 2 classes share a method name in one file

    edges_added = 0
    for file_path in py_files:
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue  # already logged during earlier passes

        for class_node in ast.walk(tree):
            if not isinstance(class_node, ast.FunctionDef):
                continue

            caller_chunk_id = _find_enclosing_chunk_id(graph, str(file_path), class_node)
            if caller_chunk_id is None:
                continue

            for call_node in ast.walk(class_node):
                if not isinstance(call_node, ast.Call):
                    continue

                target_id = _resolve_call_target(
                    call_node, str(file_path), name_index, class_methods
                )
                if target_id and target_id != caller_chunk_id:
                    graph.add_edge(caller_chunk_id, target_id, relation=EdgeType.CALLS.value)
                    edges_added += 1

    logger.info(f"Call graph: {edges_added} best-effort call edges added")
    return graph


def _find_enclosing_chunk_id(graph: nx.MultiDiGraph, file_path: str, func_node: ast.FunctionDef) -> str | None:
    """Match an ast function node back to its chunk_id by (file_path, name, start_line).
    We rebuild this match by scanning graph nodes — acceptable cost at this scale.
    """
    for node_id, data in graph.nodes(data=True):
        if (
            data.get("node_type") == "chunk"
            and data.get("file_path") == file_path
            and data.get("name") == func_node.name
            and data.get("start_line") == func_node.lineno
        ):
            return node_id
    return None


def _resolve_call_target(
    call_node: ast.Call,
    file_path: str,
    name_index: dict[tuple[str, str], str],
    class_methods: dict[tuple[str, str], str],
) -> str | None:
    func = call_node.func

    # Case 1: direct call, e.g. helper()
    if isinstance(func, ast.Name):
        return name_index.get((file_path, func.id))

    # Case 2: self.method() or cls.method()
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        if func.value.id in ("self", "cls"):
            return class_methods.get((file_path, func.attr))
        # Case 3 (NOT attempted): obj.method() for arbitrary obj — skip, no type info
        return None

    return None