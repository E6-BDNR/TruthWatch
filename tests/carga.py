"""Manda N ediciones sintéticas, con la forma de las de Wikimedia, al tópico de pruebas."""
import json
import sys
import time
from datetime import datetime, timezone

from common import producer

n, run = int(sys.argv[1]), sys.argv[2]
failed = []
p = producer()
start = time.time()

for i in range(n):
    now = datetime.now(timezone.utc).isoformat()
    doc = {
        "_id": f"carga-{run}-{i}",
        "source": "carga",
        "received_at": now,
        "data": {
            "meta": {"domain": "carga.wikipedia.org", "dt": now, "id": f"{run}-{i}"},
            "type": "edit", "wiki": "cargawiki", "title": f"Página {i % 1000}", "namespace": 0,
            "user": f"usuario{i % 500}", "bot": False, "minor": False, "timestamp": int(time.time()),
            "length": {"old": 1000, "new": 1000 + i % 300}, "comment": "prueba de carga " * 10,
        },
    }
    while True:
        try:
            p.produce("carga", key=doc["_id"], value=json.dumps(doc), on_delivery=lambda err, _: err and failed.append(err))
            break
        except BufferError:  # la cola local está llena: esperar a que Kafka confirme
            p.poll(0.1)
    p.poll(0)

p.flush()
print(f"enviados {n} en {time.time() - start:.1f} s, fallidos: {len(failed)}")
