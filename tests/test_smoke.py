from __future__ import annotations

import shutil

import infra_agent


def test_version():
    assert infra_agent.__version__ == "0.1.0"


def test_toolchain_present():
    assert shutil.which("terraform") is not None
    assert shutil.which("opa") is not None
    assert shutil.which("git") is not None
