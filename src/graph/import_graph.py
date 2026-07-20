import ast
from pathlib import Path
import networkx as nx
from src.graph.schema import NodeType, EdgeType
from src.config.logging_config import setup_logging

logger = setup_logging(__name__)

def build_import_graph(repo_path: Path, py_files: list[Path]) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    module_to_file = _build_module_index(repo_path, py_files)

    for file_path in py_files:
        graph.add_node(str(file_path), node_type=NodeType.FILE.value)

    for file_path in py_files:
        imports = _extract_imports(file_path, repo_path)   # <-- pass repo_path now
        for imported_module in imports:
            target_file = _resolve_import(imported_module, module_to_file)
            if target_file and target_file != file_path:
                graph.add_edge(
                    str(file_path),
                    str(target_file),
                    relation=EdgeType.IMPORTS.value,
                    module_name=imported_module,
                )

    logger.info(
        f"Import graph: {graph.number_of_nodes()} files, "
        f"{graph.number_of_edges()} import edges"
    )
    return graph


def _file_to_dotted_module(file_path: Path, repo_path: Path) -> list[str]:
    """Return the dotted package path of the file's PARENT package,
    e.g. src/requests/sessions.py -> ['src', 'requests'] (used as the base
    for resolving relative imports inside sessions.py).
    """
    rel = file_path.relative_to(repo_path).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        return parts[:-1]      # __init__.py's own package IS its parent dir
    return parts[:-1]          # drop the filename itself, keep containing dirs


def _extract_imports(file_path: Path, repo_path: Path) -> list[str]:
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError, OSError) as e:
        logger.warning(f"Could not extract imports from {file_path}: {e}")
        return []

    package_parts = _file_to_dotted_module(file_path, repo_path)
    imports = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)

        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                # absolute import: from requests.models import Response
                if node.module:
                    imports.append(node.module)
            else:
                # relative import: from . import x  /  from ..models import Foo
                # node.level dots means: go up (level) packages from the
                # CURRENT file's own package, then append node.module if present
                base = package_parts[: len(package_parts) - (node.level - 1)] if node.level > 1 else package_parts
                if node.module:
                    resolved = base + node.module.split(".")
                else:
                    resolved = base
                imports.append(".".join(resolved))

    return imports

def _build_module_index(repo_path: Path, py_files: list[Path]) -> dict[str, Path]:
    """Map dotted module paths to file paths, e.g.
    'src.requests.models' -> Path('src/requests/models.py')
    Also registers the un-prefixed form since repos often import relative
    to a 'src' or package root that isn't the repo root itself.
    """
    index: dict[str, Path] = {}
    for file_path in py_files:
        rel = file_path.relative_to(repo_path).with_suffix("")
        parts = list(rel.parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if not parts:
            continue
        dotted = ".".join(parts)
        index[dotted] = file_path

        # also index without common src-layout prefixes so "requests.models"
        # resolves even if the real path is "src/requests/models.py"
        if len(parts) > 1 and parts[0] in ("src", "lib"):
            index[".".join(parts[1:])] = file_path

    return index





def _resolve_import(module_name: str, module_to_file: dict[str, Path]) -> Path | None:
    if module_name in module_to_file:
        return module_to_file[module_name]

    # try progressively shorter prefixes: "requests.models.utils" -> "requests.models" -> "requests"
    parts = module_name.split(".")
    for i in range(len(parts), 0, -1):
        candidate = ".".join(parts[:i])
        if candidate in module_to_file:
            return module_to_file[candidate]
    return None