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

## 進程與職責

同一個 codebase，以不同入口啟動多個進程（ADR 0001）。

| 進程 | 職責 | 刻意不做的事 |
|---|---|---|
| API server | 驗證 token（使用快取的 JWKS）、租戶與授權、寫入案件與 outbox（同一交易）、回答查詢、簽發預簽名上傳連結 | 不呼叫推論平台與計費服務，不直接發佈訊息，不處理影像內容 |
| Outbox relay | 以 `FOR UPDATE SKIP LOCKED` 讀取未送出的 outbox，投進 RabbitMQ 並等待 publisher confirm，成功後標記已送出 | 不含業務邏輯 |
| Worker（可水平擴展） | 消費佇列，執行去識別化、送出推論、處理結果；以條件式 `UPDATE` 轉移狀態；CPU 密集工作放進行程池 | 不直接呼叫計費服務 |
| Sweeper | 掃描逾時或卡住的案件與到期的重試，重新排入 outbox | 不直接處理案件 |
| Billing reporter | 把用量帳本中尚未送出的事件送到計費服務（ADR 0008） | 不在案件處理的關鍵路徑上 |

## 元件之間怎麼溝通

| 從 → 到 | 方式 | 同步／非同步 | 對方故障時 |
|---|---|---|---|
| 客戶端 → API server | HTTPS REST | 同步 | 回傳錯誤，客戶端重試（寫入帶冪等鍵） |
| 客戶端 → 物件儲存 | 預簽名 URL 直傳 | 同步 | 重新取得連結再傳；影像不經過 API |
| API server → Postgres | SQL 交易 | 同步 | 回傳 503；這是整個產品的單點 |
| API server → 平台身分驗證 | 以快取的 JWKS 在本地驗證 token，不逐次呼叫 | 本地 | 已有金鑰時仍可驗證；金鑰過期且取不到時拒絕請求 |
| API server → RabbitMQ | 不直接發佈，只寫 outbox | — | broker 故障不影響收件 |
| Outbox relay → RabbitMQ | AMQP，publisher confirm | 非同步 | 未確認就不標記，稍後重送 |
| RabbitMQ → Worker | AMQP 消費與 ack | 非同步 | 重試與退避，用盡後進入 DLQ |
| Worker → 內部平台（推論） | HTTPS，冪等鍵 `request_id`，逾時與斷路器 | 非同步 | 案件排隊重試，逾時由 Sweeper 處理 |
| 內部平台（推論）→ Worker | 輪詢或回呼 | 非同步 | 待 DS 確認（見契約 README） |
| Worker → 用量帳本 | 與結果同一個 Postgres 交易 | 同步 | 與案件狀態一起回滾，不會有「完成但未記帳」 |
| Billing reporter → 計費服務 | HTTPS，冪等鍵為事件 ID，逾時與斷路器 | 非同步 | 事件留在帳本，稍後重送，產品照常運作 |

## API server 與 Worker 之間的流程

```mermaid
sequenceDiagram
autonumber
participant C as 客戶端
participant A as API server
participant D as Postgres
participant O as 物件儲存
participant R as Outbox relay
participant Q as RabbitMQ
participant W as Worker
participant P as 內部平台（推論）
C->>A: 建立案件
A->>D: 新增案件，狀態為已建立
A-->>C: 預簽名上傳連結
C->>O: 直接上傳影像
C->>A: 通知上傳完成
A->>O: 確認物件存在與雜湊
A->>D: 同一交易，狀態改為已收件並寫入 outbox
A-->>C: 202 Accepted 與任務編號
R->>D: 讀取未送出的 outbox
R->>Q: 投遞並等待 publisher confirm
R->>D: 標記已送出
Q->>W: 派工去識別化
W->>D: 查 inbox 去重，條件式更新為去識別化中
W->>W: 去識別化（行程池）
W->>D: 同一交易，狀態改為待分析並寫入 outbox
Note over R,W: 下一步同樣經由 outbox 與 relay 派工
W->>P: 送出分析，附 request_id
P-->>W: 結果（輪詢或回呼，待 DS 確認）
W->>D: 同一交易，存結果、狀態改為完成、寫入用量帳本
```

重點：API server 回覆 202 時，案件已經安全地記在資料庫；之後任何一個進程當機，都能由 outbox、重試與 Sweeper 接續。

## 計費服務的流程與故障處理

計費服務是內部平台的一部分，不歸我們管。**計費不在案件處理的關鍵路徑上**：結果完成時只把用量事件寫進本地帳本，再由 Billing reporter 非同步送出（ADR 0008）。

```mermaid
sequenceDiagram
autonumber
participant L as 用量帳本（Postgres）
participant B as Billing reporter
participant S as 計費服務
Note over L: 結果完成時，用量事件與案件狀態在同一交易寫入，不呼叫計費服務
loop 週期輪詢待送出且到期的事件
B->>L: 取出一批（SKIP LOCKED）
alt 斷路器為關閉
B->>S: 送出事件，冪等鍵為事件 ID
alt 2xx 或 409 已記錄
S-->>B: 成功
B->>L: 標記已送出
else 4xx 永久拒絕
S-->>B: 拒絕
B->>L: 標記已拒絕並告警，不再重試
else 逾時、5xx 或連線失敗
S--xB: 失敗
B->>L: 增加嘗試次數，退避加抖動後重新排程
Note over B: 連續失敗達門檻就開啟斷路器
end
else 斷路器為開啟
Note over B: 冷卻期內不呼叫計費服務，之後以單筆探測
end
end
```

| 故障情境 | 行為 |
|---|---|
| 計費服務暫時不可用（逾時、5xx） | 事件留在帳本，退避重試；案件處理不受影響 |
| 長時間中斷 | 事件持續累積、不丟棄；依最舊待送事件的年齡告警；恢復後依序補送 |
| 我方送出後沒收到回應 | 以事件 ID 作冪等鍵重送，對方回 409 或成功都視為已送出 |
| 對方永久拒絕（例如租戶不存在） | 標為已拒絕並告警，由人處理，不無限重試 |
| 帳本與計費服務數字不一致 | 定期對帳，帳本為我方的事實來源 |
| 若計費服務同時負責配額檢查 | 需要業務決策，見 ADR 0008 |
