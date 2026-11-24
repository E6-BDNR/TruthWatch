#!/usr/bin/env bash
# Prueba de carga: manda N eventos por Kafka y comprueba que todos llegan a MongoDB.
# Con un segundo argumento provoca una falla a media prueba: mongo, router, kafka, sink o shard.
#   ./tests/carga.sh 100000 mongo
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
n=${1:-100000} falla=${2:-} run=$(date +%s)

mongo() { docker exec tw-mongo-router mongosh --quiet -u "$MONGO_ROOT_USER" -p "$MONGO_ROOT_PASSWORD" --authenticationDatabase admin --eval "$1"; }
count() { mongo "db.getSiblingDB('raw').carga.countDocuments({_id: /^carga-$run-/})" 2>/dev/null || echo 0; }

docker exec tw-kafka-1 /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka-1:9092 --create --if-not-exists --topic carga >/dev/null
docker compose run --rm --no-deps -T -v ./tests:/tests -e PYTHONPATH=/app wikimedia python /tests/carga.py "$n" "$run" &
start=$(date +%s)

# Término de elección del shard s1 si tiene primario, 0 si no
term() { docker exec tw-mongo-s1-2 mongosh --quiet -u "$MONGO_ROOT_USER" -p "$MONGO_ROOT_PASSWORD" --authenticationDatabase admin \
  --eval "const s = rs.status(); s.members.some((m) => m.stateStr == 'PRIMARY') ? Number(s.term) : 0" 2>/dev/null || echo 0; }

# Mata el proceso desde fuera, como si fallara solo: Docker lo reinicia por su política de reinicio
crash() {
  sleep 5
  local term0=$(term)
  docker run --rm --pid=host -u root truthwatch-sink sh -c "kill -9 $(docker inspect -f '{{.State.Pid}}' "$1")"
  local t=$(date +%s)
  until [ "$(docker inspect -f '{{.State.Running}}' "$1")" = true ]; do sleep 0.5; done
  echo "$1 reiniciado solo en $(( $(date +%s) - t )) s"
  if [ "$1" = tw-mongo-s1-1 ]; then
    until [ "$(term)" -gt "$term0" ]; do sleep 0.5; done
    echo "s1 eligió un nuevo primario en $(( $(date +%s) - t )) s"
  fi
}

case $falla in
  mongo) crash tw-mongo-s1-1 ;;
  router) crash tw-mongo-router ;;
  kafka) crash tw-kafka-2 ;;
  sink) crash tw-sink ;;
  shard)  # s1 sin mayoría: no puede elegir primario y deja de aceptar escrituras
    sleep 5; docker stop tw-mongo-s1-1 tw-mongo-s1-2 >/dev/null
    echo "s1 sin mayoría durante 60 s"; sleep 60
    docker start tw-mongo-s1-1 tw-mongo-s1-2 >/dev/null ;;
esac

wait %1
until [ "$(count)" -ge "$n" ] || [ $(( $(date +%s) - start )) -gt 600 ]; do sleep 2; done
total=$(( $(date +%s) - start )) got=$(count)
echo "en MongoDB: $got de $n en $total s (~$(( got / total )) eventos/s), perdidos: $(( n - got ))"

mongo "db.getSiblingDB('raw').carga.deleteMany({_id: /^carga-$run-/}).deletedCount" >/dev/null
