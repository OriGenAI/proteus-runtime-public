import json
import typing
from contextlib import asynccontextmanager

from asyncio_mqtt import Client

if typing.TYPE_CHECKING:
    from . import Proteus


class ProteusPubSub:
    def __init__(self, proteus: "Proteus"):
        self.proteus = proteus

    @asynccontextmanager
    async def connect(self, token):
        client = Client(
            hostname=self.proteus.config.mqtt_broker_url,
            port=self.proteus.config.mqtt_broker_port,
            username=self.proteus.config.mqtt_id if self.proteus.config.mqtt_id else self.proteus.config.username,
            password=token,
        )
        try:
            await client.connect()
            self.proteus.logger.info("MQTT connected")
            yield ProteusPubSubContext(client)
        except Exception as e:
            self.proteus.logger.error(f"Error connecting MQTT: {e}")
        finally:
            await client.disconnect()


class ProteusPubSubContext:
    def __init__(self, client):
        self.client = client

    async def subscribe(self, topics, callback=None):
        async with self.client.filtered_messages(topics) as messages:
            await self.client.subscribe(topics)
            async for message in messages:
                if callback:
                    await callback(message)

    async def send(self, topic, msg):
        await self.client.publish(topic, json.dumps(msg))

    async def disconnect(self):
        await self.client.disconnect()
