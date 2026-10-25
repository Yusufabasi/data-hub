from datetime import date

import pytest

from data_hub.generate import RuleBasedGenerator
from data_hub.seed import build_database

TODAY = date(2026, 10, 24)


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "hub.db"
    build_database(path, seed=7, today=TODAY)
    return path


@pytest.fixture
def rules():
    return RuleBasedGenerator(today=TODAY)


class Scripted:
    """A generator that returns fixed SQL, standing in for a misbehaving or manipulated model."""

    def __init__(self, sql: str) -> None:
        self.sql = sql

    def generate(self, question, schema):
        return self.sql
