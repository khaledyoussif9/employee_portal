"""
app.py
السيرفر الرئيسي. فيه:
  1) route لتسجيل الدخول (/api/login)
  2) route لجلب البيانات الإدارية (/api/employee/me)
  3) route لجلب شريط المرتب لشهر وسنة معينين (/api/payslip)

تشغيل السيرفر: python app.py
"""

import os
import re
import io
import bcrypt
import jwt
import datetime
import random
import secrets
import smtplib
import uuid
import threading
from email.mime.text import MIMEText
from functools import wraps
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
from PIL import Image, UnidentifiedImageError
from dotenv import load_dotenv

from db import get_connection
from pdf_generator import generate_payslip_pdf, generate_wage_record_pdf

load_dotenv()

app = Flask(__name__)
CORS(app)  # يسمح لصفحة الويب (Frontend) إنها تكلم السيرفر ده من دومين مختلف

# مجلد حفظ الملفات المرفقة مع الإشعارات (بيتعمل تلقائيًا لو مش موجود)
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}

ASSET_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(ASSET_FOLDER, exist_ok=True)

# صور الموظفين تحفظ باسم ثابت لكل موظف، ولا نحتاج لإضافة عمود جديد في قاعدة البيانات.
PROFILE_PHOTO_FOLDER = os.path.join(UPLOAD_FOLDER, "profile_photos")
os.makedirs(PROFILE_PHOTO_FOLDER, exist_ok=True)
MAX_PROFILE_PHOTO_BYTES = 2 * 1024 * 1024

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY غير مضبوط. أضفه إلى ملف .env أو متغيرات تشغيل السيرفر.")

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")


def send_email(to_address, subject, body):
    """
    بتبعت إيميل حقيقي عن طريق حساب Gmail (باستخدام App Password).
    لو حصل أي مشكلة في الإرسال، بترمي Exception ونمسكها في المكان اللي بنستخدمها فيه.
    """
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = to_address

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, [to_address], msg.as_string())


def log_action(admin_id, action_type, target_employee_id=None, details=None):
    """
    بتسجّل أي عملية إدارية حساسة في جدول audit_log (مين عمل إيه وإمتى).
    لو حصل أي خطأ في التسجيل نفسه، منوقفش العملية الأساسية بسببه - بس بنتجاهله بصمت.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO audit_log (admin_id, action_type, target_employee_id, details) VALUES (?, ?, ?, ?)",
            admin_id, action_type, target_employee_id, details,
        )
        conn.commit()
        conn.close()
    except Exception:
        pass


# ------------------------------------------------------------
# الصفحة الرئيسية: بتقدّم ملف employee_portal.html مباشرة
# ------------------------------------------------------------
@app.route("/")
def home():
    return send_from_directory(os.path.dirname(os.path.abspath(__file__)), "employee_portal.html")


@app.route("/assets/<path:filename>")
def serve_asset(filename):
    return send_from_directory(ASSET_FOLDER, filename)


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
        else:
            token = request.args.get("token")

        if not token:
            return jsonify({"error": "لازم تسجل الدخول الأول"}), 401

        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.employee_id = payload["employee_id"]
            request.role = payload.get("role", "employee")
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "انتهت صلاحية الجلسة، سجل دخول تاني"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "جلسة غير صالحة"}), 401

        return f(*args, **kwargs)
    return decorated


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

    cursor.execute(
        """
        SELECT u.id, u.password_hash, u.role, u.is_active, u.must_change_password,
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

    user_id, password_hash, role, is_active, must_change_password, employee_id, full_name, emp_code = row

    if not is_active:
        return jsonify({"error": "الحساب موقوف، راجع الموارد البشرية"}), 403

    password_correct = bcrypt.checkpw(
        password.encode("utf-8"), password_hash.encode("utf-8")
    )
    if not password_correct:
        return jsonify({"error": "كود الموظف أو كلمة المرور غير صحيحة"}), 401

    if must_change_password:
        return jsonify({
            "must_change_password": True,
            "employee_code": emp_code,
        })

    conn2 = get_connection()
    cursor2 = conn2.cursor()
    cursor2.execute("SELECT phone, national_id FROM employees WHERE id = ?", employee_id)
    contact_row = cursor2.fetchone()
    conn2.close()

    phone_valid = contact_row and contact_row.phone and re.fullmatch(r"\d{11}", contact_row.phone)
    national_id_valid = contact_row and contact_row.national_id and re.fullmatch(r"\d{14}", contact_row.national_id)

    if not phone_valid or not national_id_valid:
        return jsonify({
            "must_complete_profile": True,
            "employee_code": emp_code,
        })

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
# 1.5) الإعداد الإجباري لأول مرة
# ------------------------------------------------------------
@app.route("/api/first-login-setup", methods=["POST"])
def first_login_setup():
    data = request.get_json()
    employee_code = data.get("employee_code")
    old_password = data.get("old_password")
    new_password = data.get("new_password")
    email = (data.get("email") or "").strip().lower()

    if not employee_code or not old_password or not new_password or not email:
        return jsonify({"error": "من فضلك املأ كل الحقول"}), 400

    if "@" not in email:
        return jsonify({"error": "من فضلك ادخل بريد إلكتروني صحيح"}), 400

    if len(new_password) < 8:
        return jsonify({"error": "كلمة المرور الجديدة يجب ألا تقل عن 8 أحرف"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT u.id, u.password_hash, u.role,
               e.id AS employee_id, e.full_name, e.employee_code
        FROM users u
        JOIN employees e ON e.id = u.employee_id
        WHERE e.employee_code = ?
        """,
        employee_code,
    )
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return jsonify({"error": "بيانات غير صحيحة"}), 401

    old_password_correct = bcrypt.checkpw(
        old_password.encode("utf-8"), row.password_hash.encode("utf-8")
    )
    if not old_password_correct:
        conn.close()
        return jsonify({"error": "كلمة المرور الحالية غير صحيحة"}), 400

    new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    cursor.execute(
        "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
        new_hash, row.id,
    )
    cursor.execute(
        "UPDATE employees SET email = ? WHERE id = ?",
        email, row.employee_id,
    )
    conn.commit()
    conn.close()

    try:
        send_email(
            to_address=email,
            subject="تم تغيير كلمة المرور - بوابة الموظفين",
            body=(
                f"مرحبًا {row.full_name}،\n\n"
                "لقد تم تغيير كلمة المرور بنجاح.\n"
                "نتمنى لكم تجربة ممتعة.\n\n"
                "مسئول منظومة التطوير بالشركة\n"
                "خالد يوسف المنسي"
            ),
        )
    except Exception:
        pass

    conn3 = get_connection()
    cursor3 = conn3.cursor()
    cursor3.execute("SELECT phone, national_id FROM employees WHERE id = ?", row.employee_id)
    contact_row = cursor3.fetchone()
    conn3.close()

    phone_valid = contact_row and contact_row.phone and re.fullmatch(r"\d{11}", contact_row.phone)
    national_id_valid = contact_row and contact_row.national_id and re.fullmatch(r"\d{14}", contact_row.national_id)

    if not phone_valid or not national_id_valid:
        return jsonify({
            "must_complete_profile": True,
            "employee_code": row.employee_code,
        })

    token = jwt.encode(
        {
            "employee_id": row.employee_id,
            "role": row.role,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8),
        },
        SECRET_KEY,
        algorithm="HS256",
    )

    return jsonify({
        "token": token,
        "full_name": row.full_name,
        "role": row.role,
        "employee_code": row.employee_code,
    })


# ------------------------------------------------------------
# 1.6) إتمام البيانات الإجباري
# ------------------------------------------------------------
@app.route("/api/complete-profile", methods=["POST"])
def complete_profile():
    data = request.get_json()
    employee_code = data.get("employee_code")
    password = data.get("password")
    phone = (data.get("phone") or "").strip()
    national_id = (data.get("national_id") or "").strip()

    if not employee_code or not password or not phone or not national_id:
        return jsonify({"error": "من فضلك املأ كل الحقول"}), 400

    if not re.fullmatch(r"\d{11}", phone):
        return jsonify({"error": "رقم الهاتف لازم يكون 11 رقم بالظبط، أرقام فقط"}), 400

    if not re.fullmatch(r"\d{14}", national_id):
        return jsonify({"error": "الرقم القومي لازم يكون 14 رقم بالظبط، أرقام فقط"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT u.password_hash, u.role,
               e.id AS employee_id, e.full_name, e.employee_code
        FROM users u
        JOIN employees e ON e.id = u.employee_id
        WHERE e.employee_code = ?
        """,
        employee_code,
    )
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return jsonify({"error": "بيانات غير صحيحة"}), 401

    password_correct = bcrypt.checkpw(password.encode("utf-8"), row.password_hash.encode("utf-8"))
    if not password_correct:
        conn.close()
        return jsonify({"error": "كلمة المرور غير صحيحة"}), 401

    cursor.execute(
        "UPDATE employees SET phone = ?, national_id = ? WHERE id = ?",
        phone, national_id, row.employee_id,
    )
    conn.commit()
    conn.close()

    token = jwt.encode(
        {
            "employee_id": row.employee_id,
            "role": row.role,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8),
        },
        SECRET_KEY,
        algorithm="HS256",
    )

    return jsonify({
        "token": token,
        "full_name": row.full_name,
        "role": row.role,
        "employee_code": row.employee_code,
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
               e.phone, e.status, e.insurance_number, e.email, d.name AS department_name
        FROM employees e
        LEFT JOIN departments d ON d.id = e.department_id
        WHERE e.id = ?
        """,
        request.employee_id,
    )
    row = cursor.fetchone()
    conn.close()

    if row is None:
        return jsonify({"error": "الموظف غير موجود"}), 404

    photo_filename = f"employee_{request.employee_id}.jpg"
    photo_path = os.path.join(PROFILE_PHOTO_FOLDER, photo_filename)

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
        "email": row.email,
        "photo_url": f"/uploads/profile_photos/{photo_filename}" if os.path.isfile(photo_path) else None,
    })


# ------------------------------------------------------------
# 2.5) الموظف يسجّل/يعدّل بريده الإلكتروني بنفسه
# ------------------------------------------------------------
@app.route("/api/employee/email", methods=["PUT"])
@token_required
def update_my_email():
    data = request.get_json()
    email = (data.get("email") or "").strip().lower()

    if not email or "@" not in email:
        return jsonify({"error": "من فضلك ادخل بريد إلكتروني صحيح"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE employees SET email = ? WHERE id = ?",
        email, request.employee_id,
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "تم حفظ البريد الإلكتروني بنجاح", "email": email})


# ------------------------------------------------------------
# 2.6) الموظف يعدّل رقم الهاتف والرقم القومي بتاعه بنفسه
# ------------------------------------------------------------
@app.route("/api/employee/contact-info", methods=["PUT"])
@token_required
def update_my_contact_info():
    data = request.get_json()
    phone = (data.get("phone") or "").strip()
    national_id = (data.get("national_id") or "").strip()

    if not phone or not national_id:
        return jsonify({"error": "رقم الهاتف والرقم القومي مطلوبين، مينفعش يفضلوا فاضيين"}), 400

    if not re.fullmatch(r"\d{11}", phone):
        return jsonify({"error": "رقم الهاتف لازم يكون 11 رقم بالظبط، أرقام فقط"}), 400

    if not re.fullmatch(r"\d{14}", national_id):
        return jsonify({"error": "الرقم القومي لازم يكون 14 رقم بالظبط، أرقام فقط"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE employees SET phone = ?, national_id = ? WHERE id = ?",
        phone, national_id, request.employee_id,
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "تم حفظ البيانات بنجاح", "phone": phone, "national_id": national_id})


# ------------------------------------------------------------
# 2.7) رفع وعرض صورة الموظف الشخصية
# ------------------------------------------------------------
@app.route("/api/employee/photo", methods=["POST"])
@token_required
def upload_my_photo():
    photo = request.files.get("photo")
    if photo is None or not photo.filename:
        return jsonify({"error": "من فضلك اختر صورة"}), 400

    raw = photo.read(MAX_PROFILE_PHOTO_BYTES + 1)
    if len(raw) > MAX_PROFILE_PHOTO_BYTES:
        return jsonify({"error": "حجم الصورة يجب ألا يزيد عن 2MB"}), 413

    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image = image.convert("RGB")
            image.thumbnail((1000, 1000))
            filename = f"employee_{request.employee_id}.jpg"
            filepath = os.path.join(PROFILE_PHOTO_FOLDER, filename)
            image.save(filepath, format="JPEG", quality=88, optimize=True)
    except (UnidentifiedImageError, OSError, ValueError):
        return jsonify({"error": "الملف المرفوع ليس صورة صالحة"}), 400

    return jsonify({
        "message": "تم رفع الصورة بنجاح",
        "photo_url": f"/uploads/profile_photos/{filename}",
    })


# ------------------------------------------------------------
# 3) شريط المرتب لشهر وسنة معينين
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

    cursor.execute("SELECT code_sarf FROM employees WHERE id = ?", request.employee_id)
    code_sarf_row = cursor.fetchone()
    code_sarf = code_sarf_row.code_sarf if code_sarf_row else None

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
# 3.5) سجل الأجور: الصرفيات الإضافية
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


MONTHS_AR = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
             "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]

PDF_TEMP_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_pdfs")
os.makedirs(PDF_TEMP_FOLDER, exist_ok=True)


@app.route("/api/payslip/pdf", methods=["GET"])
@token_required
def download_payslip_pdf():
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    if not month or not year:
        return jsonify({"error": "لازم تحدد الشهر والسنة"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT full_name, employee_code, code_sarf FROM employees WHERE id = ?",
        request.employee_id,
    )
    emp_row = cursor.fetchone()
    if emp_row is None:
        conn.close()
        return jsonify({"error": "الموظف غير موجود"}), 404

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
        request.employee_id, month, year,
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return jsonify({"error": "لا يوجد سجل أجور لهذا الشهر"}), 404

    earnings = [(r.display_name or "بند غير مسمى", float(r.amount)) for r in rows if r.band_type == "earning"]
    deductions = [(r.display_name or "بند غير مسمى", float(r.amount)) for r in rows if r.band_type == "deduction"]
    net_salary = sum(a for _, a in earnings) - sum(a for _, a in deductions)

    filename = f"payslip_{emp_row.employee_code}_{year}_{month}_{uuid.uuid4().hex[:8]}.pdf"
    filepath = os.path.join(PDF_TEMP_FOLDER, filename)

    generate_payslip_pdf(
        filepath,
        employee_name=emp_row.full_name,
        employee_code=emp_row.employee_code,
        month_name=MONTHS_AR[month - 1],
        year=year,
        code_sarf=emp_row.code_sarf,
        earnings=earnings,
        deductions=deductions,
        net_salary=net_salary,
    )

    return send_file(filepath, as_attachment=True, download_name=f"شريط_المرتب_{MONTHS_AR[month-1]}_{year}.pdf")


@app.route("/api/wage-record/pdf", methods=["GET"])
@token_required
def download_wage_record_pdf():
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)

    if not month or not year:
        return jsonify({"error": "لازم تحدد الشهر والسنة"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT full_name, employee_code FROM employees WHERE id = ?",
        request.employee_id,
    )
    emp_row = cursor.fetchone()
    if emp_row is None:
        conn.close()
        return jsonify({"error": "الموظف غير موجود"}), 404

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
        request.employee_id, month, year,
    )
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        return jsonify({"error": "لا يوجد سجل أجور إضافي لهذا الشهر"}), 404

    grouped = {}
    for r in rows:
        grouped.setdefault(r.sarfia_no, {"earnings": [], "deductions": []})
        target = grouped[r.sarfia_no]["earnings"] if r.band_type == "earning" else grouped[r.sarfia_no]["deductions"]
        target.append((r.band_name or "بند غير مسمى", float(r.amount)))

    disbursements = []
    for sarfia_no in sorted(grouped.keys()):
        e = grouped[sarfia_no]["earnings"]
        d = grouped[sarfia_no]["deductions"]
        disbursements.append({
            "sarfia_no": sarfia_no,
            "earnings": e,
            "deductions": d,
            "net_salary": sum(a for _, a in e) - sum(a for _, a in d),
        })

    filename = f"wage_{emp_row.employee_code}_{year}_{month}_{uuid.uuid4().hex[:8]}.pdf"
    filepath = os.path.join(PDF_TEMP_FOLDER, filename)

    generate_wage_record_pdf(
        filepath,
        employee_name=emp_row.full_name,
        employee_code=emp_row.employee_code,
        month_name=MONTHS_AR[month - 1],
        year=year,
        disbursements=disbursements,
    )

    return send_file(filepath, as_attachment=True, download_name=f"سجل_الأجور_{MONTHS_AR[month-1]}_{year}.pdf")


# ------------------------------------------------------------
# نسيت كلمة المرور
# ------------------------------------------------------------
@app.route("/api/forgot-password", methods=["POST"])
def forgot_password():
    data = request.get_json()
    employee_code = data.get("employee_code")
    email = (data.get("email") or "").strip().lower()

    if not employee_code or not email:
        return jsonify({"error": "من فضلك ادخل كود الموظف والبريد الإلكتروني"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, email FROM employees WHERE employee_code = ?",
        employee_code,
    )
    row = cursor.fetchone()

    if row is None or (row.email or "").strip().lower() != email:
        conn.close()
        return jsonify({"error": "البيانات المدخلة غير صحيحة"}), 400

    employee_id = row.id

    code = str(random.randint(100000, 999999))
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)

    cursor.execute(
        "INSERT INTO password_resets (employee_id, code, expires_at) VALUES (?, ?, ?)",
        employee_id, code, expires_at,
    )
    conn.commit()
    conn.close()

    try:
        send_email(
            to_address=email,
            subject="كود إعادة تعيين كلمة المرور - بوابة الموظفين",
            body=f"كود التحقق بتاعك هو: {code}\n\nالكود صالح لمدة 10 دقائق فقط.\nلو محدش طلب الكود ده، تجاهل الرسالة دي.",
        )
    except Exception as e:
        return jsonify({"error": "حصل خطأ أثناء إرسال الإيميل، حاول تاني بعدين"}), 500

    return jsonify({
        "message": "تم إرسال كود التحقق على بريدك الإلكتروني",
    })


@app.route("/api/reset-password", methods=["POST"])
def reset_password():
    data = request.get_json()
    employee_code = data.get("employee_code")
    code = data.get("code")
    new_password = data.get("new_password")

    if not employee_code or not code or not new_password:
        return jsonify({"error": "بيانات ناقصة"}), 400

    if len(new_password) < 8:
        return jsonify({"error": "كلمة المرور يجب ألا تقل عن 8 أحرف"}), 400

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
        "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE employee_id = ?",
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
# تغيير كلمة المرور (للموظف وهو مسجل دخول بالفعل)
# ------------------------------------------------------------
@app.route("/api/change-password", methods=["POST"])
@token_required
def change_password():
    data = request.get_json()
    old_password = data.get("old_password")
    new_password = data.get("new_password")

    if not old_password or not new_password:
        return jsonify({"error": "من فضلك املأ كل الحقول"}), 400

    if len(new_password) < 8:
        return jsonify({"error": "كلمة المرور الجديدة يجب ألا تقل عن 8 أحرف"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT password_hash FROM users WHERE employee_id = ?",
        request.employee_id,
    )
    row = cursor.fetchone()

    if row is None:
        conn.close()
        return jsonify({"error": "الحساب غير موجود"}), 404

    old_password_correct = bcrypt.checkpw(
        old_password.encode("utf-8"), row.password_hash.encode("utf-8")
    )
    if not old_password_correct:
        conn.close()
        return jsonify({"error": "كلمة المرور الحالية غير صحيحة"}), 400

    new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    cursor.execute(
        "UPDATE users SET password_hash = ?, must_change_password = 0 WHERE employee_id = ?",
        new_hash, request.employee_id,
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "تم تغيير كلمة المرور بنجاح"})


# ------------------------------------------------------------
# 4) [إداري] البحث عن موظف بالكود أو الاسم
# ------------------------------------------------------------
@app.route("/api/admin/employees", methods=["GET"])
@admin_required
def admin_search_employees():
    search = request.args.get("search", "").strip()
    if not search:
        return jsonify({"error": "اكتب كود أو اسم للبحث"}), 400

    conn = get_connection()
    cursor = conn.cursor()

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
               e.national_id, e.phone, e.status, e.department_id, e.email, d.name AS department_name
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
        "email": row.email,
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

    log_action(
        admin_id=request.employee_id,
        action_type="update_employee",
        target_employee_id=emp_id,
        details=f"full_name={data.get('full_name')}, job_title={data.get('job_title')}, phone={data.get('phone')}, status={data.get('status')}",
    )

    return jsonify({"message": "تم تحديث البيانات بنجاح"})


# ------------------------------------------------------------
# 5.5) [إداري] تغيير/إعادة تعيين كلمة مرور أي موظف مباشرة من لوحة المدير
# ------------------------------------------------------------
@app.route("/api/admin/employees/<int:emp_id>/reset-password", methods=["POST"])
@admin_required
def admin_reset_password(emp_id):
    data = request.get_json() or {}
    new_password = data.get("new_password") or secrets.token_urlsafe(9)

    if len(new_password) < 8:
        return jsonify({"error": "كلمة المرور يجب ألا تقل عن 8 أحرف"}), 400

    new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT email, full_name FROM employees WHERE id = ?", emp_id)
    emp_row = cursor.fetchone()

    cursor.execute(
        "UPDATE users SET password_hash = ?, must_change_password = 1 WHERE employee_id = ?",
        new_hash, emp_id,
    )
    conn.commit()
    updated = cursor.rowcount
    conn.close()

    if updated == 0:
        return jsonify({"error": "الموظف غير موجود أو معندوش حساب دخول"}), 404

    email_sent = False
    if emp_row and emp_row.email:
        try:
            send_email(
                to_address=emp_row.email,
                subject="إعادة تعيين كلمة المرور - بوابة الموظفين",
                body=(
                    f"مرحبًا {emp_row.full_name}،\n\n"
                    f"تم إعادة تعيين كلمة المرور الخاصة بك.\n"
                    f"كلمة المرور الجديدة: {new_password}\n\n"
                    "ننصحك بتغييرها بعد أول تسجيل دخول.\n\n"
                    "مسئول منظومة التطوير بالشركة\n"
                    "خالد يوسف المنسي"
                ),
            )
            email_sent = True
        except Exception:
            email_sent = False

    log_action(
        admin_id=request.employee_id,
        action_type="reset_password",
        target_employee_id=emp_id,
        details=f"email_sent={email_sent}",
    )

    return jsonify({
        "message": "تم تغيير كلمة المرور بنجاح" + (" وتم إرسالها على إيميل الموظف" if email_sent else " (الموظف معندوش إيميل مسجل، لازم تبلّغه يدويًا)"),
        "new_password": new_password,
        "email_sent": email_sent,
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

    log_action(
        admin_id=request.employee_id,
        action_type="save_payroll",
        target_employee_id=emp_id,
        details=f"month={month}, year={year}, basic={basic_salary}, transport={transport_allowance}, housing={housing_allowance}, bonus={bonus}, insurance={insurance_deduction}, tax={tax_deduction}, absence={absence_deduction}",
    )

    return jsonify({"message": message})


# ------------------------------------------------------------
# 7) الإشعارات (لوحة إعلانات المسؤول لكل الموظفين)
# ------------------------------------------------------------

def _send_announcement_emails_bg(title, body, recipients):
    """
    بترسل إيميلات الإشعار في Thread منفصل بالخلفية،
    عشان الـ API يرجع رد سريع للأدمن من غير ما ينتظر كل الإيميلات.
    لو إيميل واحد فشل، بتكمل الباقي عادي.
    """
    for email, name in recipients:
        try:
            send_email(
                to_address=email,
                subject=f"إشعار جديد - {title}",
                body=(
                    f"مرحبًا {name}،\n\n"
                    f"{title}\n\n"
                    f"{body}\n\n"
                    "يمكنك مراجعة الإشعار بالتفصيل من بوابة الموظفين.\n\n"
                    "مسئول منظومة التطوير بالشركة\n"
                    "خالد يوسف المنسي"
                ),
            )
        except Exception:
            continue


@app.route("/api/admin/announcements", methods=["POST"])
@admin_required
def admin_create_announcement():
    title = request.form.get("title")
    body = request.form.get("body", "")
    target_employee_code = (request.form.get("target_employee_code") or "").strip()

    if not title:
        return jsonify({"error": "العنوان مطلوب"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    target_employee_id = None
    if target_employee_code:
        cursor.execute("SELECT id FROM employees WHERE employee_code = ?", target_employee_code)
        target_row = cursor.fetchone()
        if target_row is None:
            conn.close()
            return jsonify({"error": "كود الموظف المحدد مش موجود"}), 400
        target_employee_id = target_row.id

    saved_file_name = None
    original_name = None

    file = request.files.get("file")
    if file and file.filename:
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            conn.close()
            return jsonify({"error": "الملف لازم يكون PDF أو صورة (png/jpg) بس"}), 400
        original_name = secure_filename(file.filename)
        saved_file_name = f"{uuid.uuid4().hex}.{ext}"
        file.save(os.path.join(UPLOAD_FOLDER, saved_file_name))

    cursor.execute(
        "INSERT INTO announcements (title, body, file_name, original_name, target_employee_id) VALUES (?, ?, ?, ?, ?)",
        title, body, saved_file_name, original_name, target_employee_id,
    )
    conn.commit()

    # ---- تجهيز قائمة مستلمين الإيميل ----
    if target_employee_id:
        cursor.execute("SELECT email, full_name FROM employees WHERE id = ?", target_employee_id)
        r = cursor.fetchone()
        recipients = [(r.email, r.full_name)] if (r and r.email) else []
    else:
        # إشعار عام: كل الموظفين السارين اللي عندهم إيميل مسجل
        # ⚠️ لو العدد كبير، Gmail العادي بيحدد الإرسال بحوالي 500 إيميل/يوم
        cursor.execute(
            "SELECT email, full_name FROM employees WHERE email IS NOT NULL AND email <> '' AND status = 'active'"
        )
        recipients = [(r.email, r.full_name) for r in cursor.fetchall()]

    conn.close()

    if recipients:
        threading.Thread(
            target=_send_announcement_emails_bg,
            args=(title, body, recipients),
            daemon=True,
        ).start()

    return jsonify({
        "message": "تم إرسال الإشعار لموظف محدد بنجاح" if target_employee_id else "تم نشر الإشعار لكل الموظفين بنجاح",
        "emails_queued": len(recipients),
    })


@app.route("/api/announcements", methods=["GET"])
@token_required
def get_announcements():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.id, a.title, a.body, a.original_name, a.file_name, a.created_at,
               CASE WHEN ar.employee_id IS NULL THEN 0 ELSE 1 END AS is_read,
               CASE WHEN al.employee_id IS NULL THEN 0 ELSE 1 END AS is_liked,
               (SELECT COUNT(*) FROM announcement_likes WHERE announcement_id = a.id) AS like_count
        FROM announcements a
        LEFT JOIN announcement_reads ar
            ON ar.announcement_id = a.id AND ar.employee_id = ?
        LEFT JOIN announcement_likes al
            ON al.announcement_id = a.id AND al.employee_id = ?
        WHERE a.target_employee_id IS NULL OR a.target_employee_id = ?
        ORDER BY a.created_at DESC
        """,
        request.employee_id, request.employee_id, request.employee_id,
    )
    rows = cursor.fetchall()
    conn.close()

    return jsonify([
        {
            "id": r.id,
            "title": r.title,
            "body": r.body,
            "file_name": r.file_name,
            "original_name": r.original_name,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
            "is_read": bool(r.is_read),
            "is_liked": bool(r.is_liked),
            "like_count": r.like_count,
        }
        for r in rows
    ])


@app.route("/api/announcements/<int:ann_id>/like", methods=["POST"])
@token_required
def toggle_announcement_like(ann_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM announcement_likes WHERE employee_id = ? AND announcement_id = ?",
        request.employee_id, ann_id,
    )
    already_liked = cursor.fetchone() is not None

    if already_liked:
        cursor.execute(
            "DELETE FROM announcement_likes WHERE employee_id = ? AND announcement_id = ?",
            request.employee_id, ann_id,
        )
    else:
        cursor.execute(
            "INSERT INTO announcement_likes (employee_id, announcement_id) VALUES (?, ?)",
            request.employee_id, ann_id,
        )
    conn.commit()

    cursor.execute("SELECT COUNT(*) AS c FROM announcement_likes WHERE announcement_id = ?", ann_id)
    like_count = cursor.fetchone().c
    conn.close()

    return jsonify({"is_liked": not already_liked, "like_count": like_count})


@app.route("/api/admin/announcements/<int:ann_id>", methods=["DELETE"])
@admin_required
def admin_delete_announcement(ann_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT file_name FROM announcements WHERE id = ?", ann_id)
    row = cursor.fetchone()

    cursor.execute("DELETE FROM announcements WHERE id = ?", ann_id)
    conn.commit()
    conn.close()

    if row and row.file_name:
        try:
            os.remove(os.path.join(UPLOAD_FOLDER, row.file_name))
        except OSError:
            pass

    log_action(admin_id=request.employee_id, action_type="delete_announcement", details=f"announcement_id={ann_id}")

    return jsonify({"message": "تم حذف الإشعار"})


@app.route("/api/admin/announcements/list", methods=["GET"])
@admin_required
def admin_list_announcements():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT a.id, a.title, a.body, a.created_at, a.target_employee_id, e.full_name AS target_name,
               (SELECT COUNT(*) FROM announcement_likes WHERE announcement_id = a.id) AS like_count
        FROM announcements a
        LEFT JOIN employees e ON e.id = a.target_employee_id
        ORDER BY a.created_at DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()

    return jsonify([
        {
            "id": r.id,
            "title": r.title,
            "body": r.body,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
            "target_name": r.target_name,
            "like_count": r.like_count,
        }
        for r in rows
    ])


@app.route("/api/announcements/<int:ann_id>/read", methods=["POST"])
@token_required
def mark_announcement_read(ann_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        IF NOT EXISTS (SELECT 1 FROM announcement_reads WHERE employee_id = ? AND announcement_id = ?)
        INSERT INTO announcement_reads (employee_id, announcement_id) VALUES (?, ?)
        """,
        request.employee_id, ann_id, request.employee_id, ann_id,
    )
    conn.commit()
    conn.close()
    return jsonify({"message": "تم"})


@app.route("/uploads/<path:filename>")
@token_required
def download_announcement_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ------------------------------------------------------------
# 8) صندوق تواصل الموظفين مع المسؤول - نظام محادثة مستمرة
#    (محادثة واحدة لكل موظف، رد ورد تاني من غير حد أقصى)
# ------------------------------------------------------------

@app.route("/api/messages", methods=["POST"])
@token_required
def send_message_to_admin():
    data = request.get_json()
    message = (data.get("message") or "").strip()

    if not message:
        return jsonify({"error": "من فضلك اكتب رسالة"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    # هات محادثة الموظف لو موجودة، أو اعملها لو أول مرة
    cursor.execute("SELECT id FROM message_threads WHERE employee_id = ?", request.employee_id)
    trow = cursor.fetchone()
    if trow:
        thread_id = trow.id
    else:
        cursor.execute(
            "INSERT INTO message_threads (employee_id) OUTPUT INSERTED.id VALUES (?)",
            request.employee_id,
        )
        thread_id = cursor.fetchone()[0]

    cursor.execute(
        """
        INSERT INTO thread_messages (thread_id, sender_role, body, read_by_admin, read_by_employee)
        VALUES (?, 'employee', ?, 0, 1)
        """,
        thread_id, message,
    )
    cursor.execute("UPDATE message_threads SET updated_at = GETDATE() WHERE id = ?", thread_id)
    conn.commit()
    conn.close()

    return jsonify({"message": "تم إرسال رسالتك بنجاح"})


@app.route("/api/messages/my", methods=["GET"])
@token_required
def get_my_thread():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM message_threads WHERE employee_id = ?", request.employee_id)
    trow = cursor.fetchone()
    if trow is None:
        conn.close()
        return jsonify({"messages": []})

    thread_id = trow.id
    cursor.execute(
        """
        SELECT id, sender_role, body, created_at
        FROM thread_messages
        WHERE thread_id = ?
        ORDER BY created_at ASC
        """,
        thread_id,
    )
    rows = cursor.fetchall()

    # يعلّم رسائل الأدمن كمقروءة بمجرد ما الموظف يفتح المحادثة
    cursor.execute(
        "UPDATE thread_messages SET read_by_employee = 1 WHERE thread_id = ? AND sender_role = 'admin'",
        thread_id,
    )
    conn.commit()
    conn.close()

    return jsonify({
        "messages": [
            {
                "id": r.id,
                "sender_role": r.sender_role,
                "body": r.body,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for r in rows
        ]
    })


@app.route("/api/admin/messages", methods=["GET"])
@admin_required
def admin_list_threads():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT t.id AS thread_id, e.id AS employee_id, e.employee_code, e.full_name, t.updated_at,
               (SELECT TOP 1 body FROM thread_messages WHERE thread_id = t.id ORDER BY created_at DESC) AS last_body,
               (SELECT TOP 1 sender_role FROM thread_messages WHERE thread_id = t.id ORDER BY created_at DESC) AS last_sender,
               (SELECT COUNT(*) FROM thread_messages WHERE thread_id = t.id AND sender_role = 'employee' AND read_by_admin = 0) AS unread_count
        FROM message_threads t
        JOIN employees e ON e.id = t.employee_id
        ORDER BY t.updated_at DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()

    return jsonify([
        {
            "thread_id": r.thread_id,
            "employee_id": r.employee_id,
            "employee_code": r.employee_code,
            "full_name": r.full_name,
            "updated_at": r.updated_at.strftime("%Y-%m-%d %H:%M"),
            "last_body": r.last_body,
            "last_sender": r.last_sender,
            "unread_count": r.unread_count,
        }
        for r in rows
    ])


@app.route("/api/admin/messages/<int:thread_id>", methods=["GET"])
@admin_required
def admin_get_thread(thread_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT t.id, e.employee_code, e.full_name
        FROM message_threads t
        JOIN employees e ON e.id = t.employee_id
        WHERE t.id = ?
        """,
        thread_id,
    )
    trow = cursor.fetchone()
    if trow is None:
        conn.close()
        return jsonify({"error": "المحادثة غير موجودة"}), 404

    cursor.execute(
        "SELECT id, sender_role, body, created_at FROM thread_messages WHERE thread_id = ? ORDER BY created_at ASC",
        thread_id,
    )
    rows = cursor.fetchall()

    cursor.execute(
        "UPDATE thread_messages SET read_by_admin = 1 WHERE thread_id = ? AND sender_role = 'employee'",
        thread_id,
    )
    conn.commit()
    conn.close()

    return jsonify({
        "employee_code": trow.employee_code,
        "full_name": trow.full_name,
        "messages": [
            {
                "id": r.id,
                "sender_role": r.sender_role,
                "body": r.body,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
            }
            for r in rows
        ],
    })


@app.route("/api/admin/messages/<int:thread_id>/messages/<int:message_id>", methods=["DELETE"])
@admin_required
def admin_delete_thread_message(thread_id, message_id):
    """يحذف المسؤول رسالة واحدة فقط من المحادثة، وتختفي عند الطرفين."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT employee_id FROM message_threads WHERE id = ?",
        thread_id,
    )
    thread = cursor.fetchone()
    if thread is None:
        conn.close()
        return jsonify({"error": "المحادثة غير موجودة"}), 404

    cursor.execute(
        "DELETE FROM thread_messages WHERE id = ? AND thread_id = ?",
        message_id, thread_id,
    )
    deleted = cursor.rowcount
    if deleted == 0:
        conn.close()
        return jsonify({"error": "الرسالة غير موجودة داخل هذه المحادثة"}), 404

    cursor.execute(
        """
        UPDATE message_threads
        SET updated_at = COALESCE(
            (SELECT MAX(created_at) FROM thread_messages WHERE thread_id = ?),
            GETDATE()
        )
        WHERE id = ?
        """,
        thread_id, thread_id,
    )
    conn.commit()
    conn.close()

    log_action(
        admin_id=request.employee_id,
        action_type="delete_thread_message",
        target_employee_id=thread.employee_id,
        details=f"thread_id={thread_id}, message_id={message_id}",
    )
    return jsonify({"message": "تم حذف الرسالة من المحادثة للطرفين"})


@app.route("/api/admin/messages/<int:thread_id>", methods=["DELETE"])
@admin_required
def admin_delete_thread(thread_id):
    """يحذف المسؤول المحادثة ورسائلها بالكامل، فتختفي عند الطرفين."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT employee_id FROM message_threads WHERE id = ?",
        thread_id,
    )
    thread = cursor.fetchone()
    if thread is None:
        conn.close()
        return jsonify({"error": "المحادثة غير موجودة"}), 404

    cursor.execute("DELETE FROM thread_messages WHERE thread_id = ?", thread_id)
    cursor.execute("DELETE FROM message_threads WHERE id = ?", thread_id)
    conn.commit()
    conn.close()

    log_action(
        admin_id=request.employee_id,
        action_type="delete_message_thread",
        target_employee_id=thread.employee_id,
        details=f"thread_id={thread_id}",
    )
    return jsonify({"message": "تم حذف المحادثة بالكامل للطرفين"})


@app.route("/api/admin/messages/<int:thread_id>/reply", methods=["POST"])
@admin_required
def admin_reply_thread(thread_id):
    data = request.get_json()
    reply = (data.get("reply") or "").strip()

    if not reply:
        return jsonify({"error": "من فضلك اكتب نص الرد"}), 400

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT e.id AS employee_id, e.email, e.full_name
        FROM message_threads t
        JOIN employees e ON e.id = t.employee_id
        WHERE t.id = ?
        """,
        thread_id,
    )
    row = cursor.fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "المحادثة غير موجودة"}), 404

    cursor.execute(
        """
        INSERT INTO thread_messages (thread_id, sender_role, body, read_by_employee, read_by_admin)
        VALUES (?, 'admin', ?, 0, 1)
        """,
        thread_id, reply,
    )
    cursor.execute("UPDATE message_threads SET updated_at = GETDATE() WHERE id = ?", thread_id)
    conn.commit()
    conn.close()

    if row.email:
        try:
            send_email(
                to_address=row.email,
                subject="رد جديد على رسالتك - بوابة الموظفين",
                body=(
                    f"مرحبًا {row.full_name}،\n\n"
                    f"تم الرد على رسالتك:\n\n{reply}\n\n"
                    "تقدر تراجع المحادثة كاملة وترد تاني من صفحة 'تواصل معنا' على البوابة.\n\n"
                    "مسئول منظومة التطوير بالشركة\n"
                    "خالد يوسف المنسي"
                ),
            )
        except Exception:
            pass

    log_action(
        admin_id=request.employee_id,
        action_type="reply_thread",
        target_employee_id=row.employee_id,
        details=f"thread_id={thread_id}",
    )

    return jsonify({"message": "تم إرسال الرد بنجاح"})


# ------------------------------------------------------------
# 9) تقييم الخدمة (الموظف يقيّم من 1-5 نجوم + تعليق اختياري)
# ------------------------------------------------------------

@app.route("/api/service-rating", methods=["POST"])
@token_required
def submit_service_rating():
    data = request.get_json()
    rating = data.get("rating")
    comment = (data.get("comment") or "").strip()

    if not rating or not isinstance(rating, int) or rating < 1 or rating > 5:
        return jsonify({"error": "التقييم لازم يكون رقم من 1 لـ 5"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO service_ratings (employee_id, rating, comment) VALUES (?, ?, ?)",
        request.employee_id, rating, comment or None,
    )
    conn.commit()
    conn.close()

    return jsonify({"message": "شكرًا لتقييمك، رأيك يهمنا"})


@app.route("/api/service-rating/my", methods=["GET"])
@token_required
def get_my_service_ratings():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT rating, comment, created_at
        FROM service_ratings
        WHERE employee_id = ?
        ORDER BY created_at DESC
        """,
        request.employee_id,
    )
    rows = cursor.fetchall()
    conn.close()

    return jsonify([
        {
            "rating": r.rating,
            "comment": r.comment,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        for r in rows
    ])


@app.route("/api/admin/service-ratings", methods=["GET"])
@admin_required
def admin_list_service_ratings():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT sr.rating, sr.comment, sr.created_at, e.employee_code, e.full_name
        FROM service_ratings sr
        JOIN employees e ON e.id = sr.employee_id
        ORDER BY sr.created_at DESC
        """
    )
    rows = cursor.fetchall()

    cursor.execute("SELECT AVG(CAST(rating AS FLOAT)) AS avg_rating, COUNT(*) AS total FROM service_ratings")
    summary_row = cursor.fetchone()
    conn.close()

    return jsonify({
        "average": round(summary_row.avg_rating, 2) if summary_row.avg_rating else None,
        "total": summary_row.total,
        "ratings": [
            {
                "rating": r.rating,
                "comment": r.comment,
                "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
                "employee_code": r.employee_code,
                "full_name": r.full_name,
            }
            for r in rows
        ],
    })


# ------------------------------------------------------------
# 10) سجل التدقيق (Audit Log)
# ------------------------------------------------------------
@app.route("/api/admin/audit-log", methods=["GET"])
@admin_required
def admin_get_audit_log():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT TOP 200
               al.action_type, al.details, al.created_at,
               admin_e.full_name AS admin_name, admin_e.employee_code AS admin_code,
               target_e.full_name AS target_name, target_e.employee_code AS target_code
        FROM audit_log al
        JOIN employees admin_e ON admin_e.id = al.admin_id
        LEFT JOIN employees target_e ON target_e.id = al.target_employee_id
        ORDER BY al.created_at DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()

    action_labels = {
        "update_employee": "تعديل بيانات موظف",
        "reset_password": "إعادة تعيين كلمة مرور",
        "save_payroll": "حفظ/تعديل مرتب",
        "delete_announcement": "حذف إشعار",
        "reply_thread": "رد على محادثة موظف",
    }

    return jsonify([
        {
            "action_type": action_labels.get(r.action_type, r.action_type),
            "details": r.details,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
            "admin_name": r.admin_name,
            "admin_code": r.admin_code,
            "target_name": r.target_name,
            "target_code": r.target_code,
        }
        for r in rows
    ])


if __name__ == "__main__":
    # host="0.0.0.0" يخلي السيرفر متاح لأي جهاز على نفس الشبكة، مش بس جهازك
    debug_enabled = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_enabled, host="0.0.0.0", port=5000)
