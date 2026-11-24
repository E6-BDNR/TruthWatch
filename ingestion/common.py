import json
import logging
import time
from datetime import datetime, timezone
from functools import cache

from confluent_kafka import Consumer, Producer, TopicPartition

KAFKA = "kafka-1:9092,kafka-2:9092,kafka-3:9092"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s | %(message)s", datefmt="%H:%M:%S")


@cache
def producer():
    return Producer({
        "bootstrap.servers": KAFKA,
        "enable.idempotence": True,  # acks=all y sin duplicados por reintentos
        "compression.type": "lz4",
        "linger.ms": 50,
    })


stats = {"count": 0, "since": time.time()}


def publish(source, event_id, data, key=None):
    """Envuelve el evento crudo y lo manda al tópico de su fuente. Los eventos con la
    misma llave caen en la misma partición y se leen en orden (por omisión, el _id)."""
    msg = {
        "_id": event_id,
        "source": source,
        "received_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    producer().produce(source, key=key or event_id, value=json.dumps(msg))
    producer().poll(0)

    stats["count"] += 1
    elapsed = time.time() - stats["since"]
    if elapsed >= 60:
        logging.getLogger(source).info("%.1f eventos/s", stats["count"] / elapsed)
        stats.update(count=0, since=time.time())


def last_events(topic, n=1):
    """Los últimos n eventos de cada partición del tópico. Kafka funciona como cursor:
    al reiniciar, cada consumidor retoma desde lo último que alcanzó a publicar."""
    c = Consumer({"bootstrap.servers": KAFKA, "group.id": "cursores", "enable.auto.commit": False})
    parts, pending = [], 0
    for p in c.list_topics(topic, timeout=10).topics[topic].partitions:
        lo, hi = c.get_watermark_offsets(TopicPartition(topic, p), timeout=10)
        parts.append(TopicPartition(topic, p, max(lo, hi - n)))
        pending += hi - max(lo, hi - n)
    c.assign(parts)
    events = []
    while len(events) < pending and (msgs := c.consume(pending - len(events), timeout=10)):
        events += [json.loads(m.value())["data"] for m in msgs if not m.error()]
    c.close()
    return events


def forever(source, run):
    """Corre `run` y lo reinicia con espera exponencial si la conexión se cae."""
    log = logging.getLogger(source)
    wait = 1
    while True:
        start = time.time()
        try:
            log.info("conectando")
            run()
        except Exception as e:
            log.warning("conexión perdida: %s", e)
        wait = 1 if time.time() - start > 60 else min(wait * 2, 60)
        producer().flush(10)
        time.sleep(wait)
