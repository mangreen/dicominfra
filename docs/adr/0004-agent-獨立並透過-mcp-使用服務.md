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

## Monorepo 配置（2026-11-24 增補，同日修訂）

三個可獨立啟動的套件放在同一個 `src/` 底下，名稱加 `dicominfra_` 前綴，避免與第三方套件撞名：

```
src/dicominfra/          後端（API、worker、relay、sweeper…）
src/dicominfra_mcp/      MCP 薄轉接層（獨立進程）
src/dicominfra_agent/    獨立 Agent
docs/contracts/          共用契約（推論契約、MCP 工具 schema、計費事件）
```

- **保留 `src/` 配置：** repo 根目錄還有 `tests/`、`docs/` 等非套件目錄；`src/` 讓所有可 import 的程式碼集中一處，並確保測試跑的是「安裝後的套件」（與 Docker 映像相同），而不是誤 import 到根目錄的程式碼。
- **一個 `pyproject.toml`、一個 `uv.lock`**，各部署單元以 extras 區分依賴（例如 `agent`、`mcp`），映像只安裝自己需要的 extras。PoC 不使用 uv workspace 或多個專案，成本較低。
- **邊界以規則維持，與目錄無關：**
  - `dicominfra_mcp` 與 `dicominfra_agent` 不得 import `dicominfra`；`dicominfra_agent` 不得 import `dicominfra_mcp`（只透過 MCP 協定溝通）；`dicominfra` 不得 import 另外兩者。
  - `dicominfra_mcp` 只呼叫公開 REST API，自己定義工具的資料模型，並以契約測試對照 `docs/contracts/`。
  - 以測試檢查 import 方向（M5a、M5b 動工時加入），違反就讓 CI 失敗。
- **日後要拆成獨立專案：** 因為邊界已被測試守住，只需要搬目錄並補上自己的 `pyproject.toml`，不必改程式碼。
- CI 依路徑分工：`src/dicominfra_agent/**` 與 `src/dicominfra_mcp/**` 變動只跑各自的檢查；`docs/contracts/**` 變動全部都跑。測試目錄在第二個套件出現時再依套件分子目錄。
- 代價：三個部署單元共用一份依賴解析，版本衝突時要一起解決。

## MCP SDK 與規範版本（2026-11-24 決定）

**決定：使用官方 `mcp` Python SDK v2，精確釘住版本；伺服器以 `MCPServer` 搭配 `stateless_http=True`、`json_response=True` 運行；Agent 端使用同一個 SDK 的 `Client`。**

- **規範背景：** MCP 的 2026-07-28 修訂把協定改成無狀態：移除 `initialize` 握手與 `Mcp-Session-Id`，每個請求自成一體，任何伺服器實例都能處理。
  官方 Python SDK v2 同時支援新舊協定版本，同一個端點兩種都回應。
- **為什麼選官方 SDK：** 它支援新規範，宣告式 API 足夠簡單，沒有雲端綁定；自己實作協定的風險更高，因為規範在一年內改了兩次傳輸行為。
  社群的獨立 `fastmcp` 套件我沒有做完整評估；因為官方 SDK 已提供同等的宣告式 API，所以不多引入一層依賴。
- **已驗證（沙箱，Linux、Python 3.12、`mcp` 2.3.0）：** 無狀態加 JSON 回應的伺服器可啟動；以 2026-07-28 的標頭直接 POST 得到 `application/json` 回應且沒有 session 標頭；SDK 客戶端的 `list_tools` 與 `call_tool` 成功。
  **未驗證：** 在你的 Mac 上、與舊版協定客戶端的互通、串流進度的行為。M5a 會把這個 spike 轉成契約測試。
- **替換空間：** SDK 只出現在 `dicominfra_mcp` 的轉接層；工具本身是呼叫 REST API 的普通函式，登記在我們自己的工具註冊表。換 SDK 或協定版本只需要改轉接層。
- **對設計的影響（與先前決定一致）：** 新規範沒有伺服器主動發起的請求，SDK 在無狀態模式下遇到 elicitation 之類的呼叫會直接失敗，因此「寫入核准在服務端」的設計是對的，不能依賴 MCP 的使用者確認。
  以工具發出的明確代號（任務編號、提案編號）取代 session 狀態，也與本設計一致。
- **風險：** v2 是大幅改寫的新版本，需精確釘住版本並在升級時重跑契約測試。

## 後果

- 多一跳呼叫與兩個專案的版本需要一起管理。
- 長連線與 LLM 串流的負載由 Agent 層承擔，醫療影像服務維持短請求。
- 殘餘風險：Agent 仍可能被誘導做「允許範圍內」的錯誤操作，因此寫入工具要少、可回復，並完整稽核。
