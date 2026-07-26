from __future__ import annotations

import os
from pathlib import Path

import pytest

from autumn_ledger.database import Database
from autumn_ledger.paths import AppPaths
from autumn_ledger.repository import ApplicationRepository
from autumn_ledger.services import ApplicationService

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def app_paths(tmp_path: Path) -> AppPaths:
    paths = AppPaths.from_root(tmp_path / "app-data")
    paths.ensure_directories()
    return paths


@pytest.fixture
def database(app_paths: AppPaths) -> Database:
    db = Database(app_paths.database_path)
    db.initialize()
    yield db
    db.close()


@pytest.fixture
def repository(database: Database) -> ApplicationRepository:
    return ApplicationRepository(database)


@pytest.fixture
def service(repository: ApplicationRepository) -> ApplicationService:
    return ApplicationService(repository)

