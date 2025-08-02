from fastapi import FastAPI, HTTPException, Depends, status, Form, UploadFile, File
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from passlib.hash import bcrypt
from pydantic import BaseModel, EmailStr
from typing import Optional
from dotenv import load_dotenv
from db import get_db_connection
from psycopg2.extras import RealDictCursor
import os

# Load environment variables
load_dotenv()

# App initialization
app = FastAPI(title="FarmNaturals API")

# CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with actual domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class UserCreate(BaseModel):
    email: EmailStr
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    is_admin: bool

# OAuth2 for protected endpoints
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Routes

@app.post("/register")
def register(user: UserCreate):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE email = %s;", (user.email,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="Email already registered")

            hashed_pw = bcrypt.hash(user.password)
            cur.execute(
                "INSERT INTO users (email, password, is_admin) VALUES (%s, %s, %s);",
                (user.email, hashed_pw, False)
            )
            conn.commit()
            return {"message": "User registered successfully"}

@app.post("/token", response_model=LoginResponse)
def login_token(form_data: OAuth2PasswordRequestForm = Depends()):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT password, is_admin FROM users WHERE email = %s;", (form_data.username,))
            result = cur.fetchone()
            if not result or not bcrypt.verify(form_data.password, result["password"]):
                raise HTTPException(status_code=401, detail="Invalid credentials")

            return {
                "access_token": form_data.username,
                "token_type": "bearer",
                "is_admin": result["is_admin"]
            }

# Admin route (protected)
@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return FileResponse("admin.html")

# Token verification utility
async def verify_admin(token: str = Depends(oauth2_scheme)):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT is_admin FROM users WHERE email = %s;", (token,))
            result = cur.fetchone()
            if not result:
                raise HTTPException(status_code=401, detail="Invalid authentication credentials")
            if not result["is_admin"]:
                raise HTTPException(status_code=403, detail="Admin privileges required")
    return token
