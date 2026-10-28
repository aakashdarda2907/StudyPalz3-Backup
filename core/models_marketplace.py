# core/models_marketplace.py — NEW FILE.
#
# Deliberately kept separate from models.py. Nothing in here modifies
# Subject, UserProfile, or Purchase directly — instead:
#   - CreatorProfile   holds creator-application data, linked 1:1 to User.
#   - CourseOwnership  holds "who owns this course + what's their cut",
#                       linked 1:1 to Subject. A Subject with NO
#                       CourseOwnership row is simply platform-owned
#                       (all your existing courses today) — always
#                       visible, no approval step, nothing changes for
#                       them.
#   - CreatorEarning   one row per paid Purchase that belongs to a
#                       creator's approved course — created automatically
#                       via a signal the moment a Purchase is marked
#                       paid, so Purchase.mark_paid() in models.py never
#                       had to be touched.
#
# IMPORTANT — what this step does NOT include yet:
#   There's no self-serve "creator dashboard" where a creator adds their
#   own Subject/Content. That's real, separate work (permission-scoped
#   views, its own UI). For now, once you approve a creator, YOU still
#   create their Subject/Content in the admin on their behalf, then
#   attach a CourseOwnership row pointing to them. This step builds the
#   accounts, the approval workflow, and the revenue tracking — the
#   self-serve creation UI is the next phase.

from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Subject, Purchase


class CreatorProfile(models.Model):
    """
    One per user who has applied to become a course creator. Plain
    'viewer' accounts (the vast majority) never get one of these at all.
    """
    STATUS_CHOICES = [
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="creator_profile")
    display_name = models.CharField(max_length=100, help_text="Shown publicly as the course author, e.g. on course pages.")
    bio = models.TextField(help_text="What they want to teach + a short pitch — this is what you review.")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")

    applied_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.display_name} ({self.get_status_display()})"

    @property
    def is_approved(self):
        return self.status == "approved"


class CourseOwnership(models.Model):
    """
    Links a Subject to the creator who made it, plus their revenue split
    and the course's own approval state (separate from the creator being
    approved — an approved creator's course still starts pending until
    you personally review that specific course).
    """
    REVIEW_CHOICES = [
        ("pending", "Pending Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    subject = models.OneToOneField(Subject, on_delete=models.CASCADE, related_name="ownership")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="owned_courses")
    revenue_split_percent = models.PositiveSmallIntegerField(
        default=70, help_text="What percentage of each sale the creator keeps. Platform keeps the rest."
    )
    review_status = models.CharField(max_length=10, choices=REVIEW_CHOICES, default="pending")

    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.subject.name} — {self.owner.username} ({self.revenue_split_percent}%)"


class CreatorEarning(models.Model):
    """
    One row per paid Purchase that belongs to a creator's approved
    course. Created automatically by the signal below — never created
    manually, so "unpaid earnings" always reflects real sales.

    Note on scope: only direct chapter/course purchases generate creator
    earnings in this version. All-Access plan purchases aren't tied to a
    single creator's course, so the platform keeps 100% of plan revenue
    for now — worth revisiting once/if plan purchases become a
    significant share of revenue.
    """
    PAYOUT_CHOICES = [
        ("unpaid", "Unpaid"),
        ("paid", "Paid Out"),
    ]

    purchase = models.OneToOneField(Purchase, on_delete=models.CASCADE, related_name="creator_earning")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="earnings")
    amount = models.DecimalField(max_digits=8, decimal_places=2)
    payout_status = models.CharField(max_length=10, choices=PAYOUT_CHOICES, default="unpaid")

    created_at = models.DateTimeField(auto_now_add=True)
    paid_out_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.owner.username} · ₹{self.amount} · {self.get_payout_status_display()}"


@receiver(post_save, sender=Purchase)
def create_creator_earning(sender, instance, **kwargs):
    """
    Fires on every Purchase save. Only acts when: the purchase is paid,
    it's tied to a subject with an APPROVED CourseOwnership, and no
    CreatorEarning exists for it yet (idempotent — safe to fire on every
    save, not just the first).
    """
    if instance.status != "paid":
        return
    if CreatorEarning.objects.filter(purchase=instance).exists():
        return

    relevant_subject = None
    if instance.purchase_type == "content" and instance.content:
        relevant_subject = instance.content.subject
    elif instance.purchase_type == "subject" and instance.subject:
        relevant_subject = instance.subject
    # purchase_type == "plan": intentionally not tied to a single
    # creator's course — see CreatorEarning docstring above.

    if not relevant_subject:
        return

    ownership = CourseOwnership.objects.filter(subject=relevant_subject, review_status="approved").first()
    if not ownership:
        return

    earning_amount = (instance.amount * ownership.revenue_split_percent) / 100
    CreatorEarning.objects.create(
        purchase=instance,
        owner=ownership.owner,
        amount=earning_amount,
    )
