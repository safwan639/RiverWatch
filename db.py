"""Database connection helper for RiverWatch."""

import os

import psycopg
from dotenv import load_dotenv

load_dotenv()  # reads DATABASE_URL from the .env file in the project folder


def get_connection() -> psycopg.Connection:
    """Open a connection to the RiverWatch PostgreSQL database."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Add it to your .env file.")
    # prepare_threshold=None keeps psycopg compatible with Supabase's connection pooler
    return psycopg.connect(url, prepare_threshold=None, connect_timeout=15)