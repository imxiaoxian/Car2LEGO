"""Exercise the real SQLite migration, including preservation and identity uniqueness."""

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest

from app.config import settings


def test_optional_year_migration_preserves_existing_cars(tmp_path, monkeypatch):
    path = tmp_path / "migration.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite+aiosqlite:///{path.as_posix()}")
    config = Config()
    config.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
    command.upgrade(config, "002")
    with sqlite3.connect(path) as db:
        db.execute("INSERT INTO cars (id,make,model,year) VALUES (?,?,?,?)", ("a"*32, "Ferrari", "F40", 1990))
    command.upgrade(config, "head")
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT make,model,year FROM cars").fetchall() == [("Ferrari", "F40", 1990)]
        db.execute("INSERT INTO cars (id,make,model,year) VALUES (?,?,?,?)", ("b"*32, "Ferrari", "F40", None))
        with pytest.raises(sqlite3.IntegrityError):
            db.execute("INSERT INTO cars (id,make,model,year) VALUES (?,?,?,?)", ("c"*32, "ferrari", "f40", None))
    with pytest.raises(ValueError, match="real model years"):
        command.downgrade(config, "002")
