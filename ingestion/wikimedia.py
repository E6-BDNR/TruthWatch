import json

import requests

from common import forever, last_events, publish

URL = "https://stream.wikimedia.org/v2/stream/recentchange"
HEADERS = {"User-Agent": "TruthWatch/1.0 (proyecto escolar)", "Accept": "text/event-stream"}


def run():
    # Retoma desde la fecha del último evento publicado
    since = max((e["meta"]["dt"] for e in last_events("wikimedia")), default=None)
    with requests.get(URL, params={"since": since}, headers=HEADERS, stream=True, timeout=(10, 60)) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if line.startswith("data: "):
                e = json.loads(line[6:])
                if e["meta"]["domain"] != "canary":  # eventos de monitoreo de Wikimedia
                    publish("wikimedia", e["meta"]["id"], e)


forever("wikimedia", run)
