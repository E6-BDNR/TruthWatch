"""Lee los tópicos de Kafka y escribe cada evento en raw.<fuente> de MongoDB."""
import json
import logging
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from urllib.parse import quote_plus

from confluent_kafka import Consumer
from pymongo import MongoClient, UpdateMany
from pymongo.errors import BulkWriteError

from common import KAFKA

SOURCES = ["bluesky", "wikimedia", "mastodon", "gdelt", "carga"]  # carga: tests/carga.sh
DUPLICATE = 11000

log = logging.getLogger("sink")

consumer = Consumer({
    "bootstrap.servers": KAFKA,
    "group.id": "mongo-sink",
    "enable.auto.commit": False,  # el offset se confirma solo después de escribir en MongoDB
    "auto.offset.reset": "earliest",
    "topic.metadata.refresh.interval.ms": 10000,  # detecta pronto el tópico de carga
})
consumer.subscribe(SOURCES)

password = quote_plus(os.environ["MONGO_INGESTOR_PASSWORD"])
mongo = MongoClient(f"mongodb://ingestor:{password}@mongo-router:27017/?authSource=admin", w="majority")
raw = mongo.raw
saved, since = 0, time.time()


def forget(docs):
    """Quita el texto de los posts que su autor borró y de las cuentas eliminadas o dadas de baja.
    Se conservan los metadatos (quién, cuándo) pero no el contenido."""
    no_content = {"$unset": {"data.commit.record": ""}}
    ops = []
    for d in docs:
        e, c = d["data"], d["data"].get("commit")
        if c and c["operation"] == "delete":
            post = re.escape(f"{e['did']}/{c['rkey']}/")
            ops.append(UpdateMany({"_id": {"$regex": f"^{post}"}, "data.commit.record": {"$exists": True}}, no_content))
        elif e["kind"] == "account" and e["account"].get("status") in ("deleted", "takendown"):
            ops.append(UpdateMany({"data.did": e["did"], "data.commit.record": {"$exists": True}}, no_content))
    if ops:
        raw.bluesky.bulk_write(ops, ordered=False)


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
            # Un _id repetido es un evento que ya teníamos: se ignora. Cualquier otro error,
            # o una escritura sin confirmar por la mayoría, reinicia el sink sin avanzar el offset.
            if e.details["writeConcernErrors"] or any(err["code"] != DUPLICATE for err in e.details["writeErrors"]):
                raise
        if source == "bluesky":
            forget(docs)

    consumer.commit(asynchronous=False)
    saved += len(msgs)
    if time.time() - since >= 60:
        log.info("%d eventos guardados en el último minuto", saved)
        saved, since = 0, time.time()
