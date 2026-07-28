# core/middleware.py

from django.utils import timezone
from django.conf import settings
from django.shortcuts import render
from datetime import timedelta

from .models import BlockedIP


class BotBlockerMiddleware:
    """
    Global security middleware that:
    - Ignores static/media files
    - Applies a HUMAN-SAFE global rate limit
    - Temporarily blocks abusive IPs (cooldown)
    - Permanently blocks obvious bots/scrapers
    """

    # ✅ SAFE for humans (≈ 5 req/sec)
    MAX_REQUESTS_PER_MINUTE = 100

    # ⏳ Temporary cooldown duration
    COOLDOWN_MINUTES = 15

    # 🚫 Obvious bot/scraper user agents
    BAD_UA_KEYWORDS = [
        "facebookexternalhit",
        "facebot",
        "twitterbot",
        "discordbot",
        "whatsapp",
        "crawler",
        "scraper",
        "preview",
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        self.manual_blocked_ips = set(getattr(settings, "BLOCKED_IPS", []))

    def __call__(self, request):
        path = request.path

        # ✅ 0) Ignore static & media files completely
        if path.startswith("/static/") or path.startswith("/media/"):
            return self.get_response(request)

        ip = self.get_client_ip(request)
        ua = (request.META.get("HTTP_USER_AGENT") or "").lower()

        if not ip:
            return self.get_response(request)

        now = timezone.now()

        # 1) Manual hard block (admin-controlled)
        if ip in self.manual_blocked_ips:
            return render(request, "core/too_many_attempts.html", status=403)

        block, _ = BlockedIP.objects.get_or_create(ip=ip)

        # 2) Permanent ban (ONLY for obvious bots)
        if block.permanently_blocked:
            return render(request, "core/too_many_attempts.html", status=403)

        # 3) Temporary cooldown check
        if block.blocked_until and block.blocked_until > now:
            return render(request, "core/too_many_attempts.html", status=429)

        # 4) Per-minute rate limiting
        current_window = now.replace(second=0, microsecond=0)

        if block.window_start != current_window:
            block.window_start = current_window
            block.request_count = 1
        else:
            block.request_count += 1

        block.last_seen = now

        # 5) Exceeded limit → TEMPORARY block (NOT permanent)
        if block.request_count > self.MAX_REQUESTS_PER_MINUTE:
            block.blocked_until = now + timedelta(minutes=self.COOLDOWN_MINUTES)
            block.save()
            return render(request, "core/too_many_attempts.html", status=429)

        # 6) Obvious bot UA → PERMANENT ban
        if any(bad in ua for bad in self.BAD_UA_KEYWORDS):
            block.permanently_blocked = True
            block.save()
            return render(request, "core/too_many_attempts.html", status=403)

        # 7) Save normal traffic
        block.save()

        return self.get_response(request)

    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
