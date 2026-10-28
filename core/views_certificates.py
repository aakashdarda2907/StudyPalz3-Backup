# core/views_certificates.py — NEW FILE, add it alongside your other views.
#
# pip install reportlab
#
# reportlab is pure Python — no system libraries needed (unlike
# WeasyPrint, which needs cairo/pango and often fails to install on
# PythonAnywhere's free/low tiers). This draws the PDF directly rather
# than converting HTML, which is more code but zero deployment risk.

import io

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .models import Subject, Certificate, user_is_eligible_for_certificate


@login_required
@require_http_methods(["POST"])
def claim_certificate_view(request, subject_slug):
    """
    The student clicks "Claim Your Certificate" on the course page. If
    they're not actually eligible (someone hitting this URL directly
    without having paid/completed everything), just bounce them back to
    the course page rather than erroring — the button simply won't have
    been visible to them in the first place.
    """
    subject = get_object_or_404(Subject, slug=subject_slug, access_type="open")

    if not user_is_eligible_for_certificate(request.user, subject):
        return redirect('public_subject', slug=subject_slug)

    certificate, _ = Certificate.objects.get_or_create(user=request.user, subject=subject)
    return redirect('certificate_view', certificate_id=certificate.certificate_id)


def certificate_view(request, certificate_id):
    """
    Public, no-login-required verification page — this is the whole point
    of a certificate: anyone (an employer, a friend) can check it's real
    by visiting the link, without needing an account.
    """
    certificate = get_object_or_404(Certificate, certificate_id=certificate_id)
    return render(request, "core/certificate.html", {"certificate": certificate})


def certificate_pdf_view(request, certificate_id):
    """Generates the downloadable PDF on the fly — nothing is stored on disk."""
    certificate = get_object_or_404(Certificate, certificate_id=certificate_id)

    import math

    from reportlab.lib.pagesizes import landscape, A4
    from reportlab.lib.units import cm
    from reportlab.lib.colors import HexColor
    from reportlab.pdfgen import canvas

    buffer = io.BytesIO()
    width, height = landscape(A4)
    c = canvas.Canvas(buffer, pagesize=landscape(A4))

    navy = HexColor("#0f172a")
    gold = HexColor("#f59e0b")
    gold_dark = HexColor("#b45309")
    teal = HexColor("#0891b2")
    muted = HexColor("#64748b")
    faint = HexColor("#94a3b8")
    ivory = HexColor("#fffbeb")

    # ---- Background wash ----
    c.setFillColor(ivory)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # ---- Decorative double border ----
    c.setStrokeColor(gold)
    c.setLineWidth(3)
    c.rect(1 * cm, 1 * cm, width - 2 * cm, height - 2 * cm)
    c.setStrokeColor(navy)
    c.setLineWidth(0.6)
    c.rect(1.35 * cm, 1.35 * cm, width - 2.7 * cm, height - 2.7 * cm)

    # ---- Corner flourishes (small double diagonal marks) ----
    def corner_flourish(x, y, dx, dy):
        c.setStrokeColor(gold)
        c.setLineWidth(1.2)
        c.line(x, y, x + dx * 1.1 * cm, y)
        c.line(x, y, x, y + dy * 1.1 * cm)

    m = 1.35 * cm
    corner_flourish(m, height - m, 1, -1)
    corner_flourish(width - m, height - m, -1, -1)
    corner_flourish(m, m, 1, 1)
    corner_flourish(width - m, m, -1, 1)

    # ---- Brand ----
    c.setFont("Helvetica-Bold", 14)
    c.setFillColor(gold_dark)
    c.drawCentredString(width / 2, height - 2.7 * cm, "S T U D Y P A L Z")

    # ---- Thin gold rule ----
    c.setStrokeColor(gold)
    c.setLineWidth(0.75)
    c.line(width / 2 - 2.2 * cm, height - 3.15 * cm, width / 2 + 2.2 * cm, height - 3.15 * cm)

    # ---- Title ----
    c.setFont("Times-Bold", 34)
    c.setFillColor(navy)
    c.drawCentredString(width / 2, height - 4.5 * cm, "Certificate of Completion")

    c.setFont("Helvetica", 12.5)
    c.setFillColor(muted)
    c.drawCentredString(width / 2, height - 5.5 * cm, "This certifies that")

    # ---- Student name ----
    student_name = certificate.user.get_full_name() or certificate.user.username
    c.setFont("Times-BoldItalic", 30)
    c.setFillColor(teal)
    c.drawCentredString(width / 2, height - 6.8 * cm, student_name)

    # underline flourish beneath the name
    name_width = c.stringWidth(student_name, "Times-BoldItalic", 30)
    c.setStrokeColor(gold)
    c.setLineWidth(1)
    c.line(width / 2 - name_width / 2 - 0.4 * cm, height - 7.15 * cm,
           width / 2 + name_width / 2 + 0.4 * cm, height - 7.15 * cm)

    c.setFont("Helvetica", 12.5)
    c.setFillColor(muted)
    c.drawCentredString(width / 2, height - 8 * cm, "has successfully completed the course")

    # ---- Course name ----
    c.setFont("Times-Bold", 22)
    c.setFillColor(navy)
    c.drawCentredString(width / 2, height - 9.15 * cm, certificate.subject.name)

    # ---- Signature block (bottom left) ----
    sig_y = 3.1 * cm
    sig_x = width / 2 - 8 * cm
    c.setStrokeColor(navy)
    c.setLineWidth(0.75)
    c.line(sig_x, sig_y, sig_x + 5.5 * cm, sig_y)
    c.setFont("Times-Italic", 13)
    c.setFillColor(navy)
    c.drawCentredString(sig_x + 2.75 * cm, sig_y + 0.25 * cm, "Aakash Darda")
    c.setFont("Helvetica", 9)
    c.setFillColor(muted)
    c.drawCentredString(sig_x + 2.75 * cm, sig_y - 0.5 * cm, "Founder, StudyPalz")

    # ---- Date block (bottom right) ----
    date_str = certificate.issued_at.strftime("%B %d, %Y")
    date_x = width / 2 + 2.5 * cm
    c.line(date_x, sig_y, date_x + 5.5 * cm, sig_y)
    c.setFont("Times-Italic", 13)
    c.setFillColor(navy)
    c.drawCentredString(date_x + 2.75 * cm, sig_y + 0.25 * cm, date_str)
    c.setFont("Helvetica", 9)
    c.setFillColor(muted)
    c.drawCentredString(date_x + 2.75 * cm, sig_y - 0.5 * cm, "Date Issued")

    # ---- Gold wax-seal medallion ----
    seal_x, seal_y, seal_r = width / 2, height - 10.7 * cm, 1.15 * cm

    # ribbon tails hanging below the seal
    c.setFillColor(gold_dark)
    c.saveState()
    for dx in (-0.35 * cm, 0.35 * cm):
        p = c.beginPath()
        p.moveTo(seal_x + dx - 0.28 * cm, seal_y - seal_r + 0.1 * cm)
        p.lineTo(seal_x + dx + 0.28 * cm, seal_y - seal_r + 0.1 * cm)
        p.lineTo(seal_x + dx, seal_y - seal_r - 1.1 * cm)
        p.close()
        c.drawPath(p, fill=1, stroke=0)
    c.restoreState()

    # outer + inner circle
    c.setFillColor(gold)
    c.circle(seal_x, seal_y, seal_r, fill=1, stroke=0)
    c.setStrokeColor(HexColor("#fde68a"))
    c.setLineWidth(1.2)
    c.circle(seal_x, seal_y, seal_r - 0.18 * cm, fill=0, stroke=1)

    # 6-point star in the center
    c.setFillColor(HexColor("#78350f"))
    star_r_outer = seal_r * 0.55
    star_r_inner = seal_r * 0.25
    path = c.beginPath()
    points = 6
    for i in range(points * 2):
        ang = math.pi / points * i - math.pi / 2
        r = star_r_outer if i % 2 == 0 else star_r_inner
        px = seal_x + r * math.cos(ang)
        py = seal_y + r * math.sin(ang)
        if i == 0:
            path.moveTo(px, py)
        else:
            path.lineTo(px, py)
    path.close()
    c.drawPath(path, fill=1, stroke=0)

    # ---- Footer: certificate ID + verification link ----
    verify_url = request.build_absolute_uri(
        reverse('certificate_view', args=[certificate.certificate_id])
    )
    c.setFont("Helvetica", 9)
    c.setFillColor(faint)
    c.drawCentredString(width / 2, 1.75 * cm, f"Certificate ID: {certificate.certificate_id}")
    c.drawCentredString(width / 2, 1.3 * cm, f"Verify at {verify_url}")

    c.showPage()
    c.save()
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    filename = f"StudyPalz-Certificate-{certificate.subject.slug}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response