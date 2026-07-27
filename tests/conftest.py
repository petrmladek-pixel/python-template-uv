import os
from collections.abc import Iterator

os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

from python_template_uv.database import engine
from python_template_uv.dependencies import get_analysis_service
from python_template_uv.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    SQLModel.metadata.drop_all(engine)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(engine)


@pytest.fixture
def override_analysis_service():
    def override(service: object) -> None:
        app.dependency_overrides[get_analysis_service] = lambda: service

    return override
