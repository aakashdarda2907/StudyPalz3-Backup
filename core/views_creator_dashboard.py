# core/views_creator_dashboard.py — NEW FILE.
#
# Self-serve dashboard for APPROVED creators: list their courses, create
# new ones, add/edit chapters. Every view here is scoped so a creator can
# only ever touch their own courses — there's no way to reach someone
# else's Subject/Content through these URLs, even by guessing an ID.

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods

from .models import Subject, Content, Department, Category
from .models_marketplace import CreatorProfile, CourseOwnership, CreatorEarning


def creator_required(view_func):
    """
    Only lets APPROVED creators through. No profile at all -> sent to
    apply. A pending/rejected profile -> shown a status page instead of
    the dashboard (so it's clear what's going on, not just a blank 403).
    """
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        profile = CreatorProfile.objects.filter(user=request.user).first()
        if not profile:
            return redirect('open_signup')
        if profile.status != 'approved':
            return render(request, 'core/creator_not_approved.html', {'profile': profile})
        return view_func(request, *args, **kwargs, creator_profile=profile)
    return wrapper


@creator_required
def creator_dashboard_view(request, creator_profile):
    ownerships = (
        CourseOwnership.objects.filter(owner=request.user)
        .select_related('subject')
        .order_by('-submitted_at')
    )

    earnings = CreatorEarning.objects.filter(owner=request.user)
    total_earned = earnings.aggregate(total=Sum('amount'))['total'] or 0
    total_unpaid = earnings.filter(payout_status='unpaid').aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'creator_profile': creator_profile,
        'ownerships': ownerships,
        'total_earned': total_earned,
        'total_unpaid': total_unpaid,
    }
    return render(request, 'core/creator_dashboard.html', context)


@creator_required
@require_http_methods(["GET", "POST"])
def creator_create_course_view(request, creator_profile):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        syllabus = request.POST.get('syllabus', '').strip()
        price = request.POST.get('price', '').strip() or None

        errors = {}
        if not name:
            errors['name'] = 'Course name is required.'

        if not errors:
            # department is irrelevant for open/creator courses — placeholder
            # default only, never shown to the creator.
            department, _ = Department.objects.get_or_create(id=1, defaults={'name': 'General'})

            subject = Subject.objects.create(
                name=name,
                syllabus=syllabus,
                department=department,
                access_type='open',
                price=price,
            )
            category_ids = request.POST.getlist('categories')
            if category_ids:
                subject.categories.set(Category.objects.filter(id__in=category_ids, is_open_category=True))
            CourseOwnership.objects.create(
                subject=subject,
                owner=request.user,
                revenue_split_percent=70,
                review_status='pending',
            )
            return redirect('creator_course_detail', slug=subject.slug)

        return render(request, 'core/creator_create_course.html', {
            'errors': errors, 'posted': request.POST, 'categories': Category.objects.filter(is_open_category=True),
        })

    return render(request, 'core/creator_create_course.html', {
        'errors': {}, 'posted': {}, 'categories': Category.objects.filter(is_open_category=True),
    })


@creator_required
def creator_course_detail_view(request, slug, creator_profile):
    ownership = get_object_or_404(CourseOwnership, subject__slug=slug, owner=request.user)
    subject = ownership.subject
    chapters = subject.contents.order_by('unit_number', 'created_at')

    context = {
        'ownership': ownership,
        'subject': subject,
        'chapters': chapters,
    }
    return render(request, 'core/creator_course_detail.html', context)


@creator_required
@require_http_methods(["GET", "POST"])
def creator_chapter_form_view(request, slug, content_id=None, creator_profile=None):
    """Shared add/edit form — content_id is None when creating a new chapter."""
    ownership = get_object_or_404(CourseOwnership, subject__slug=slug, owner=request.user)
    subject = ownership.subject

    chapter = None
    if content_id:
        chapter = get_object_or_404(Content, id=content_id, subject=subject)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        unit_number = request.POST.get('unit_number') or None
        content_type = request.POST.get('content_type', 'Theory')
        youtube_link = request.POST.get('youtube_link', '').strip()
        notes = request.POST.get('notes', '')
        price = request.POST.get('price', '').strip() or None

        errors = {}
        if not title:
            errors['title'] = 'Title is required.'

        if not errors:
            if chapter is None:
                chapter = Content(subject=subject)
            chapter.title = title
            chapter.unit_number = unit_number
            chapter.content_type = content_type
            chapter.youtube_link = youtube_link
            chapter.notes = notes
            chapter.price = price
            chapter.save()
            return redirect('creator_course_detail', slug=subject.slug)

        # Redisplay exactly what was submitted, as a plain dict — never
        # chain attribute access on `chapter` here, it may still be None.
        form_values = {
            'title': title, 'unit_number': unit_number, 'content_type': content_type,
            'youtube_link': youtube_link, 'notes': notes, 'price': price,
        }
        return render(request, 'core/creator_chapter_form.html', {
            'subject': subject, 'chapter': chapter, 'errors': errors, 'form_values': form_values,
        })

    # GET: prefill from the existing chapter if editing, or blank defaults if adding.
    form_values = {
        'title': chapter.title if chapter else '',
        'unit_number': chapter.unit_number if chapter else '',
        'content_type': chapter.content_type if chapter else 'Theory',
        'youtube_link': chapter.youtube_link if chapter else '',
        'notes': chapter.notes if chapter else '',
        'price': chapter.price if chapter else '',
    }
    return render(request, 'core/creator_chapter_form.html', {
        'subject': subject, 'chapter': chapter, 'errors': {}, 'form_values': form_values,
    })