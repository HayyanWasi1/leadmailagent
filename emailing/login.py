# from fastapi import FastAPI, Depends, HTTPException, status
# from fastapi.security import OAuth2PasswordRequestForm
# from motor.motor_asyncio import AsyncIOMotorClient
# from passlib.context import CryptContext
# from jose import JWTError, jwt
# from datetime import datetime, timedelta

# app = FastAPI()

# # DB
# client = AsyncIOMotorClient("mongodb://localhost:27017")
# db = client["auth_db"]
# users_collection = db["users"]

# # Security
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# SECRET_KEY = "supersecretkey123"  # 🔐 change in production
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 30  # 30 days


# def verify_password(plain, hashed):
#     return pwd_context.verify(plain, hashed)

# def create_access_token(data: dict, expires_delta: timedelta | None = None):
#     to_encode = data.copy()
#     expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
#     to_encode.update({"exp": expire})
#     return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# @app.post("/login")
# async def login(form_data: OAuth2PasswordRequestForm = Depends()):
#     user = await users_collection.find_one({"email": form_data.username})
#     if not user or not verify_password(form_data.password, user["password"]):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid email or password",
#         )
#     access_token = create_access_token({"sub": user["email"]}, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
#     return {"access_token": access_token, "token_type": "bearer"}
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.context import CryptContext
import asyncio
from dotenv import load_dotenv
import os

load_dotenv()
app = FastAPI()


MONGODB_DB = os.getenv("MONGODB_DB", "email_agent_db")

# Database connection
MONGO_URI = "mongodb://localhost:27017"
client = AsyncIOMotorClient(MONGO_URI)
db = client[MONGODB_DB]
users_collection = db["users"]

# Password hasher
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Function to add user
async def add_user(email: str, password: str):
    hashed_password = pwd_context.hash(password)
    user = {"email": email, "password": hashed_password}
    await users_collection.insert_one(user)
    print(f"✅ User {email} added to database")

# Run it once to insert user
if __name__ == "__main__":
    email = "testuser@example.com"
    password = "mypassword123"
    asyncio.run(add_user(email, password))
