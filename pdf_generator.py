"""
pdf_generator.py
مسؤول عن توليد شريط المرتب وسجل الأجور كملفات PDF حقيقية
(مش طباعة متصفح) مع Metadata فعلية جوه الملف نفسه:
Author, Creator, Producer, Title.

بيستخدم:
- reportlab: لبناء الـ PDF نفسه
- arabic_reshaper + python-bidi: عشان الحروف العربي تتوصل ببعض
  وتتقرا صح من اليمين لليسار جوه الـ PDF (من غير المكتبتين دول
  النص العربي بيطلع منفصل وبالعكس)
- خط Amiri: خط عربي حقيقي مرفق مع المشروع في مجلد fonts/
"""

import os
import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")

def _first_existing_font(paths):
    for path in paths:
        if os.path.isfile(path):
            return path
    raise RuntimeError(
        "لم يتم العثور على خط عربي. أضف Amiri-Regular.ttf وAmiri-Bold.ttf داخل مجلد fonts."
    )


# نفضّل خط Amiri المرفق، مع بدائل شائعة على Windows وLinux حتى لا يتوقف السيرفر.
REGULAR_FONT = _first_existing_font([
    os.path.join(FONT_DIR, "Amiri-Regular.ttf"),
    r"C:\Windows\Fonts\arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
])
BOLD_FONT = _first_existing_font([
    os.path.join(FONT_DIR, "Amiri-Bold.ttf"),
    r"C:\Windows\Fonts\arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
])

pdfmetrics.registerFont(TTFont("Amiri", REGULAR_FONT))
pdfmetrics.registerFont(TTFont("Amiri-Bold", BOLD_FONT))

NAVY = HexColor("#5C1524")
GOLD = HexColor("#C9A24B")
GRAY = HexColor("#6B7280")
RED = HexColor("#B14A3D")
GREEN = HexColor("#2F7A4F")
LINE = HexColor("#DFD9C8")

APP_VERSION = "Version 1.0.0"


def ar(text):
    """بتاخد نص عربي عادي وترجعه جاهز يتكتب صح جوه الـ PDF."""
    if text is None:
        return ""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)


def fmt_num(n):
    return f"{n:,.2f}"


def _draw_header(c, width, height, title, subtitle, code_sarf=None):
    y = height - 60

    c.setFillColor(NAVY)
    c.rect(0, height - 90, width, 90, fill=1, stroke=0)

    c.setFillColor(GOLD)
    c.setFont("Amiri-Bold", 16)
    c.drawRightString(width - 40, y, ar(title))

    c.setFillColor(HexColor("#E9D9AE"))
    c.setFont("Amiri", 11)
    sub_text = subtitle
    if code_sarf:
        sub_text += f" — كود الصرف: {code_sarf}"
    c.drawRightString(width - 40, y - 22, ar(sub_text))

    return height - 110


def _draw_columns(c, width, y_start, earnings, deductions):
    """بترسم عمودين (استحقاقات | استقطاعات) وترجع نقطة النهاية Y."""
    col_width = (width - 80) / 2
    right_col_x = width - 40
    left_col_x = width - 40 - col_width - 20

    y = y_start

    c.setFillColor(NAVY)
    c.setFont("Amiri-Bold", 12)
    c.drawRightString(right_col_x, y, ar("الاستحقاقات"))
    c.drawRightString(left_col_x, y, ar("الاستقطاعات"))
    c.setStrokeColor(GOLD)
    c.line(right_col_x - col_width, y - 4, right_col_x, y - 4)
    c.line(left_col_x - col_width, y - 4, left_col_x, y - 4)

    y -= 22
    c.setFont("Amiri", 10.5)

    max_rows = max(len(earnings), len(deductions))
    earnings_total = 0
    deductions_total = 0

    for i in range(max_rows):
        row_y = y - (i * 16)
        if i < len(earnings):
            name, amount = earnings[i]
            earnings_total += amount
            c.setFillColor(HexColor("#242730"))
            c.drawRightString(right_col_x, row_y, ar(name))
            c.drawString(right_col_x - col_width, row_y, fmt_num(amount))
        if i < len(deductions):
            name, amount = deductions[i]
            deductions_total += amount
            c.setFillColor(RED)
            c.drawRightString(left_col_x, row_y, ar(name))
            c.drawString(left_col_x - col_width, row_y, fmt_num(amount))

    content_bottom = y - (max_rows * 16) - 10

    # مجموع كل عمود
    c.setStrokeColor(LINE)
    c.line(right_col_x - col_width, content_bottom, right_col_x, content_bottom)
    c.line(left_col_x - col_width, content_bottom, left_col_x, content_bottom)

    c.setFont("Amiri-Bold", 11)
    c.setFillColor(GREEN)
    c.drawRightString(right_col_x, content_bottom - 16, ar(f"الإجمالي: {fmt_num(earnings_total)}"))
    c.setFillColor(RED)
    c.drawRightString(left_col_x, content_bottom - 16, ar(f"الإجمالي: {fmt_num(deductions_total)}"))

    return content_bottom - 40, earnings_total, deductions_total


def _draw_net_box(c, width, y, net):
    c.setFillColor(HexColor("#E9D9AE"))
    c.roundRect(40, y - 30, width - 80, 40, 6, fill=1, stroke=0)
    c.setFillColor(NAVY)
    c.setFont("Amiri-Bold", 14)
    c.drawRightString(width - 55, y - 15, ar(f"الصافي: {fmt_num(net)} ج.م"))
    return y - 55


def _draw_footer(c, width, y):
    c.setStrokeColor(RED)
    c.setFillColor(RED)
    c.setFont("Amiri", 8.5)
    c.drawCentredString(
        width / 2, y,
        ar("لا يعتد بهذا البيان كمستند رسمي أمام أي جهة خارجية بدون اعتماد جهة العمل والختم"),
    )
    y -= 16
    c.setFillColor(GRAY)
    c.setFont("Amiri", 7.5)
    c.drawCentredString(y=y, x=width / 2, text=ar("تم إنشاء وتصميم وتطوير هذا النظام بالكامل بواسطة المبرمج / خالد يوسف المنسي"))
    y -= 11
    c.drawCentredString(width / 2, y, f"{APP_VERSION} — (c) 2026 All Rights Reserved")

    # علامة مائية خفيفة جدًا في نص الصفحة
    c.saveState()
    c.setFillColor(HexColor("#B4463D"))
    c.setFillAlpha(0.07)
    c.setFont("Amiri-Bold", 46)
    c.translate(width / 2, 420)
    c.rotate(30)
    c.drawCentredString(0, 0, ar("سري للاستعلام فقط"))
    c.restoreState()


def generate_payslip_pdf(output_path, employee_name, employee_code, month_name, year,
                          code_sarf, earnings, deductions, net_salary):
    """
    earnings / deductions: قايمة من tuples (اسم البند, القيمة)
    """
    c = canvas.Canvas(output_path, pagesize=A4)
    c.setAuthor("Khaled Youssif Elmansy")
    c.setTitle(f"Payslip - {employee_code}")
    c.setCreator("Payroll Management System - Khaled Youssif Elmansy")
    c.setSubject("Employee Payslip")

    width, height = A4

    y = _draw_header(
        c, width, height,
        "شريط المرتب",
        f"{month_name} {year} — {employee_name} (كود {employee_code})",
        code_sarf,
    )
    y, _, _ = _draw_columns(c, width, y, earnings, deductions)
    y = _draw_net_box(c, width, y, net_salary)
    _draw_footer(c, width, 60)

    c.save()


def generate_wage_record_pdf(output_path, employee_name, employee_code, month_name, year, disbursements):
    """
    disbursements: قايمة من dicts فيها sarfia_no, earnings, deductions, net_salary
    كل صرفية بترسم في صفحة منفصلة (أو تحت بعض لو المساحة سمحت)
    """
    c = canvas.Canvas(output_path, pagesize=A4)
    c.setAuthor("Khaled Youssif Elmansy")
    c.setTitle(f"Wage Record - {employee_code}")
    c.setCreator("Payroll Management System - Khaled Youssif Elmansy")
    c.setSubject("Employee Wage Record")

    width, height = A4

    for i, d in enumerate(disbursements):
        if i > 0:
            c.showPage()

        y = _draw_header(
            c, width, height,
            f"صرفية رقم {d['sarfia_no']}",
            f"{month_name} {year} — {employee_name} (كود {employee_code})",
        )
        y, _, _ = _draw_columns(c, width, y, d["earnings"], d["deductions"])
        y = _draw_net_box(c, width, y, d["net_salary"])
        _draw_footer(c, width, 60)

    c.save()
