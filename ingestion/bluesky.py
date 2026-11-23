import json

from websockets.sync.client import connect

from common import forever, last_events, publish

URL = "wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post"


def run():
    # Retoma desde el time_us del último evento publicado; Jetstream reenvía lo que falte
    cursor = max((e["time_us"] for e in last_events("bluesky")), default=None)
    with connect(URL + (f"&cursor={cursor}" if cursor else "")) as ws:
        for raw in ws:
            e = json.loads(raw)
            c = e.get("commit")
            if c:  # las versiones de un post comparten partición, así el borrado llega después de la creación
                publish("bluesky", f"{e['did']}/{c['rkey']}/{c['rev']}", e, key=f"{e['did']}/{c['rkey']}")
            else:
                publish("bluesky", f"{e['did']}/{e['kind']}/{e['time_us']}", e)


forever("bluesky", run)
