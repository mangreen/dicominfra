# 正式映像：只含執行所需的依賴，以非 root 使用者執行。
FROM python:3.12-slim

ARG UV_VERSION=0.11.32
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

RUN pip install --no-cache-dir "uv==${UV_VERSION}"

WORKDIR /app

# 先安裝依賴（利用層快取），再複製原始碼
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

RUN useradd --system --uid 10001 --no-create-home app
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]

CMD ["uvicorn", "dicominfra.main:app", "--host", "0.0.0.0", "--port", "8000"]
