"""
generate_hash.py
سكريبت مستقل بس، مش جزء من السيرفر.
مهمته: تديله باسورد عادي، يطلعلك الـ hash بتاعه
عشان تنسخه وتحطه في جدول users بدل الـ password_hash

طريقة التشغيل:
    python generate_hash.py
"""

import bcrypt

password = input("اكتب الباسورد اللي عايز تعمله hash: ")

# bcrypt.gensalt() بيعمل "ملح" عشوائي، فكل مرة تشغل السكريبت
# بنفس الباسورد هتاخد hash مختلف - ده طبيعي ومقصود، الأمان بيزيد بيه
hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

print("\nالـ hash بتاعك (انسخه كامل):")
print(hashed.decode("utf-8"))
