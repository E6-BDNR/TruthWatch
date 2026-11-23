import csv
import io
import time
import zipfile

import requests

from common import forever, publish

LAST_UPDATE = "http://data.gdeltproject.org/gdeltv2/lastupdate.txt"

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

last_file = None


def run():
    """GDELT publica un archivo nuevo cada 15 minutos; revisamos cada minuto."""
    global last_file
    while True:
        url = requests.get(LAST_UPDATE, timeout=30).text.split()[2]  # primera línea: eventos
        if url != last_file:
            z = zipfile.ZipFile(io.BytesIO(requests.get(url, timeout=120).content))
            text = z.read(z.namelist()[0]).decode("utf-8", "replace")
            for row in csv.reader(io.StringIO(text), delimiter="\t"):
                publish("gdelt", row[0], dict(zip(COLUMNS, row)))
            last_file = url
        time.sleep(60)


forever("gdelt", run)
