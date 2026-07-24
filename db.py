"""
db.py
المسؤول الوحيد عن فتح اتصال مع قاعدة بيانات SQL Server.
كل ملف تاني في المشروع هيستدعي get_connection() من هنا لما يحتاج يكلم الداتابيز.
"""

import os
import pyodbc
from dotenv import load_dotenv

# بيقرأ القيم من ملف .env ويحطها في متغيرات البيئة
load_dotenv()

DB_SERVER = os.getenv("DB_SERVER")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


def get_connection():
    """
    بتفتح اتصال جديد مع SQL Server وترجعه.
    لو الاتصال فشل (بيانات غلط، السيرفر واقف...) هيرمي Exception
    ونمسكه في الأماكن اللي بنستخدمه فيها.
    """
    connection_string = (
        "DRIVER={ODBC Driver 17 for SQL Server};"
        f"SERVER={DB_SERVER};"
        f"DATABASE={DB_NAME};"
        f"UID={DB_USER};"
        f"PWD={DB_PASSWORD};"
    )
    return pyodbc.connect(connection_string)
