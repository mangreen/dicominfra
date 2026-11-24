# ADR 0004：Agent 獨立專案，透過 MCP 使用服務

- 狀態：已接受（2026-11-24，經使用者確認）；同日增補：Agent 採 monorepo、連線模式修訂
- 範圍：Agent 與醫療影像服務之間的邊界

## 背景

使用者除了 API 之外，也希望透過 Agent 取得服務。Agent 與服務的演進速度與風險不同，
且服務不應該信任 Agent。

## 決定

1. **方向：** Agent 不內建於服務，是獨立專案，只透過 MCP 與服務互動。
2. **MCP server 為薄轉接層**，獨立進程，沒有資料庫權限，只呼叫公開的 REST API，因此 Agent 與一般客戶端走同一條授權與租戶隔離路徑。
3. **Token：** 依 MCP 授權規範，MCP server 只接受發給自己的 token，且不得把收到的 token 轉傳給上游 API；
   呼叫 API 時使用另一組憑證，並標明代表的使用者。
4. **寫入核准在服務端：** 「重送」這類改資料的動作，由 MCP 建立提案，使用者本人以自己的身分在服務端核准。
   核准不依賴 Agent 或 MCP 客戶端，因此 Agent 被誘導也無法替使用者核准。
5. **連線：三段都採同一種模式，HTTP POST，回應為 JSON 或事件串流（SSE 格式）。** 這與 MCP 的 Streamable HTTP 是同一種做法；SSE 是串流回應的格式，不是另一種傳輸。
   - 使用者到 Agent：每則訊息一個 POST，回應為事件串流（LLM 輸出與進度），回答結束就關閉，**不維持閒置的長連線**。
     瀏覽器的 `EventSource` 只能用 GET、無法帶自訂標頭，因此改用 `fetch` 讀取串流。使用者中止就關閉連線，Agent 隨即取消對 LLM 的呼叫。
   - Agent 到 MCP：一般 POST，回 JSON；只有工具需要串流進度時才回事件串流。
   - MCP 到 API：短請求。
   - 長時間分析回傳任務編號，由 Agent 輪詢，不佔用連線。
   - 不做串流續接（`Last-Event-ID`）：中斷時，客戶端以訊息 ID 向 Agent 取回已完成的回答。
6. **Agent loop 自行撰寫**，LLM 供應商以兩個 adapter 涵蓋（Anthropic 原生、OpenAI 相容），離線時降級為規則／狀態機模式。
7. 工具輸出一律視為不可信資料，只回傳已去識別化的欄位，並限制長度。

## Monorepo 配置（2026-11-24 增補）

Agent 與服務放在同一個 repo，但邊界以規則維持：

```
src/dicominfra/    後端（API、worker、relay、sweeper…）
mcp_server/        MCP 薄轉接層（獨立進程）：只能使用公開 REST API 的 client 與契約，不得 import 後端的資料庫或業務模組
agent/             獨立 Agent 專案：自己的 pyproject 與測試，只透過 MCP 與服務互動，不得 import dicominfra
docs/contracts/    共用契約（推論契約、MCP 工具 schema、計費事件）
```

- 以測試檢查 import 方向（M5a、M5b 動工時加入），違反就讓 CI 失敗。
- CI 依路徑分工：`agent/**` 變動執行 agent 的檢查；`docs/contracts/**` 變動兩邊都執行。
- 實際的 pyproject 與依賴鎖定方式（uv workspace 或各自鎖定）在 M5a、M5b 動工時決定；現在只定邊界規則。

## MCP 規範版本

MCP 的 Streamable HTTP 在 2026-07-28 的修訂中移除了 GET 串流端點與協定層的 session，並且不支援串流續接；
較早的修訂（2025-03-26 到 2025-11-25）則有這些功能。因此 MCP 層只作為工具註冊表外的薄轉接，
SDK 支援的協定版本在 M5a 前確認（見 `docs/assumptions.md` 的 E1），協定改變時只換轉接層。

## 後果

- 多一跳呼叫與兩個專案的版本需要一起管理。
- 長連線與 LLM 串流的負載由 Agent 層承擔，醫療影像服務維持短請求。
- 殘餘風險：Agent 仍可能被誘導做「允許範圍內」的錯誤操作，因此寫入工具要少、可回復，並完整稽核。
