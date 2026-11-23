#!/usr/bin/env bash
# Apaga los consumidores de Bluesky y Wikimedia N segundos y muestra, minuto a minuto según
# la hora de cada evento, que lo ocurrido mientras estaban apagados también llegó a MongoDB.
#   ./tests/cursor.sh 120
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
pause=${1:-120}

stop=$(date -u +%FT%TZ)
docker compose stop bluesky wikimedia >/dev/null
echo "consumidores apagados de $stop"
sleep "$pause"
docker compose start bluesky wikimedia >/dev/null
start=$(date -u +%FT%TZ)
echo "a $start; esperando a que se pongan al día"
sleep 120

docker exec tw-mongo-router mongosh --quiet -u "$MONGO_ROOT_USER" -p "$MONGO_ROOT_PASSWORD" --authenticationDatabase admin --eval "
const raw = db.getSiblingDB('raw')
const minute = (d) => new Date(Math.floor(d / 60000) * 60000)
const stop = new Date('$stop'), start = new Date('$start')
const from = minute(stop - 3 * 60000), to = minute(start.getTime() + 2 * 60000)
const perMinute = (c, time) => Object.fromEntries(raw[c].aggregate([
  { \$match: { received_at: { \$gte: new Date(from - 5 * 60000) } } },
  { \$set: { t: time } },
  { \$match: { t: { \$gte: from, \$lt: to } } },
  { \$group: { _id: { \$dateTrunc: { date: '\$t', unit: 'minute' } }, n: { \$sum: 1 } } },
]).toArray().map((x) => [x._id.toISOString().slice(11, 16), x.n]))
const b = perMinute('bluesky', { \$toDate: { \$divide: ['\$data.time_us', 1000] } })
const w = perMinute('wikimedia', { \$dateFromString: { dateString: '\$data.meta.dt' } })
print('minuto (UTC)  bluesky  wikimedia')
for (let t = from; t < to; t = new Date(t.getTime() + 60000)) {
  const m = t.toISOString().slice(11, 16)
  const off = t.getTime() + 60000 > stop && t < start ? '  <- apagados' : ''
  print(m.padEnd(14) + String(b[m] ?? 0).padStart(7) + String(w[m] ?? 0).padStart(11) + off)
}"
