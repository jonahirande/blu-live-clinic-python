import os
import urllib.parse
import asyncio
from typing import List, Optional
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

# --- DATABASE CONFIG ---
db_user = "clinic_admin"
db_pass = "p@ssw0rd_db_user"

# FIX: URL encode the password to handle the '@' symbol
safe_pass = urllib.parse.quote_plus(db_pass)

# Force localhost 127.0.0.1 for GitHub Codespaces
MONGO_URI = f"mongodb://{db_user}:{safe_pass}@127.0.0.1:27017/liveclinic?authSource=admin"

client = AsyncIOMotorClient(MONGO_URI)
db = client.liveclinic
users_collection = db.users

# --- SEED LOGIC ---
async def seed_users():
    try:
        # Create the application user (self-healing setup)
        await db.command("createUser", db_user, 
                         pwd=db_pass, 
                         roles=[{"role": "readWrite", "db": "liveclinic"}])
        print("👤 Database user created")
    except Exception:
        print("ℹ️ User setup skipped (likely already exists)")

    # Ensure 'users' collection exists
    collections = await db.list_collection_names()
    if 'users' not in collections:
        await db.create_collection('users')
        print("📁 'users' collection created")

    doctors = ['Jonah Irande', 'Oluwatosin Daniel', 'Faith Bitrus']
    for name in doctors:
        await users_collection.update_one(
            {"username": name},
            {"$set": {"role": "doctor", "password": "p@ssw0rd"}},
            upsert=True
        )
    await users_collection.update_one(
        {"username": "admin"},
        {"$set": {"role": "admin", "password": "p@ssw0rd"}},
        upsert=True
    )
    print("✅ Database Seeded")

# --- LIFESPAN (Replaces deprecated startup event) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Server starting...")
    await seed_users()
    yield
    print("🛑 Server shutting down...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELS ---
class User(BaseModel):
    username: str
    password: str
    phone: str = ""
    role: str = "patient"
    symptoms: str = ""
    age: Optional[str] = None
    location: Optional[str] = None
    diagnosis: str = ""
    prescription: str = ""
    assignedDoctor: Optional[str] = None
    status: str = "Pending"
    createdAt: datetime = Field(default_factory=datetime.utcnow)

# --- ROUTES ---

@app.post("/api/register", status_code=201)
async def register(user: User):
    try:
        user_dict = user.model_dump() # model_dump() is the modern version of .dict()
        result = await users_collection.insert_one(user_dict)
        user_dict["_id"] = str(result.inserted_id)
        return user_dict
    except Exception as e:
        raise HTTPException(status_code=500, detail="Register failed")

@app.get("/api/patients")
async def get_patients():
    cursor = users_collection.find({"role": "patient"}).sort("createdAt", -1)
    patients = []
    async for patient in cursor:
        patient["_id"] = str(patient["_id"])
        patients.append(patient)
    return patients

@app.put("/api/assign")
async def assign_doctor(data: dict):
    patient_id = data.get("patientId")
    doctor_name = data.get("doctorName")
    await users_collection.update_one(
        {"_id": ObjectId(patient_id)},
        {"$set": {"assignedDoctor": doctor_name, "status": "Assigned"}}
    )
    return {"msg": "Assigned"}

@app.put("/api/reset-password")
async def reset_password(data: dict):
    patient_id = data.get("patientId")
    new_password = data.get("newPassword")
    result = await users_collection.update_one(
        {"_id": ObjectId(patient_id)},
        {"$set": {"password": new_password}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Patient not found")
    return {"msg": "Password Reset Successful"}

@app.put("/api/diagnose")
async def diagnose(data: dict):
    patient_id = data.get("patientId")
    await users_collection.update_one(
        {"_id": ObjectId(patient_id)},
        {"$set": {
            "diagnosis": data.get("diagnosis"),
            "prescription": data.get("prescription"),
            "status": "Completed"
        }}
    )
    return {"msg": "Finalized"}

@app.delete("/api/patients/{patient_id}")
async def delete_patient(patient_id: str):
    await users_collection.delete_one({"_id": ObjectId(patient_id)})
    return {"msg": "Deleted"}

if __name__ == "__main__":
    import uvicorn
    # Listening on HTTP (Port 5000)
    uvicorn.run(app, host="0.0.0.0", port=5000)