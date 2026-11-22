// Shards, colecciones e índices, roles y usuarios. Se corre en el router como admin.
const env = process.env
const sources = ['bluesky', 'wikimedia', 'mastodon', 'gdelt']

for (const s of ['s1', 's2']) {
  sh.addShard(`${s}/mongo-${s}-1:27017,mongo-${s}-2:27017,mongo-${s}-3:27017`)
}

// Una colección por fuente, repartida entre shards por hash del _id
sh.enableSharding('raw')
for (const src of sources) {
  sh.shardCollection(`raw.${src}`, { _id: 'hashed' })
  db.getSiblingDB('raw')[src].createIndex({ received_at: 1 })
}

// Mastodon no expone borrados sin cuenta: sus posts crudos se eliminan solos a los 30 días
db.getSiblingDB('raw').runCommand({
  collMod: 'mastodon',
  index: { keyPattern: { received_at: 1 }, expireAfterSeconds: 30 * 24 * 3600 },
})

// Roles y usuarios
const admin = db.getSiblingDB('admin')

if (!admin.getRole('ingesta')) {
  admin.createRole({
    role: 'ingesta',
    privileges: [{ resource: { db: 'raw', collection: '' }, actions: ['find', 'insert', 'update'] }],
    roles: [],
  })
}

const users = {
  ingestor: [env.MONGO_INGESTOR_PASSWORD, [{ role: 'ingesta', db: 'admin' }]],
  spark: [env.MONGO_SPARK_PASSWORD, [{ role: 'read', db: 'raw' }, { role: 'readWrite', db: 'curated' }]],
  analyst: [env.MONGO_ANALYST_PASSWORD, [{ role: 'read', db: 'curated' }]],
}

for (const [user, [pwd, roles]] of Object.entries(users)) {
  if (admin.getUser(user)) admin.updateUser(user, { pwd, roles })
  else admin.createUser({ user, pwd, roles })
}

print('Shards:', db.adminCommand({ listShards: 1 }).shards.map((s) => s._id).join(', '))
print('Usuarios:', admin.getUsers().users.map((u) => u.user).join(', '))
