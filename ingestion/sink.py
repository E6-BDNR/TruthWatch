"""Lee los tópicos de Kafka y escribe cada evento en raw.<fuente> de MongoDB."""
import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime

from confluent_kafka import Consumer
from pymongo import MongoClient
from pymongo.errors import BulkWriteError

from common import KAFKA

SOURCES = ["bluesky", "wikimedia", "mastodon", "gdelt"]
DUPLICATE = 11000

log = logging.getLogger("sink")

consumer = Consumer({
    "bootstrap.servers": KAFKA,
    "group.id": "mongo-sink",
    "enable.auto.commit": False,  # el offset se confirma solo después de escribir en MongoDB
    "auto.offset.reset": "earliest",
})
consumer.subscribe(SOURCES)

mongo = MongoClient(f"mongodb://ingestor:{os.environ['MONGO_INGESTOR_PASSWORD']}@mongo-router:27017/?authSource=admin", w="majority")
raw = mongo.raw
saved, since = 0, time.time()

while True:
    msgs = [m for m in consumer.consume(1000, timeout=1) if not m.error()]
    if not msgs:
        continue

    batches = defaultdict(list)
    for m in msgs:
        doc = json.loads(m.value())
        doc["received_at"] = datetime.fromisoformat(doc["received_at"])
        batches[m.topic()].append(doc)

    for source, docs in batches.items():
        try:
            raw[source].insert_many(docs, ordered=False)
        except BulkWriteError as e:
            # Un _id repetido es un evento que ya teníamos: se ignora
            if any(err["code"] != DUPLICATE for err in e.details["writeErrors"]):
                raise

    consumer.commit(asynchronous=False)
    saved += len(msgs)
    if time.time() - since >= 60:
        log.info("%d eventos guardados en el último minuto", saved)
        saved, since = 0, time.time()
