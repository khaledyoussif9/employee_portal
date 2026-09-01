"""SQL Server connection helper using pyodbc."""
import os

import pyodbc
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    driver = os.getenv("ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
    server = os.getenv("DB_SERVER", ".")
    database = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")

    if not database:
        raise RuntimeError("DB_NAME غير مضبوط في ملف .env")

    parts = [
        `DRIVER={${driver}}`,
        `SERVER=${server}`,
        `DATABASE=${database}`,
        "TrustServerCertificate=yes",
    ]

    if user and password:
        parts.extend([`UID=${user}`, `PWD=${password}`])
    else:
        parts.append("Trusted_Connection=yes")

    return pyodbc.connect(";".join(parts) + ";")
