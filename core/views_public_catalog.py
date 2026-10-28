# core/views_public_catalog.py — UPDATED (adds YouTube embed-URL conversion
# for public_content_view; everything else unchanged from before).
#
# These are deliberately NOT @login_required — anyone with your YouTube
# link should land here and see the video + a preview or the full notes,
# no wall in front of *browsing*. Login is only enforced at the "Buy"
# click (create_order_view in views_payments.py IS @login_required — an
# anonymous click there 302s to /login/?next=<this page>).

import re

from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods

from .models import (
    Content, Subject, SubscriptionPlan, UserContentState, user_has_access,
    Certificate, user_is_eligible_for_certificate, CourseOwnership, Category,
)


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
    Public /courses/ page — the 'Open' section, organized Spotify-style
    into horizontal-scroll sections by Category (only categories flagged
    is_open_category=True — college-dashboard categories like '4th Sem'
    never leak in here). A separate paid catalog for everyone, including
    your own logged-in college students — access_type='college' subjects
    never appear here.
    """
    open_subjects = (
        Subject.objects.filter(access_type="open")
        .exclude(ownership__review_status__in=["pending", "rejected"])
        .select_related("department")
        .prefetch_related("categories", "contents")
    )

    open_categories = Category.objects.filter(is_open_category=True).order_by("order", "name")

    sections = []
    categorized_subject_ids = set()

    for category in open_categories:
        subjects_in_category = [s for s in open_subjects if category in s.categories.all()]
        if subjects_in_category:
            sections.append({"title": category.name, "subjects": subjects_in_category})
            categorized_subject_ids.update(s.id for s in subjects_in_category)

    uncategorized = [s for s in open_subjects if s.id not in categorized_subject_ids]
    if uncategorized:
        sections.append({"title": "More Courses", "subjects": uncategorized})

    plans = SubscriptionPlan.objects.filter(is_active=True)

    context = {
        "sections": sections,
        "has_any_courses": bool(open_subjects),
        "plans": plans,
    }
    return render(request, "core/courses_catalog.html", context)


def public_subject_view(request, slug):
    """Public course landing page — chapter list, locked/unlocked state per chapter."""
    subject = get_object_or_404(
        Subject.objects.exclude(ownership__review_status__in=["pending", "rejected"]),
        slug=slug, access_type="open",
    )
    contents = subject.contents.order_by("unit_number", "created_at")

    chapters = [
        {"content": c, "has_access": user_has_access(request.user, c)}
        for c in contents
    ]

    existing_certificate = None
    is_eligible_for_certificate = False
    if request.user.is_authenticated:
        existing_certificate = Certificate.objects.filter(user=request.user, subject=subject).first()
        if not existing_certificate:
            is_eligible_for_certificate = user_is_eligible_for_certificate(request.user, subject)

    context = {
        "subject": subject,
        "chapters": chapters,
        "plans": SubscriptionPlan.objects.filter(is_active=True),
        "existing_certificate": existing_certificate,
        "is_eligible_for_certificate": is_eligible_for_certificate,
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

    is_completed = False
    if request.user.is_authenticated:
        is_completed = UserContentState.objects.filter(
            user=request.user, content=content, is_completed=True
        ).exists()

    full_notes = content.notes or ""
    word_count = len(full_notes.split())
    reading_time = max(1, round(word_count / 200))  # ~200 wpm

    # SECURITY: when locked, only a short preview is ever sent to the
    # browser. The CSS fade-out is cosmetic; this is the real gate —
    # Inspect/View Source can't reveal text the server never sent.
    if has_access:
        notes_display = full_notes
    else:
        words = full_notes.split(" ")
        notes_display = " ".join(words[:90]) + ("…" if len(words) > 90 else "")

    context = {
        "content": content,
        "notes_display": notes_display,
        "subject": content.subject,
        "has_access": has_access,
        "is_completed": is_completed,
        "embed_url": _youtube_embed_url(content.youtube_link),
        "reading_time": reading_time,
        "plans": SubscriptionPlan.objects.filter(is_active=True) if not has_access else None,
    }
    return render(request, "core/public_content.html", context)


@login_required
@require_http_methods(["POST"])
def toggle_complete_public_view(request, content_id):
    """
    Dedicated mark-complete endpoint for the public content page — kept
    separate from the college dashboard's toggle_complete_view so it
    redirects back to /c/<slug>/ specifically and never risks touching
    that existing flow.
    """
    content = get_object_or_404(Content, id=content_id)
    state, _ = UserContentState.objects.get_or_create(user=request.user, content=content)
    state.is_completed = not state.is_completed
    state.save()
    return redirect('public_content', slug=content.slug)