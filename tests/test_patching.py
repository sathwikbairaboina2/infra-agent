from __future__ import annotations

from pathlib import Path

import pytest

from infra_agent.hashing import sha256_bytes
from infra_agent.patching import (
    FileChange,
    PatchRefused,
    apply_changes,
    prepare_workdir,
    validate_changes,
)
from infra_agent.runner import SubprocessRunner

TABLE = 'resource "aws_dynamodb_table" "t" {\n  name = "t"\n}\n'


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    (r / "main.tf").write_text('resource "aws_s3_bucket" "b" {\n  bucket = "b"\n}\n')
    (r / "extra.tf").write_text("# extra\n")
    return r


def _work(tmp_path: Path, repo: Path) -> Path:
    wd = tmp_path / "work"
    prepare_workdir(repo, wd, SubprocessRunner())
    return wd


def _apply(wd: Path, changes, cap: int = 200):
    return apply_changes(wd, changes, max_changed_lines=cap, runner=SubprocessRunner())


@pytest.mark.parametrize(
    "path",
    [
        ".github/workflows/x.yml",
        "policy/infra.rego",
        "Makefile",
        "../x.tf",
        "/etc/x.tf",
        "a/b/c/d.tf",
        "x.tf.json",
        "main.tfvars",
    ],
)
def test_patch_path_allowlist(path: str):
    reasons = validate_changes([FileChange(path, "# x\n")])
    assert reasons and path in reasons[0]


@pytest.mark.parametrize("path", ["override.tf", "zz_override.tf", "mod/x_override.tf"])
def test_override_files_refused(path: str):
    reasons = validate_changes([FileChange(path, "# x\n")])
    assert any("override files are not allowed" in r for r in reasons)


@pytest.mark.parametrize(
    "content,msg",
    [
        ('resource "a" "b" {\n  provisioner "local-exec" {}\n}\n', "provisioner"),
        ('terraform {\n  backend "s3" {}\n}\n', "backend"),
        ("terraform {\n  cloud {\n  }\n}\n", "cloud"),
    ],
)
def test_forbidden_content_refused(content: str, msg: str):
    reasons = validate_changes([FileChange("main.tf", content)])
    assert any(msg in r and "main.tf" in r for r in reasons)


def test_duplicate_and_too_many_files():
    assert validate_changes([FileChange("a.tf", "#"), FileChange("a.tf", "#")])
    many = [FileChange(f"f{i}.tf", "#") for i in range(21)]
    assert validate_changes(many)


def test_from_dict_validates():
    assert FileChange.from_dict({"path": "a.tf", "content": None}).content is None
    with pytest.raises(ValueError):
        FileChange.from_dict({"path": 1, "content": "x"})
    with pytest.raises(ValueError):
        FileChange.from_dict({"path": "a.tf", "content": 3})


def test_oversize_change_refused(tmp_path: Path, repo: Path):
    wd = _work(tmp_path, repo)
    body = "".join(f"# line {i}\n" for i in range(11))
    with pytest.raises(PatchRefused) as e:
        _apply(wd, [FileChange("new.tf", body)], cap=10)
    assert "change too large: 11 lines > 10" in e.value.reasons[0]


def test_empty_change_refused(tmp_path: Path, repo: Path):
    wd = _work(tmp_path, repo)
    same = (repo / "extra.tf").read_text()
    with pytest.raises(PatchRefused) as e:
        _apply(wd, [FileChange("extra.tf", same)])
    assert e.value.reasons == ["change is empty"]


def test_happy_path_diff_and_hash(tmp_path: Path, repo: Path):
    wd = _work(tmp_path, repo)
    res = _apply(wd, [FileChange("db.tf", TABLE)])
    assert '+resource "aws_dynamodb_table"' in res.diff
    assert res.patch_sha256 == sha256_bytes(res.diff.encode())
    assert len(res.base_commit) == 40
    assert res.changed_files == ["db.tf"]
    assert res.changed_lines == 3
    assert not (repo / "db.tf").exists()
    assert (wd / "db.tf").read_text() == TABLE


def test_delete_file(tmp_path: Path, repo: Path):
    wd = _work(tmp_path, repo)
    res = _apply(wd, [FileChange("extra.tf", None)])
    assert not (wd / "extra.tf").exists()
    assert "-# extra" in res.diff


def test_delete_missing_file_refused(tmp_path: Path, repo: Path):
    wd = _work(tmp_path, repo)
    with pytest.raises(PatchRefused):
        _apply(wd, [FileChange("nope.tf", None)])


def test_prepare_skips_state_and_dot_terraform(tmp_path: Path, repo: Path):
    (repo / ".terraform").mkdir()
    (repo / ".terraform" / "x").write_text("1")
    (repo / "terraform.tfstate").write_text("{}")
    (repo / ".infra-agent").mkdir()
    wd = _work(tmp_path, repo)
    assert not (wd / ".terraform").exists()
    assert not (wd / "terraform.tfstate").exists()
    assert not (wd / ".infra-agent").exists()
    assert (wd / "main.tf").exists()
