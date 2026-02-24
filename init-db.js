// init-db.js
db = db.getSiblingDB('liveclinic');

db.createUser({
  user: "clinic_admin",
  pwd: "p@ssw0rd_db_user",
  roles: [{ role: "readWrite", db: "liveclinic" }]
});

db.createCollection('users');
