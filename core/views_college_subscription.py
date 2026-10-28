# core/views_college_subscription.py — NEW FILE

from decimal import Decimal, ROUND_HALF_UP
from functools import wraps

from django.shortcuts import render, redirect
from django.utils import timezone

from .models import (
    SubscriptionPlan, Purchase, UserProfile, user_has_active_college_subscription,
)


def college_subscription_required(view_func):
    """
    Put this BELOW @login_required on every college-side view. Order of checks:
      1. Open-catalog accounts (no department) never belong on the college
         side -> sent to /courses/.
      2. Everyone else needs Premium (grandfathered), an active college
         plan, or staff status -> otherwise sent to the subscribe page.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        profile = UserProfile.objects.filter(user=request.user).first()
        if profile and profile.department_id is None and not request.user.is_staff:
            return redirect('courses_catalog')
        if not user_has_active_college_subscription(request.user):
            return redirect('college_subscribe')
        return view_func(request, *args, **kwargs)
    return wrapper


def college_subscribe_view(request):
    plans = list(SubscriptionPlan.objects.filter(is_active=True, scope="college"))

    is_premium = False
    active_until = None
    if request.user.is_authenticated:
        profile = UserProfile.objects.filter(user=request.user).first()
        is_premium = bool(profile and profile.is_premium)
        latest = Purchase.objects.filter(
            user=request.user, status="paid", purchase_type="plan",
            plan__scope="college", expires_at__gte=timezone.now(),
        ).order_by("-expires_at").first()
        active_until = latest.expires_at if latest else None

    best_id = max(plans, key=lambda p: p.duration_days).id if len(plans) > 1 else None

    cards = []
    for p in plans:
        per_day = (Decimal(p.final_price) / Decimal(p.duration_days)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        cards.append({"plan": p, "per_day": per_day, "is_best": p.id == best_id})

    return render(request, "core/college_subscribe.html", {
        "cards": cards,
        "is_premium": is_premium,
        "active_until": active_until,
    })
