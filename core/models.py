# core/models.py

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Department(models.Model):
    """
    Academic department, e.g. CSAI, AIDS, IOT.
    """
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Subject(models.Model):
    """
    Subject under a department, e.g. OOP, MI.
    """
    name = models.CharField(max_length=100)
    syllabus = models.TextField(
        blank=True,
        null=True,
        help_text="Enter each syllabus topic on a new line."
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name='subjects',
        default=1
    )

    # NEW
    is_pinned = models.BooleanField(
        default=False,
        help_text="Pinned subjects always appear at the top of lists and dropdowns."
    )
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-is_pinned', '-created_at']  # pinned first, then newest → oldest

    def __str__(self):
        return f"{self.name} ({self.department.name})"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    current_streak = models.IntegerField(default=0)
    last_active_at = models.DateTimeField(null=True, blank=True)

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        related_name='users',
        null=True,
        blank=True,
        default=1
    )

    is_premium = models.BooleanField(default=False)
    premium_since = models.DateTimeField(null=True, blank=True)
    # Used by dashboard_view and toggle_* views for streak logic

       # NEW: subjects from OTHER departments the user has pinned to their dashboard
    pinned_subjects = models.ManyToManyField(
        Subject,
        related_name='pinned_by_profiles',
        blank=True
    )



    def __str__(self):
        return f"{self.user.username}'s Profile"


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

    class Meta:
        ordering = ['created_at']

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
    updated_at = models.DateTimeField(auto_now=True)  # used in dashboard_view

    class Meta:
        unique_together = ('user', 'content')

    def __str__(self):
        return f"{self.user.username} - {self.content.title}"


from django.db import models
from django.utils import timezone

class BlockedIP(models.Model):
    ip = models.GenericIPAddressField(unique=True)

    # Permanent ban (ONLY for obvious bots / manual bans)
    permanently_blocked = models.BooleanField(default=False)

    # Temporary rate-limit cooldown
    blocked_until = models.DateTimeField(null=True, blank=True)

    # Per-minute rate limiting
    window_start = models.DateTimeField(null=True, blank=True)
    request_count = models.PositiveIntegerField(default=0)

    # Debug / visibility
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.permanently_blocked:
            status = "PERMANENTLY BLOCKED"
        elif self.blocked_until:
            status = f"TEMP BLOCKED until {self.blocked_until}"
        else:
            status = "ACTIVE"

        return f"{self.ip} ({status})"
