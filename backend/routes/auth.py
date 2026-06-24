#auth.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from backend.db.mongo import db as mongo_db
import uuid
import hashlib
import secrets

router = APIRouter()

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

def hash_password(password: str) -> str:
    """Hash password using PBKDF2-HMAC with random salt"""
    salt = secrets.token_hex(16)
    iterations = 100000
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        iterations
    )
    return f"{salt}:{iterations}:{key.hex()}"

def verify_password(stored_password: str, provided_password: str) -> bool:
    """Verify a password, supporting legacy plaintext checks for compatibility"""
    if not stored_password or not provided_password:
        return False
        
    if ":" not in stored_password:
        return stored_password == provided_password
        
    try:
        parts = stored_password.split(":")
        if len(parts) != 3:
            return False
        salt, iterations_str, key_hex = parts
        iterations = int(iterations_str)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            provided_password.encode('utf-8'),
            salt.encode('utf-8'),
            iterations
        )
        return key.hex() == key_hex
    except Exception as e:
        print(f"[AUTH] Error verifying password: {e}")
        return False

def get_db():
    """Dependency to get database connection at request time"""
    return mongo_db

@router.post("/register")
def register(request: RegisterRequest, db=Depends(get_db)):
    if db is None:
        return {"status": "error", "message": "Database connection failed"}
    
    # Input validation
    if not request.name or len(request.name.strip()) < 2:
        return {"error": "Name must be at least 2 characters"}
    
    # Standardize email representation
    email_clean = request.email.lower().strip()
    if not request.email or "@" not in request.email:
        return {"error": "Invalid email format"}
    
    if not request.password or len(request.password) < 4:
        return {"error": "Password must be at least 4 characters"}
    
    # Check if user already exists with defensive database error handling
    try:
        existing_user = db["users"].find_one({"email": email_clean})
    except Exception as e:
        print(f"[AUTH] Database error during registration check: {e}")
        return {"error": "Database connection error. Please try again."}
        
    if existing_user:
        return {"error": "Email already registered"}
    
    user = {
        "user_id": str(uuid.uuid4()),
        "name": request.name.strip(),
        "email": email_clean,
        "password": hash_password(request.password)
    }
    
    try:
        db["users"].insert_one(user)
    except Exception as e:
        print(f"[AUTH] Database error during user insertion: {e}")
        return {"error": "Database write error. Please try again."}
        
    return {
        "message": "User registered successfully",
        "user_id": user["user_id"],
        "name": user["name"]
    }

@router.post("/login")
def login(request: LoginRequest, db=Depends(get_db)):
    if db is None:
        return {"status": "error", "message": "Database connection failed"}
    
    # Input validation
    if not request.email or "@" not in request.email:
        return {"error": "Invalid email format"}
    
    if not request.password:
        return {"error": "Password required"}
    
    email_clean = request.email.lower().strip()
    
    # Defensive database fetch
    try:
        user = db["users"].find_one({"email": email_clean})
    except Exception as e:
        print(f"[AUTH] Database connection error during login: {e}")
        return {"error": "Database connection error. Please check your network."}
    
    if not user or not verify_password(user.get("password"), request.password):
        return {"error": "Invalid credentials"}
    
    return {
        "message": "Login successful",
        "user_id": user["user_id"],
        "name": user["name"],
        "email": user["email"]
    }
