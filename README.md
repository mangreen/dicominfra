# dicominfra

醫療影像雲端服務 PoC 後端：收件、去識別化、送出推論、處理結果與報告數字，並提供多租戶隔離。
Agent 為**獨立專案**，只透過 MCP 使用本服務（ADR 0004）。

> 狀態：M0（基礎）已完成。尚無業務功能，只有骨架、工具鏈、真實基礎設施測試、CI 與設計文件。

## 範圍

- **要證明：** 非同步流程可靠（重試、冪等、DLQ、逾時）、租戶資料隔離、外部平台故障時產品仍可用、報告數字可重現。
- **不做：** ML 模型、真實病患資料、前端 UI、舊 TypeScript 服務、地端 K8s。
- 內部平台（身分、推論、計費）在 PoC 中以可注入故障的假服務取代，只存在於測試與開發環境。

## 快速開始

需求：Docker（含 Compose）、[uv](https://docs.astral.sh/uv/)。

```bash
cp .env.example .env     # 僅限本機的範例值
make up                  # 啟動真實的 Postgres 與 RabbitMQ
uv sync
make check               # lint + 型別 + 單元／契約測試
make test-int            # 整合測試（需要 make up）
```

`make` 會自動載入 `.env`；不透過 make 執行 pytest 時，請自行匯出 `TEST_DATABASE_URL`、`TEST_AMQP_URL`。

沒有 Docker 的環境，只要自行提供 Postgres 16 與 RabbitMQ 並設定 `TEST_DATABASE_URL`、`TEST_AMQP_URL` 即可。

## 目錄

```
src/dicominfra/        應用程式（app.py、messaging/ 介面）
tests/unit/            單元測試
tests/contract/        契約 schema 測試
tests/integration/     真實基礎設施測試
docs/adr/              架構決策記錄
docs/contracts/        與 DS 團隊的推論契約（草案）
docs/architecture.md   架構與流程圖（Mermaid）
docs/assumptions.md    假設登記表（PoC 的簡單假設與替換點）
```

## 里程碑

| 階段 | 內容 | 狀態 |
|---|---|---|
| M0 | 骨架、ADR、Compose、CI、真實基礎設施測試、契約草案 | 完成（本機與 GitHub Actions 驗證通過） |
| M1 | 租戶與身分、RLS | 未開始 |
| M2 | 收件與去識別化 | 未開始 |
| M3 | 非同步流程、重試、DLQ、逾時 | 未開始 |
| M4 | 結果契約、報告數字、用量計費 | 未開始 |
| M5a | MCP server | 未開始 |
| M5b | 獨立 Agent 專案 | 未開始 |
| M6 | 可觀測性與端到端展示 | 未開始 |

## Monorepo 規劃（ADR 0004）

M5a、M5b 動工時才會建立，現在只定邊界：

```
mcp_server/   MCP 薄轉接層，只呼叫公開 REST API
agent/        獨立 Agent 專案，只透過 MCP 使用服務
```

規則見 [AGENTS.md](AGENTS.md)。
