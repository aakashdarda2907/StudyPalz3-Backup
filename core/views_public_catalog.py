# core/views_public_catalog.py — UPDATED (adds YouTube embed-URL conversion
# for public_content_view; everything else unchanged from before).
#
# These are deliberately NOT @login_required — anyone with your YouTube
# link should land here and see the video + a preview or the full notes,
# no wall in front of *browsing*. Login is only enforced at the "Buy"
# click (create_order_view in views_payments.py IS @login_required — an
# anonymous click there 302s to /login/?next=<this page>).

import re

from django.shortcuts import render, get_object_or_404

from .models import Content, Subject, SubscriptionPlan, user_has_access


def _youtube_embed_url(url):
    """
    Accepts any common YouTube URL shape (watch?v=, youtu.be/, shorts/,
    already-embed) and returns an /embed/<id> URL safe to put in an
    <iframe>. Plain watch-page URLs refuse to load inside an iframe, so
    this conversion is required, not cosmetic. Returns None if no video
    ID could be found (template just skips the video block then).
    """
    if not url:
        return None
    patterns = [
        r"(?:v=|/embed/|youtu\.be/|/shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return f"https://www.youtube.com/embed/{match.group(1)}"
    return None


def courses_catalog_view(request):
    """
    Public /courses/ page — the 'Open' section. A separate paid catalog
    for everyone, including your own logged-in college students —
    access_type='college' subjects never appear here.
    """
    open_subjects = (
        Subject.objects.filter(access_type="open")
        .select_related("department")
        .prefetch_related("categories", "contents")
    )
    plans = SubscriptionPlan.objects.filter(is_active=True)

    context = {
        "open_subjects": open_subjects,
        "plans": plans,
    }
    return render(request, "core/courses_catalog.html", context)


def public_subject_view(request, slug):
    """Public course landing page — chapter list, locked/unlocked state per chapter."""
    subject = get_object_or_404(Subject, slug=slug, access_type="open")
    contents = subject.contents.order_by("unit_number", "created_at")

    chapters = [
        {"content": c, "has_access": user_has_access(request.user, c)}
        for c in contents
    ]

    context = {
        "subject": subject,
        "chapters": chapters,
        "plans": SubscriptionPlan.objects.filter(is_active=True),
    }
    return render(request, "core/public_subject.html", context)


def public_content_view(request, slug):
    """
    The actual shareable link for your YouTube description / pinned
    comment: studypalz.com/c/<slug>/
    Shows the video always; shows full notes only if unlocked, otherwise a
    teaser + the three buy options (chapter / whole subject / monthly
    plan — template only renders the ones that are actually priced).
    """
    content = get_object_or_404(Content, slug=slug)
    has_access = user_has_access(request.user, content)

    context = {
        "content": content,
        "subject": content.subject,
        "has_access": has_access,
        "embed_url": _youtube_embed_url(content.youtube_link),
        "plans": SubscriptionPlan.objects.filter(is_active=True) if not has_access else None,
    }
    return render(request, "core/public_content.html", context)
