import os
from pathlib import Path

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """tests/integration/ 下的測試自動標記為 integration，避免忘記加標記。"""
    for item in items:
        if "integration" in Path(str(item.fspath)).parts:
            item.add_marker(pytest.mark.integration)


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        # 刻意使用 fail 而不是 skip：缺少真實基礎設施不能被當成測試通過
        pytest.fail(
            f"整合測試需要環境變數 {name}（範例見 .env.example，說明見 docs/adr/0003）",
            pytrace=False,
        )
    return value


@pytest.fixture
def database_url() -> str:
    return _require_env("TEST_DATABASE_URL")


@pytest.fixture
def amqp_url() -> str:
    return _require_env("TEST_AMQP_URL")
