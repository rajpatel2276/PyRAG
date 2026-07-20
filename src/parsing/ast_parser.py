from pathlib import Path
from dataclasses import dataclass, field
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
from src.config.logging_config import setup_logging

logger = setup_logging(__name__)

PY_LANGUAGE = Language(tspython.language())
parser = Parser(PY_LANGUAGE)


@dataclass
class CodeChunk:
    chunk_id: str       
    file_path: str
    chunk_type: str         
    name: str
    parent_class: str | None
    start_line: int
    end_line: int
    source_code: str
    docstring: str | None
    decorators: list[str] = field(default_factory=list)
    base_classes: list[str] = field(default_factory=list)


def parse_file(file_path: Path) -> list[CodeChunk]:
    try:
        source_bytes = file_path.read_bytes()
    except OSError as e:
        logger.error(f"Could not read {file_path}: {e}")
        return None

    try:
        tree = parser.parse(source_bytes)
    except Exception as e:
        logger.error(f"Tree-sitter failed to parse {file_path}: {e}")
        return None

    chunks: list[CodeChunk] = []
    _walk(tree.root_node, source_bytes, file_path, chunks, parent_class=None)

    if not chunks and len(source_bytes.strip()) > 0:
        chunks.append(_make_module_chunk(tree.root_node, source_bytes, file_path))


    return chunks


def _walk(node, source_bytes: bytes, file_path: Path, chunks: list[CodeChunk], parent_class: str | None):
    for child in node.children:
        if child.type == "class_definition":
            class_name = _get_name(child, source_bytes)
            chunks.append(_make_chunk(child, source_bytes, file_path, "class", class_name, parent_class))
            # recurse into class body to find methods, tagging them with this class as parent
            _walk(child, source_bytes, file_path, chunks, parent_class=class_name)

        elif child.type == "function_definition":
            func_name = _get_name(child, source_bytes)
            chunk_type = "method" if parent_class else "function"
            chunks.append(_make_chunk(child, source_bytes, file_path, chunk_type, func_name, parent_class))
            # don't recurse into function bodies — we don't want nested functions as separate top-level chunks yet

        else:
            _walk(child, source_bytes, file_path, chunks, parent_class)


def _get_name(node, source_bytes: bytes) -> str:
    name_node = node.child_by_field_name("name")
    return source_bytes[name_node.start_byte:name_node.end_byte].decode("utf-8")


def _get_docstring(node, source_bytes: bytes) -> str | None:
    body = node.child_by_field_name("body")
    if body is None or body.child_count == 0:
        return None
    first_stmt = body.children[0]
    if first_stmt.type == "expression_statement" and first_stmt.child_count > 0:
        expr = first_stmt.children[0]
        if expr.type == "string":
            text = source_bytes[expr.start_byte:expr.end_byte].decode("utf-8")
            return text.strip("'\" \n")
    return None


def _get_decorators(node, source_bytes: bytes) -> list[str]:
    decorators = []
    prev = node.prev_sibling
    while prev is not None and prev.type == "decorator":
        text = source_bytes[prev.start_byte:prev.end_byte].decode("utf-8")
        decorators.insert(0, text)
        prev = prev.prev_sibling
    return decorators


def _make_chunk(node, source_bytes: bytes, file_path: Path, chunk_type: str, name: str, parent_class: str | None) -> CodeChunk:
    start_line = node.start_point[0] + 1
    end_line = node.end_point[0] + 1
    source_code = source_bytes[node.start_byte:node.end_byte].decode("utf-8")
    docstring = _get_docstring(node, source_bytes)
    decorators = _get_decorators(node, source_bytes)
    base_classes = _get_base_classes(node, source_bytes) if chunk_type == "class" else []

    qualified_name = f"{parent_class}.{name}" if parent_class else name
    chunk_id = f"{file_path}::{qualified_name}::{start_line}"

    return CodeChunk(
        chunk_id=chunk_id,
        file_path=str(file_path),
        chunk_type=chunk_type,
        name=name,
        parent_class=parent_class,
        start_line=start_line,
        end_line=end_line,
        source_code=source_code,
        docstring=docstring,
        decorators=decorators,
        base_classes=base_classes,
    )

def _make_module_chunk(root_node, source_bytes: bytes, file_path: Path) -> CodeChunk:
    source_code = source_bytes.decode("utf-8", errors="replace")
    return CodeChunk(
        chunk_id=f"{file_path}::__module__",
        file_path=str(file_path),
        chunk_type="module",
        name=file_path.stem,
        parent_class=None,
        start_line=1,
        end_line=root_node.end_point[0] + 1,
        source_code=source_code,
        docstring=_get_docstring(root_node, source_bytes),
        decorators=[],
    )

def _get_base_classes(node, source_bytes: bytes) -> list[str]:
    """For a class_definition node, extract superclass names from
    class Foo(Bar, Baz): ...  ->  ['Bar', 'Baz']
    """
    superclasses_node = node.child_by_field_name("superclasses")
    if superclasses_node is None:
        return []
    bases = []
    for child in superclasses_node.children:
        if child.type == "identifier":
            bases.append(source_bytes[child.start_byte:child.end_byte].decode("utf-8"))
        elif child.type == "keyword_argument":
            continue  # skip things like metaclass=ABCMeta
        elif child.type == "attribute":
            # e.g. "requests.exceptions.RequestException" as a base — take full dotted text
            bases.append(source_bytes[child.start_byte:child.end_byte].decode("utf-8"))
    return bases