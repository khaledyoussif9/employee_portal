"""
db.py
المسؤول الوحيد عن فتح اتصال مع قاعدة بيانات SQL Server.
كل ملف تاني في المشروع هيستدعي get_connection() من هنا لما يحتاج يكلم الداتابيز.
"""

import os
import pymssql

def get_connection():
    return pymssql.connect(
        server=DB_SERVER,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=1433,
        as_dict=True
)
