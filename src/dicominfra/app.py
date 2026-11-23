from fastapi import FastAPI

from dicominfra import __version__


def create_app() -> FastAPI:
    """建立 FastAPI 應用。M0 只有存活檢查；就緒檢查（含資料庫）在 M1 加入。"""
    app = FastAPI(title="dicominfra", version=__version__)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app
