import threading
import time

import requests

from common import forever, publish

# Instancias grandes con el timeline federado abierto. Un mismo post puede
# llegar por varias; se deduplica por su uri al guardarlo.
INSTANCES = ["mas.to", "mastodon.world", "social.vivaldi.net", "universeodon.com"]


def poll(instance):
    url = f"https://{instance}/api/v1/timelines/public"
    since = None  # id del último post visto, para pedir solo los nuevos
    while True:
        posts = requests.get(url, params={"limit": 40, "min_id": since}, timeout=15).json()
        for p in posts:
            publish("mastodon", f"{p['uri']}@{p['edited_at'] or p['created_at']}", {"instance": instance, "status": p})
        if posts:
            since = max((p["id"] for p in posts), key=int)
        if len(posts) < 40:
            time.sleep(5)


for instance in INSTANCES:
    threading.Thread(target=forever, args=(f"mastodon {instance}", lambda i=instance: poll(i))).start()
