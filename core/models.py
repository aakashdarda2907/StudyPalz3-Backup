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
import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator
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
    is_open_category = models.BooleanField(
        default=False,
        help_text="Check this for categories meant to organize the Open catalog (e.g. Technical, Lifestyle, Spiritual) — "
                   "keeps them separate from college-dashboard categories like '4th Sem' or 'Premium'.",
    )

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
        max_length=50, choices=ACCESS_TYPE_CHOICES, default="college",
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

    # Dashboard declutter: the first time a student ever loads the
    # dashboard, we auto-pin their own department's subjects so existing
    # users aren't suddenly staring at an empty main dashboard. This flag
    # ensures that only ever happens once — if they later unpin
    # everything on purpose, we don't silently re-pin it for them.
    pins_initialized = models.BooleanField(default=False)

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
    content_type = models.CharField(max_length=100, choices=CONTENT_TYPE_CHOICES)
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
        max_length=200, unique=True, blank=True,
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
    SCOPE_CHOICES = [("open", "Open Catalog"), ("college", "College")]

    name = models.CharField(max_length=100)
    duration_days = models.PositiveIntegerField(default=30)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    is_active = models.BooleanField(default=True)
    scope = models.CharField(
        max_length=100, choices=SCOPE_CHOICES, default="open",
        help_text="'college' plans gate the entire college side (dashboard, subjects, lessons). 'open' plans are the All-Access pass for the Open catalog.",
    )

    discount_percent = models.PositiveSmallIntegerField(
        default=0, validators=[MaxValueValidator(100)],
        help_text="Optional discount (0-100). Students pay price minus this percentage.",
    )
    sort_order = models.PositiveIntegerField(default=0, help_text="Lower numbers show first.")

    class Meta:
        ordering = ["sort_order", "duration_days"]

    @property
    def final_price(self):
        """What the student actually pays (whole rupees)."""
        from decimal import Decimal, ROUND_HALF_UP
        if not self.discount_percent:
            return self.price
        discounted = Decimal(self.price) * (Decimal(100) - Decimal(self.discount_percent)) / Decimal(100)
        return discounted.quantize(Decimal("1"), rounding=ROUND_HALF_UP)

    @property
    def has_discount(self):
        return bool(self.discount_percent)

    def __str__(self):
        return f"{self.name} (₹{self.final_price} / {self.duration_days}d)"


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
        ("college_premium", "College Premium"),
    ]
    STATUS_CHOICES = [
        ("created", "Created"),
        ("paid", "Paid"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="purchases")
    purchase_type = models.CharField(max_length=100, choices=PURCHASE_TYPE_CHOICES)

    content = models.ForeignKey(Content, null=True, blank=True, on_delete=models.SET_NULL, related_name="purchases")
    subject = models.ForeignKey(Subject, null=True, blank=True, on_delete=models.SET_NULL, related_name="purchases")
    plan = models.ForeignKey(SubscriptionPlan, null=True, blank=True, on_delete=models.SET_NULL, related_name="purchases")

    amount = models.DecimalField(max_digits=8, decimal_places=2)
    status = models.CharField(max_length=100, choices=STATUS_CHOICES, default="created")

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
            # Buying while a plan is still active extends it instead of
            # resetting — nobody loses days they already paid for.
            base = timezone.now()
            latest = Purchase.objects.filter(
                user=self.user, status="paid", purchase_type="plan",
                plan__scope=self.plan.scope, expires_at__gt=base,
            ).exclude(pk=self.pk).order_by("-expires_at").first()
            if latest:
                base = latest.expires_at
            self.expires_at = base + timedelta(days=self.plan.duration_days)
        if self.purchase_type == "college_premium":
            # NOTE: no expiry enforcement yet, even though this is framed
            # as "₹499/year" — is_premium just stays True once set. If you
            # want it to actually lapse after a year, that needs a
            # scheduled task to check premium_since and flip it back —
            # worth building once this flow is live and tested, not
            # bundled into this step.
            profile = UserProfile.objects.filter(user=self.user).first()
            if profile:
                profile.is_premium = True
                profile.premium_since = timezone.now()
                profile.save(update_fields=["is_premium", "premium_since"])
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


def user_has_active_college_subscription(user):
    """
    True if this student may use the college side. Two ways in:
      1. Grandfathered: UserProfile.is_premium is already True (they bought
         the old College Premium) — treated as permanently active so nobody
         who already paid gets locked out by this change.
      2. An active, paid, unexpired college-scope plan Purchase.
    """
    if not user or not user.is_authenticated:
        return False

    if user.is_staff:  # you/admins can always test without buying
        return True

    profile = UserProfile.objects.filter(user=user).first()
    if profile and profile.is_premium:
        return True

    return Purchase.objects.filter(
        user=user, status="paid", purchase_type="plan",
        plan__scope="college", expires_at__gte=timezone.now(),
    ).exists()


# =====================================================================
# NEW: CERTIFICATES
# =====================================================================

class Certificate(models.Model):
    """
    One row per (user, subject) — a certificate is only ever created once
    a student has genuinely earned it (see user_is_eligible_for_certificate
    below), and Certificates are immutable once issued: the date and the
    fact of completion shouldn't silently change later even if the student
    somehow un-completes a chapter afterward.
    """
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="certificates")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="certificates")
    certificate_id = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "subject")

    def __str__(self):
        return f"{self.user.username} — {self.subject.name} ({self.issued_at.date()})"


def user_is_eligible_for_certificate(user, subject):
    """
    A certificate only means something if it represents genuine PAID
    completion — not just clicking through a free preview chapter. So
    eligibility requires, for every single chapter in the subject:
      1. The student has actually completed it (UserContentState.is_completed)
      2. The student has real access to it (user_has_access) — which, for
         any priced chapter, can only be true via an actual Purchase.
    A subject with zero chapters is never eligible (nothing to complete).
    """
    if not user or not user.is_authenticated:
        return False

    contents = list(subject.contents.all())
    if not contents:
        return False

    completed_ids = set(
        UserContentState.objects.filter(
            user=user, content__in=contents, is_completed=True
        ).values_list("content_id", flat=True)
    )

    for c in contents:
        if c.id not in completed_ids:
            return False
        if not user_has_access(user, c):
            return False

    return True


# Marketplace models (CreatorProfile, CourseOwnership, CreatorEarning) live
# in their own file — see models_marketplace.py. This import is what makes
# Django's migration system discover them (they need to be imported
# somewhere that always loads at startup), without cluttering this file.
from .models_marketplace import CreatorProfile, CourseOwnership, CreatorEarning  # noqa: F401