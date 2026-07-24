"""
debug_login.py
سكريبت تشخيصي مؤقت بس - مش جزء من السيرفر.
مهمته: يجيب بيانات الموظف بنفس طريقة الكود بالظبط، ويطلعها "خام"
عشان نشوف أي فرق مخفي (مسافات، أحرف غريبة...) ونتأكد فين المشكلة بالظبط.

تشغيل: python debug_login.py
"""

import bcrypt
from db import get_connection

employee_code_to_test = "9999"
password_to_test = "1234"

conn = get_connection()
cursor = conn.cursor()

cursor.execute(
    """
    SELECT u.id, u.password_hash, u.role, u.is_active,
           e.id AS employee_id, e.full_name
    FROM users u
    JOIN employees e ON e.id = u.employee_id
    WHERE e.employee_code = ?
    """,
    employee_code_to_test,
)
row = cursor.fetchone()
conn.close()

if row is None:
    print("مفيش صف اتلقى خالص - المشكلة في الـ JOIN أو employee_code")
else:
    user_id, password_hash, role, is_active, employee_id, full_name = row

    print("الصف اللي اتلقى:")
    print("  user_id:", repr(user_id))
    print("  password_hash:", repr(password_hash))
    print("  role:", repr(role))
    print("  is_active:", repr(is_active), "| type:", type(is_active))
    print("  employee_id:", repr(employee_id))
    print("  full_name:", repr(full_name))

    print("\nطول password_hash:", len(password_hash))

    print("\nبنجرب bcrypt.checkpw دلوقتي...")
    try:
        match = bcrypt.checkpw(
            password_to_test.encode("utf-8"), password_hash.encode("utf-8")
        )
        print("النتيجة:", match)
    except Exception as e:
        print("حصل خطأ أثناء المقارنة:", repr(e))

    print("\n" + "=" * 50)
    print("دلوقتي اكتب '1234' يدويًا في الكيبورد (زي ما بتكتبها عادي):")
    typed_password = input("اكتب الباسورد: ")
    print("الشكل الخام اللي اتسجل:", repr(typed_password))
    print("عدد البايتات (لازم يكون 4 بالظبط لو الأرقام إنجليزي):", len(typed_password.encode("utf-8")))

    match2 = bcrypt.checkpw(typed_password.encode("utf-8"), password_hash.encode("utf-8"))
    print("نتيجة المقارنة بالباسورد اللي كتبته دلوقتي:", match2)