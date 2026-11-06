"""Shared fixtures: the dbt rule warehouse is built once per test session."""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import build_warehouse  # noqa: E402


@pytest.fixture(scope="session")
def built_warehouse(tmp_path_factory):
    db = tmp_path_factory.mktemp("warehouse") / "tariff.duckdb"
    return db, build_warehouse.build(db)
