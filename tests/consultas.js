// Latencia de consultas puntuales sobre la capa de ingesta.
// docker exec tw-mongo-router mongosh -u admin -p ... --authenticationDatabase admin --eval "$(cat tests/consultas.js)"
const raw = db.getSiblingDB('raw')
const latest = (c) => raw[c].find().sort({ received_at: -1 }).limit(1).next()

const [gdelt, wiki, bsky] = ['gdelt', 'wikimedia', 'bluesky'].map(latest)

const consultas = {
  'Evento de GDELT por id': () => raw.gdelt.find({ _id: gdelt._id }),
  'Última edición de una página de Wikipedia': () =>
    raw.wikimedia.find({ 'data.title': wiki.data.title }).sort({ received_at: -1 }).limit(1),
  'Últimos 10 posts de una cuenta de Bluesky': () =>
    raw.bluesky.find({ 'data.did': bsky.data.did }).sort({ received_at: -1 }).limit(10),
}

for (const [nombre, q] of Object.entries(consultas)) {
  q().toArray() // calienta la caché
  const ini = Date.now()
  const docs = q().toArray()
  const ms = Date.now() - ini
  const e = q().explain('executionStats')
  print(`${nombre}: ${ms} ms, ${docs.length} docs, ${e.executionStats.totalDocsExamined} revisados, ${e.queryPlanner.winningPlan.shards.length} shard(s)`)
}
