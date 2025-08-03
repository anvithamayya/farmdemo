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
from fastapi import APIRouter

from fastapi import UploadFile, File
from fastapi.responses import JSONResponse

from fastapi import Body

from uuid import uuid4


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
# Create the router for admin APIs
admin_router = APIRouter(prefix="/admin/api", tags=["Admin"])

class Category(BaseModel):
    name: str
    description: Optional[str] = None

class ProductIn(BaseModel):
    name: str
    category: str
    price: float
    unit: str
    stock: float
    stock_unit: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    featured: Optional[bool] = False

class CartItemIn(BaseModel):
    email: EmailStr
    product_name: str
    quantity: int = 1


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

@admin_router.get("/categories")
def get_categories(token: str = Depends(verify_admin)):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT id, name, description FROM categories ORDER BY id;")
            categories = cur.fetchall()
            return categories

from pydantic import BaseModel

class CategoryIn(BaseModel):
    name: str
    description: Optional[str] = None

@admin_router.put("/categories/{category_id}")
def update_category(
    category_id: int,
    category: CategoryIn,
    token: str = Depends(verify_admin)
):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE categories SET name = %s, description = %s WHERE id = %s;",
                (category.name, category.description, category_id)
            )
            conn.commit()
    return {"message": "Category updated successfully"}
@admin_router.get("/products")
def get_products(token: str = Depends(verify_admin)):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, name, category, price, unit, stock, stock_unit, description, image_url, featured
                FROM products ORDER BY id;
            """)
            return cur.fetchall()

@admin_router.post("/products")
def add_product(product: ProductIn, token: str = Depends(verify_admin)):
    # Insert product into the database
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO products (name, category, price, unit, stock, stock_unit, description, image_url, featured)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                product.name, product.category, product.price, product.unit,
                product.stock, product.stock_unit, product.description,
                product.image_url, product.featured
            ))
            conn.commit()

    # Map category to HTML file
    CATEGORY_HTML_FILES = {
        "Fruits": "Fruits.html",
        "Grains": "Grains.html",
        "Vegetables": "veg.html",
        "Dairy": "Dairy.html",
        "Organic": "Organic.html"
    }

    file_path = CATEGORY_HTML_FILES.get(product.category)
    if file_path and os.path.exists(file_path):
        # Create HTML snippet
        product_html = f"""
        <div class="product-card">
            <div class="product-image">
                <img src="{product.image_url or 'images/placeholder.jpg'}" alt="{product.name}">
            </div>
            <div class="product-info">
                <h3 class="product-title">{product.name}</h3>
                <p class="product-price">₹{product.price}/{product.unit}</p>
                <button class="add-to-cart" data-name="{product.name}" data-price="{product.price}">Add to Cart</button>
            </div>
        </div>
        """

        # Append to products-grid container
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        insert_pos = content.rfind('</div>')  # last </div> of products-grid
        if insert_pos != -1:
            new_content = content[:insert_pos] + product_html + '\n' + content[insert_pos:]
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

    return {"message": "Product added successfully"}


@admin_router.put("/products/{product_id}")
def update_product(product_id: int, product: ProductIn, token: str = Depends(verify_admin)):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE products
                SET name=%s, category=%s, price=%s, unit=%s, stock=%s, stock_unit=%s,
                    description=%s, image_url=%s, featured=%s
                WHERE id=%s;
            """, (
                product.name, product.category, product.price, product.unit,
                product.stock, product.stock_unit, product.description,
                product.image_url, product.featured, product_id
            ))
            conn.commit()
    return {"message": "Product updated successfully"}

@admin_router.delete("/products/{product_id}")
def delete_product(product_id: int, token: str = Depends(verify_admin)):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM products WHERE id = %s;", (product_id,))
            conn.commit()
    return {"message": "Product deleted successfully"}
# Mount the router
app.include_router(admin_router)
from fastapi import UploadFile, File
import shutil
import os

UPLOAD_DIR = "images"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return {"url": f"images/{file.filename}"}
from fastapi.staticfiles import StaticFiles

app.mount("/images", StaticFiles(directory=r"D:\farm demo\images"), name="images")
@admin_router.get("/products/{product_id}")
def get_product_by_id(product_id: int, token: str = Depends(verify_admin)):
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM products WHERE id = %s;", (product_id,))
            product = cur.fetchone()
            if not product:
                raise HTTPException(status_code=404, detail="Product not found")
            return product
from fastapi import Query

@app.post("/cart/add")
def add_to_cart(
    item: CartItemIn,
    email: EmailStr = Query(...)
):
    if email != item.email:
        raise HTTPException(status_code=400, detail="Email mismatch in body and query")

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO cart_items (product_name, email, quantity)
                VALUES (%s, %s, %s)
                ON CONFLICT (email, product_name)
                DO UPDATE SET quantity = cart_items.quantity + EXCLUDED.quantity
                RETURNING quantity;
            """, (item.product_name, email, item.quantity))

            result = cur.fetchone()
            quantity = result[0] if result else item.quantity
            conn.commit()
    
    return {"message": "Item added to cart successfully", "email": email, "quantity": quantity}
