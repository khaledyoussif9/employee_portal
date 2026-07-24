"""
db.py
المسؤول الوحيد عن فتح اتصال مع قاعدة بيانات SQL Server.
كل ملف تاني في المشروع هيستدعي get_connection() من هنا لما يحتاج يكلم الداتابيز.
"""
import os
import pymssql

# قراءة البيانات من متغيّرات بيئة Render
DB_SERVER = os.getenv('DB_SERVER')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME')

def get_connection():
    return pymssql.connect(
        server=DB_SERVER,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
