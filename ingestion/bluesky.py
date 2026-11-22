import json

from websockets.sync.client import connect

from common import forever, publish

URL = "wss://jetstream2.us-east.bsky.network/subscribe?wantedCollections=app.bsky.feed.post"
cursor = None  # time_us del último evento, para retomar sin huecos


def run():
    global cursor
    with connect(URL + (f"&cursor={cursor}" if cursor else "")) as ws:
        for raw in ws:
            e = json.loads(raw)
            c = e.get("commit")
            key = f"{e['did']}/{c['rkey']}/{c['rev']}" if c else f"{e['did']}/{e['kind']}/{e['time_us']}"
            publish("bluesky", key, e)
            cursor = e["time_us"]


forever("bluesky", run)
