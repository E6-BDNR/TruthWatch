#!/usr/bin/env bash
# Crea el superusuario propio, el keyspace, las tablas y los roles de Cassandra.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a

docker compose up -d --wait cassandra-1 cassandra-2 cassandra-3

cql() { docker exec -i tw-cassandra-1 cqlsh -u "$1" -p "$2" "${@:3}" 2>&1 | grep -v -E "^(Warning|Recommendation)"; }

# La primera vez entramos con el usuario por defecto, creamos admin y desactivamos el original
if ! docker exec tw-cassandra-1 cqlsh -u admin -p "$CASSANDRA_SUPERUSER_PASSWORD" -e "SELECT now() FROM system.local" &>/dev/null; then
  cql cassandra cassandra -e "CREATE ROLE admin WITH PASSWORD = '$CASSANDRA_SUPERUSER_PASSWORD' AND SUPERUSER = true AND LOGIN = true"
  cql admin "$CASSANDRA_SUPERUSER_PASSWORD" -e "ALTER ROLE cassandra WITH SUPERUSER = false AND LOGIN = false"
fi

cql admin "$CASSANDRA_SUPERUSER_PASSWORD" <<CQL
  ALTER KEYSPACE system_auth WITH replication = {'class': 'NetworkTopologyStrategy', 'dc1': 3};

  CREATE KEYSPACE IF NOT EXISTS truthwatch
    WITH replication = {'class': 'NetworkTopologyStrategy', 'dc1': 3};

  -- Métricas por tema y ventana de tiempo, partidas por día para que ninguna partición crezca sin límite
  CREATE TABLE IF NOT EXISTS truthwatch.metrics_by_topic (
    topic text, day date, window_start timestamp, source text,
    events int, zscore double,
    PRIMARY KEY ((topic, day), window_start, source)
  ) WITH CLUSTERING ORDER BY (window_start DESC, source ASC);

  -- Alertas del día, las más recientes primero
  CREATE TABLE IF NOT EXISTS truthwatch.alerts_by_day (
    day date, created_at timestamp, alert_id uuid,
    topic text, kind text, score double, evidence text,
    PRIMARY KEY (day, created_at, alert_id)
  ) WITH CLUSTERING ORDER BY (created_at DESC, alert_id ASC);

  CREATE ROLE IF NOT EXISTS spark_writer WITH LOGIN = true AND PASSWORD = '$CASSANDRA_SPARK_PASSWORD';
  CREATE ROLE IF NOT EXISTS web_reader WITH LOGIN = true AND PASSWORD = '$CASSANDRA_WEB_PASSWORD';
  GRANT SELECT ON KEYSPACE truthwatch TO spark_writer;
  GRANT MODIFY ON KEYSPACE truthwatch TO spark_writer;
  GRANT SELECT ON KEYSPACE truthwatch TO web_reader;
CQL

# Replica los usuarios en los 3 nodos
for n in 1 2 3; do docker exec tw-cassandra-$n nodetool repair system_auth &>/dev/null; done
cql admin "$CASSANDRA_SUPERUSER_PASSWORD" -e "LIST ROLES"
