# core/models.py
#
# This is the FULL file — replace your current core/models.py with this
# entirely (don't merge by hand). It contains:
#   - Everything you already had (Department, Category, Subject, UserProfile,
#     Content, UserContentState, BlockedIP) — logic unchanged except where
#     noted below.
#   - New fields on Subject and Content for the Open catalog + pricing.
#   - New models: SubscriptionPlan, Purchase.
#   - BlockedIP updated for the captcha-based anti-abuse middleware
#     (already live if you did that step — same as before).
#
# WHAT CHANGED vs your original, in plain terms:
#   Subject   -> added access_type, price, slug
#   Content   -> added price, slug   (notes/notes_html: see note below)
#   BlockedIP -> identifier-based bucketing + captcha_failures (unchanged
#                from the earlier step, included here for completeness)
#   NEW: SubscriptionPlan, Purchase, user_has_access()
#
# On notes formatting: for now `notes` stays a plain TextField. Nothing
# stops you from pasting already-formatted HTML into it today (e.g. from
# any free online rich-text editor) and rendering it with `|safe` in the
# template — that alone gets you headings/bold/color. Swapping to a proper
# in-admin rich text editor (django-ckeditor) is a separate, later step
# that needs a pip install; we'll do that once this part is settled.

import random
import string
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


# =====================================================================
# EXISTING MODELS
# =====================================================================

class Department(models.Model):
    """
    Academic department, e.g. CSAI, AIDS, IOT.
    """
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Category(models.Model):
    """
    Cross-cutting tag for Subjects: '4th Sem', '5th Sem', 'Premium', etc.
    Fully admin-manageable — add new ones anytime without code changes.
    """
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)
    is_premium = models.BooleanField(
        default=False,
        help_text="Mark this as the special Premium category — gets splashy treatment and ignores department restrictions."
    )
    order = models.PositiveIntegerField(default=0, help_text="Lower numbers appear first in filter chips.")

    class Meta:
        ordering = ['order', 'name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


def _generate_subject_slug(name):
    base = slugify(name)
    slug = base
    n = 1
    while Subject.objects.filter(slug=slug).exists():
        n += 1
        slug = f"{base}-{n}"
    return slug


class Subject(models.Model):
    ACCESS_TYPE_CHOICES = [
        ("college", "College"),   # existing behavior: gated by Department, shows in the college dashboard
        ("open", "Open"),         # NEW: public, paid catalog course, shown at /courses/ — never department-gated
    ]

    name = models.CharField(max_length=100)
    syllabus = models.TextField(blank=True, null=True, help_text="Enter each syllabus topic on a new line.")
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='subjects', default=1)

    categories = models.ManyToManyField(Category, related_name='subjects', blank=True)
    is_pinned = models.BooleanField(default=False, help_text="Pinned subjects always appear at the top.")
    created_at = models.DateTimeField(default=timezone.now)

    # --- NEW: Open catalog support ---
    access_type = models.CharField(
        max_length=10, choices=ACCESS_TYPE_CHOICES, default="college",
        help_text="'open' subjects are the public paid catalog — separate from the college dashboard, paid for by everyone.",
    )
    price = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Price (INR) to unlock the WHOLE subject/course as a bundle. Leave blank if it's not sold as a bundle.",
    )
    slug = models.SlugField(max_length=120, unique=True, blank=True, help_text="Auto-generated if left blank.")
    class Meta:
        ordering = ['-is_pinned', '-created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _generate_subject_slug(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.department.name})"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    current_streak = models.IntegerField(default=0)
    last_active_at = models.DateTimeField(null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, related_name='users', null=True, blank=True, default=1)
    is_premium = models.BooleanField(default=False)
    premium_since = models.DateTimeField(null=True, blank=True)
    pinned_subjects = models.ManyToManyField(Subject, related_name='pinned_by_profiles', blank=True)

    active_filter_categories = models.ManyToManyField(Category, related_name='active_by_profiles', blank=True)
    show_all_departments = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}'s Profile"


def _generate_content_slug():
    """Short, random, non-guessable — this is what goes in a public
    shareable link like studypalz.com/c/<slug>/, so it should NOT be
    predictable from the content's title or id."""
    alphabet = string.ascii_lowercase + string.digits
    while True:
        candidate = ''.join(random.choices(alphabet, k=8))
        if not Content.objects.filter(slug=candidate).exists():
            return candidate


class Content(models.Model):
    """
    Individual content items (Theory / Lab) under a subject.
    Includes notes, viva, problem statement, solution code, etc.
    """
    CONTENT_TYPE_CHOICES = [
        ('Theory', 'Theory'),
        ('Lab', 'Lab'),
    ]

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='contents'
    )
    title = models.CharField(max_length=200)
    unit_number = models.PositiveIntegerField(null=True, blank=True, help_text="Unit/chapter number, used for ordering")
    content_type = models.CharField(max_length=10, choices=CONTENT_TYPE_CHOICES)
    is_premium = models.BooleanField(default=False)

    youtube_link = models.URLField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    viva_questions = models.TextField(blank=True, null=True)
    problem_statement = models.TextField(blank=True, null=True)
    solution_code = models.TextField(blank=True, null=True)
    explanation = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    helpful_votes = models.IntegerField(default=0)
    unhelpful_votes = models.IntegerField(default=0)
    users_voted = models.ManyToManyField(
        User,
        related_name='voted_content',
        blank=True
    )

    # --- NEW: per-chapter pricing + public shareable slug ---
    price = models.DecimalField(
        max_digits=8, decimal_places=2, null=True, blank=True,
        help_text="Price (INR) to unlock just THIS chapter individually. Leave blank if not sold on its own.",
    )
    slug = models.SlugField(
        max_length=20, unique=True, blank=True,
        help_text="Auto-generated random slug — this is the public link, e.g. studypalz.com/c/<slug>/",
    )

    class Meta:
        ordering = ['created_at']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = _generate_content_slug()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.subject.name} - {self.title}"


class UserContentState(models.Model):
    """
    Per-user state for each Content:
    - completed / not
    - marked for revision / not
    - timestamps for streak/engagement tracking
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.ForeignKey(Content, on_delete=models.CASCADE)
    is_completed = models.BooleanField(default=False)
    marked_for_revision = models.BooleanField(default=False)

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'content')

    def __str__(self):
        return f"{self.user.username} - {self.content.title}"


class BlockedIP(models.Model):
    """
    One row per rate-limit bucket (anti-abuse middleware).

    `identifier` is the actual bucket key used by the middleware:
      - "user:<id>"           for logged-in users
      - "anon:<ip>:<session>" for anonymous visitors
      - "ua:<ip>"             for known-bot User-Agents (permanent bans)

    `ip` is kept purely for admin reference/search — it is NOT what's used
    for rate-limit bucketing.
    """
    identifier = models.CharField(max_length=255, unique=True)
    ip = models.GenericIPAddressField(
        help_text="Most recent IP seen for this bucket (admin reference only, not unique)."
    )

    permanently_blocked = models.BooleanField(default=False)
    blocked_until = models.DateTimeField(null=True, blank=True)

    window_start = models.DateTimeField(null=True, blank=True)
    request_count = models.PositiveIntegerField(default=0)

    captcha_failures = models.PositiveIntegerField(default=0)

    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.permanently_blocked:
            status = "PERMANENTLY BLOCKED"
        elif self.blocked_until:
            status = f"TEMP BLOCKED until {self.blocked_until}"
        else:
            status = "ACTIVE"
        return f"{self.identifier} ({status})"


# =====================================================================
# NEW: MONETIZATION MODELS
# =====================================================================

class SubscriptionPlan(models.Model):
    """
    A time-limited all-access pass (e.g. "Monthly All-Access"). An active
    paid Purchase against this plan unlocks every 'open' subject/content
    for its duration. College-gated subjects are unaffected either way —
    this plan is only ever relevant to the Open catalog.
    """
    name = models.CharField(max_length=100)
    duration_days = models.PositiveIntegerField(default=30)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} (₹{self.price} / {self.duration_days}d)"


class Purchase(models.Model):
    """
    One row per buy attempt. `purchase_type` says what it unlocks:
      - 'content' -> single chapter (self.content set)
      - 'subject' -> whole course      (self.subject set)
      - 'plan'    -> time-limited pass (self.plan set, self.expires_at set on payment)

    Starts as 'created' the moment a Razorpay order is opened, and only
    flips to 'paid' after signature verification — never treat 'created'
    as proof of access. (Purchase rows reference razorpay_order_id etc.,
    which get populated once we build the payments views — those fields
    are simple CharFields here with no dependency on the razorpay package.)
    """
    PURCHASE_TYPE_CHOICES = [
        ("content", "Single Content"),
        ("subject", "Whole Subject"),
        ("plan", "Subscription Plan"),
    ]
    STATUS_CHOICES = [
        ("created", "Created"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="purchases")
    purchase_type = models.CharField(max_length=10, choices=PURCHASE_TYPE_CHOICES)

    content = models.ForeignKey(Content, null=True, blank=True, on_delete=models.SET_NULL, related_name="purchases")
    subject = models.ForeignKey(Subject, null=True, blank=True, on_delete=models.SET_NULL, related_name="purchases")
    plan = models.ForeignKey(SubscriptionPlan, null=True, blank=True, on_delete=models.SET_NULL, related_name="purchases")

    amount = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="created")

    razorpay_order_id = models.CharField(max_length=64, unique=True, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=64, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=128, blank=True, null=True)

    expires_at = models.DateTimeField(null=True, blank=True, help_text="Only set for purchase_type='plan'.")
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    def mark_paid(self, payment_id, signature):
        self.status = "paid"
        self.razorpay_payment_id = payment_id
        self.razorpay_signature = signature
        self.paid_at = timezone.now()
        if self.purchase_type == "plan" and self.plan:
            self.expires_at = timezone.now() + timedelta(days=self.plan.duration_days)
        self.save()

    def __str__(self):
        target = self.content or self.subject or self.plan
        return f"{self.user.username} · {self.purchase_type} · {target} · {self.status}"


def user_has_access(user, content):
    """
    Single source of truth for "can this user see this content's full
    notes". Free content is always visible. Premium/priced content needs
    one of:
      - a paid Purchase for this exact content
      - a paid Purchase for the content's parent subject
      - an active (unexpired) paid subscription-plan Purchase
    """
    if not content.is_premium and not content.price:
        return True

    if not user or not user.is_authenticated:
        return False

    now = timezone.now()

    return Purchase.objects.filter(
        user=user, status="paid"
    ).filter(
        models.Q(purchase_type="content", content=content)
        | models.Q(purchase_type="subject", subject=content.subject)
        | models.Q(purchase_type="plan", expires_at__gte=now)
    ).exists()