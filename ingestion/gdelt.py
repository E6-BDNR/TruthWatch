import csv
import io
import time
import zipfile
from datetime import datetime, timedelta

import requests

from common import forever, last_events, publish

LAST_UPDATE = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"
FILE = "http://data.gdeltproject.org/gdeltv2/{}.export.CSV.zip"
STAMP = "%Y%m%d%H%M%S"
EVERY = timedelta(minutes=15)

# Columnas de la tabla de eventos de GDELT 2.0 (el CSV no trae encabezado)
ACTOR = "Code Name CountryCode KnownGroupCode EthnicCode Religion1Code Religion2Code Type1Code Type2Code Type3Code"
GEO = "Type FullName CountryCode ADM1Code ADM2Code Lat Long FeatureID"
COLUMNS = [
    "GLOBALEVENTID", "SQLDATE", "MonthYear", "Year", "FractionDate",
    *[f"Actor1{c}" for c in ACTOR.split()],
    *[f"Actor2{c}" for c in ACTOR.split()],
    "IsRootEvent", "EventCode", "EventBaseCode", "EventRootCode", "QuadClass",
    "GoldsteinScale", "NumMentions", "NumSources", "NumArticles", "AvgTone",
    *[f"{a}Geo_{c}" for a in ("Actor1", "Actor2", "Action") for c in GEO.split()],
    "DATEADDED", "SOURCEURL",
]


def publish_file(stamp):
    r = requests.get(FILE.format(stamp), timeout=120)
    if r.status_code == 404:  # de vez en cuando GDELT no publica un lote
        return
    r.raise_for_status()
    z = zipfile.ZipFile(io.BytesIO(r.content))
    text = z.read(z.namelist()[0]).decode("utf-8", "replace")
    for row in csv.reader(io.StringIO(text), delimiter="\t"):
        publish("gdelt", row[0], dict(zip(COLUMNS, row)))


def run():
    """GDELT publica un archivo cada 15 minutos, nombrado con su fecha. Se revisa cada minuto y
    se descargan todos los que falten. Al arrancar se repite el último publicado en Kafka, por si
    quedó a medias; los eventos repetidos se descartan al guardar."""
    last = max((e["DATEADDED"] for e in last_events("gdelt")), default=None)
    t = datetime.strptime(last, STAMP) if last else None  # siguiente lote por publicar
    while True:
        newest = requests.get(LAST_UPDATE, timeout=30).text.split()[2].rsplit("/", 1)[1][:14]
        t = t or datetime.strptime(newest, STAMP)
        while t.strftime(STAMP) <= newest:
            publish_file(t.strftime(STAMP))
            t += EVERY
        time.sleep(60)


forever("gdelt", run)
