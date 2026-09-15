# core/middleware.py

import random
from datetime import timedelta

from django.conf import settings
from django.shortcuts import render
from django.utils import timezone

from .models import BlockedIP


class BotBlockerMiddleware:
    """
    Global anti-abuse middleware.

    BUCKETING (this is the main fix):
      - Logged-in users are rate-limited per account: "user:<id>".
      - Anonymous visitors are rate-limited per (ip, browser session) pair:
        "anon:<ip>:<session_key>" — NOT per raw IP.
        This is what stops two people on the same WiFi / office network /
        mobile-carrier NAT from sharing (and blowing through) one budget.

    ENFORCEMENT (also changed):
      - Exceeding the per-minute budget no longer hard-blocks. It shows a
        tiny math captcha ("7 + 11 = ?"). Solving it immediately clears the
        block and lets the visitor continue.
      - Solving it once marks that browser session as "human_verified" for
        HUMAN_VERIFIED_FOR_MINUTES, so people aren't re-challenged on every
        page.
      - Only a known bot/scraper User-Agent, or a manual admin IP block,
        causes a real PERMANENT block. Rate-limit hits never do.
      - A visitor that keeps failing the captcha (a script blindly
        guessing) gets a fresh short cooldown, but still isn't permanently
        banned — humans occasionally fat-finger a sum.
    """

    MAX_REQUESTS_PER_MINUTE = 100
    COOLDOWN_MINUTES = 15
    HUMAN_VERIFIED_FOR_MINUTES = 60
    MAX_CAPTCHA_FAILURES_BEFORE_EXTRA_COOLDOWN = 8

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

        # Use the REAL configured prefixes, not a hardcoded guess. If
        # STATIC_URL / MEDIA_URL differ from "/static/" / "/media/" in
        # settings.py, every asset request was silently counting against
        # the budget — enough on its own to exhaust it on one page load.
        static_url = getattr(settings, "STATIC_URL", "/static/") or "/static/"
        media_url = getattr(settings, "MEDIA_URL", "/media/") or "/media/"
        exempt_prefixes = (static_url, media_url, "/verify-human/")

        if path.startswith(exempt_prefixes):
            return self.get_response(request)

        ip = self.get_client_ip(request)
        ua = (request.META.get("HTTP_USER_AGENT") or "").lower()

        if not ip:
            return self.get_response(request)

        now = timezone.now()

        # 1) Manual hard block (admin-controlled) — unchanged behavior.
        if ip in self.manual_blocked_ips:
            return render(request, "core/too_many_attempts.html", status=403)

        # 2) Obvious bot UA -> permanent block, checked before we touch
        #    sessions/DB for real visitors at all.
        if any(bad in ua for bad in self.BAD_UA_KEYWORDS):
            identifier = f"ua:{ip}"
            block, _ = BlockedIP.objects.get_or_create(
                identifier=identifier, defaults={"ip": ip}
            )
            block.ip = ip
            block.permanently_blocked = True
            block.save()
            return render(request, "core/too_many_attempts.html", status=403)

        # Make sure we have a stable per-browser session key to bucket
        # anonymous users by (this is what separates two people on the
        # same WiFi from each other).
        if not request.session.session_key:
            request.session.save()
        session_key = request.session.session_key or "no-session"

        if request.user.is_authenticated:
            identifier = f"user:{request.user.id}"
        else:
            identifier = f"anon:{ip}:{session_key}"

        block, _ = BlockedIP.objects.get_or_create(
            identifier=identifier, defaults={"ip": ip}
        )

        # 3) Already permanently blocked (bot UA earlier, or manual).
        if block.permanently_blocked:
            return render(request, "core/too_many_attempts.html", status=403)

        # A browser that recently solved the captcha skips straight
        # through, so people aren't re-challenged on every page.
        verified_until = request.session.get("human_verified_until")
        if verified_until and verified_until > now.timestamp():
            block.ip = ip
            block.last_seen = now
            block.save(update_fields=["ip", "last_seen"])
            return self.get_response(request)

        # 4) Currently in a temporary cooldown -> show the captcha, not a wall.
        if block.blocked_until and block.blocked_until > now:
            return self._render_captcha(request, block)

        # 5) Per-minute rate limiting.
        current_window = now.replace(second=0, microsecond=0)
        if block.window_start != current_window:
            block.window_start = current_window
            block.request_count = 1
        else:
            block.request_count += 1

        block.ip = ip
        block.last_seen = now

        if block.request_count > self.MAX_REQUESTS_PER_MINUTE:
            block.blocked_until = now + timedelta(minutes=self.COOLDOWN_MINUTES)
            block.save()
            return self._render_captcha(request, block)

        block.save()
        return self.get_response(request)

    def _render_captcha(self, request, block):
        num1 = random.randint(1, 15)
        num2 = random.randint(1, 15)
        request.session["captcha_num1"] = num1
        request.session["captcha_num2"] = num2
        request.session["captcha_answer"] = num1 + num2
        request.session["captcha_next"] = request.get_full_path()
        request.session["captcha_identifier"] = block.identifier

        return render(
            request,
            "core/captcha_challenge.html",
            {"num1": num1, "num2": num2},
            status=429,
        )

    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")