# app/infrastructure/messaging/rabbitmq_publisher.py

import json

import aio_pika

from app.config.settings import settings


class RabbitMQPublisher:
    def __init__(self):
        self._connection = None
        self._channel = None

    async def connect(self):
        self._connection = await aio_pika.connect_robust(settings.rabbitmq_url)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=10)

    async def publish(
        self,
        exchange_name: str,
        routing_key: str,
        message: dict,
        idempotency_key: str,
    ):

        if not self._channel:
            await self.connect()

        exchange = await self._channel.declare_exchange(
            exchange_name,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )

        msg = aio_pika.Message(
            body=json.dumps(message).encode(),
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            headers={
                "idempotency_key": idempotency_key,
            },
        )

        await exchange.publish(msg, routing_key=routing_key)
