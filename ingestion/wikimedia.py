import json

import requests

from common import forever, publish

URL = "https://stream.wikimedia.org/v2/stream/recentchange"
HEADERS = {"User-Agent": "TruthWatch/1.0 (proyecto escolar)", "Accept": "text/event-stream"}
last_id = None  # Last-Event-ID de SSE, para retomar sin huecos


def run():
    global last_id
    headers = HEADERS | ({"Last-Event-ID": last_id} if last_id else {})
    with requests.get(URL, headers=headers, stream=True, timeout=(10, 60)) as r:
        r.raise_for_status()
        event_id = last_id
        for line in r.iter_lines(decode_unicode=True):
            if line.startswith("id: "):
                event_id = line[4:]
            elif line.startswith("data: "):
                e = json.loads(line[6:])
                if e["meta"]["domain"] != "canary":  # eventos de monitoreo de Wikimedia
                    publish("wikimedia", e["meta"]["id"], e)
                last_id = event_id


forever("wikimedia", run)
