"""
app.py
السيرفر الرئيسي. فيه:
  1) route لتسجيل الدخول (/api/login)
  2) route لجلب البيانات الإدارية (/api/employee/me)
  3) route لجلب شريط المرتب لشهر وسنة معينين (/api/payslip)

تشغيل السيرفر: python app.py
"""

import os
import bcrypt
import jwt
import datetime
import random
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

from db import get_connection

load_dotenv()

app = Flask(__name__)
CORS(app)  # يسمح لصفحة الويب (Frontend) إنها تكلم السيرفر ده من دومين مختلف

@app.route('/')
def home():
    return jsonify({"message": "Welcome to Employee Portal API"})

SECRET_KEY = os.getenv("SECRET_KEY")


# ------------------------------------------------------------
# دالة مساعدة: تتحقق من التوكن (Token) اللي بيبعته المستخدم
# بعد ما يعمل تسجيل دخول، عشان نتأكد إنه فعلاً مسجل دخول
# قبل ما نديله أي بيانات حساسة
# ------------------------------------------------------------
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "لازم تسجل الدخول الأول"}), 401

        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            # بنحط بيانات المستخدم متاحة جوه الـ route اللي طلبها
            request.employee_id = payload["employee_id"]
            request.role = payload.get("role", "employee")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "انتهت صلاحية الجلسة، سجل دخول تاني"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "جلسة غير صالحة"}), 401

        return f(*args, **kwargs)
    return decorated


# ------------------------------------------------------------
# دالة مساعدة تانية: زي اللي فوق، بس كمان بتتأكد إن المستخدم
# عنده صلاحية "hr_admin" - نستخدمها في كل صفحات الإدارة
# ------------------------------------------------------------
def admin_required(f):
    @wraps(f)
    @token_required
    def decorated(*args, **kwargs):
        if request.role != "hr_admin":
            return jsonify({"error": "الصفحة دي للموارد البشرية بس"}), 403
        return f(*args, **kwargs)
    return decorated


# ------------------------------------------------------------
# 1) تسجيل الدخول
# ------------------------------------------------------------
@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    employee_code = data.get("employee_code")
    password = data.get("password")

    if not employee_code or not password:
        return jsonify({"error": "من فضلك ادخل كود الموظف وكلمة المرور"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    # ملحوظة أمان: بنستخدم "?" مكان القيمة، مش بنحط القيمة جوه النص مباشرة
    # ده بيمنع هجمات SQL Injection
    cursor.execute(
        """
        SELECT u.id, u.password_hash, u.role, u.is_active,
               e.id AS employee_id, e.full_name, e.employee_code
        FROM users u
        JOIN employees e ON e.id = u.employee_id
        WHERE e.employee_code = ?
        """,
        employee_code,
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "كود الموظف أو كلمة المرور غير صحيحة"}), 401

    user_id, password_hash, role, is_active, employee_id, full_name, emp_code = row

    if not is_active:
        return jsonify({"error": "الحساب موقوف، راجع الموارد البشرية"}), 403

    # بنقارن الباسورد اللي المستخدم كتبه مع الـ hash المخزن
    password_correct = bcrypt.checkpw(
        password.encode("utf-8"), password_hash.encode("utf-8")
    )
    if not password_correct:
        return jsonify({"error": "كود الموظف أو كلمة المرور غير صحيحة"}), 401

    # لو البيانات صح، بنعمل "توكن" (Token) - زي تذكرة دخول مؤقتة
    # الفرونت إند هيحفظها ويبعتها مع كل طلب بعد كده عشان يثبت إنه مسجل دخول
    token = jwt.encode(
        {
            "employee_id": employee_id,
            "role": role,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8),
        },
        SECRET_KEY,
        algorithm="HS256",
    )

    return jsonify({
        "token": token,
        "full_name": full_name,
        "role": role,
        "employee_code": emp_code,
    })


# ------------------------------------------------------------
# 2) البيانات الإدارية للموظف اللي مسجل دخول
# ------------------------------------------------------------
@app.route("/api/employee/me", methods=["GET"])
@token_required
def get_my_info():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT e.employee_code, e.full_name, e.job_title, e.hire_date, e.national_id,
               e.phone, e.status, e.insurance_number, d.name AS department_name
        FROM employees e
        LEFT JOIN departments d ON d.id = e.department_id
        WHERE e.id = ?
        """,
        request.employee_id,  # جاي من التوكن، مش من طلب المستخدم - أمان مهم جدًا
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "الموظف غير موجود"}), 404

    return jsonify({
        "employee_code": row.employee_code,
        "insurance_number": row.insurance_number,
        "full_name": row.full_name,
        "job_title": row.job_title,
        "hire_date": str(row.hire_date) if row.hire_date else None,
        "national_id": row.national_id,
        "phone": row.phone,
        "status": row.status,
        "department": row.department_name,
    })


# ------------------------------------------------------------
# 3) شريط المرتب لشهر وسنة معينين
#    بيدوّر الأول في payroll_items (بيانات حقيقية مفصّلة، بند بند)
#    لو مالقاش حاجة، يرجع لجدول payroll_records القديم (بيانات يدوية/تجريبية)
# ------------------------------------------------------------
@app.route("/api/payslip", methods=["GET"])
@token_required
def get_payslip():
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    if not month or not year:
        return jsonify({"error": "لازم تحدد الشهر والسنة"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    # كود الصرف الخاص بالموظف (من بيانات النظام الإداري)
    cursor.execute("SELECT code_sarf FROM employees WHERE id = ?", request.employee_id)
    code_sarf_row = cursor.fetchone()
    code_sarf = code_sarf_row.code_sarf if code_sarf_row else None

    # المحاولة الأولى: البيانات الحقيقية المفصّلة (بند بند)
    # sarfia_no = 1 يعني "صرفية المرتب" (مش صرفيات الحوافز التانية)
    # وبنستبعد بنود "ت ..." اللي من غير "حصة العامل" و"مصاريف إدارية"
    # لأنها نسخ مكررة (نصيب الحكومة/الشركة) بتتلغي في الصافي لكن تفضل بتلوّث العرض
    # وبنجمّع المجرد + العلاوات (87-2013) + غلاء المعيشة في بند واحد اسمه "الأساسي"
    cursor.execute(
        """
        SELECT
            CASE WHEN band_code IN (1,5,6,7,8,9,10,11,12,13,14,15,28,29,30,31,32,33,34,37,39,43,47,53,54,59,60,84,198)
                 THEN N'الأساسي'
                 ELSE band_name
            END AS display_name,
            band_type,
            SUM(amount) AS amount
        FROM payroll_items
        WHERE employee_id = ? AND month = ? AND year = ?
          AND sarfia_no = 1
          AND NOT (band_name LIKE N'ت %' AND band_name NOT LIKE N'%حصة العامل%')
          AND band_name NOT LIKE N'%مصاريف ادارية%'
        GROUP BY
            CASE WHEN band_code IN (1,5,6,7,8,9,10,11,12,13,14,15,28,29,30,31,32,33,34,37,39,43,47,53,54,59,60,84,198)
                 THEN N'الأساسي'
                 ELSE band_name
            END,
            band_type
        ORDER BY band_type DESC, amount DESC
        """,
        request.employee_id,
        month,
        year,
    )
    item_rows = cursor.fetchall()

    if item_rows:
        items = [
            {
                "name": r.display_name or "بند غير مسمى",
                "type": r.band_type,
                "amount": float(r.amount),
            }
            for r in item_rows
        ]
        earnings_total = sum(i["amount"] for i in items if i["type"] == "earning")
        deductions_total = sum(i["amount"] for i in items if i["type"] == "deduction")

        conn.close()
        return jsonify({
            "month": month,
            "year": year,
            "source": "items",
            "code_sarf": code_sarf,
            "items": items,
            "earnings_total": earnings_total,
            "deductions_total": deductions_total,
            "net_salary": earnings_total - deductions_total,
        })

    # لو مفيش بيانات مفصّلة، نرجع للطريقة القديمة (سجلات يدوية)
    cursor.execute(
        """
        SELECT month, year, basic_salary, transport_allowance,
               housing_allowance, bonus, insurance_deduction,
               tax_deduction, absence_deduction, net_salary
        FROM payroll_records
        WHERE employee_id = ? AND month = ? AND year = ?
        """,
        request.employee_id,
        month,
        year,
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "لا يوجد سجل أجور لهذا الشهر"}), 404

    # نحوّل الأعمدة الثابتة لنفس شكل "بنود" عشان الفرونت إند يتعامل بنفس الطريقة دايمًا
    items = []
    if row.basic_salary:
        items.append({"name": "المرتب الأساسي", "type": "earning", "amount": float(row.basic_salary)})
    if row.transport_allowance:
        items.append({"name": "بدل انتقال", "type": "earning", "amount": float(row.transport_allowance)})
    if row.housing_allowance:
        items.append({"name": "بدل سكن", "type": "earning", "amount": float(row.housing_allowance)})
    if row.bonus:
        items.append({"name": "حافز / مكافأة", "type": "earning", "amount": float(row.bonus)})
    if row.insurance_deduction:
        items.append({"name": "التأمينات الاجتماعية", "type": "deduction", "amount": float(row.insurance_deduction)})
    if row.tax_deduction:
        items.append({"name": "ضريبة كسب العمل", "type": "deduction", "amount": float(row.tax_deduction)})
    if row.absence_deduction:
        items.append({"name": "خصم غياب", "type": "deduction", "amount": float(row.absence_deduction)})

    return jsonify({
        "month": row.month,
        "year": row.year,
        "source": "fixed",
        "code_sarf": code_sarf,
        "items": items,
        "earnings_total": float(row.basic_salary + row.transport_allowance + row.housing_allowance + row.bonus),
        "deductions_total": float(row.insurance_deduction + row.tax_deduction + row.absence_deduction),
        "net_salary": float(row.net_salary),
    })


# ------------------------------------------------------------
# 3.5) سجل الأجور: الصرفيات الإضافية (حوافز وغيرها) بخلاف صرفية المرتب الأساسية
#      كل رقم صرفية (sarfia_no > 1) بيرجع منفصل لوحده، مش مجمّع مع الباقي
# ------------------------------------------------------------
@app.route("/api/wage-record", methods=["GET"])
@token_required
def get_wage_record():
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    if not month or not year:
        return jsonify({"error": "لازم تحدد الشهر والسنة"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT sarfia_no, band_name, band_type, SUM(amount) AS amount
        FROM payroll_items
        WHERE employee_id = ? AND month = ? AND year = ?
          AND sarfia_no > 1
          AND NOT (band_name LIKE N'ت %' AND band_name NOT LIKE N'%حصة العامل%')
          AND band_name NOT LIKE N'%مصاريف ادارية%'
        GROUP BY sarfia_no, band_name, band_type
        ORDER BY sarfia_no, band_type DESC, amount DESC
        """,
        request.employee_id,
        month,
        year,
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return jsonify({"error": "لا يوجد سجل أجور إضافي لهذا الشهر"}), 404

    # نجمّع الصفوف حسب رقم الصرفية، كل صرفية لوحدها مع بنودها ومجاميعها
    disbursements = {}
    for r in rows:
        sarfia = r.sarfia_no
        if sarfia not in disbursements:
            disbursements[sarfia] = {"sarfia_no": sarfia, "items": []}
        disbursements[sarfia]["items"].append({
            "name": r.band_name or "بند غير مسمى",
            "type": r.band_type,
            "amount": float(r.amount),
        })

    result = []
    for sarfia_no in sorted(disbursements.keys()):
        d = disbursements[sarfia_no]
        earnings_total = sum(i["amount"] for i in d["items"] if i["type"] == "earning")
        deductions_total = sum(i["amount"] for i in d["items"] if i["type"] == "deduction")
        result.append({
            "sarfia_no": sarfia_no,
            "items": d["items"],
            "earnings_total": earnings_total,
            "deductions_total": deductions_total,
            "net_salary": earnings_total - deductions_total,
        })

    return jsonify({
        "month": month,
        "year": year,
        "disbursements": result,
    })


# ------------------------------------------------------------
# نسيت كلمة المرور: خطوة 1) طلب كود، خطوة 2) تأكيد الكود وتغيير الباسورد
# ------------------------------------------------------------
@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json()
    employee_code = data.get("employee_code")
    phone = data.get("phone")

    if not employee_code or not phone:
        return jsonify({"error": "من فضلك ادخل كود الموظف ورقم الموبايل"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, phone FROM employees WHERE employee_code = ?",
        employee_code,
    )
    row = cursor.fetchone()

    # ملحوظة أمان: مش بنقول "الكود غلط" أو "الموبايل غلط" بالتحديد
    # عشان محدش يقدر "يجرب" أكواد موظفين عشوائي ويعرف مين موجود فعلاً
    if row is None or (row.phone or "").strip() != phone.strip():
        conn.close()
        return jsonify({"error": "البيانات المدخلة غير صحيحة"}), 400

    employee_id = row.id

    # كود مكوّن من 6 أرقام، صلاحيته 10 دقايق
    code = str(random.randint(100000, 999999))
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)

    cursor.execute(
        "INSERT INTO password_resets (employee_id, code, expires_at) VALUES (?, ?, ?)",
        employee_id, code, expires_at,
    )
    conn.commit()
    conn.close()

    # ==========================================================================
    # === مكان محجوز (TODO) لإرسال الكود فعليًا عن طريق SMS أو إيميل حقيقي ===
    # لما يبقى عندك حساب في خدمة إرسال SMS (مثلاً بوابة SMS مصرية) أو إيميل SMTP،
    # هنا بالظبط المكان اللي تستدعي فيه الخدمة دي وتبعتلها رقم الموبايل + الكود.
    # مثال (لو استخدمت SMTP للإيميل مثلاً):
    #   send_email(to=employee_email, subject="كود إعادة تعيين كلمة المرور", body=code)
    # ==========================================================================

    return jsonify({
        "message": "تم إرسال كود التحقق",
        # ⚠️ السطر ده للتجربة بس لحد ما تربط خدمة إرسال حقيقية - لازم يتشال بعد كده
        "dev_only_code": code,
    })


@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()
    employee_code = data.get("employee_code")
    code = data.get("code")
    new_password = data.get("new_password")

    if not employee_code or not code or not new_password:
        return jsonify({"error": "بيانات ناقصة"}), 400

    if len(new_password) < 4:
        return jsonify({"error": "كلمة المرور قصيرة جدًا"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT pr.id, pr.employee_id, pr.expires_at, pr.used
        FROM password_resets pr
        JOIN employees e ON e.id = pr.employee_id
        WHERE e.employee_code = ? AND pr.code = ?
        ORDER BY pr.id DESC
        """,
        employee_code, code,
    )
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return jsonify({"error": "الكود غير صحيح"}), 400

    if row.used:
        conn.close()
        return jsonify({"error": "الكود ده مستخدم قبل كده، اطلب كود جديد"}), 400

    if datetime.datetime.utcnow() > row.expires_at:
        conn.close()
        return jsonify({"error": "انتهت صلاحية الكود، اطلب كود جديد"}), 400

    new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE employee_id = ?",
        new_hash, row.employee_id,
    )
    cursor.execute(
        "UPDATE password_resets SET used = 1 WHERE id = ?",
        row.id,
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "تم تغيير كلمة المرور بنجاح"})


# ------------------------------------------------------------
# 4) [إداري] البحث عن موظف بالكود أو الاسم
#    مثال: /api/admin/employees?search=احمد
# ------------------------------------------------------------
@app.route("/api/admin/employees", methods=["GET"])
@admin_required
def admin_search_employees():
    search = request.args.get("search", "").strip()
    if not search:
        return jsonify({"error": "اكتب كود أو اسم للبحث"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    # % علامة "أي حاجة قبل/بعد" في البحث الجزئي
    like_pattern = f"%{search}%"

    cursor.execute(
        """
        SELECT TOP 20 id, employee_code, full_name, job_title, status
        FROM employees
        WHERE employee_code LIKE ? OR full_name LIKE ?
        ORDER BY full_name
        """,
        like_pattern,
        like_pattern,
    )
    rows = cursor.fetchall()
    conn.close()

    return jsonify([
        {
            "id": r.id,
            "employee_code": r.employee_code,
            "full_name": r.full_name,
            "job_title": r.job_title,
            "status": r.status,
        }
        for r in rows
    ])


# ------------------------------------------------------------
# 5) [إداري] بيانات موظف معيّن كاملة (عرض وتعديل)
# ------------------------------------------------------------
@app.route("/api/admin/employees/<int:emp_id>", methods=["GET"])
@admin_required
def admin_get_employee(emp_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT e.id, e.employee_code, e.full_name, e.job_title, e.hire_date,
               e.national_id, e.phone, e.status, e.department_id, d.name AS department_name
        FROM employees e
        LEFT JOIN departments d ON d.id = e.department_id
        WHERE e.id = ?
        """,
        emp_id,
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "الموظف غير موجود"}), 404

    return jsonify({
        "id": row.id,
        "employee_code": row.employee_code,
        "full_name": row.full_name,
        "job_title": row.job_title,
        "hire_date": str(row.hire_date) if row.hire_date else None,
        "national_id": row.national_id,
        "phone": row.phone,
        "status": row.status,
        "department_id": row.department_id,
        "department_name": row.department_name,
    })


@app.route("/api/admin/employees/<int:emp_id>", methods=["PUT"])
@admin_required
def admin_update_employee(emp_id):
    data = request.get_json()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE employees
        SET full_name = ?, job_title = ?, phone = ?, status = ?, national_id = ?
        WHERE id = ?
        """,
        data.get("full_name"),
        data.get("job_title"),
        data.get("phone"),
        data.get("status"),
        data.get("national_id"),
        emp_id,
    )
    conn.commit()
    updated = cursor.rowcount
    conn.close()

    if updated == 0:
        return jsonify({"error": "الموظف غير موجود"}), 404

    return jsonify({"message": "تم تحديث البيانات بنجاح"})


# ------------------------------------------------------------
# 5.5) [إداري] تغيير/إعادة تعيين كلمة مرور أي موظف مباشرة من لوحة المدير
#      لو new_password مش مبعوتة، بيرجّعها لباسورد افتراضي موحّد (Welcome123)
# ------------------------------------------------------------
@app.route("/api/admin/employees/<int:emp_id>/reset-password", methods=["POST"])
@admin_required
def admin_reset_password(emp_id):
    data = request.get_json() or {}
    new_password = data.get("new_password") or "Welcome123"

    if len(new_password) < 4:
        return jsonify({"error": "كلمة المرور قصيرة جدًا"}), 400

    new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE employee_id = ?",
        new_hash, emp_id,
    )
    conn.commit()
    updated = cursor.rowcount
    conn.close()

    if updated == 0:
        return jsonify({"error": "الموظف غير موجود أو معندوش حساب دخول"}), 404

    return jsonify({
        "message": "تم تغيير كلمة المرور بنجاح",
        "new_password": new_password,  # عشان المدير يقدر يبلغ الموظف بيها
    })


# ------------------------------------------------------------
# 6) [إداري] عرض / إضافة / تعديل سجل مرتب لموظف معيّن
# ------------------------------------------------------------
@app.route("/api/admin/payroll", methods=["GET"])
@admin_required
def admin_get_payroll():
    emp_id = request.args.get("employee_id", type=int)
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    if not emp_id or not month or not year:
        return jsonify({"error": "لازم تحدد الموظف والشهر والسنة"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT basic_salary, transport_allowance, housing_allowance, bonus,
               insurance_deduction, tax_deduction, absence_deduction, net_salary
        FROM payroll_records
        WHERE employee_id = ? AND month = ? AND year = ?
        """,
        emp_id, month, year,
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify(None)

    return jsonify({
        "basic_salary": float(row.basic_salary),
        "transport_allowance": float(row.transport_allowance),
        "housing_allowance": float(row.housing_allowance),
        "bonus": float(row.bonus),
        "insurance_deduction": float(row.insurance_deduction),
        "tax_deduction": float(row.tax_deduction),
        "absence_deduction": float(row.absence_deduction),
        "net_salary": float(row.net_salary),
    })


@app.route("/api/admin/payroll", methods=["POST"])
@admin_required
def admin_save_payroll():
    data = request.get_json()

    emp_id = data.get("employee_id")
    month = data.get("month")
    year = data.get("year")

    if not emp_id or not month or not year:
        return jsonify({"error": "لازم تحدد الموظف والشهر والسنة"}), 400

    basic_salary = data.get("basic_salary", 0)
    transport_allowance = data.get("transport_allowance", 0)
    housing_allowance = data.get("housing_allowance", 0)
    bonus = data.get("bonus", 0)
    insurance_deduction = data.get("insurance_deduction", 0)
    tax_deduction = data.get("tax_deduction", 0)
    absence_deduction = data.get("absence_deduction", 0)

    conn = get_connection()
    cursor = conn.cursor()

    # هل فيه سجل موجود أصلاً لنفس الموظف/الشهر/السنة؟
    cursor.execute(
        "SELECT id FROM payroll_records WHERE employee_id = ? AND month = ? AND year = ?",
        emp_id, month, year,
    )
    existing = cursor.fetchone()

    if existing:
        cursor.execute(
            """
            UPDATE payroll_records
            SET basic_salary = ?, transport_allowance = ?, housing_allowance = ?, bonus = ?,
                insurance_deduction = ?, tax_deduction = ?, absence_deduction = ?
            WHERE id = ?
            """,
            basic_salary, transport_allowance, housing_allowance, bonus,
            insurance_deduction, tax_deduction, absence_deduction,
            existing.id,
        )
        message = "تم تحديث سجل المرتب بنجاح"
    else:
        cursor.execute(
            """
            INSERT INTO payroll_records
                (employee_id, month, year, basic_salary, transport_allowance,
                 housing_allowance, bonus, insurance_deduction, tax_deduction, absence_deduction)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            emp_id, month, year, basic_salary, transport_allowance,
            housing_allowance, bonus, insurance_deduction, tax_deduction, absence_deduction,
        )
        message = "تم إضافة سجل المرتب بنجاح"

    conn.commit()
    conn.close()

    return jsonify({"message": message})


if __name__ == "__main__":
    # host="0.0.0.0" يخلي السيرفر متاح لأي جهاز على نفس الشبكة، مش بس جهازك
    app.run(debug=True, host="0.0.0.0", port=5000)
