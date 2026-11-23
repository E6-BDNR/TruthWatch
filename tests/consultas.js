// Latencia de consultas puntuales sobre la capa de ingesta.
// docker exec tw-mongo-router mongosh -u admin -p ... --authenticationDatabase admin --eval "$(cat tests/consultas.js)"
const raw = db.getSiblingDB('raw')
const latest = (c) => raw[c].find().sort({ received_at: -1 }).limit(1).next()
const [gdelt, wiki, bsky] = ['gdelt', 'wikimedia', 'bluesky'].map(latest)

// Un post reciente que su autor creó y después borró. Sus versiones comparten el prefijo did/rkey/
const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
const borrado = raw.bluesky.find({ 'data.commit.operation': 'delete' }).sort({ received_at: -1 }).limit(500).toArray()
  .map((d) => new RegExp('^' + escape(`${d.data.did}/${d.data.commit.rkey}/`)))
  .find((post) => raw.bluesky.countDocuments({ _id: post }) > 1)

const consultas = {
  'Evento de GDELT por id': () => raw.gdelt.find({ _id: gdelt._id }),
  'Última edición de una página de Wikipedia': () =>
    raw.wikimedia.find({ 'data.title': wiki.data.title }).sort({ received_at: -1 }).limit(1),
  'Últimos 10 posts de una cuenta de Bluesky': () =>
    raw.bluesky.find({ 'data.did': bsky.data.did }).sort({ received_at: -1 }).limit(10),
  'Estado actual de un post de Bluesky': () => raw.bluesky.find({ _id: borrado }).sort({ _id: -1 }),
}

for (const [nombre, q] of Object.entries(consultas)) {
  q().toArray() // calienta la caché
  const ini = Date.now()
  const docs = q().toArray()
  const ms = Date.now() - ini
  const e = q().explain('executionStats')
  print(`${nombre}: ${ms} ms, ${docs.length} docs, ${e.executionStats.totalDocsExamined} revisados, ${e.queryPlanner.winningPlan.shards.length} shard(s)`)
}

print('\nVersiones del post borrado (la más reciente primero):')
consultas['Estado actual de un post de Bluesky']().forEach((d) =>
  print(`  ${d.data.commit.operation.padEnd(7)} ${d.received_at.toISOString()}  texto: ${d.data.commit.record ? 'sí' : 'no'}`))
