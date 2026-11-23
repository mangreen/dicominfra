"""真實 RabbitMQ 的冒煙測試：確認 broker 支援 quorum queue，並能完成一次投遞與確認。"""

import uuid

import aio_pika


async def test_quorum_queue_publish_and_consume_roundtrip(amqp_url: str) -> None:
    queue_name = f"smoke.{uuid.uuid4().hex}"
    connection = await aio_pika.connect_robust(amqp_url)
    async with connection:
        channel = await connection.channel()
        queue = await channel.declare_queue(
            queue_name, durable=True, arguments={"x-queue-type": "quorum"}
        )
        try:
            await channel.default_exchange.publish(
                aio_pika.Message(body=b"hello", message_id="msg-1", delivery_mode=2),
                routing_key=queue_name,
            )
            incoming = await queue.get(timeout=10)
            async with incoming.process():
                assert incoming.body == b"hello"
                assert incoming.message_id == "msg-1"
        finally:
            # quorum queue 不支援 if-unused / if-empty 旗標，必須明確關閉
            await queue.delete(if_unused=False, if_empty=False)
