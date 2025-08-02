import psycopg2
from psycopg2 import pool, OperationalError
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Global connection pool
connection_pool = None

def init_connection_pool():
    """Initialize PostgreSQL connection pool"""
    global connection_pool
    try:
        connection_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,
            maxconn=10,
            host=os.getenv("DB_HOST", "localhost"),
            database=os.getenv("DB_NAME", "farmnaturals"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", "postgres"),
            port=os.getenv("DB_PORT", 5432)
        )
        print("✅ FarmNaturals DB connection pool created")
    except OperationalError as e:
        print(f"❌ Failed to create FarmNaturals connection pool: {e}")
        raise

@contextmanager
def get_db_connection():
    """Context manager to get a DB connection with RealDictCursor"""
    conn = None
    try:
        if connection_pool:
            conn = connection_pool.getconn()
        else:
            conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "localhost"),
                database=os.getenv("DB_NAME", "farmnaturals"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", "postgres"),
                port=os.getenv("DB_PORT", 5432)
            )
        # 👇 Ensure RealDictCursor is used
        conn.cursor_factory = RealDictCursor
        yield conn
    except OperationalError as e:
        print(f"❌ FarmNaturals DB error: {e}")
        raise
    finally:
        if conn:
            if connection_pool:
                connection_pool.putconn(conn)
            else:
                conn.close()

def test_farmnaturals_db():
    """Ping the database to check connection"""
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                print("✅ FarmNaturals DB connection test passed")
                return True
    except Exception as e:
        print(f"❌ FarmNaturals DB test failed: {e}")
        return False

# Initialize on import
try:
    init_connection_pool()
    test_farmnaturals_db()
except:
    print("⚠️ Proceeding without FarmNaturals connection pool")
