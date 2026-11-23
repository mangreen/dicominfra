# 架構與流程

本文件描述 PoC 的目標架構。M0 只實作其中的骨架（見 README 的里程碑），其餘為設計。決策與取捨見 [docs/adr/](adr/)。

## 元件

```mermaid
flowchart LR
subgraph AG["獨立 Agent（自成一個專案，ADR 0004）"]
L["Agent loop（自寫）"] --> M1["LLM 模式"]
L --> M2["規則／狀態機模式（離線降級）"]
end
subgraph SV["醫療影像雲端服務（本 repo）"]
MCP["MCP server（薄轉接層）"] --> API["REST API"]
API --> DB[("Postgres＋RLS")]
API --> OBJ[("物件儲存")]
DB --> MQ{{"RabbitMQ"}}
MQ --> W["Worker"]
W --> P["內部平台（PoC 用假的）"]
W --> DB
end
AG -- "MCP 協定＋使用者授權" --> MCP
U["使用者／其他系統"] --> API
```

- **事實來源是 Postgres**：案件狀態、待送訊息（outbox）、重試記帳、用量事件都在資料庫（ADR 0002）。
- **MCP server 沒有資料庫權限**，只呼叫公開的 REST API（ADR 0004）。
- 內部平台（身分、推論、計費）在 PoC 中由可注入故障的假服務取代，只存在於測試與開發環境。

## 案件狀態

```mermaid
stateDiagram-v2
state "已收件" as S1
state "去識別化中" as S2
state "已送出分析" as S3
state "完成" as S4
state "失敗" as S5
state "逾時" as S6
[*] --> S1
S1 --> S2: 工人接手
S2 --> S3: 去識別化完成
S3 --> S4: 收到結果
S3 --> S6: 等太久
S3 --> S5: 重試用完
S6 --> S3: 重新送出
S5 --> S3: 人工重送
S4 --> [*]
```

狀態轉移以條件式 `UPDATE ... WHERE status = ...` 完成，避免更新被覆蓋；重複的轉移請求不會產生第二次副作用。

## 一張影像的流程

```mermaid
sequenceDiagram
autonumber
participant U as 使用者／Agent
participant A as API
participant D as 資料庫＋物件儲存
participant Q as RabbitMQ
participant W as Worker
participant P as 內部平台
U->>A: 上傳影像
A->>D: 存檔，狀態為已收件，並寫下待送訊息
A-->>U: 回傳任務編號，不必等分析
D->>Q: 轉送程序把待送訊息投進佇列
Q->>W: 派工
W->>W: 去識別化
W->>P: 送出分析，附上冪等鍵 request_id
P-->>W: 回傳結果
W->>D: 存結果、產生報告數字、記錄用量
U->>A: 用任務編號查詢
A-->>U: 回傳狀態與報告
```

## 可靠性原則

- 訊息 at-least-once，消費端冪等；不宣稱 exactly-once。
- 對外部平台：逐層逾時（下游期限比上游短）、有限次數退避重試加抖動、斷路器、並發上限；收件不依賴平台。
- 非同步工作有逾時掃描器（`FOR UPDATE SKIP LOCKED`），重試用完進入 DLQ 並可重播。
- 租戶隔離：應用層授權為第一道，Postgres RLS（`FORCE ROW LEVEL SECURITY`、非 owner 角色）為最後防線。
