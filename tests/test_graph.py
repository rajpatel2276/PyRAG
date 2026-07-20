import textwrap
from pathlib import Path
import networkx as nx
from src.parsing.repo_walker import walk_repo
from src.graph.import_graph import build_import_graph
from src.graph.chunk_graph import add_chunk_nodes_and_edges
from src.parsing.repo_walker import _collect_python_files
from src.graph.call_graph import add_call_edges

def make_test_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "testrepo"
    repo.mkdir()
    (repo / "base.py").write_text(textwrap.dedent("""
        class Animal:
            def speak(self):
                pass
    """))
    (repo / "main.py").write_text(textwrap.dedent("""
        from .base import Animal

        class Dog(Animal):
            def bark(self):
                pass

            def speak(self):
                return "woof"
    """))
    return repo


def test_import_edge_created(tmp_path):
    repo = make_test_repo(tmp_path)
    py_files = _collect_python_files(repo)
    graph = build_import_graph(repo, py_files)

    main_py = str(repo / "main.py")
    base_py = str(repo / "base.py")
    assert graph.has_edge(main_py, base_py)


def test_containment_and_inheritance_edges(tmp_path):
    repo = make_test_repo(tmp_path)
    py_files = _collect_python_files(repo)
    graph = build_import_graph(repo, py_files)

    chunks, _ = walk_repo(repo)
    graph = add_chunk_nodes_and_edges(graph, chunks)

    dog_chunk = next(c for c in chunks if c.name == "Dog")
    animal_chunk = next(c for c in chunks if c.name == "Animal")
    bark_chunk = next(c for c in chunks if c.name == "bark")

    # class -> method containment
    assert graph.has_edge(dog_chunk.chunk_id, bark_chunk.chunk_id)

    # class -> base class inheritance (cross-file — should NOT resolve, known limitation)
    assert not graph.has_edge(dog_chunk.chunk_id, animal_chunk.chunk_id)


def test_same_file_inheritance_resolves(tmp_path):
    repo = tmp_path / "testrepo2"
    repo.mkdir()
    (repo / "shapes.py").write_text(textwrap.dedent("""
        class Shape:
            pass

        class Circle(Shape):
            pass
    """))
    py_files = _collect_python_files(repo)
    graph = build_import_graph(repo, py_files)
    chunks, _ = walk_repo(repo)
    graph = add_chunk_nodes_and_edges(graph, chunks)

    circle = next(c for c in chunks if c.name == "Circle")
    shape = next(c for c in chunks if c.name == "Shape")
    assert graph.has_edge(circle.chunk_id, shape.chunk_id)





def test_direct_function_call_resolved(tmp_path):
    repo = tmp_path / "testrepo3"
    repo.mkdir()
    (repo / "mod.py").write_text(textwrap.dedent("""
        def helper():
            return 1

        def main():
            return helper()
    """))
    py_files = _collect_python_files(repo)
    graph = build_import_graph(repo, py_files)
    chunks, _ = walk_repo(repo)
    graph = add_chunk_nodes_and_edges(graph, chunks)
    graph = add_call_edges(graph, repo, py_files)

    main_chunk = next(c for c in chunks if c.name == "main")
    helper_chunk = next(c for c in chunks if c.name == "helper")
    assert graph.has_edge(main_chunk.chunk_id, helper_chunk.chunk_id)


def test_self_method_call_resolved(tmp_path):
    repo = tmp_path / "testrepo4"
    repo.mkdir()
    (repo / "mod.py").write_text(textwrap.dedent("""
        class Foo:
            def a(self):
                return self.b()

            def b(self):
                return 42
    """))
    py_files = _collect_python_files(repo)
    graph = build_import_graph(repo, py_files)
    chunks, _ = walk_repo(repo)
    graph = add_chunk_nodes_and_edges(graph, chunks)
    graph = add_call_edges(graph, repo, py_files)

    a_chunk = next(c for c in chunks if c.name == "a")
    b_chunk = next(c for c in chunks if c.name == "b")
    assert graph.has_edge(a_chunk.chunk_id, b_chunk.chunk_id)


def test_dynamic_dispatch_not_falsely_resolved(tmp_path):
    """obj.method() where obj's type is unknown should NOT create an edge —
    this pins down our deliberate scope limitation."""
    repo = tmp_path / "testrepo5"
    repo.mkdir()
    (repo / "mod.py").write_text(textwrap.dedent("""
        class Handler:
            def run(self):
                pass

        def process(handler):
            return handler.run()
    """))
    py_files = _collect_python_files(repo)
    graph = build_import_graph(repo, py_files)
    chunks, _ = walk_repo(repo)
    graph = add_chunk_nodes_and_edges(graph, chunks)
    graph = add_call_edges(graph, repo, py_files)

    call_edges = [(u, v) for u, v, d in graph.edges(data=True) if d["relation"] == "calls"]
    assert len(call_edges) == 0