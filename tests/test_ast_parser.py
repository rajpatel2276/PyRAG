import textwrap
from pathlib import Path
from src.parsing.ast_parser import parse_file

def write_temp_file(tmp_path: Path, content: str) -> Path:
    f = tmp_path / "sample.py"
    f.write_text(textwrap.dedent(content))
    return f

def test_parses_simple_function(tmp_path):
    f = write_temp_file(tmp_path, """
        def add(a, b):
            '''Add two numbers.'''
            return a + b
    """)
    chunks = parse_file(f)
    assert len(chunks) == 1
    assert chunks[0].chunk_type == "function"
    assert chunks[0].name == "add"
    assert chunks[0].docstring == "Add two numbers."

def test_parses_class_with_methods(tmp_path):
    f = write_temp_file(tmp_path, """
        class Foo:
            def bar(self):
                pass

            def baz(self):
                pass
    """)
    chunks = parse_file(f)
    types = {c.chunk_type for c in chunks}
    assert types == {"class", "method"}
    methods = [c for c in chunks if c.chunk_type == "method"]
    assert all(c.parent_class == "Foo" for c in methods)
    assert len(methods) == 2

def test_module_with_no_defs_becomes_module_chunk(tmp_path):
    f = write_temp_file(tmp_path, """
        __version__ = "1.0.0"
        AUTHOR = "someone"
    """)
    chunks = parse_file(f)
    assert len(chunks) == 1
    assert chunks[0].chunk_type == "module"

def test_empty_file_returns_empty_list(tmp_path):
    f = write_temp_file(tmp_path, "")
    chunks = parse_file(f)
    assert chunks == []

def test_decorators_captured(tmp_path):
    f = write_temp_file(tmp_path, """
        class Foo:
            @property
            @staticmethod
            def bar(self):
                pass
    """)
    chunks = parse_file(f)
    method = [c for c in chunks if c.chunk_type == "method"][0]
    assert method.decorators == ["@property", "@staticmethod"]

def test_duplicate_names_get_unique_chunk_ids(tmp_path):
    f = write_temp_file(tmp_path, """
        from typing import overload

        @overload
        def foo(x: int) -> int: ...
        @overload
        def foo(x: str) -> str: ...
        def foo(x):
            return x
    """)
    chunks = parse_file(f)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids)), "chunk_ids must be unique"