"""真實 Postgres 的冒煙測試，同時驗證併發測試的做法可行（M2、M3 的競態測試會沿用）。"""

import asyncio
import uuid
from collections.abc import AsyncIterator

import asyncpg
import pytest


async def test_server_is_postgres_16_or_newer(database_url: str) -> None:
    conn = await asyncpg.connect(database_url)
    try:
        version_num = int(await conn.fetchval("SHOW server_version_num"))
    finally:
        await conn.close()
    assert version_num >= 160000


@pytest.fixture
async def scratch_table(database_url: str) -> AsyncIterator[str]:
    table = f"scratch_{uuid.uuid4().hex}"
    conn = await asyncpg.connect(database_url)
    try:
        await conn.execute(f"CREATE TABLE {table} (k text PRIMARY KEY)")
        yield table
    finally:
        await conn.execute(f"DROP TABLE IF EXISTS {table}")
        await conn.close()


async def test_concurrent_inserts_of_same_key_only_one_wins(
    database_url: str, scratch_table: str
) -> None:
    """兩個連線同時插入同一個唯一鍵：必須恰好一個成功、一個被唯一約束擋下。"""
    barrier = asyncio.Barrier(2)

    async def attempt() -> bool:
        conn = await asyncpg.connect(database_url)
        try:
            async with conn.transaction():
                await barrier.wait()  # 讓兩個交易同時進入臨界區，不靠 sleep
                await conn.execute(f"INSERT INTO {scratch_table} (k) VALUES ('same')")
            return True
        except asyncpg.UniqueViolationError:
            return False
        finally:
            await conn.close()

    results = await asyncio.gather(attempt(), attempt())

    assert sorted(results) == [False, True]
