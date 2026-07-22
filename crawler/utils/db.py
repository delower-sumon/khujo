"""
Shared database connection utility for KhujoBot v1.
Loads environment variables from backend/.env or root .env
"""

import os
from sqlalchemy import create_engine
from dotenv import load_dotenv

# Try backend/.env first, then root .env
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_env = os.path.join(current_dir, "..", "..", "backend", ".env")
root_env = os.path.join(current_dir, "..", "..", ".env")

if os.path.exists(backend_env):
    load_dotenv(backend_env)
elif os.path.exists(root_env):
    load_dotenv(root_env)
else:
    load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not found in environment variables.")

# Create SQLAlchemy engine with connection pooling and timeouts
engine = create_engine(
    DATABASE_URL,
    connect_args={"connect_timeout": 30},
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10
)

def get_engine():
    return engine
