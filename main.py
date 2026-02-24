import os
import asyncio
from typing import List, Optional
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId

app = FastAPI()

# 1. CORS Configuration (Matches your app.use(cors()))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with your frontend URL
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Database Connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://mongodb:27017/liveclinic")
client = AsyncIOMotorClient(MONGO_URI)
db = client.liveclinic
users_collection = db.users

# 3. Models (The "UserSchema" equivalent)
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

# 4. Seed Function
async def seed_users():
    async def seed_users():
    # 1. Create the application user (Equivalent to your init-db.js)
    try:
        await db.command("createUser", "clinic_admin", 
                         pwd="p@ssw0rd_db_user", 
                         roles=[{"role": "readWrite", "db": "liveclinic"}])
        print("👤 Database user created")
    except Exception as e:
        # User might already exist, which is fine
        print("ℹ️ User setup skipped (likely already exists)")

    # 2. Ensure 'users' collection exists
    collections = await db.list_collection_names()
    if 'users' not in collections:
        await db.create_collection('users')
        print("📁 'users' collection created")

    # 3. Rest of your existing seed logic (doctors/admins)...
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

@app.on_event("startup")
async def startup_db_client():
    await seed_users()

# --- ROUTES ---

@app.post("/api/register", status_code=201)
async def register(user: User):
    user_dict = user.dict()
    result = await users_collection.insert_one(user_dict)
    user_dict["_id"] = str(result.inserted_id)
    return user_dict

@app.get("/api/patients")
async def get_patients():
    cursor = users_collection.find({"role": "patient"}).sort("createdAt", -1)
    patients = []
    async for patient in cursor:
        patient["_id"] = str(patient["_id"]) # Convert ObjectId to string
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