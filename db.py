"""
db.py
المسؤول الوحيد عن فتح اتصال مع قاعدة بيانات SQL Server.
كل ملف تاني في المشروع هيستدعي get_connection() من هنا لما يحتاج يكلم الداتابيز.
"""

import os
import pymssql
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
    def get_connection():
    """
    بتفتح اتصال جديد مع SQL Server وترجعه.
    """
    return pymssql.connect(
        server=DB_SERVER,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=1433,
        as_dict=True
    )
