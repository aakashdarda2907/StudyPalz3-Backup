# core/views_open_signup.py — NEW FILE.
#
# Completely separate from your existing signup_view in views.py — that
# one is untouched, still requires department, still for college students.
# This is the new /join/ flow for everyone else: no department field at
# all, and a viewer-vs-creator branch.

from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from .models import UserProfile
from .models_marketplace import CreatorProfile


def _safe_next(request, next_url):
    """Only ever redirect to a URL on our own site — never trust an
    arbitrary `next` value blindly (open-redirect protection)."""
    if next_url and url_has_allowed_host_and_scheme(
        url=next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return None


@require_http_methods(["GET", "POST"])
def open_signup_view(request):
    next_url = request.GET.get('next') or request.POST.get('next', '')

    if request.user.is_authenticated:
        return redirect(_safe_next(request, next_url) or 'courses_catalog')

    if request.method == 'POST':
        # honeypot, same pattern as your existing signup_view
        if request.POST.get('website_url'):
            return redirect('home')

        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        account_type = request.POST.get('account_type')  # 'viewer' or 'creator'

        # Creator-only fields
        creator_display_name = request.POST.get('creator_display_name', '').strip()
        creator_bio = request.POST.get('creator_bio', '').strip()

        errors = {}
        if not username:
            errors['username'] = 'Username is required.'
        elif User.objects.filter(username__iexact=username).exists():
            errors['username'] = 'That username is already taken.'
        if password != password_confirm:
            errors['password'] = 'Passwords do not match.'
        if account_type not in ('viewer', 'creator'):
            errors['account_type'] = 'Please choose one.'
        if account_type == 'creator':
            if not creator_display_name:
                errors['creator_display_name'] = 'Tell us what name to show on your courses.'
            if not creator_bio:
                errors['creator_bio'] = 'Tell us a bit about what you want to teach.'

        if errors:
            return render(request, 'core/open_signup.html', {
                'errors': errors,
                'posted': request.POST,
                'next_url': next_url,
            })

        user = User.objects.create_user(
            username=username, password=password, first_name=first_name, email=email,
        )

        # No department — this is the whole point of this signup path.
        UserProfile.objects.create(user=user, department=None, current_streak=0, last_active_at=None)

        if account_type == 'creator':
            CreatorProfile.objects.create(
                user=user,
                display_name=creator_display_name,
                bio=creator_bio,
                status='pending',
            )

        auth_user = authenticate(request, username=username, password=password)
        if auth_user:
            auth_login(request, auth_user)

        safe_next = _safe_next(request, next_url)

        if account_type == 'creator':
            # Still show the pending-review page even if they came from a
            # buy flow — but let them continue to what they were doing.
            return render(request, 'core/open_signup_creator_pending.html', {'next_url': safe_next})

        return redirect(safe_next or 'courses_catalog')

    return render(request, 'core/open_signup.html', {'errors': {}, 'posted': {}, 'next_url': next_url})