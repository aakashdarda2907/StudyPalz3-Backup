# core/admin.py — ADDITIONS. Add these imports and admin classes to your
# existing admin.py (don't replace the whole file — just merge this in).

# Add to your existing "from .models import (...)" line:
#   from .models_marketplace import CreatorProfile, CourseOwnership, CreatorEarning

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models_marketplace import CreatorProfile, CourseOwnership, CreatorEarning


@admin.register(CreatorProfile)
class CreatorProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "user", "status_badge", "applied_at")
    list_filter = ("status",)
    search_fields = ("display_name", "user__username", "user__email", "bio")
    readonly_fields = ("applied_at",)
    actions = ["approve_creators", "reject_creators"]

    def status_badge(self, obj):
        colors = {"pending": "#b45309", "approved": "#059669", "rejected": "#dc2626"}
        return format_html(
            '<span style="color:{}; font-weight:700;">{}</span>',
            colors.get(obj.status, "#64748b"), obj.get_status_display(),
        )
    status_badge.short_description = "Status"

    def approve_creators(self, request, queryset):
        updated = queryset.update(status="approved", reviewed_at=timezone.now())
        self.message_user(request, f"Approved {updated} creator(s).")
    approve_creators.short_description = "Approve selected creators"

    def reject_creators(self, request, queryset):
        updated = queryset.update(status="rejected", reviewed_at=timezone.now())
        self.message_user(request, f"Rejected {updated} creator(s).")
    reject_creators.short_description = "Reject selected creators"


@admin.register(CourseOwnership)
class CourseOwnershipAdmin(admin.ModelAdmin):
    """
    This is where you approve an individual COURSE (separate from
    approving the creator themselves). Until this row's review_status is
    'approved', the linked Subject stays invisible on /courses/ even if
    access_type is already 'open' — see the exclude() filter added to
    courses_catalog_view / public_subject_view.
    """
    list_display = ("subject", "owner", "revenue_split_percent", "review_status_badge", "submitted_at")
    list_filter = ("review_status",)
    search_fields = ("subject__name", "owner__username")
    autocomplete_fields = ("subject", "owner")
    readonly_fields = ("submitted_at",)
    actions = ["approve_courses", "reject_courses"]

    def review_status_badge(self, obj):
        colors = {"pending": "#b45309", "approved": "#059669", "rejected": "#dc2626"}
        return format_html(
            '<span style="color:{}; font-weight:700;">{}</span>',
            colors.get(obj.review_status, "#64748b"), obj.get_review_status_display(),
        )
    review_status_badge.short_description = "Status"

    def approve_courses(self, request, queryset):
        updated = queryset.update(review_status="approved", reviewed_at=timezone.now())
        self.message_user(request, f"Approved {updated} course(s) — now live on /courses/.")
    approve_courses.short_description = "Approve selected courses"

    def reject_courses(self, request, queryset):
        updated = queryset.update(review_status="rejected", reviewed_at=timezone.now())
        self.message_user(request, f"Rejected {updated} course(s).")
    reject_courses.short_description = "Reject selected courses"


@admin.register(CreatorEarning)
class CreatorEarningAdmin(admin.ModelAdmin):
    """
    Your manual payout ledger. Filter by payout_status='unpaid' + owner
    to see exactly how much you owe a specific creator, then select those
    rows and mark them paid once you've actually sent the money.
    """
    list_display = ("owner", "amount", "purchase", "payout_status_badge", "created_at")
    list_filter = ("payout_status", "owner")
    search_fields = ("owner__username",)
    readonly_fields = ("purchase", "owner", "amount", "created_at")
    actions = ["mark_paid_out"]

    def payout_status_badge(self, obj):
        color = "#059669" if obj.payout_status == "paid" else "#b45309"
        return format_html('<span style="color:{}; font-weight:700;">{}</span>', color, obj.get_payout_status_display())
    payout_status_badge.short_description = "Payout"

    def mark_paid_out(self, request, queryset):
        updated = queryset.filter(payout_status="unpaid").update(payout_status="paid", paid_out_at=timezone.now())
        self.message_user(request, f"Marked {updated} earning(s) as paid out.")
    mark_paid_out.short_description = "Mark selected as paid out to creator"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
