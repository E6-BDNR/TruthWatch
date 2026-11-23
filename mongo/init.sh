#!/usr/bin/env bash
# Levanta e inicializa el clúster: replica sets, shards, colecciones y usuarios.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

[ -f mongo/keyfile ] || { openssl rand -base64 756 > mongo/keyfile; chmod 400 mongo/keyfile; }
docker compose up -d

mongo() { docker exec -i "${@:3}" "tw-mongo-$1" mongosh --quiet --eval "$2"; }

wait_for() {
  for _ in {1..90}; do mongo "$1" "$2" 2>/dev/null | grep -q true && return; sleep 2; done
  echo "tw-mongo-$1 no respondió en 3 minutos" >&2; exit 1
}

# rs_init <set> <configsvr> <nodos...>
rs_init() {
  local set=$1 cfg=$2 i=0 members=""; shift 2
  # El primer nodo tiene prioridad para ser primario
  for n in "$@"; do members+="{_id:$i,host:'mongo-$n:27017',priority:$((i++ ? 1 : 2))},"; done
  wait_for "$1" "db.adminCommand('ping').ok == 1"
  mongo "$1" "try { rs.initiate({_id:'$set', configsvr:$cfg, members:[$members]}) } catch {}"
  wait_for "$1" "db.hello().isWritablePrimary"
}

rs_init cfg true cfg-1 cfg-2 cfg-3
rs_init s1 false s1-1 s1-2 s1-3
rs_init s2 false s2-1 s2-2 s2-3

# Admin local en cada shard para cerrar la excepción de localhost
create_admin="try { db.getSiblingDB('admin').createUser({user: process.env.MONGO_ROOT_USER, pwd: process.env.MONGO_ROOT_PASSWORD, roles: ['root']}) } catch {}"
for n in s1-1 s2-1 router; do
  wait_for "$n" "db.adminCommand('ping').ok == 1"
  mongo "$n" "$create_admin" -e MONGO_ROOT_USER -e MONGO_ROOT_PASSWORD
done

docker exec -i -e MONGO_INGESTOR_PASSWORD -e MONGO_SPARK_PASSWORD -e MONGO_ANALYST_PASSWORD tw-mongo-router \
  mongosh --quiet -u "$MONGO_ROOT_USER" -p "$MONGO_ROOT_PASSWORD" --authenticationDatabase admin --eval "$(cat mongo/setup.js)"
