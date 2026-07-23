import numpy as np
from src.parsing.ast_parser import CodeChunk
from src.embedding.embedder import CodeEmbedder, SAFE_TOKEN_LIMIT


def make_chunk(name="foo", source="def foo(): pass", parent_class=None, docstring=None) -> CodeChunk:
    return CodeChunk(
        chunk_id=f"test::{name}",
        file_path="test.py",
        chunk_type="method" if parent_class else "function",
        name=name,
        parent_class=parent_class,
        start_line=1,
        end_line=1,
        source_code=source,
        docstring=docstring,
    )


def test_embed_returns_correct_shape():
    embedder = CodeEmbedder()
    chunks = [make_chunk(name="a"), make_chunk(name="b")]
    vectors = embedder.embed_chunks(chunks)
    assert vectors.shape == (2, 768)


def test_header_includes_parent_class():
    embedder = CodeEmbedder()
    chunk = make_chunk(name="send", parent_class="Session")
    text = embedder._text_for_embedding(chunk)
    assert "Session.send" in text


def test_oversized_chunk_falls_back_to_summary():
    embedder = CodeEmbedder()
    huge_source = "def big():\n" + ("    x = 1\n" * 5000)  # forces token count over SAFE_TOKEN_LIMIT
    chunk = make_chunk(name="big", source=huge_source)
    text = embedder._text_for_embedding(chunk)
    assert "too large to embed in full" in text
    assert huge_source not in text  # confirms we did NOT embed the full body


def test_similar_code_embeds_closer_than_unrelated_code():
    """Sanity check that the model produces meaningful (not random) vectors:
    two similar functions should be closer to each other than to something
    completely unrelated.
    """
    embedder = CodeEmbedder()
    a = make_chunk(name="add", source="def add(a, b): return a + b")
    b = make_chunk(name="sum_two", source="def sum_two(x, y): return x + y")
    c = make_chunk(name="reverse_string", source="def reverse_string(s): return s[::-1]")

    vecs = embedder.embed_chunks([a, b, c])
    sim_ab = np.dot(vecs[0], vecs[1]) / (np.linalg.norm(vecs[0]) * np.linalg.norm(vecs[1]))
    sim_ac = np.dot(vecs[0], vecs[2]) / (np.linalg.norm(vecs[0]) * np.linalg.norm(vecs[2]))
    assert sim_ab > sim_ac