# ADR 0002：訊息佇列選用 RabbitMQ，Postgres 為事實來源

- 狀態：已接受（2026-11-23）
- 範圍：非同步影像流程的訊息傳遞

## 背景

流程需要逐則確認、有限次數的退避重試、死信佇列（DLQ）與逾時處理。
沒有 GCP 預算，先在本機運行；職缺提到地端部署的可能性。

## 選項

| | Pub/Sub emulator | RabbitMQ | NATS JetStream | Kafka |
|---|---|---|---|---|
| 優點 | 與雲端 API 一致 | 成熟；quorum queue 搭配投遞上限與 dead-letter exchange 原生支援 DLQ；可攜到地端 | 極輕量；原生 ack-wait、max-deliver、backoff | 高吞吐、可重播 |
| 缺點 | 地端無法使用；emulator 保真度有限且資料來源不一致，需實測 | 延遲重試要靠 TTL 加 DLX 組合 | 無原生 DLQ topic，要自建 | offset 型，無逐則重試，單一毒訊息會卡住分區；營運重；託管版要付費 |

## 決定

使用 **RabbitMQ（quorum queue）**。不採用 Kafka：工作負載是任務佇列而非事件串流，用不到重播與高吞吐。
重新考慮 Kafka 的條件：需要事件重播、多個獨立消費者，或影像事件串流分析。

1. **Postgres 是事實來源。** 案件狀態與待送訊息（outbox）在同一個交易寫入，由轉送程序投進 RabbitMQ。
2. 投遞為 **at-least-once**，消費端以 `message_id` 去重（冪等），不宣稱 exactly-once。
3. 重試次數與退避記在 Postgres，不依賴特定 broker 的功能，因此 broker 可替換。
4. 提供薄的 `MessageBus` 介面（`src/dicominfra/messaging/bus.py`）。RabbitMQ adapter 於 M3 實作；Pub/Sub adapter 為選配，不在 PoC 範圍。

## 後果

- 雲端沒有託管的 RabbitMQ，上 GCP 時需要自架或使用第三方服務。
- 延遲重試以 TTL 與 DLX 實作較繞，M3 需驗證。
- 本機開發用的 RabbitMQ 版本（Compose 使用 `rabbitmq:4-management`）可能與日後正式環境不同，版本差異需在 M3 檢查。
