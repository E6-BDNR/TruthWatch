import threading
import time

import requests

from common import forever, last_events, publish

# Instancias grandes con el timeline federado abierto. Un mismo post puede
# llegar por varias; se deduplica por su uri al guardarlo.
INSTANCES = ["mas.to", "mastodon.world", "social.vivaldi.net", "universeodon.com"]


def poll(instance):
    url = f"https://{instance}/api/v1/timelines/public"
    # id del último post publicado de esta instancia, para pedir solo los nuevos
    seen = [e["status"]["id"] for e in last_events("mastodon", 200) if e["instance"] == instance]
    since = max(seen, key=int, default=None)
    while True:
        r = requests.get(url, params={"limit": 40, "min_id": since}, timeout=15)
        r.raise_for_status()  # p. ej. 429 si excedemos el límite de la instancia
        posts = r.json()
        for p in posts:
            publish("mastodon", f"{p['uri']}@{p['edited_at'] or p['created_at']}", {"instance": instance, "status": p})
        if posts:
            since = max((p["id"] for p in posts), key=int)
        if len(posts) < 40:
            time.sleep(5)


for instance in INSTANCES:
    threading.Thread(target=forever, args=(f"mastodon {instance}", lambda i=instance: poll(i))).start()
