from datetime import timedelta
from django.utils import timezone


from django.contrib.auth import authenticate, logout
from django.contrib.auth import login as auth_login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.db.models import Count
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
import random
from datetime import timedelta
from django.http import JsonResponse
from .middleware import BotBlockerMiddleware
from .views_college_subscription import college_subscription_required
from .models import user_has_active_college_subscription

# Third-party imports
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter
from django_ratelimit.decorators import ratelimit
from django.db.models import Count, Q

# Local imports
from .models import Department, Subject, Content, UserContentState, UserProfile, Category


# -------------------------
# PUBLIC VIEWS
# -------------------------


def home_view(request):
    if request.user.is_authenticated:
        try:
            profile = UserProfile.objects.get(user=request.user)
            if profile.department_id is None:
                return redirect('courses_catalog')
        except UserProfile.DoesNotExist:
            pass
        return redirect('dashboard')

    premium_category = Category.objects.filter(is_premium=True).first()
    premium_subjects = (
        premium_category.subjects.select_related('department').all()
        if premium_category else Subject.objects.none()
    )
    context = {
        'premium_subjects': premium_subjects,
        'premium_subject_count': premium_subjects.count(),
    }
    return render(request, 'core/home.html', context)



@require_http_methods(["GET", "POST"])
@ratelimit(key='post:username', rate='10/m', method='POST', block=False)
@ratelimit(key='ip', rate='30/m', method='POST', block=False)
def login_view(request):

    if request.user.is_authenticated:
        return redirect('dashboard')

    is_limited = getattr(request, 'limited', False)

    if request.method == 'POST':

        if is_limited:
            return render(request, 'core/too_many_attempts.html', status=429)

        if request.POST.get('website_url'):
            return redirect('home')

        form = AuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)

            try:
                profile = UserProfile.objects.get(user=user)
            except UserProfile.DoesNotExist:
                logout(request)
                return redirect('login')

            # ==============================
            # ✅ FIXED STREAK LOGIC (IST BASED)
            # ==============================
            # ist = timezone.get_current_timezone()
            # now = timezone.now().astimezone(ist)
            # last_active = profile.last_active_at

            # streak_increased = False

            # if last_active is None:
            #     profile.current_streak = 1
            #     streak_increased = True

            # else:
            #     last_active = last_active.astimezone(ist)
            #     delta_days = (now.date() - last_active.date()).days

            #     if delta_days == 1:
            #         profile.current_streak += 1
            #         streak_increased = True

            #     elif delta_days > 1:
            #         profile.current_streak = 1
            #         streak_increased = True
            #     # delta_days == 0 → same day, do nothing

            # profile.last_active_at = now
            # profile.save()

            # request.session['streak_increased'] = streak_increased
            # ==============================

            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                return redirect(next_url)
            if profile.department_id is None:
                return redirect('courses_catalog')
            return redirect('dashboard')

        return render(request, 'core/login.html', {'form': form})

    return render(request, 'core/login.html', {'form': AuthenticationForm()})


# core/views.py — additions.
#
# 1) At the top of views.py, make sure these imports exist:
#      import random
#      from datetime import timedelta
#      from django.http import JsonResponse   # <-- was MISSING; used in
#                                              #     update_dashboard_filters_view
#                                              #     and would 500 on every call.
#      from .middleware import BotBlockerMiddleware
#
# 2) Paste this view anywhere in views.py (e.g. near login_view):

@require_http_methods(["POST"])
def verify_human_view(request):
    """
    Handles the math captcha shown when a bucket (a logged-in user, or an
    anonymous ip+browser-session pair) trips the rate limit.

    Correct answer -> block is cleared immediately and the visitor is sent
    back to the page they were trying to reach.
    Wrong answer -> a fresh question is shown; no permanent penalty for a
    human mistyping a sum. Repeated wrong answers (a script blindly
    guessing) just get a fresh short cooldown, not a permanent ban.
    """
    expected = request.session.get("captcha_answer")
    identifier = request.session.get("captcha_identifier")
    next_url = request.session.get("captcha_next") or "home"

    try:
        submitted = int(request.POST.get("answer", "").strip())
    except (TypeError, ValueError):
        submitted = None

    block = BlockedIP.objects.filter(identifier=identifier).first() if identifier else None

    if submitted is not None and expected is not None and submitted == expected:
        if block:
            block.blocked_until = None
            block.request_count = 0
            block.captcha_failures = 0
            block.save()

        request.session["human_verified_until"] = (
            timezone.now() + timedelta(minutes=BotBlockerMiddleware.HUMAN_VERIFIED_FOR_MINUTES)
        ).timestamp()

        for key in ("captcha_num1", "captcha_num2", "captcha_answer", "captcha_next", "captcha_identifier"):
            request.session.pop(key, None)

        return redirect(next_url)

    # Wrong answer.
    if block:
        block.captcha_failures += 1
        if block.captcha_failures >= BotBlockerMiddleware.MAX_CAPTCHA_FAILURES_BEFORE_EXTRA_COOLDOWN:
            block.blocked_until = timezone.now() + timedelta(
                minutes=BotBlockerMiddleware.COOLDOWN_MINUTES
            )
        block.save()

    num1 = random.randint(1, 15)
    num2 = random.randint(1, 15)
    request.session["captcha_num1"] = num1
    request.session["captcha_num2"] = num2
    request.session["captcha_answer"] = num1 + num2

    return render(
        request,
        "core/captcha_challenge.html",
        {"num1": num1, "num2": num2, "error": "That wasn't quite right — try again."},
        status=429,
    )




@require_http_methods(["GET", "POST"])
@ratelimit(key='ip', rate='20/m', method='POST', block=False)
def signup_view(request):

    departments = Department.objects.all()
    is_limited = getattr(request, 'limited', False)

    if request.method == 'POST':

        if is_limited:
            return render(request, 'core/too_many_attempts.html', status=429)

        if request.POST.get('website_url'):
            return redirect('home')

        username = request.POST.get('username')
        first_name = request.POST.get('name')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        department_id = request.POST.get('department')

        if password != password_confirm:
            return render(request, 'core/signup.html', {
                'error': 'Passwords do not match',
                'departments': departments
            })

        if User.objects.filter(username__iexact=username).exists():
            return render(request, 'core/signup.html', {
                'error': 'Username already exists',
                'departments': departments
            })

        if not department_id:
            return render(request, 'core/signup.html', {
                'error': 'Please select a department',
                'departments': departments
            })

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
        )

        department = get_object_or_404(Department, id=department_id)

        UserProfile.objects.create(
            user=user,
            department=department,
            current_streak=0,
            last_active_at=None
        )

        user = authenticate(request, username=username, password=password)
        if user:
            auth_login(request, user)
            return redirect('dashboard')

        return render(request, 'core/signup.html', {
            'error': 'Account created. Please log in manually.',
            'departments': departments
        })

    return render(request, 'core/signup.html', {'departments': departments})


def logout_view(request):
    """Log the user out and go back home."""
    logout(request)
    return redirect('home')


# -------------------------
# AUTHENTICATED VIEWS
# -------------------------
@login_required
@college_subscription_required
def dashboard_view(request):
    """
    Dashboard:
    - Updates streak once per calendar day (IST based)
    - Works even if user stays logged in
    """

    try:
        profile = UserProfile.objects.select_related('department').get(user=request.user)
    except UserProfile.DoesNotExist:
        return redirect('logout')
    if profile.department_id is None:
        return redirect('courses_catalog')

        # One-time auto-pin: give existing/new students a populated dashboard
    # on their very first visit, instead of an empty "pin something"
    # screen. Only ever runs once per account.
    if not profile.pins_initialized:
        own_dept_subjects = Subject.objects.filter(department=profile.department, access_type='college')
        profile.pinned_subjects.set(own_dept_subjects)
        profile.pins_initialized = True
        profile.save(update_fields=['pins_initialized'])

    # ==============================
    # ✅ DAILY STREAK LOGIC (IST)
    # ==============================
    ist = timezone.get_current_timezone()
    now = timezone.now().astimezone(ist)
    last_active = profile.last_active_at

    streak_increased = False

    if last_active is None:
        profile.current_streak = 1
        streak_increased = True

    else:
        last_active = last_active.astimezone(ist)
        delta_days = (now.date() - last_active.date()).days

        if delta_days == 1:
            profile.current_streak += 1
            streak_increased = True

        elif delta_days > 1:
            profile.current_streak = 1
            streak_increased = True
        # delta_days == 0 → same day, do nothing

    profile.last_active_at = now
    profile.save()
    # ==============================

    # ---------------------------------------
    # SUBJECT PROGRESS (UNCHANGED)
    # ---------------------------------------
    user_department = profile.department
    department_subject_ids = set(
        Subject.objects.filter(department=user_department).values_list('id', flat=True)
    ) if user_department else set()
    pinned_subject_ids = set(profile.pinned_subjects.values_list('id', flat=True))

    all_subjects = Subject.objects.filter(access_type="college").select_related('department').prefetch_related('categories').all()
    user_states = UserContentState.objects.filter(user=request.user).select_related('content__subject')

    total_content_counts = Content.objects.filter(subject__in=all_subjects).values('subject').annotate(total=Count('id'))
    total_content_map = {item['subject']: item['total'] for item in total_content_counts}

    completed_content_map = {}
    for state in user_states.filter(is_completed=True):
        sid = state.content.subject.id
        completed_content_map[sid] = completed_content_map.get(sid, 0) + 1

    subject_progress = []
    for subject in all_subjects:
        total = total_content_map.get(subject.id, 0)
        completed = completed_content_map.get(subject.id, 0)
        percent = int((completed / total) * 100) if total > 0 else 0
        subject_progress.append({
            'subject': subject,
            'percentage': percent,
            'is_own_department': subject.id in department_subject_ids,
            'is_pinned': subject.id in pinned_subject_ids,
            'category_ids': list(subject.categories.values_list('id', flat=True)),
            'is_premium_subject': any(c.is_premium for c in subject.categories.all()),
        })

    categories = Category.objects.all()
    active_category_ids = set(profile.active_filter_categories.values_list('id', flat=True))
    premium_category = categories.filter(is_premium=True).first()
    premium_subject_count = premium_category.subjects.count() if premium_category else 0

    context = {
        'subject_progress': subject_progress,
        'current_streak': profile.current_streak or 0,
        'streak_increased': streak_increased,
        'user_department': user_department,
        'is_premium_user': profile.is_premium,
        'categories': categories,
        'active_category_ids': active_category_ids,
        'show_all_departments': profile.show_all_departments,
        'premium_category': premium_category,
        'premium_subject_count': premium_subject_count,
    }
    return render(request, 'core/dashboard.html', context)


@login_required
@require_http_methods(["POST"])
def update_dashboard_filters_view(request):
    """AJAX endpoint — saves active category chips + dept toggle to the user's account."""
    profile = get_object_or_404(UserProfile, user=request.user)
    category_ids = request.POST.getlist('category_ids[]')
    show_all = request.POST.get('show_all_departments') == 'true'

    valid_ids = Category.objects.filter(id__in=category_ids).values_list('id', flat=True)
    profile.active_filter_categories.set(valid_ids)
    profile.show_all_departments = show_all
    profile.save(update_fields=['show_all_departments'])

    return JsonResponse({'status': 'ok'})

@login_required
@require_http_methods(["POST"])
def toggle_pin_subject_view(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    profile = get_object_or_404(UserProfile, user=request.user)

    if profile.pinned_subjects.filter(id=subject.id).exists():
        profile.pinned_subjects.remove(subject)
    else:
        profile.pinned_subjects.add(subject)

    return redirect(request.META.get('HTTP_REFERER') or 'dashboard')


@login_required
@college_subscription_required
def subject_detail_view(request, subject_id):
    """
    Subject detail:
    - Shows all Content under the subject
    - Attaches is_completed / marked_for_revision flags from UserContentState
    - Orders content by created_at, then id
    """
    subject = get_object_or_404(Subject, id=subject_id)
    try:
        viewer_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        viewer_profile = None
    is_premium_user = bool(viewer_profile and viewer_profile.is_premium) or user_has_active_college_subscription(request.user)
    # No module_number field in Content, so order by created_at and id
    content_list = Content.objects.filter(subject=subject).order_by('unit_number', '-created_at', 'id')

    # Get user's progress for this subject in one query
    user_progress = UserContentState.objects.filter(
        user=request.user,
        content__subject=subject
    ).values('content_id', 'is_completed', 'marked_for_revision')

    progress_map = {item['content_id']: item for item in user_progress}

    completed_content_count = 0
    for content in content_list:
        progress = progress_map.get(content.id)

        if progress:
            content.is_completed = progress['is_completed']
            content.marked_for_revision = progress['marked_for_revision']
        else:
            content.is_completed = False
            content.marked_for_revision = False

        if content.is_completed:
            completed_content_count += 1

    syllabus_topics = subject.syllabus.splitlines() if subject.syllabus else []

    total_content_count = content_list.count()

    remaining_count = total_content_count - completed_content_count

    context = {
        'subject': subject,
        'content_list': content_list,
        'syllabus_topics': syllabus_topics,
        'total_content_count': content_list.count(),
        'completed_content_count': completed_content_count,
        'remaining_count': remaining_count,
        'is_premium_user': is_premium_user,

    }
    return render(request, 'core/subject_detail.html', context)


@login_required
@college_subscription_required
def content_detail_view(request, content_id):
    content = get_object_or_404(Content, id=content_id)

    try:
        viewer_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        viewer_profile = None
    is_premium_user = bool(viewer_profile and viewer_profile.is_premium) or user_has_active_college_subscription(request.user)

    # 🔒 Premium gate — check the user's own premium status
    if content.is_premium and not is_premium_user:
        return render(request, 'core/premium_upgrade.html', {
            'content': content,
        })

    highlighted_code = None
    pygments_css = None

    try:
        user_state = UserContentState.objects.get(user=request.user, content=content)
    except UserContentState.DoesNotExist:
        user_state = None

    if content.content_type == 'Lab' and content.solution_code:
        lexer = get_lexer_by_name('cpp', stripall=True)
        formatter = HtmlFormatter(style='solarized-dark', full=False, linenos=True)
        highlighted_code = highlight(content.solution_code, lexer, formatter)
        pygments_css = formatter.get_style_defs('.highlight')

    context = {
        'content': content,
        'highlighted_code': highlighted_code,
        'pygments_css': pygments_css,
        'is_completed': user_state.is_completed if user_state else False,
        'marked_for_revision': user_state.marked_for_revision if user_state else False,
        'is_premium_user': is_premium_user,
    }
    return render(request, 'core/content_detail.html', context)


@login_required
@require_http_methods(["POST"])
def toggle_complete_view(request, content_id):
    """
    Toggle completion state for a content item.
    (No streak logic here anymore.)
    """
    content = get_object_or_404(Content, id=content_id)
    state, _ = UserContentState.objects.get_or_create(user=request.user, content=content)
    state.is_completed = not state.is_completed
    state.save()

    return redirect(request.META.get('HTTP_REFERER') or 'subject_detail', subject_id=content.subject.id)


@login_required
@require_http_methods(["POST"])
def toggle_revision_view(request, content_id):
    """
    Toggle 'marked for revision' for a content item.
    (No streak logic here anymore.)
    """
    content = get_object_or_404(Content, id=content_id)
    state, _ = UserContentState.objects.get_or_create(user=request.user, content=content)
    state.marked_for_revision = not state.marked_for_revision
    state.save()

    return redirect(request.META.get('HTTP_REFERER') or 'subject_detail', subject_id=content.subject.id)


@login_required
@college_subscription_required
def revision_hub_view(request):
    """
    Shows all content the user has marked for revision.
    """
    revision_items = Content.objects.filter(
        usercontentstate__user=request.user,
        usercontentstate__marked_for_revision=True
    ).select_related('subject')

    context = {'revision_items': revision_items}
    return render(request, 'core/revision_hub.html', context)


@login_required
@require_http_methods(["POST"])
def feedback_view(request, content_id):
    """
    Upvote/downvote a content item as helpful/unhelpful.
    Each user can vote only once per content.
    """
    content = get_object_or_404(Content, id=content_id)
    vote_type = request.POST.get('vote_type')

    # Prevent double voting using the many-to-many relation
    if content.users_voted.filter(id=request.user.id).exists():
        return redirect('content_detail', content_id=content_id)

    if vote_type == 'helpful':
        content.helpful_votes += 1
    elif vote_type == 'unhelpful':
        content.unhelpful_votes += 1

    content.users_voted.add(request.user)
    content.save()

    return redirect('content_detail', content_id=content_id)

# ... existing imports ...

# -------------------------
# ERROR HANDLERS
# -------------------------

def custom_404(request, exception):
    """
    Custom 404 error handler.
    Renders a friendly 'Page Not Found' template.
    """
    return render(request, 'core/404.html', status=404)


@login_required
def profile_view(request):
    user = request.user
    profile = get_object_or_404(UserProfile, user=user)

    # --- 1. Handle Profile Edits (POST) ---
    if request.method == 'POST':
        user.first_name = request.POST.get('first_name', '').strip()
        user.last_name = request.POST.get('last_name', '').strip()
        user.email = request.POST.get('email', '').strip()
        user.save()
        return redirect('profile')

    # --- 2. Calculate User's Study Stats ---
    completed_topics_count = UserContentState.objects.filter(
        user=user,
        is_completed=True
    ).count()

    # --- 3. The Leaderboards ---

    # 48-Hour Cutoff Logic
    forty_eight_hours_ago = timezone.now() - timedelta(hours=48)

    # Top 5 Students by Streak (Must be active in last 48h AND have a streak > 0)
    top_streak_users = UserProfile.objects.select_related('user').filter(
        last_active_at__gte=forty_eight_hours_ago,
        current_streak__gt=0
    ).order_by('-current_streak')[:5]

    # Top 3 Students by Topics Completed
    top_topics_users = User.objects.annotate(
        completed_count=Count(
            'usercontentstate',
            filter=Q(usercontentstate__is_completed=True)
        )
    ).order_by('-completed_count')[:3]

    context = {
        'profile': profile,
        'completed_topics_count': completed_topics_count,
        'top_streak_users': top_streak_users,
        'top_topics_users': top_topics_users,
    }
    return render(request, 'core/profile.html', context)

def premium_upgrade_view(request):
    premium_category = Category.objects.filter(is_premium=True).first()
    premium_subjects = (
        premium_category.subjects.select_related('department').all()
        if premium_category else Subject.objects.none()
    )
    is_already_premium = False
    if request.user.is_authenticated:
        profile = UserProfile.objects.filter(user=request.user).first()
        is_already_premium = bool(profile and profile.is_premium)

    context = {
        'premium_subjects': premium_subjects,
        'premium_subject_count': premium_subjects.count(),
        'is_already_premium': is_already_premium,
    }
    return render(request, 'core/premium_upgrade.html', context)

def forgot_password_view(request):
    """
    Since we don't collect emails, users must contact admin to reset.
    """
    return render(request, 'core/forgot_password.html')

from django.http import JsonResponse  # add if not already imported

@login_required
@require_http_methods(["POST"])
def toggle_pin_subject_ajax_view(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)
    profile = get_object_or_404(UserProfile, user=request.user)

    if profile.pinned_subjects.filter(id=subject.id).exists():
        profile.pinned_subjects.remove(subject)
        is_pinned = False
    else:
        profile.pinned_subjects.add(subject)
        is_pinned = True

    return JsonResponse({'status': 'ok', 'is_pinned': is_pinned})