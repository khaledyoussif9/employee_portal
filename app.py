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
import time
import json
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from functools import wraps

# Passkeys / WebAuthn
try:
    from webauthn import (
        generate_registration_options, verify_registration_response,
        generate_authentication_options, verify_authentication_response,
        options_to_json,
    )
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria, ResidentKeyRequirement,
        UserVerificationRequirement,
    )
    WEBAUTHN_AVAILABLE = True
except ImportError:
    WEBAUTHN_AVAILABLE = False
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
APP_STARTED_AT = time.time()

SARFIA_DATABASE = os.getenv("SARFIA_DATABASE", "human_r_ash")
if not re.fullmatch(r"[A-Za-z0-9_]+", SARFIA_DATABASE):
    raise RuntimeError("SARFIA_DATABASE يحتوي اسم قاعدة بيانات غير صالح")
HR_DATABASE = os.getenv("HR_DATABASE", SARFIA_DATABASE)
if not re.fullmatch(r"[A-Za-z0-9_]+", HR_DATABASE):
    raise RuntimeError("HR_DATABASE يحتوي اسم قاعدة بيانات غير صالح")

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

# حساب عرض افتراضي لا يرتبط بأي موظف أو بيانات حقيقية في قاعدة البيانات.
DEMO_EMPLOYEE_CODE = os.getenv("DEMO_EMPLOYEE_CODE", "11092026")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "11092026")
DEMO_EMPLOYEE_ID = 0


def birth_date_from_national_id(national_id):
    """يستخرج تاريخ الميلاد من الرقم القومي المصري بعد التحقق من صلاحيته."""
    value = str(national_id or "").strip()
    if not (value.isdigit() and len(value) == 14 and value[0] in "23"):
        return None
    century = 1900 if value[0] == "2" else 2000
    try:
        return datetime.date(century + int(value[1:3]), int(value[3:5]), int(value[5:7]))
    except ValueError:
        return None


def load_employee_birth_date(cursor, employee_code, national_id=None):
    """يقرأ تاريخ الميلاد الإداري، ويستخدم الرقم القومي فقط عند غيابه."""
    try:
        cursor.execute(
            f"""
            SELECT c.name AS column_name
            FROM [{HR_DATABASE}].sys.columns AS c
            INNER JOIN [{HR_DATABASE}].sys.tables AS t ON t.object_id = c.object_id
            INNER JOIN [{HR_DATABASE}].sys.schemas AS s ON s.schema_id = t.schema_id
            WHERE s.name = N'dbo'
              AND t.name = N'emply_details_old'
              AND LOWER(c.name) IN ('emp_no', 'emptid', 'employee_code', 'emp_code')
            """
        )
        available = {str(row.column_name).lower(): str(row.column_name) for row in cursor.fetchall()}
        for candidate in ("emp_no", "emptid", "employee_code", "emp_code"):
            column_name = available.get(candidate)
            if not column_name:
                continue
            cursor.execute(
                f"""
                SELECT TOP (1) BIRTHDATE
                FROM [{HR_DATABASE}].[dbo].[emply_details_old]
                WHERE TRY_CONVERT(NVARCHAR(50), [{column_name}]) = ?
                  AND BIRTHDATE IS NOT NULL
                """,
                str(employee_code),
            )
            row = cursor.fetchone()
            if row and row.BIRTHDATE:
                value = row.BIRTHDATE
                return value.date() if isinstance(value, datetime.datetime) else value
    except Exception:
        # لا نوقف البيانات الإدارية أو تسجيل الدخول إذا تعذر المصدر القديم.
        pass
    return birth_date_from_national_id(national_id)

def _loan_key(name):
    """اسم موحّد لربط بند القسط ببند الرصيد المقابل له."""
    value = re.sub(r"(?:قسط|رصيد|المتبقي|متبقى|متبقي|باقي)", " ", name or "", flags=re.IGNORECASE)
    return re.sub(r"[^\w\u0600-\u06ff]+", "", value).lower()


def attach_installment_balances(items):
    """يدمج بنود الرصيد مع الأقساط دون إدخال الرصيد في إجمالي الاستقطاعات."""
    balances = [item for item in items if "رصيد" in (item.get("name") or "")]
    visible_items = [item for item in items if item not in balances]
    unmatched = balances.copy()

    for item in visible_items:
        if "قسط" not in (item.get("name") or ""):
            continue

        key = _loan_key(item.get("name"))
        match = next((b for b in unmatched if key and _loan_key(b.get("name")) == key), None)
        if match is None and len(unmatched) == 1:
            match = unmatched[0]
        if match is not None:
            item["balance"] = float(match.get("amount") or 0)
            unmatched.remove(match)

    # لو تعذر الربط، نظهر الرصيد كبند معلومات مستقل بدل فقده.
    visible_items.extend({**item, "type": "balance"} for item in unmatched)
    return visible_items


def load_sarfia_names(cursor, month, year):
    """يحدّث دليل الصرفيات المحلي ثم يقرأه، مع استمرار الخدمة عند تعذر المصدر."""
    cursor.execute(
        """
        IF OBJECT_ID(N'dbo.payroll_sarfia_names', N'U') IS NULL
        BEGIN
            CREATE TABLE dbo.payroll_sarfia_names (
                id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                sarfia_no INT NOT NULL,
                sarfia_month TINYINT NOT NULL,
                sarfia_year SMALLINT NOT NULL,
                sarfia_desc_id INT NULL,
                sarfia_name NVARCHAR(250) NOT NULL,
                updated_at DATETIME2 NOT NULL
                    CONSTRAINT DF_payroll_sarfia_names_updated_at DEFAULT SYSDATETIME(),
                CONSTRAINT UQ_payroll_sarfia_names
                    UNIQUE (sarfia_no, sarfia_month, sarfia_year)
            );
        END
        """
    )
    cursor.connection.commit()

    try:
        cursor.execute(
            f"""
            ;WITH source_data AS (
                SELECT
                    s.Sarfia_no AS sarfia_no,
                    s.Sarfia_Month AS sarfia_month,
                    s.Sarfia_Year AS sarfia_year,
                    MAX(s.SarfiaDesc_ID) AS sarfia_desc_id,
                    MAX(CONVERT(NVARCHAR(250), NULLIF(LTRIM(RTRIM(d.SarfiaDesc_Desc)), '')))
                        AS sarfia_name
                FROM [{SARFIA_DATABASE}].[dbo].[Payroll_Sarfiat] AS s
                INNER JOIN [{SARFIA_DATABASE}].[dbo].[payroll_SarfiaDesc] AS d
                    ON d.SarfiaDesc_ID = s.SarfiaDesc_ID
                WHERE s.Sarfia_Month = ? AND s.Sarfia_Year = ?
                GROUP BY s.Sarfia_no, s.Sarfia_Month, s.Sarfia_Year
            )
            MERGE dbo.payroll_sarfia_names AS target
            USING source_data AS source
               ON target.sarfia_no = source.sarfia_no
              AND target.sarfia_month = source.sarfia_month
              AND target.sarfia_year = source.sarfia_year
            WHEN MATCHED AND source.sarfia_name IS NOT NULL THEN
                UPDATE SET
                    sarfia_desc_id = source.sarfia_desc_id,
                    sarfia_name = source.sarfia_name,
                    updated_at = SYSDATETIME()
            WHEN NOT MATCHED BY TARGET AND source.sarfia_name IS NOT NULL THEN
                INSERT (sarfia_no, sarfia_month, sarfia_year, sarfia_desc_id, sarfia_name)
                VALUES (source.sarfia_no, source.sarfia_month, source.sarfia_year,
                        source.sarfia_desc_id, source.sarfia_name);
            """,
            month, year,
        )
        cursor.connection.commit()
    except Exception:
        cursor.connection.rollback()

    cursor.execute(
        """
        SELECT sarfia_no AS Sarfia_no, sarfia_name
        FROM dbo.payroll_sarfia_names
        WHERE sarfia_month = ? AND sarfia_year = ?
        """,
        month, year,
    )
    return {
        int(row.Sarfia_no): (row.sarfia_name or "صرفية إضافية")
        for row in cursor.fetchall()
    }


def demo_payslip(month, year):
    """بيانات وهمية ثابتة تسمح بتجربة شريط المرتب بدون كشف بيانات حقيقية."""
    items = [
        {"name": "الأساسي", "type": "earning", "amount": 7250.00},
        {"name": "حافز أداء", "type": "earning", "amount": 1850.00},
        {"name": "بدل انتقال", "type": "earning", "amount": 650.00},
        {"name": "التأمينات الاجتماعية", "type": "deduction", "amount": 820.00},
        {"name": "ضريبة كسب العمل", "type": "deduction", "amount": 430.00},
        {"name": "قسط قرض", "type": "deduction", "amount": 600.00, "balance": 5400.00},
    ]
    earnings_total = sum(i["amount"] for i in items if i["type"] == "earning")
    deductions_total = sum(i["amount"] for i in items if i["type"] == "deduction")
    return {
        "month": month,
        "year": year,
        "source": "demo",
        "code_sarf": "DEMO",
        "items": items,
        "earnings_total": earnings_total,
        "deductions_total": deductions_total,
        "net_salary": earnings_total - deductions_total,
        "is_demo": True,
    }


def demo_wage_record(month, year):
    """صرفيات إضافية وهمية لحساب العرض."""
    items = [
        {"name": "مكافأة مجهود غير عادي", "type": "earning", "amount": 1200.00},
        {"name": "ضريبة كسب العمل", "type": "deduction", "amount": 120.00},
    ]
    earnings_total = sum(i["amount"] for i in items if i["type"] == "earning")
    deductions_total = sum(i["amount"] for i in items if i["type"] == "deduction")
    return {
        "month": month,
        "year": year,
        "disbursements": [{
            "sarfia_no": 2,
            "sarfia_name": "مكافأة مجهود غير عادي",
            "items": items,
            "earnings_total": earnings_total,
            "deductions_total": deductions_total,
            "net_salary": earnings_total - deductions_total,
        }],
        "is_demo": True,
    }


@app.before_request
def block_demo_writes():
    """حماية مركزية: حساب العرض لا ينفّذ أي عملية كتابة حتى باستدعاء API مباشر."""
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if request.path == "/api/login":
        return None

    auth_header = request.headers.get("Authorization", "")
    token = auth_header.split(" ", 1)[1] if auth_header.startswith("Bearer ") else request.args.get("token")
    if not token:
        return None

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None

    if payload.get("is_demo"):
        return jsonify({"error": "حساب العرض مخصص للاستعلام فقط ولا يسمح بحفظ أو تعديل البيانات"}), 403
    return None


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
    response = send_from_directory(os.path.dirname(os.path.abspath(__file__)), "employee_portal.html", max_age=0)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.route("/assets/<path:filename>")
def serve_asset(filename):
    response = send_from_directory(ASSET_FOLDER, filename, max_age=0)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return response


@app.route("/api/system-status", methods=["GET"])
def system_status():
    """حالة تشغيل عامة تستخدمها شاشة الدخول بدون الحاجة إلى تسجيل الدخول."""
    forced_status = os.getenv("SYSTEM_STATUS", "auto").strip().lower()
    if forced_status in {"maintenance", "improvements"}:
        return jsonify({"status": "maintenance", "message": "تحسينات جارية"})
    if forced_status in {"stopped", "offline"}:
        return jsonify({"status": "stopped", "message": "النظام متوقف مؤقتًا"}), 503

    monitored_files = (
        os.path.abspath(__file__),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "employee_portal.html"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "pdf_generator.py"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "db.py"),
    )
    has_pending_changes = any(
        os.path.isfile(path) and os.path.getmtime(path) > APP_STARTED_AT + 1
        for path in monitored_files
    )
    if has_pending_changes:
        return jsonify({"status": "maintenance", "message": "تحسينات جارية - أعد تشغيل السيرفر بعد الانتهاء"})
    return jsonify({"status": "operational", "message": "النظام يعمل بصورة طبيعية"})


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
            request.is_demo = bool(payload.get("is_demo", False))
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

    # حساب العرض افتراضي بالكامل ولا يحتاج سجلًا داخل قاعدة البيانات.
    if employee_code == DEMO_EMPLOYEE_CODE:
        if not secrets.compare_digest(password, DEMO_PASSWORD):
            return jsonify({"error": "كود الموظف أو كلمة المرور غير صحيحة"}), 401

        token = jwt.encode(
            {
                "employee_id": DEMO_EMPLOYEE_ID,
                "role": "viewer",
                "is_demo": True,
                "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=8),
            },
            SECRET_KEY,
            algorithm="HS256",
        )
        return jsonify({
            "token": token,
            "full_name": "خالد المنسي",
            "role": "viewer",
            "employee_code": DEMO_EMPLOYEE_CODE,
            "is_demo": True,
            "read_only": True,
        })

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
# 1.4) Passkeys / WebAuthn (بصمة / Windows Hello / Face ID)
# ------------------------------------------------------------
def _passkey_origin_and_rp():
    """يربط الـPasskey بالـhost الحالي. في الإنتاج استخدم دومين HTTPS ثابت."""
    host = request.host.split(":", 1)[0].strip().lower()
    forwarded_proto = (request.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip()
    scheme = forwarded_proto or request.scheme
    origin = f"{scheme}://{request.host}"
    return origin, host


def _ensure_passkey_tables(cursor):
    cursor.execute("""
        IF OBJECT_ID('dbo.user_passkeys','U') IS NULL
        BEGIN
            CREATE TABLE dbo.user_passkeys(
                id BIGINT IDENTITY(1,1) PRIMARY KEY,
                user_id INT NOT NULL,
                credential_id VARBINARY(1024) NOT NULL UNIQUE,
                public_key VARBINARY(MAX) NOT NULL,
                sign_count BIGINT NOT NULL CONSTRAINT DF_user_passkeys_sign_count DEFAULT(0),
                device_name NVARCHAR(200) NULL,
                rp_id NVARCHAR(255) NOT NULL,
                created_at DATETIME2 NOT NULL CONSTRAINT DF_user_passkeys_created_at DEFAULT(SYSDATETIME()),
                last_used_at DATETIME2 NULL,
                is_active BIT NOT NULL CONSTRAINT DF_user_passkeys_is_active DEFAULT(1),
                CONSTRAINT FK_user_passkeys_users FOREIGN KEY(user_id) REFERENCES dbo.users(id)
            );
            CREATE INDEX IX_user_passkeys_user ON dbo.user_passkeys(user_id, is_active);
        END
        IF OBJECT_ID('dbo.passkey_challenges','U') IS NULL
        BEGIN
            CREATE TABLE dbo.passkey_challenges(
                challenge_id VARCHAR(64) PRIMARY KEY,
                user_id INT NULL,
                challenge VARBINARY(256) NOT NULL,
                purpose VARCHAR(20) NOT NULL,
                rp_id NVARCHAR(255) NOT NULL,
                origin NVARCHAR(500) NOT NULL,
                expires_at DATETIME2 NOT NULL,
                created_at DATETIME2 NOT NULL CONSTRAINT DF_passkey_challenges_created_at DEFAULT(SYSDATETIME())
            );
            CREATE INDEX IX_passkey_challenges_expiry ON dbo.passkey_challenges(expires_at);
        END
    """)


def _passkey_user_id_for_employee(cursor, employee_id):
    cursor.execute("SELECT id FROM users WHERE employee_id = ? AND is_active = 1", employee_id)
    row = cursor.fetchone()
    return int(row.id) if row else None


@app.route('/api/passkeys/register/options', methods=['POST'])
@token_required
def passkey_register_options():
    if not WEBAUTHN_AVAILABLE:
        return jsonify({'error': 'مكتبة WebAuthn غير مثبتة على السيرفر'}), 503
    origin, rp_id = _passkey_origin_and_rp()
    conn = get_connection(); cur = conn.cursor()
    try:
        _ensure_passkey_tables(cur)
        user_id = _passkey_user_id_for_employee(cur, request.employee_id)
        if not user_id:
            return jsonify({'error': 'تعذر تحديد حساب المستخدم'}), 404
        cur.execute("SELECT full_name, employee_code FROM employees WHERE id = ?", request.employee_id)
        emp = cur.fetchone()
        opts = generate_registration_options(
            rp_id=rp_id,
            rp_name='المنظومة الإلكترونية الموحدة - منطقة الدلتا',
            user_id=str(user_id).encode('utf-8'),
            user_name=str(emp.employee_code),
            user_display_name=str(emp.full_name),
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.REQUIRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
        )
        cid = secrets.token_hex(24)
        cur.execute("DELETE FROM passkey_challenges WHERE expires_at < SYSDATETIME()")
        cur.execute("INSERT INTO passkey_challenges(challenge_id,user_id,challenge,purpose,rp_id,origin,expires_at) VALUES(?,?,?,?,?,?,DATEADD(MINUTE,5,SYSDATETIME()))",
                    cid, user_id, bytes(opts.challenge), 'register', rp_id, origin)
        conn.commit()
        return jsonify({'challenge_id': cid, 'options': json.loads(options_to_json(opts))})
    finally:
        conn.close()


@app.route('/api/passkeys/register/verify', methods=['POST'])
@token_required
def passkey_register_verify():
    if not WEBAUTHN_AVAILABLE:
        return jsonify({'error': 'مكتبة WebAuthn غير مثبتة على السيرفر'}), 503
    data = request.get_json(silent=True) or {}
    cid = str(data.get('challenge_id') or '')
    credential = data.get('credential')
    device_name = (data.get('device_name') or 'هذا الجهاز').strip()[:200]
    if not cid or not credential:
        return jsonify({'error': 'بيانات تفعيل البصمة غير مكتملة'}), 400
    conn = get_connection(); cur = conn.cursor()
    try:
        _ensure_passkey_tables(cur)
        user_id = _passkey_user_id_for_employee(cur, request.employee_id)
        cur.execute("SELECT challenge,rp_id,origin FROM passkey_challenges WHERE challenge_id=? AND user_id=? AND purpose='register' AND expires_at>=SYSDATETIME()", cid, user_id)
        ch = cur.fetchone()
        if not ch:
            return jsonify({'error': 'انتهت صلاحية طلب التفعيل؛ حاول مرة أخرى'}), 400
        result = verify_registration_response(
            credential=credential,
            expected_challenge=bytes(ch.challenge),
            expected_rp_id=str(ch.rp_id),
            expected_origin=str(ch.origin),
            require_user_verification=True,
        )
        cur.execute("SELECT 1 FROM user_passkeys WHERE credential_id=?", bytes(result.credential_id))
        if cur.fetchone():
            return jsonify({'error': 'هذه البصمة/Passkey مسجلة بالفعل'}), 409
        cur.execute("INSERT INTO user_passkeys(user_id,credential_id,public_key,sign_count,device_name,rp_id) VALUES(?,?,?,?,?,?)",
                    user_id, bytes(result.credential_id), bytes(result.credential_public_key), int(result.sign_count), device_name, str(ch.rp_id))
        cur.execute("DELETE FROM passkey_challenges WHERE challenge_id=?", cid)
        conn.commit()
        return jsonify({'success': True, 'message': 'تم تفعيل الدخول بالبصمة على هذا الموقع'})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'تعذر تفعيل البصمة: {str(e)}'}), 400
    finally:
        conn.close()


@app.route('/api/passkeys/auth/options', methods=['POST'])
def passkey_auth_options():
    if not WEBAUTHN_AVAILABLE:
        return jsonify({'error': 'مكتبة WebAuthn غير مثبتة على السيرفر'}), 503
    origin, rp_id = _passkey_origin_and_rp()
    conn = get_connection(); cur = conn.cursor()
    try:
        _ensure_passkey_tables(cur)
        cur.execute("SELECT COUNT(*) AS n FROM user_passkeys WHERE rp_id=? AND is_active=1", rp_id)
        if int(cur.fetchone().n) == 0:
            return jsonify({'error': 'لا توجد بصمة مفعلة لهذا الموقع حتى الآن'}), 404
        opts = generate_authentication_options(rp_id=rp_id, user_verification=UserVerificationRequirement.REQUIRED)
        cid = secrets.token_hex(24)
        cur.execute("DELETE FROM passkey_challenges WHERE expires_at < SYSDATETIME()")
        cur.execute("INSERT INTO passkey_challenges(challenge_id,user_id,challenge,purpose,rp_id,origin,expires_at) VALUES(?,NULL,?,'authenticate',?,?,DATEADD(MINUTE,5,SYSDATETIME()))",
                    cid, bytes(opts.challenge), rp_id, origin)
        conn.commit()
        return jsonify({'challenge_id': cid, 'options': json.loads(options_to_json(opts))})
    finally:
        conn.close()


@app.route('/api/passkeys/auth/verify', methods=['POST'])
def passkey_auth_verify():
    if not WEBAUTHN_AVAILABLE:
        return jsonify({'error': 'مكتبة WebAuthn غير مثبتة على السيرفر'}), 503
    data = request.get_json(silent=True) or {}
    cid = str(data.get('challenge_id') or '')
    credential = data.get('credential') or {}
    raw_id = credential.get('rawId') or credential.get('id')
    if not cid or not raw_id:
        return jsonify({'error': 'بيانات الدخول بالبصمة غير مكتملة'}), 400
    import base64
    pad = '=' * (-len(raw_id) % 4)
    try:
        credential_id = base64.urlsafe_b64decode(raw_id + pad)
    except Exception:
        return jsonify({'error': 'معرف البصمة غير صالح'}), 400
    conn = get_connection(); cur = conn.cursor()
    try:
        _ensure_passkey_tables(cur)
        cur.execute("SELECT challenge,rp_id,origin FROM passkey_challenges WHERE challenge_id=? AND purpose='authenticate' AND expires_at>=SYSDATETIME()", cid)
        ch = cur.fetchone()
        if not ch:
            return jsonify({'error': 'انتهت صلاحية محاولة الدخول؛ حاول مرة أخرى'}), 400
        cur.execute("""SELECT p.id,p.user_id,p.public_key,p.sign_count,u.role,u.is_active,e.id AS employee_id,e.full_name,e.employee_code,u.must_change_password,e.phone,e.national_id
                       FROM user_passkeys p JOIN users u ON u.id=p.user_id JOIN employees e ON e.id=u.employee_id
                       WHERE p.credential_id=? AND p.is_active=1 AND p.rp_id=?""", credential_id, str(ch.rp_id))
        row = cur.fetchone()
        if not row or not row.is_active:
            return jsonify({'error': 'البصمة غير مسجلة أو الحساب موقوف'}), 401
        if row.must_change_password:
            return jsonify({'error': 'يجب تسجيل الدخول بكلمة المرور وتغييرها أولًا'}), 403
        phone_ok = row.phone and re.fullmatch(r'\d{11}', str(row.phone))
        nid_ok = row.national_id and re.fullmatch(r'\d{14}', str(row.national_id))
        if not phone_ok or not nid_ok:
            return jsonify({'error': 'يجب تسجيل الدخول بكلمة المرور واستكمال البيانات أولًا'}), 403
        result = verify_authentication_response(
            credential=credential,
            expected_challenge=bytes(ch.challenge),
            expected_rp_id=str(ch.rp_id),
            expected_origin=str(ch.origin),
            credential_public_key=bytes(row.public_key),
            credential_current_sign_count=int(row.sign_count),
            require_user_verification=True,
        )
        cur.execute("UPDATE user_passkeys SET sign_count=?,last_used_at=SYSDATETIME() WHERE id=?", int(result.new_sign_count), int(row.id))
        cur.execute("DELETE FROM passkey_challenges WHERE challenge_id=?", cid)
        conn.commit()
        token = jwt.encode({'employee_id': int(row.employee_id), 'role': str(row.role), 'exp': datetime.datetime.utcnow()+datetime.timedelta(hours=8)}, SECRET_KEY, algorithm='HS256')
        return jsonify({'token': token, 'full_name': str(row.full_name), 'role': str(row.role), 'employee_code': str(row.employee_code)})
    except Exception as e:
        conn.rollback()
        return jsonify({'error': f'فشل التحقق من البصمة: {str(e)}'}), 401
    finally:
        conn.close()


@app.route('/api/passkeys', methods=['GET'])
@token_required
def passkey_list():
    conn=get_connection(); cur=conn.cursor()
    try:
        _ensure_passkey_tables(cur)
        uid=_passkey_user_id_for_employee(cur, request.employee_id)
        cur.execute("SELECT id,device_name,rp_id,created_at,last_used_at FROM user_passkeys WHERE user_id=? AND is_active=1 ORDER BY created_at DESC", uid)
        items=[{'id':int(r.id),'device_name':r.device_name or 'جهاز','rp_id':r.rp_id,'created_at':r.created_at.isoformat() if r.created_at else None,'last_used_at':r.last_used_at.isoformat() if r.last_used_at else None} for r in cur.fetchall()]
        return jsonify({'items':items})
    finally: conn.close()


@app.route('/api/passkeys/<int:passkey_id>', methods=['DELETE'])
@token_required
def passkey_delete(passkey_id):
    conn=get_connection(); cur=conn.cursor()
    try:
        _ensure_passkey_tables(cur)
        uid=_passkey_user_id_for_employee(cur, request.employee_id)
        cur.execute("UPDATE user_passkeys SET is_active=0 WHERE id=? AND user_id=?", passkey_id, uid)
        conn.commit()
        return jsonify({'success':True})
    finally: conn.close()


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
    if request.is_demo:
        demo_birth_date = birth_date_from_national_id("30109011234567")
        return jsonify({
            "employee_code": DEMO_EMPLOYEE_CODE,
            "insurance_number": "000000000",
            "full_name": "خالد المنسي",
            "job_title": "مطور",
            "hire_date": "2026-09-11",
            "national_id": "00000000000000",
            "phone": "01000000000",
            "status": "active",
            "department": "المنظومة الإلكترونية الموحدة",
            "email": "demo@example.com",
            "photo_url": None,
            "is_demo": True,
            "read_only": True,
            "birth_day": demo_birth_date.day if demo_birth_date else None,
            "birth_month": demo_birth_date.month if demo_birth_date else None,
        })

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

    if row is None:
        conn.close()
        return jsonify({"error": "الموظف غير موجود"}), 404

    photo_filename = f"employee_{request.employee_id}.jpg"
    photo_path = os.path.join(PROFILE_PHOTO_FOLDER, photo_filename)

    birth_date = load_employee_birth_date(cursor, row.employee_code, row.national_id)
    conn.close()
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
        "birth_day": birth_date.day if birth_date else None,
        "birth_month": birth_date.month if birth_date else None,
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

    if request.is_demo:
        return jsonify(demo_payslip(month, year))

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
            MIN(band_code) AS band_code,
            band_type,
            SUM(amount) AS amount,
            MAX(balance) AS balance
        FROM payroll_items
        WHERE employee_id = ? AND month = ? AND year = ?
          AND sarfia_no = 1
          AND NOT (band_name LIKE N'ت %' AND band_name NOT LIKE N'%حصة العامل%' AND band_name NOT LIKE N'%رصيد%')
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
        items = attach_installment_balances([
            {
                "name": r.display_name or "بند غير مسمى",
                "band_code": int(r.band_code),
                "type": r.band_type,
                "amount": float(r.amount),
                **({"balance": float(r.balance)} if r.balance is not None and r.band_type == "deduction" else {}),
            }
            for r in item_rows
        ])
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

    if request.is_demo:
        return jsonify(demo_wage_record(month, year))

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT sarfia_no, band_name, band_type, SUM(amount) AS amount
        FROM payroll_items
        WHERE employee_id = ? AND month = ? AND year = ?
          AND sarfia_no > 1
          AND NOT (band_name LIKE N'ت %' AND band_name NOT LIKE N'%حصة العامل%' AND band_name NOT LIKE N'%رصيد%')
          AND band_name NOT LIKE N'%مصاريف ادارية%'
        GROUP BY sarfia_no, band_name, band_type
        ORDER BY sarfia_no, band_type DESC, amount DESC
        """,
        request.employee_id,
        month,
        year,
    )
    rows = cursor.fetchall()
    sarfia_names = load_sarfia_names(cursor, month, year)
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
            "sarfia_name": sarfia_names.get(int(sarfia_no), "صرفية إضافية"),
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

    if request.is_demo:
        data = demo_payslip(month, year)
        earnings = [i for i in data["items"] if i["type"] == "earning"]
        deductions = [i for i in data["items"] if i["type"] == "deduction"]
        filename = f"payslip_demo_{year}_{month}_{uuid.uuid4().hex[:8]}.pdf"
        filepath = os.path.join(PDF_TEMP_FOLDER, filename)
        generate_payslip_pdf(
            filepath,
            employee_name="خالد المنسي",
            employee_code=DEMO_EMPLOYEE_CODE,
            month_name=MONTHS_AR[month - 1],
            year=year,
            code_sarf="DEMO",
            earnings=earnings,
            deductions=deductions,
            net_salary=data["net_salary"],
        )
        return send_file(filepath, as_attachment=True, download_name=f"شريط_مرتب_تجريبي_{MONTHS_AR[month-1]}_{year}.pdf")

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
            MIN(band_code) AS band_code,
            band_type,
            SUM(amount) AS amount,
            MAX(balance) AS balance
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

    pdf_items = attach_installment_balances([
        {
            "name": r.display_name or "بند غير مسمى",
            "band_code": int(r.band_code),
            "type": r.band_type,
            "amount": float(r.amount),
            **({"balance": float(r.balance)} if r.balance is not None and r.band_type == "deduction" else {}),
        }
        for r in rows
    ])
    earnings = [i for i in pdf_items if i["type"] == "earning"]
    deductions = [i for i in pdf_items if i["type"] == "deduction"]
    net_salary = sum(i["amount"] for i in earnings) - sum(i["amount"] for i in deductions)

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

    if request.is_demo:
        data = demo_wage_record(month, year)
        disbursements = []
        for entry in data["disbursements"]:
            earnings = [(i["name"], i["amount"]) for i in entry["items"] if i["type"] == "earning"]
            deductions = [(i["name"], i["amount"]) for i in entry["items"] if i["type"] == "deduction"]
            disbursements.append({
                "sarfia_no": entry["sarfia_no"],
                "sarfia_name": entry.get("sarfia_name", "صرفية إضافية"),
                "earnings": earnings,
                "deductions": deductions,
                "net_salary": entry["net_salary"],
            })
        filename = f"wage_demo_{year}_{month}_{uuid.uuid4().hex[:8]}.pdf"
        filepath = os.path.join(PDF_TEMP_FOLDER, filename)
        generate_wage_record_pdf(
            filepath,
            employee_name="خالد المنسي",
            employee_code=DEMO_EMPLOYEE_CODE,
            month_name=MONTHS_AR[month - 1],
            year=year,
            disbursements=disbursements,
        )
        return send_file(filepath, as_attachment=True, download_name=f"سجل_أجور_تجريبي_{MONTHS_AR[month-1]}_{year}.pdf")

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
    sarfia_names = load_sarfia_names(cursor, month, year)
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
            "sarfia_name": sarfia_names.get(int(sarfia_no), "صرفية إضافية"),
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
    password_source = (data.get("password_source") or "generated").strip().lower()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email, full_name, national_id FROM employees WHERE id = ?", emp_id)
    emp_row = cursor.fetchone()

    if emp_row is None:
        conn.close()
        return jsonify({"error": "الموظف غير موجود"}), 404

    if password_source == "national_id":
        new_password = (emp_row.national_id or "").strip()
        if not (new_password.isdigit() and len(new_password) == 14):
            conn.close()
            return jsonify({"error": "الرقم القومي غير مسجل أو غير صحيح"}), 400
    elif password_source == "birth_date":
        birth_date = birth_date_from_national_id(emp_row.national_id)
        if birth_date is None:
            conn.close()
            return jsonify({"error": "تعذر استخراج تاريخ الميلاد من الرقم القومي"}), 400
        new_password = birth_date.strftime("%d%m%Y")
    else:
        new_password = data.get("new_password") or secrets.token_urlsafe(9)

    if len(new_password) < 8:
        return jsonify({"error": "كلمة المرور يجب ألا تقل عن 8 أحرف"}), 400

    new_hash = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

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
        "password_source": password_source,
    })


# ------------------------------------------------------------
# 5.6) [إداري] إحصائيات الرواتب والمعاشات والبنود - الإصدار 2.0.0
# ------------------------------------------------------------
@app.route("/api/admin/statistics/summary", methods=["GET"])
@admin_required
def admin_statistics_summary():
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)
    if not month or not year or month not in range(1, 13):
        return jsonify({"error": "لازم تحدد شهر وسنة صحيحين"}), 400

    selected = datetime.datetime(year, month, 1)
    prev_month = (selected - datetime.timedelta(days=1)).replace(day=1)
    next_month = (selected.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)

    conn = get_connection()
    cursor = conn.cursor()

    # العدد الحالي طبقًا لحالة الموظف في جدول employees.
    cursor.execute("SELECT COUNT(*) AS employee_count FROM employees WHERE status = 'active'")
    current_row = cursor.fetchone()

    # تاريخ المعاش = تاريخ الميلاد + 60 سنة. نستخدم الرقم القومي عند توافره.
    cursor.execute(
        """
        WITH employee_births AS (
          SELECT id, employee_code, full_name,
                 TRY_CONVERT(date,
                   (CASE LEFT(national_id, 1) WHEN '2' THEN '19' WHEN '3' THEN '20' END) +
                   SUBSTRING(national_id, 2, 2) + '-' + SUBSTRING(national_id, 4, 2) + '-' + SUBSTRING(national_id, 6, 2)
                 ) AS birth_date
          FROM employees
          WHERE LEN(national_id) = 14
        ), retirements AS (
          SELECT employee_code, full_name, DATEADD(year, 60, birth_date) AS retirement_date
          FROM employee_births
          WHERE birth_date IS NOT NULL
        )
        SELECT employee_code, full_name, retirement_date
        FROM retirements
        WHERE (MONTH(retirement_date) = ? AND YEAR(retirement_date) = ?)
           OR (MONTH(retirement_date) = ? AND YEAR(retirement_date) = ?)
           OR (MONTH(retirement_date) = ? AND YEAR(retirement_date) = ?)
           OR YEAR(retirement_date) = ?
        ORDER BY retirement_date, full_name
        """,
        prev_month.month, prev_month.year,
        selected.month, selected.year,
        next_month.month, next_month.year,
        selected.year,
    )
    rows = cursor.fetchall()
    conn.close()

    def retirement_entry(r):
        return {
            "employee_code": r.employee_code,
            "full_name": r.full_name,
            "retirement_date": r.retirement_date.strftime("%Y-%m-%d") if r.retirement_date else None,
        }

    def month_group(target):
        items = [retirement_entry(r) for r in rows if r.retirement_date and r.retirement_date.month == target.month and r.retirement_date.year == target.year]
        return {"month": target.month, "year": target.year, "count": len(items), "employees": items}

    year_items = [retirement_entry(r) for r in rows if r.retirement_date and r.retirement_date.year == selected.year]
    return jsonify({
        "month": month,
        "year": year,
        "current_employee_count": int(current_row.employee_count or 0) if current_row else 0,
        "retirements": {
            "previous": month_group(prev_month),
            "current": month_group(selected),
            "next": month_group(next_month),
            "year": {"year": selected.year, "count": len(year_items), "employees": year_items},
        },
    })


@app.route("/api/admin/statistics/items", methods=["GET"])
@admin_required
def admin_statistics_items():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT band_code, MAX(band_name) AS band_name
        FROM payroll_items
        GROUP BY band_code
        ORDER BY MAX(band_name)
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return jsonify([{"band_code": int(r.band_code), "band_name": r.band_name or f"بند {r.band_code}"} for r in rows])


@app.route("/api/admin/statistics/item-total", methods=["GET"])
@admin_required
def admin_statistics_item_total():
    month = request.args.get("month", type=int)
    year = request.args.get("year", type=int)
    band_code = request.args.get("band_code", type=int)
    if not month or not year or band_code is None:
        return jsonify({"error": "حدد الشهر والسنة والبند"}), 400

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT MAX(band_name) AS band_name, COALESCE(SUM(amount), 0) AS total,
               COUNT(DISTINCT employee_id) AS employee_count
        FROM payroll_items
        WHERE month = ? AND year = ? AND band_code = ?
        """,
        month, year, band_code,
    )
    row = cursor.fetchone()

    cursor.execute(
        """
        WITH item_employees AS (
          SELECT DISTINCT employee_id
          FROM payroll_items
          WHERE month = ? AND year = ? AND band_code = ?
        ), births AS (
          SELECT e.id, e.employee_code, e.full_name,
                 TRY_CONVERT(date,
                   (CASE LEFT(e.national_id, 1) WHEN '2' THEN '19' WHEN '3' THEN '20' END) +
                   SUBSTRING(e.national_id, 2, 2) + '-' + SUBSTRING(e.national_id, 4, 2) + '-' + SUBSTRING(e.national_id, 6, 2)
                 ) AS birth_date
          FROM employees e
          JOIN item_employees i ON i.employee_id = e.id
          WHERE LEN(e.national_id) = 14
        )
        SELECT employee_code, full_name, DATEADD(year, 60, birth_date) AS retirement_date
        FROM births
        WHERE birth_date IS NOT NULL
          AND MONTH(DATEADD(year, 60, birth_date)) = ?
          AND YEAR(DATEADD(year, 60, birth_date)) = ?
        ORDER BY full_name
        """,
        month, year, band_code, month, year,
    )
    retired_rows = cursor.fetchall()
    conn.close()

    retired = [{
        "employee_code": r.employee_code,
        "full_name": r.full_name,
        "retirement_date": r.retirement_date.strftime("%Y-%m-%d") if r.retirement_date else None,
    } for r in retired_rows]

    return jsonify({
        "band_code": band_code,
        "band_name": row.band_name if row and row.band_name else f"بند {band_code}",
        "total": float(row.total or 0) if row else 0,
        "employee_count": int(row.employee_count or 0) if row else 0,
        "retirement_count": len(retired),
        "retired_employees": retired,
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
    if request.is_demo:
        return jsonify([{
            "id": 0,
            "title": "مرحبًا بك في الحساب التجريبي",
            "body": "هذه بيانات وهمية للعرض فقط، ولا تؤثر على أي موظف أو بيانات حقيقية.",
            "file_name": None,
            "original_name": None,
            "created_at": "2026-09-11 09:00",
            "is_read": True,
            "is_liked": False,
            "like_count": 0,
        }])

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
    if request.is_demo:
        return jsonify({"messages": [{
            "id": 0,
            "sender_role": "admin",
            "body": "مرحبًا بك في تجربة الرسائل. الإرسال والتعديل غير متاحين في حساب العرض.",
            "created_at": "2026-09-11 09:00",
        }]})

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
    if request.is_demo:
        return jsonify([])

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



# ============================================================
# 11) خدمات كارت المرتبات - Version 2.2.0
# ============================================================

def _current_user_id(cursor):
    """يستخرج User ID من الموظف الموجود داخل JWT؛ لا نثق بأي UserID قادم من المتصفح."""
    cursor.execute(
        "SELECT TOP (1) id FROM users WHERE employee_id = ? AND is_active = 1",
        request.employee_id,
    )
    row = cursor.fetchone()
    return int(row.id) if row else None


def _card_staff_roles(cursor, user_id):
    cursor.execute(
        """
        SELECT cr.role_code
        FROM card_user_roles cur
        INNER JOIN card_roles cr
            ON cr.role_code = cur.role_code
        WHERE cur.user_id = ?
          AND cr.is_active = 1
        """,
        user_id,
    )
    return {str(r.role_code) for r in cursor.fetchall()}


def _card_error_response(exc):
    """لا نرسل تفاصيل SQL الداخلية للعميل، ونحوّل رسائل الإجراءات المعروفة لرسالة آمنة."""
    message = str(exc)
    known_messages = [
        "تسليم الكارت يجب أن يتم من خلال إجراء التسليم المخصص",
        "رد البنك يجب أن يتم من خلال إجراء رد البنك المخصص",
        "يجب تسجيل سبب رفض البنك",
        "الطلب غير موجود",
        "الحساب غير موجود أو غير نشط",
        "الموظف غير موجود",
        "الخدمة غير متاحة",
        "سبب الطلب غير صالح",
        "يوجد طلب مفتوح بالفعل",
        "انتقال الحالة غير مسموح",
        "ليس لديك صلاحية",
        "لا يمكن تنفيذ",
        "يجب اختيار الموظف",
    ]
    for known in known_messages:
        if known in message:
            return jsonify({"error": known}), 400
    app.logger.exception("Card service database error")
    return jsonify({"error": "تعذر تنفيذ العملية حاليًا. حاول مرة أخرى أو راجع مسئول النظام."}), 500


@app.route("/api/card-services", methods=["GET"])
@token_required
def card_services_catalog():
    """الخدمات والأسباب الفعالة التي تظهر للموظف."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                st.service_code, st.service_name, st.requires_card, st.display_order,
                rr.reason_code, rr.reason_name, rr.display_order AS reason_order
            FROM card_service_types st
            LEFT JOIN card_request_reasons rr
              ON rr.service_type_id = st.id AND rr.is_active = 1
            WHERE st.is_active = 1
            ORDER BY st.display_order, rr.display_order, rr.id
            """
        )
        services = {}
        for r in cursor.fetchall():
            code = str(r.service_code)
            if code not in services:
                services[code] = {
                    "service_code": code,
                    "service_name": r.service_name,
                    "requires_card": bool(r.requires_card),
                    "reasons": [],
                }
            if r.reason_code:
                services[code]["reasons"].append({
                    "reason_code": str(r.reason_code),
                    "reason_name": r.reason_name,
                })
        return jsonify(list(services.values()))
    finally:
        conn.close()



# ===== Quran & Radio services - Version 2.2.0 =====
QURAN_AUDIO_SOURCES = {
    "mishary": {"name": "مشاري راشد العفاسي", "path": r"D:\\quran\\مشاري راشد العفاسي"},
    "mixed": {"name": "قراء متنوعون", "path": r"D:\\quran\\Qoraan"},
}
QURAN_FILE_RE = re.compile(r"^\\s*(\\d{1,3})\\s+(.+?)\\.mp3$", re.IGNORECASE)

def _quran_catalog(source_key):
    source = QURAN_AUDIO_SOURCES.get(source_key)
    if not source:
        return []
    folder = source["path"]
    if not os.path.isdir(folder):
        return []
    items = {}
    try:
        for entry in os.scandir(folder):
            if not entry.is_file():
                continue
            m = QURAN_FILE_RE.match(entry.name)
            if not m:
                continue
            number = int(m.group(1))
            if 1 <= number <= 114:
                items[number] = {"number": number, "name": m.group(2).strip(), "filename": entry.name}
    except OSError:
        return []
    return [items[n] for n in sorted(items)]

@app.route("/api/quran/audio-library", methods=["GET"])
@token_required
def quran_audio_library():
    sources = []
    for key, meta in QURAN_AUDIO_SOURCES.items():
        catalog = _quran_catalog(key)
        sources.append({
            "key": key, "name": meta["name"], "available": bool(catalog),
            "surahs": [{"number": x["number"], "name": x["name"]} for x in catalog],
        })
    return jsonify({"sources": sources})

@app.route("/api/quran/audio/<source_key>/<int:surah_no>", methods=["GET"])
@token_required
def quran_audio_stream(source_key, surah_no):
    if source_key not in QURAN_AUDIO_SOURCES or not (1 <= surah_no <= 114):
        return jsonify({"error": "تلاوة أو سورة غير صحيحة"}), 404
    item = next((x for x in _quran_catalog(source_key) if x["number"] == surah_no), None)
    if not item:
        return jsonify({"error": "ملف السورة غير موجود"}), 404
    base = os.path.realpath(QURAN_AUDIO_SOURCES[source_key]["path"])
    path = os.path.realpath(os.path.join(base, item["filename"]))
    try:
        if os.path.commonpath([base, path]) != base or not os.path.isfile(path):
            return jsonify({"error": "ملف غير صالح"}), 404
    except ValueError:
        return jsonify({"error": "ملف غير صالح"}), 404
    return send_file(path, mimetype="audio/mpeg", as_attachment=False, conditional=True, max_age=0)

RADIO_BROWSER_SERVERS = (
    "https://de1.api.radio-browser.info",
    "https://at1.api.radio-browser.info",
    "https://nl1.api.radio-browser.info",
)

@app.route("/api/radio/stations", methods=["GET"])
@token_required
def radio_stations():
    country = (request.args.get("country") or "EG").strip().upper()
    if not re.fullmatch(r"[A-Z]{2}", country):
        return jsonify({"error": "كود الدولة غير صالح"}), 400
    query = urllib.parse.urlencode({
        "countrycode": country, "countrycodeExact": "true", "hidebroken": "true",
        "order": "clickcount", "reverse": "true", "limit": 250,
    })
    last_error = None
    for server in RADIO_BROWSER_SERVERS:
        try:
            req = urllib.request.Request(
                f"{server}/json/stations/search?{query}",
                headers={"User-Agent": "EETC-EmployeePortal/2.2.0"},
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            stations = []
            seen = set()
            for x in data:
                stream = (x.get("url_resolved") or x.get("url") or "").strip()
                sid = str(x.get("stationuuid") or "").strip()
                if not sid or not stream or sid in seen:
                    continue
                # الموقع العام يعمل HTTPS؛ روابط HTTP فقط تُحجب غالبًا كـ mixed content.
                if not stream.lower().startswith("https://"):
                    continue
                seen.add(sid)
                stations.append({
                    "id": sid, "name": (x.get("name") or "محطة إذاعية").strip(),
                    "stream": stream, "codec": x.get("codec") or "",
                    "bitrate": int(x.get("bitrate") or 0), "tags": x.get("tags") or "",
                })
            return jsonify({"stations": stations, "country": country})
        except Exception as exc:
            last_error = str(exc)
    return jsonify({"error": "تعذر الاتصال بدليل محطات الراديو حاليًا", "detail": last_error}), 502


CARD_ID_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "private_uploads", "card_ids")
CARD_ID_MAX_BYTES = 5 * 1024 * 1024
CARD_ID_ALLOWED_FORMATS = {"JPEG": ".jpg", "PNG": ".png"}

def _validate_private_card_image(file_storage):
    """يفحص الصورة كاملة قبل إنشاء الطلب ويعيد البايتات والامتداد."""
    if not file_storage or not file_storage.filename:
        raise ValueError("ارفع صورة وجه البطاقة وصورة الظهر.")
    raw = file_storage.read(CARD_ID_MAX_BYTES + 1)
    if len(raw) > CARD_ID_MAX_BYTES:
        raise ValueError("حجم كل صورة بطاقة يجب ألا يزيد عن 5 MB.")
    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
        fmt = (img.format or "").upper()
    except Exception:
        raise ValueError("ملف صورة البطاقة غير صالح.")
    if fmt not in CARD_ID_ALLOWED_FORMATS:
        raise ValueError("صور البطاقة يجب أن تكون JPG أو PNG فقط.")
    return raw, CARD_ID_ALLOWED_FORMATS[fmt]

def _save_private_card_image_bytes(raw, ext, request_id, side):
    os.makedirs(CARD_ID_UPLOAD_DIR, exist_ok=True)
    filename = f"req_{int(request_id)}_{side}_{secrets.token_hex(16)}{ext}"
    path = os.path.join(CARD_ID_UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(raw)
    return filename

def _save_private_card_image(file_storage, request_id, side):
    """يحفظ صورة البطاقة خارج static بعد التحقق الحقيقي من الصورة."""
    if not file_storage or not file_storage.filename:
        raise ValueError("ارفع صورة وجه البطاقة وصورة الظهر.")

    raw = file_storage.read(CARD_ID_MAX_BYTES + 1)
    if len(raw) > CARD_ID_MAX_BYTES:
        raise ValueError("حجم كل صورة بطاقة يجب ألا يزيد عن 5 MB.")

    try:
        img = Image.open(io.BytesIO(raw))
        img.verify()
        fmt = (img.format or "").upper()
    except Exception:
        raise ValueError("ملف صورة البطاقة غير صالح.")

    if fmt not in CARD_ID_ALLOWED_FORMATS:
        raise ValueError("صور البطاقة يجب أن تكون JPG أو PNG فقط.")

    os.makedirs(CARD_ID_UPLOAD_DIR, exist_ok=True)
    filename = f"req_{int(request_id)}_{side}_{secrets.token_hex(16)}{CARD_ID_ALLOWED_FORMATS[fmt]}"
    path = os.path.join(CARD_ID_UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(raw)
    return filename

def _delete_private_card_files(*filenames):
    for filename in filenames:
        if not filename:
            continue
        try:
            path = os.path.join(CARD_ID_UPLOAD_DIR, os.path.basename(filename))
            if os.path.isfile(path):
                os.remove(path)
        except Exception:
            pass


@app.route("/api/card-requests", methods=["POST"])
@token_required
def create_card_request():
    """إنشاء طلب كارت مع البيانات الخاصة وصور البطاقة للموظف الحالي."""
    service_code = (request.form.get("service_code") or "").strip().upper()
    reason_code = (request.form.get("reason_code") or "").strip().upper() or None
    address = (request.form.get("address") or "").strip()
    phone = re.sub(r"\D", "", request.form.get("phone") or "")
    national_id = re.sub(r"\D", "", request.form.get("national_id") or "")
    id_front = request.files.get("id_front")
    id_back = request.files.get("id_back")

    if service_code not in {"NEW_CARD", "REPLACEMENT", "SMS"}:
        return jsonify({"error": "اختر خدمة صحيحة"}), 400
    if service_code == "SMS":
        reason_code = None
    if len(address) < 10 or len(address) > 500:
        return jsonify({"error": "اكتب العنوان بالتفصيل وبحد أقصى 500 حرف"}), 400
    if not re.fullmatch(r"01\d{9}", phone):
        return jsonify({"error": "رقم التليفون يجب أن يكون 11 رقمًا ويبدأ بـ 01"}), 400
    if not re.fullmatch(r"\d{14}", national_id):
        return jsonify({"error": "الرقم القومي يجب أن يكون 14 رقمًا"}), 400
    if not id_front or not id_back:
        return jsonify({"error": "ارفع صورة وجه البطاقة وصورة الظهر"}), 400
    try:
        front_raw, front_ext = _validate_private_card_image(id_front)
        back_raw, back_ext = _validate_private_card_image(id_back)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    conn = get_connection()
    front_name = back_name = None
    try:
        cursor = conn.cursor()
        user_id = _current_user_id(cursor)
        if not user_id:
            return jsonify({"error": "الحساب غير موجود أو غير نشط"}), 403

        try:
            cursor.execute(
                "EXEC dbo.sp_CreateCardRequest @UserID=?, @ServiceCode=?, @ReasonCode=?",
                user_id, service_code, reason_code,
            )
            row = cursor.fetchone()

            request_id = None
            if row:
                for attr in ("request_id", "id"):
                    if hasattr(row, attr) and getattr(row, attr) is not None:
                        request_id = int(getattr(row, attr))
                        break

            if request_id is None:
                cursor.execute(
                    """
                    SELECT TOP (1) r.id
                    FROM card_requests r
                    INNER JOIN card_service_types st ON st.id = r.service_type_id
                    WHERE r.employee_id = ? AND st.service_code = ?
                    ORDER BY r.id DESC
                    """,
                    request.employee_id, service_code,
                )
                req_row = cursor.fetchone()
                if not req_row:
                    raise RuntimeError("تعذر تحديد رقم الطلب الجديد.")
                request_id = int(req_row.id)

            front_name = _save_private_card_image_bytes(front_raw, front_ext, request_id, "front")
            back_name = _save_private_card_image_bytes(back_raw, back_ext, request_id, "back")

            cursor.execute(
                """
                INSERT INTO card_request_private_data
                    (request_id, address_text, phone, national_id,
                     id_front_file, id_back_file, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, SYSDATETIME(), SYSDATETIME())
                """,
                request_id, address, phone, national_id, front_name, back_name,
            )
            conn.commit()
            return jsonify({
                "message": "تم إرسال الطلب بنجاح",
                "request_id": request_id,
                "status": "SUBMITTED",
            }), 201

        except ValueError as exc:
            conn.rollback()
            _delete_private_card_files(front_name, back_name)
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            conn.rollback()
            _delete_private_card_files(front_name, back_name)
            return _card_error_response(exc)
    finally:
        conn.close()


@app.route("/api/card-staff/requests/<int:request_id>/private-details", methods=["GET"])
@token_required
def card_request_private_details(request_id):
    """البيانات الحساسة متاحة فقط لموظفي وحدة الكروت المخولين أو hr_admin."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        user_id = _current_user_id(cursor)
        roles = _card_staff_roles(cursor, user_id) if user_id else set()
        if request.role != "hr_admin" and not roles.intersection({"REVIEWER", "EXECUTIVE"}):
            return jsonify({"error": "ليس لديك صلاحية لعرض بيانات الطلب الخاصة"}), 403

        cursor.execute(
            """
            SELECT request_id, address_text, phone, national_id
            FROM card_request_private_data
            WHERE request_id = ?
            """,
            request_id,
        )
        row = cursor.fetchone()
        if not row:
            return jsonify({"error": "لا توجد بيانات خاصة لهذا الطلب"}), 404
        return jsonify({
            "request_id": int(row.request_id),
            "address": row.address_text,
            "phone": row.phone,
            "national_id": row.national_id,
            "id_front_url": f"/api/card-staff/requests/{request_id}/id-image/front",
            "id_back_url": f"/api/card-staff/requests/{request_id}/id-image/back",
        })
    finally:
        conn.close()


@app.route("/api/card-staff/requests/<int:request_id>/id-image/<side>", methods=["GET"])
@token_required
def card_request_id_image(request_id, side):
    """عرض محمي لصورة البطاقة؛ لا توجد الصور داخل static."""
    if side not in {"front", "back"}:
        return jsonify({"error": "صورة غير صحيحة"}), 404

    conn = get_connection()
    try:
        cursor = conn.cursor()
        user_id = _current_user_id(cursor)
        roles = _card_staff_roles(cursor, user_id) if user_id else set()
        if request.role != "hr_admin" and not roles.intersection({"REVIEWER", "EXECUTIVE"}):
            return jsonify({"error": "ليس لديك صلاحية لعرض صورة البطاقة"}), 403

        col = "id_front_file" if side == "front" else "id_back_file"
        cursor.execute(f"SELECT {col} AS filename FROM card_request_private_data WHERE request_id = ?", request_id)
        row = cursor.fetchone()
        if not row or not row.filename:
            return jsonify({"error": "الصورة غير موجودة"}), 404

        filename = os.path.basename(str(row.filename))
        path = os.path.join(CARD_ID_UPLOAD_DIR, filename)
        if not os.path.isfile(path):
            return jsonify({"error": "ملف الصورة غير موجود"}), 404

        mimetype = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
        return send_file(path, mimetype=mimetype, as_attachment=False, max_age=0)
    finally:
        conn.close()


@app.route("/api/card-requests/mine", methods=["GET"])
@token_required
def my_card_requests():
    """الموظف يرى طلباته فقط."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                r.id, st.service_code, st.service_name,
                rr.reason_code, rr.reason_name,
                r.status, r.submitted_at, r.completed_at,
                r.employee_code_snapshot, r.employee_name_snapshot,
                r.bank_code_snapshot, r.code_sarf_snapshot, r.region_snapshot
            FROM card_requests r
            INNER JOIN card_service_types st ON st.id = r.service_type_id
            LEFT JOIN card_request_reasons rr ON rr.id = r.reason_id
            WHERE r.employee_id = ?
            ORDER BY r.submitted_at DESC, r.id DESC
            """,
            request.employee_id,
        )
        return jsonify([
            {
                "id": int(r.id),
                "service_code": str(r.service_code),
                "service_name": r.service_name,
                "reason_code": str(r.reason_code) if r.reason_code else None,
                "reason_name": r.reason_name,
                "status": str(r.status),
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "employee_code": r.employee_code_snapshot,
                "employee_name": r.employee_name_snapshot,
                "bank_code": r.bank_code_snapshot,
                "code_sarf": r.code_sarf_snapshot,
                "region": r.region_snapshot,
            }
            for r in cursor.fetchall()
        ])
    finally:
        conn.close()


@app.route("/api/card-requests/<int:request_id>/timeline", methods=["GET"])
@token_required
def card_request_timeline(request_id):
    """Timeline للطلب: صاحبه أو موظف الوحدة المخول فقط."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        user_id = _current_user_id(cursor)
        cursor.execute("SELECT employee_id FROM card_requests WHERE id = ?", request_id)
        owner = cursor.fetchone()
        if not owner:
            return jsonify({"error": "الطلب غير موجود"}), 404

        roles = _card_staff_roles(cursor, user_id) if user_id else set()
        if int(owner.employee_id) != int(request.employee_id) and request.role != "hr_admin" and not roles:
            return jsonify({"error": "ليس لديك صلاحية لعرض هذا الطلب"}), 403

        cursor.execute(
            """
            SELECT id, old_status, new_status, action_code, action_name,
                   actor_name, notes, created_at
            FROM card_request_history
            WHERE request_id = ?
            ORDER BY created_at, id
            """,
            request_id,
        )
        return jsonify([
            {
                "id": int(r.id),
                "old_status": str(r.old_status) if r.old_status else None,
                "new_status": str(r.new_status),
                "action_code": str(r.action_code),
                "action_name": r.action_name,
                "actor_name": r.actor_name,
                "notes": r.notes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in cursor.fetchall()
        ])
    finally:
        conn.close()


@app.route("/api/card-staff/me", methods=["GET"])
@token_required
def card_staff_me():
    """الصلاحيات الخاصة بوحدة الكروت للواجهة، بدون تغيير users.role."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        user_id = _current_user_id(cursor)
        roles = sorted(_card_staff_roles(cursor, user_id)) if user_id else []
        return jsonify({
            "user_id": user_id,
            "is_hr_admin": request.role == "hr_admin",
            "roles": roles,
        })
    finally:
        conn.close()


@app.route("/api/card-staff/queue", methods=["GET"])
@token_required
def card_staff_queue():
    """
    قائمة عمل آمنة ومقسمة حسب الشاشة المطلوبة:
      review  -> الطلبات الجديدة للمراجع
      execute -> التنفيذ/الرفع للبنك + متابعة SMS
      receive -> استلام الكروت الفعلية من البنك فقط
      deliver -> تسليم الكروت الفعلية للموظفين فقط

    لا تعرض رقم قومي أو هاتف أو أي بيانات مرتب.
    """
    view = (request.args.get("view") or "").strip().lower()
    view_rules = {
        "review": {
            "role": "REVIEWER",
            "statuses": ("SUBMITTED",),
            "requires_card": None,
        },
        "execute": {
            "role": "EXECUTIVE",
            "statuses": ("REVIEWED", "BANK_UPLOADED", "WAITING_BANK_RESPONSE"),
            "requires_card": None,
        },
        "receive": {
            "role": "BANK_RECEIVER",
            "statuses": ("BANK_UPLOADED",),
            "requires_card": True,
        },
        "deliver": {
            "role": "DELIVERY",
            "statuses": ("RECEIVED_FROM_BANK",),
            "requires_card": True,
        },
    }

    if view not in view_rules:
        return jsonify({
            "error": "يجب تحديد شاشة العمل: review أو execute أو receive أو deliver"
        }), 400

    conn = get_connection()
    try:
        cursor = conn.cursor()
        user_id = _current_user_id(cursor)
        if not user_id:
            return jsonify({"error": "الحساب غير موجود أو غير نشط"}), 403

        roles = _card_staff_roles(cursor, user_id)
        rule = view_rules[view]

        if request.role != "hr_admin" and rule["role"] not in roles:
            return jsonify({"error": "ليس لديك صلاحية للوصول إلى هذه الشاشة"}), 403

        statuses = rule["statuses"]
        placeholders = ",".join("?" for _ in statuses)
        where_parts = [f"r.status IN ({placeholders})"]
        params = list(statuses)

        # شاشتا الاستلام والتسليم للكروت الفعلية فقط.
        # بهذا لا يمكن لطلبات SMS الظهور فيهما حتى لو كانت حالتها BANK_UPLOADED.
        if rule["requires_card"] is True:
            where_parts.append("st.requires_card = 1")
        # بعد الرفع للبنك، طلبات الكروت الفعلية تنتقل لشاشة الاستلام فقط.
        # شاشة التنفيذ تحتفظ بـ REVIEWED للجميع، وبمتابعة BANK_UPLOADED/WAITING_BANK_RESPONSE للـ SMS فقط.
        if view == "execute":
            where_parts.append("(r.status = 'REVIEWED' OR st.requires_card = 0)")

        sql = f"""
            SELECT
                r.id, st.service_code, st.service_name, st.requires_card,
                rr.reason_name, r.status,
                r.employee_code_snapshot, r.employee_name_snapshot,
                r.bank_code_snapshot, r.code_sarf_snapshot, r.region_snapshot,
                r.submitted_at
            FROM card_requests r
            INNER JOIN card_service_types st ON st.id = r.service_type_id
            LEFT JOIN card_request_reasons rr ON rr.id = r.reason_id
            WHERE {" AND ".join(where_parts)}
            ORDER BY r.submitted_at, r.id
        """
        cursor.execute(sql, *params)

        return jsonify([
            {
                "id": int(r.id),
                "service_code": str(r.service_code),
                "service_name": r.service_name,
                "requires_card": bool(r.requires_card),
                "reason_name": r.reason_name,
                "status": str(r.status),
                "employee_code": r.employee_code_snapshot,
                "employee_name": r.employee_name_snapshot,
                "bank_code": r.bank_code_snapshot,
                "code_sarf": r.code_sarf_snapshot,
                "region": r.region_snapshot,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            }
            for r in cursor.fetchall()
        ])
    finally:
        conn.close()


@app.route("/api/card-staff/requests/<int:request_id>/transition", methods=["POST"])
@token_required
def card_request_transition(request_id):
    """المراحل العامة فقط؛ DELIVERED و ACCEPTED/REJECTED لها APIs متخصصة."""
    data = request.get_json(silent=True) or {}
    to_status = (data.get("to_status") or "").strip().upper()
    notes = (data.get("notes") or "").strip() or None

    allowed = {"REVIEWED", "BANK_UPLOADED", "WAITING_BANK_RESPONSE", "RECEIVED_FROM_BANK"}
    if to_status not in allowed:
        return jsonify({"error": "الحالة المطلوبة غير مسموح بتنفيذها من هذه الشاشة"}), 400

    conn = get_connection()
    try:
        cursor = conn.cursor()
        user_id = _current_user_id(cursor)
        if not user_id:
            return jsonify({"error": "الحساب غير موجود أو غير نشط"}), 403
        roles = _card_staff_roles(cursor, user_id)
        required_role = {
            "REVIEWED": "REVIEWER",
            "BANK_UPLOADED": "EXECUTIVE",
            "WAITING_BANK_RESPONSE": "EXECUTIVE",
            "RECEIVED_FROM_BANK": "BANK_RECEIVER",
        }[to_status]
        if request.role != "hr_admin" and required_role not in roles:
            return jsonify({"error": "ليس لديك صلاحية لتنفيذ هذه المرحلة"}), 403
        try:
            cursor.execute(
                "EXEC dbo.sp_CardRequestTransition @RequestID=?, @ToStatus=?, @ActorUserID=?, @Notes=?",
                request_id, to_status, user_id, notes,
            )
            row = cursor.fetchone()
            conn.commit()
        except Exception as exc:
            conn.rollback()
            return _card_error_response(exc)

        return jsonify({
            "message": "تم تحديث حالة الطلب بنجاح",
            "request_id": request_id,
            "status": to_status,
        })
    finally:
        conn.close()


@app.route("/api/card-staff/requests/<int:request_id>/bank-response", methods=["POST"])
@token_required
def card_bank_response(request_id):
    """قبول/رفض البنك لطلبات SMS فقط."""
    data = request.get_json(silent=True) or {}
    response_status = (data.get("response_status") or "").strip().upper()
    rejection_reason = (data.get("rejection_reason") or "").strip() or None

    if response_status not in {"ACCEPTED", "REJECTED"}:
        return jsonify({"error": "رد البنك يجب أن يكون ACCEPTED أو REJECTED"}), 400
    if response_status == "REJECTED" and not rejection_reason:
        return jsonify({"error": "يجب تسجيل سبب رفض البنك"}), 400

    conn = get_connection()
    try:
        cursor = conn.cursor()
        user_id = _current_user_id(cursor)
        if not user_id:
            return jsonify({"error": "الحساب غير موجود أو غير نشط"}), 403
        roles = _card_staff_roles(cursor, user_id)
        if request.role != "hr_admin" and "EXECUTIVE" not in roles:
            return jsonify({"error": "ليس لديك صلاحية تسجيل رد البنك"}), 403
        try:
            cursor.execute(
                "EXEC dbo.sp_CardBankResponse @RequestID=?, @ActorUserID=?, @ResponseStatus=?, @RejectionReason=?",
                request_id, user_id, response_status, rejection_reason,
            )
            cursor.fetchone()
            conn.commit()
        except Exception as exc:
            conn.rollback()
            return _card_error_response(exc)

        return jsonify({
            "message": "تم تسجيل رد البنك بنجاح",
            "request_id": request_id,
            "status": response_status,
        })
    finally:
        conn.close()


@app.route("/api/card-staff/requests/<int:request_id>/deliver", methods=["POST"])
@token_required
def card_deliver(request_id):
    """تسليم الكارت لصاحبه أو لموظف آخر، مع تسجيل المستلم والمنفذ والتوقيت."""
    data = request.get_json(silent=True) or {}
    receiver_type = (data.get("receiver_type") or "").strip().upper()
    receiver_employee_code = (data.get("receiver_employee_code") or "").strip() or None
    notes = (data.get("notes") or "").strip() or None

    if receiver_type not in {"SELF", "OTHER"}:
        return jsonify({"error": "حدد طريقة الاستلام: SELF أو OTHER"}), 400
    if receiver_type == "OTHER" and not receiver_employee_code:
        return jsonify({"error": "يجب اختيار الموظف الذي استلم الكارت"}), 400
    if receiver_type == "SELF":
        receiver_employee_code = None

    conn = get_connection()
    try:
        cursor = conn.cursor()
        user_id = _current_user_id(cursor)
        if not user_id:
            return jsonify({"error": "الحساب غير موجود أو غير نشط"}), 403
        roles = _card_staff_roles(cursor, user_id)
        if request.role != "hr_admin" and "DELIVERY" not in roles:
            return jsonify({"error": "ليس لديك صلاحية تسليم الكارت"}), 403
        try:
            cursor.execute(
                "EXEC dbo.sp_CardDeliver @RequestID=?, @ActorUserID=?, @ReceiverType=?, @ReceiverEmployeeCode=?, @Notes=?",
                request_id, user_id, receiver_type, receiver_employee_code, notes,
            )
            row = cursor.fetchone()
            conn.commit()
        except Exception as exc:
            conn.rollback()
            return _card_error_response(exc)

        return jsonify({
            "message": "تم تسجيل تسليم الكارت بنجاح",
            "request_id": request_id,
            "status": "DELIVERED",
            "receiver_type": receiver_type,
        })
    finally:
        conn.close()


@app.route("/api/card-staff/employee-search", methods=["GET"])
@token_required
def card_delivery_employee_search():
    """بحث محدود لاختيار مستلم OTHER؛ يعيد الكود والاسم فقط."""
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify([])

    conn = get_connection()
    try:
        cursor = conn.cursor()
        user_id = _current_user_id(cursor)
        roles = _card_staff_roles(cursor, user_id) if user_id else set()
        if request.role != "hr_admin" and "DELIVERY" not in roles:
            return jsonify({"error": "ليس لديك صلاحية التسليم"}), 403

        like = f"%{q}%"
        cursor.execute(
            """
            SELECT TOP (20) employee_code, full_name
            FROM employees
            WHERE status = 'active'
              AND (employee_code LIKE ? OR full_name LIKE ?)
            ORDER BY full_name
            """,
            like, like,
        )
        return jsonify([
            {"employee_code": r.employee_code, "full_name": r.full_name}
            for r in cursor.fetchall()
        ])
    finally:
        conn.close()


if __name__ == "__main__":
    # host="0.0.0.0" يخلي السيرفر متاح لأي جهاز على نفس الشبكة، مش بس جهازك
    debug_enabled = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_enabled, host="0.0.0.0", port=5000)
