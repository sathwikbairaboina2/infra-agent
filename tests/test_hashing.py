from __future__ import annotations

from pathlib import Path

from infra_agent.hashing import sha256_bytes, sha256_file, sha256_tree

EMPTY = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"


def test_known_vector():
    assert sha256_bytes(b"") == EMPTY


def test_file_matches_bytes(tmp_path: Path):
    p = tmp_path / "f"
    p.write_bytes(b"hello" * 50_000)
    assert sha256_file(p) == sha256_bytes(b"hello" * 50_000)


def test_tree_order_independent(tmp_path: Path):
    a, b = tmp_path / "a", tmp_path / "b"
    for d in (a, b):
        d.mkdir()
    (a / "x.rego").write_text("1")
    (a / "y.rego").write_text("2")
    (b / "y.rego").write_text("2")
    (b / "x.rego").write_text("1")
    assert sha256_tree(a) == sha256_tree(b)


def test_tree_changes_with_content_and_name(tmp_path: Path):
    (tmp_path / "x.rego").write_text("1")
    base = sha256_tree(tmp_path)
    (tmp_path / "x.rego").write_text("2")
    changed = sha256_tree(tmp_path)
    assert changed != base
    (tmp_path / "x.rego").rename(tmp_path / "z.rego")
    assert sha256_tree(tmp_path) != changed


def test_tree_ignores_other_suffixes(tmp_path: Path):
    (tmp_path / "x.rego").write_text("1")
    base = sha256_tree(tmp_path)
    (tmp_path / "notes.txt").write_text("zzz")
    assert sha256_tree(tmp_path) == base


def test_tree_recurses_with_posix_paths(tmp_path: Path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.rego").write_text("1")
    assert sha256_tree(tmp_path) != sha256_tree(tmp_path / "sub")
