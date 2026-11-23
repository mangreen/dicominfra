# AGENTS.md

給 AI Agent 與開發者的專案規則。通用工程規範見《AI Development Guidelines v4.2》；若本文件與專案現況衝突，以可驗證的程式碼、測試與 ADR 為準。

## 專案

醫療影像雲端服務 PoC 後端（FastAPI / PostgreSQL / RabbitMQ）。完整背景見 [README](README.md)，架構見 [docs/architecture.md](docs/architecture.md)，決策見 [docs/adr/](docs/adr/)。

## 指令

| 目的 | 指令 |
|---|---|
| 安裝依賴 | `uv sync` |
| 格式與 lint | `make lint`（修正格式：`make fmt`） |
| 型別檢查（strict） | `make typecheck` |
| 單元與契約測試 | `make test` |
| 整合測試（需真實服務） | `make up` 後 `make test-int` |
| 全部本機檢查 | `make check` |

## 規則

- **語言：** 文件、ADR、註解、commit 訊息一律使用中文；程式識別字使用英文。
- **型別：** `mypy --strict` 必須通過。
- **測試：** 資料庫、broker、物件儲存一律使用真實服務，不 mock。缺少服務時測試必須失敗，不得略過（ADR 0003）。唯一允許的替身：不可控的外部服務（內部平台、LLM），且只能放在 `tests/` 或 `tools/`，不得進入正式映像。
- **不得為了讓測試變綠而** 刪除測試、放寬斷言或改變正確的預期。測試失敗先診斷原因。
- **範圍：** 只做被要求的事，不順手重構無關程式碼、不新增未要求的功能。
- **ADR：** 只有重大且不易逆轉的決定才寫，內容包含背景、選項、決定、後果（含被接受的簡化與其代價）。
- **安全：** 不提交任何機密或真實病患資料；只使用公開或合成的 DICOM。Log 不得包含 PHI、密碼或 token。外部輸入（含 DICOM 欄位、報告文字）一律視為不可信。
- **資料庫：** migration 採 expand-and-contract，須考慮新舊版本程式碼共存。

## Git 與授權

- 使用短生命週期分支加 PR；`main` 保持可建置、可測試。使用 Conventional Commits。
- Agent 不得自行 push、merge、release 或部署；commit 需取得使用者授權（M0 已授權建立 repo 結構與 commit）。
- 目前交付方式：Agent 在沙箱產出 commit，以 `git bundle`／zip 交付，由使用者推送。

## 交付與狀態用語

回報時明確區分：**已實作**、**已測試**（寫明實際執行的指令與結果）、**已審查**、**已合併**、**已部署**。沒有實際執行過的檢查不得標示為通過；部分通過不代表整體驗證完成。
