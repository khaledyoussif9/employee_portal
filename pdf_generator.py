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

NAVY = HexColor("#092A4A")
ROYAL_DARK = HexColor("#123B6D")
ROYAL = HexColor("#1D5FA7")
SILVER = HexColor("#C4CBD3")
SNOW = HexColor("#F7F9FC")
INK = HexColor("#172433")
GRAY = HexColor("#6B7280")
RED = HexColor("#D92D20")
GREEN = HexColor("#22A06B")
LINE = SILVER

APP_VERSION = "Version 2.0.0"
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "logo.jpg")


def ar(text):
    """بتاخد نص عربي عادي وترجعه جاهز يتكتب صح جوه الـ PDF."""
    if text is None:
        return ""
    reshaped = arabic_reshaper.reshape(str(text))
    return get_display(reshaped)


def fmt_num(n):
    return f"{n:,.2f}"


def _draw_page_frame(c, width, height, page_number=None):
    """حد واضح لمنطقة الطباعة مع رقم الصفحة عند وجود أكثر من صفحة."""
    c.saveState()
    c.setStrokeColor(ROYAL_DARK)
    c.setLineWidth(1.2)
    c.roundRect(18, 18, width - 36, height - 36, 7, fill=0, stroke=1)
    c.setStrokeColor(SILVER)
    c.setLineWidth(0.45)
    c.roundRect(22, 22, width - 44, height - 44, 5, fill=0, stroke=1)
    if page_number is not None:
        c.setFillColor(GRAY)
        c.setFont("Amiri", 7.5)
        c.drawString(30, 29, ar(f"صفحة {page_number}"))
    c.restoreState()


def _draw_header(c, width, height, title, subtitle, code_sarf=None):
    c.setFillColor(SNOW)
    c.rect(0, 0, width, height, fill=1, stroke=0)
    y = height - 54

    header_left = 24
    header_width = width - 48
    c.setFillColor(NAVY)
    c.roundRect(header_left, height - 103, header_width, 79, 7, fill=1, stroke=0)
    c.setFillColor(ROYAL)
    c.rect(header_left, height - 106, header_width, 3, fill=1, stroke=0)

    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("Amiri-Bold", 16)
    c.drawRightString(width - 40, y, ar(title))

    c.setFillColor(SILVER)
    c.setFont("Amiri", 11)
    sub_text = subtitle
    if code_sarf:
        sub_text += f" — كود الصرف: {code_sarf}"
    c.drawRightString(width - 40, y - 22, ar(sub_text))

    if os.path.isfile(LOGO_PATH):
        c.setFillColor(HexColor("#FFFFFF"))
        c.roundRect(31, height - 94, 66, 66, 5, fill=1, stroke=0)
        c.drawImage(LOGO_PATH, 35, height - 90, 58, 58, preserveAspectRatio=True, mask="auto")

    return height - 128


def _item_parts(item):
    """Accept both legacy (name, amount) tuples and the site's item dictionaries."""
    if isinstance(item, dict):
        return item.get("name", "بند غير مسمى"), float(item.get("amount", 0)), item.get("balance")
    return item[0], float(item[1]), None


def _draw_installment_card(c, x_left, x_right, y, name, amount, balance):
    """Draw the same installment / balance card used in the website."""
    card_height = 48
    c.setFillColor(HexColor("#FFFFFF"))
    c.setStrokeColor(SILVER)
    c.roundRect(x_left, y - card_height + 7, x_right - x_left, card_height, 5, fill=1, stroke=1)
    c.setFillColor(ROYAL_DARK)
    c.setFont("Amiri-Bold", 9.5)
    c.drawRightString(x_right - 8, y - 7, ar(name))
    c.setFont("Amiri-Bold", 8)
    c.setFillColor(GRAY)
    c.drawRightString(x_right - 8, y - 27, ar("القسط"))
    c.setFillColor(RED)
    c.drawRightString(x_right - 50, y - 27, fmt_num(amount))
    c.setFillColor(GRAY)
    c.drawRightString(x_right - 105, y - 27, ar("الرصيد"))
    c.setFillColor(INK)
    c.drawRightString(x_right - 148, y - 27, fmt_num(float(balance)))
    return card_height + 5


def _draw_columns(c, width, y_start, earnings, deductions, fill_page=False):
    """بترسم عمودين (استحقاقات | استقطاعات) وترجع نقطة النهاية Y."""
    content_left = 40
    content_right = width - 40
    divider_x = width / 2
    column_gap = 18
    right_value_x = divider_x + column_gap / 2
    right_col_x = content_right
    left_value_x = content_left
    left_col_x = divider_x - column_gap / 2
    col_width = left_col_x - content_left

    y = y_start

    # إطار القسم والفاصل الرأسي يجعلان الاستحقاقات والاستقطاعات منفصلين بصريًا.
    section_top = y + 13

    c.setFillColor(NAVY)
    c.setFont("Amiri-Bold", 12)
    c.drawRightString(right_col_x, y, ar("الاستحقاقات"))
    c.drawRightString(left_col_x, y, ar("الاستقطاعات"))
    c.setStrokeColor(ROYAL)
    c.line(right_value_x, y - 4, right_col_x, y - 4)
    c.line(left_value_x, y - 4, left_col_x, y - 4)

    y -= 24
    c.setFont("Amiri", 10.5)

    earnings_total = sum(_item_parts(item)[1] for item in earnings)
    deductions_total = sum(_item_parts(item)[1] for item in deductions)
    regular_deductions = [item for item in deductions if _item_parts(item)[2] is None]
    installments = [item for item in deductions if _item_parts(item)[2] is not None]
    deduction_units = len(regular_deductions) + (len(installments) * 3)
    max_rows = max(len(earnings), deduction_units)

    row_step = 16
    if fill_page and max_rows:
        row_step = max(16, min(30, (y - 275) / max_rows))

    for i, item in enumerate(earnings):
        row_y = y - (i * row_step)
        name, amount, _ = _item_parts(item)
        if row_y > 170:
            c.setFillColor(INK)
            c.drawRightString(right_col_x, row_y, ar(name))
            c.drawString(right_value_x, row_y, fmt_num(amount))
            c.setStrokeColor(HexColor("#E4E9EF"))
            c.line(right_value_x, row_y - 5, right_col_x, row_y - 5)

    deduction_y = y
    for item in regular_deductions:
        name, amount, _ = _item_parts(item)
        if deduction_y > 170:
            c.setFillColor(RED)
            c.drawRightString(left_col_x, deduction_y, ar(name))
            c.drawString(left_value_x, deduction_y, fmt_num(amount))
            c.setStrokeColor(HexColor("#E4E9EF"))
            c.line(left_value_x, deduction_y - 5, left_col_x, deduction_y - 5)
        deduction_y -= row_step

    for item in installments:
        name, amount, balance = _item_parts(item)
        deduction_y -= 3
        deduction_y -= _draw_installment_card(
            c, left_value_x, left_col_x, deduction_y, name, amount, balance
        )

    earnings_bottom = y - (len(earnings) * row_step)
    content_bottom = min(earnings_bottom, deduction_y) - 10

    c.saveState()
    c.setStrokeColor(SILVER)
    c.setLineWidth(0.8)
    c.roundRect(content_left, content_bottom - 27, content_right - content_left, section_top - content_bottom + 27, 6, fill=0, stroke=1)
    c.line(divider_x, section_top, divider_x, content_bottom - 27)
    c.restoreState()

    # مجموع كل عمود
    c.setStrokeColor(LINE)
    c.line(right_value_x, content_bottom, right_col_x, content_bottom)
    c.line(left_value_x, content_bottom, left_col_x, content_bottom)

    c.setFont("Amiri-Bold", 11)
    c.setFillColor(GREEN)
    c.drawRightString(right_col_x, content_bottom - 16, ar(f"الإجمالي: {fmt_num(earnings_total)}"))
    c.setFillColor(RED)
    c.drawRightString(left_col_x, content_bottom - 16, ar(f"الإجمالي: {fmt_num(deductions_total)}"))

    return content_bottom - 40, earnings_total, deductions_total


def _draw_net_box(c, width, y, net):
    c.setFillColor(HexColor("#EAF1F8"))
    c.roundRect(40, y - 30, width - 80, 40, 6, fill=1, stroke=0)
    c.setStrokeColor(SILVER)
    c.setLineWidth(1.1)
    c.roundRect(40, y - 30, width - 80, 40, 6, fill=0, stroke=1)
    c.setFillColor(ROYAL_DARK)
    c.setFont("Amiri-Bold", 14)
    c.drawRightString(width - 55, y - 15, ar(f"الصافي: {fmt_num(net)} ج.م"))
    return y - 55


def _draw_footer(c, width, y):
    c.setStrokeColor(SILVER)
    c.line(40, y + 14, width - 40, y + 14)
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

    # علامة مائية قطرية تمتد بصريًا من أسفل اليسار إلى أعلى اليمين؛
    # وباتجاه قراءة العربية تبدأ من أعلى اليمين إلى أسفل اليسار.
    c.saveState()
    c.setFillColor(ROYAL)
    c.setFillAlpha(0.065)
    c.setFont("Amiri-Bold", 54)
    c.translate(width / 2, A4[1] / 2)
    c.rotate(55)
    c.drawCentredString(0, 0, ar("سري للغاية - للاستعلام فقط"))
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
    _draw_page_frame(c, width, height, 1)
    y, _, _ = _draw_columns(c, width, y, earnings, deductions, fill_page=True)
    y = _draw_net_box(c, width, y, net_salary)
    _draw_footer(c, width, 60)

    c.save()


def generate_wage_record_pdf(output_path, employee_name, employee_code, month_name, year, disbursements):
    """
    disbursements: قايمة من dicts فيها sarfia_no, earnings, deductions, net_salary
    يضع أكبر عدد ممكن من الصرفيات في الصفحة، وينتقل تلقائيًا عند امتلائها.
    """
    c = canvas.Canvas(output_path, pagesize=A4)
    c.setAuthor("Khaled Youssif Elmansy")
    c.setTitle(f"Wage Record - {employee_code}")
    c.setCreator("Payroll Management System - Khaled Youssif Elmansy")
    c.setSubject("Employee Wage Record")

    width, height = A4

    page_number = 0

    def new_page():
        nonlocal page_number
        page_number += 1
        page_y = _draw_header(
            c, width, height,
            "سجل الأجور",
            f"{month_name} {year} — {employee_name} (كود {employee_code})",
        )
        _draw_page_frame(c, width, height, page_number)
        return page_y

    def block_height(d):
        rows = max(len(d["earnings"]), len(d["deductions"]), 1)
        return 105 + rows * 15

    def draw_block(d, y):
        left, right = 40, width - 40
        mid = width / 2
        name = d.get("sarfia_name") or "صرفية إضافية"
        title = f"صرفية رقم {d['sarfia_no']} - {name}"

        c.setFillColor(HexColor("#EAF1F8"))
        c.setStrokeColor(ROYAL)
        c.setLineWidth(0.9)
        c.roundRect(left, y - 25, right - left, 27, 5, fill=1, stroke=1)
        c.setFillColor(ROYAL_DARK)
        shaped_title = ar(title)
        title_size = 11
        while title_size > 8 and c.stringWidth(shaped_title, "Amiri-Bold", title_size) > right - left - 18:
            title_size -= 0.5
        c.setFont("Amiri-Bold", title_size)
        c.drawRightString(right - 9, y - 16, shaped_title)
        y -= 42

        c.setFont("Amiri-Bold", 9)
        c.setFillColor(NAVY)
        c.drawRightString(right, y, ar("الاستحقاقات"))
        c.drawRightString(mid - 10, y, ar("الاستقطاعات"))
        c.setStrokeColor(ROYAL)
        c.line(mid + 10, y - 4, right, y - 4)
        c.line(left, y - 4, mid - 10, y - 4)
        y -= 17

        rows = max(len(d["earnings"]), len(d["deductions"]), 1)
        c.setFont("Amiri", 8.5)
        for i in range(rows):
            row_y = y - i * 15
            if i < len(d["earnings"]):
                item_name, amount, _ = _item_parts(d["earnings"][i])
                c.setFillColor(INK)
                c.drawRightString(right, row_y, ar(item_name))
                c.drawString(mid + 10, row_y, fmt_num(amount))
            if i < len(d["deductions"]):
                item_name, amount, _ = _item_parts(d["deductions"][i])
                c.setFillColor(RED)
                c.drawRightString(mid - 10, row_y, ar(item_name))
                c.drawString(left, row_y, fmt_num(amount))

        bottom = y - rows * 15 - 2
        earnings_total = sum(_item_parts(item)[1] for item in d["earnings"])
        deductions_total = sum(_item_parts(item)[1] for item in d["deductions"])

        # إطار كامل للصرفية وفاصل بين العمودين.
        table_top = y + 13
        table_bottom = bottom - 29
        c.saveState()
        c.setStrokeColor(SILVER)
        c.setLineWidth(0.8)
        c.roundRect(left, table_bottom, right - left, table_top - table_bottom, 4, fill=0, stroke=1)
        c.line(mid, table_top, mid, bottom + 8)
        c.restoreState()

        c.setStrokeColor(SILVER)
        c.line(left, bottom + 8, right, bottom + 8)
        c.setFont("Amiri-Bold", 9)
        c.setFillColor(GREEN)
        c.drawRightString(right, bottom - 4, ar(f"إجمالي الاستحقاقات: {fmt_num(earnings_total)}"))
        c.setFillColor(RED)
        c.drawRightString(mid - 10, bottom - 4, ar(f"إجمالي الاستقطاعات: {fmt_num(deductions_total)}"))
        c.setFillColor(HexColor("#EAF1F8"))
        c.roundRect(left + 4, bottom - 27, right - left - 8, 18, 3, fill=1, stroke=0)
        c.setFillColor(ROYAL_DARK)
        c.drawCentredString(width / 2, bottom - 22, ar(f"الصافي: {fmt_num(d['net_salary'])} ج.م"))
        return bottom - 34

    y = new_page()
    for index, d in enumerate(disbursements):
        required = block_height(d)
        if y - required < 100:
            _draw_footer(c, width, 60)
            c.showPage()
            y = new_page()
        y = draw_block(d, y) - 8

    _draw_footer(c, width, 60)

    c.save()
