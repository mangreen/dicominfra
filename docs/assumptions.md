# 假設登記表

這是 MVP／PoC，許多外部條件尚未確定。這裡記錄 PoC 採用的簡單假設、替換點與確認狀態（原則見 [ADR 0009](adr/0009-可替換性原則.md)）。

狀態：**假設**＝PoC 先這樣做，尚未向對方確認；**待決定**＝動工前要決定；**已確認**＝對方已確認；**已替換**＝已換成真實實作。

## 推論平台與 DS

| ID | PoC 的假設 | 替換點 | 驗證 | 確認對象 | 狀態 |
|---|---|---|---|---|---|
| A1 | 結果以輪詢取得（Worker／Sweeper 用 `request_id` 查詢） | `InferenceClient`（`submit`、`get_result`）；若平台改用回呼，新增 API 端點與 adapter，狀態機不變 | Port 契約測試 | DS、平台 | 假設 |
| A2 | 同一個 `request_id` 重送，平台回傳同一個結果 | 若平台不保證，在 adapter 內先查詢再送出 | 冪等測試 | 平台 | 假設 |
| A3 | 錯誤以 `retryable` 旗標表示，錯誤碼為小型集合 | 契約 schema 版本；錯誤碼映射為設定 | schema 測試 | DS | 假設 |
| A4 | 處理時間為數秒到數分鐘，逾時為設定值 | 逾時設定 | 逾時與 Sweeper 測試 | 平台 | 假設 |
| A5 | 影像模態通用，輸出為數值測量（十進位字串加 UCUM 單位） | 契約版本；報告組裝規則依契約版本與模態註冊 | golden 測試 | DS | 假設 |

## 計費與配額

| ID | PoC 的假設 | 替換點 | 驗證 | 確認對象 | 狀態 |
|---|---|---|---|---|---|
| B1 | 事件格式由我們定義（`id`、`tenant_id`、`study_id`、`event_type`、`quantity`、`unit`、`occurred_at`），送出時以事件 ID 為冪等鍵 | `BillingClient.report(events)`；轉換為真實格式在 adapter 內 | Port 契約測試 | 平台 | 假設 |
| B2 | 接受遲到事件，依 `occurred_at` 計入週期 | adapter；若不接受，改在 reporter 依週期關帳後再送 | 計費故障測試 | 平台 | 假設 |
| B3 | 假計費服務提供彙總查詢；真實服務若沒有，對帳降級為只比對本地帳本 | `BillingClient.get_summary()` 可回傳「不支援」 | 對帳測試 | 平台 | 假設 |
| B4 | 假計費服務提供配額查詢，由 Billing reporter 同步到本地快取；上限數值為必填設定 | `QuotaProvider`；設定 | fail-open 測試（ADR 0008） | 業務 | 假設，數值待業務 |
| B5 | 不假設速率限制；批次大小、併發、退避參數皆為設定 | 設定 | 計費故障測試 | 平台 | 假設 |

## 身分與存取

| ID | PoC 的假設 | 替換點 | 驗證 | 確認對象 | 狀態 |
|---|---|---|---|---|---|
| C1 | JWT（RS256），以 JWKS 驗證；claims 含 `sub`、`tenant_id`、`scopes` | `TokenVerifier`；issuer、audience、JWKS 位址、claim 對映為設定 | 驗證測試 | 平台 | 假設 |
| C2 | MCP server 以另一組憑證呼叫 API，並帶上代表的使用者 | `UpstreamCredentialProvider` | 越權情境測試 | 平台 | 假設 |

## 儲存與影像處理

| ID | PoC 的假設 | 替換點 | 驗證 | 確認對象 | 狀態 |
|---|---|---|---|---|---|
| D1 | 物件儲存使用 S3 相容 API，本機與 CI 以 SeaweedFS 驗證（ADR 0010） | `ObjectStore`；adapter 與端點為設定 | Port 契約測試 | 團隊 | 已決定（2026-11-24） |
| D2 | 去識別化採 DICOM PS3.15 基本設定檔的子集；規則是資料（設定檔），不是硬編碼 | `DeidProfile` 設定 | 規則測試 | 法規、DS | 假設 |

## Agent 與協定

| ID | PoC 的假設 | 替換點 | 驗證 | 確認對象 | 狀態 |
|---|---|---|---|---|---|
| E1 | 使用官方 `mcp` Python SDK v2（精確釘住版本），無狀態加 JSON 回應（ADR 0004） | MCP 轉接層薄薄包住工具註冊表 | 協定契約測試（M5a） | 團隊 | 已決定（2026-11-24） |
| E2 | LLM 以兩個 adapter 涵蓋：Anthropic 原生與 OpenAI 相容 | `LLMProvider` | fake LLM 情境測試 | 團隊 | 設計 |

## 基礎設施

| ID | PoC 的假設 | 替換點 | 驗證 | 確認對象 | 狀態 |
|---|---|---|---|---|---|
| F1 | 訊息佇列為 RabbitMQ | `MessageBus`（ADR 0002） | Port 契約測試 | 團隊 | 已確認 |
