# core/admin.py — REPLACE your current file entirely with this.
#
# Built for the actual workflow you described: uploading chapters under a
# subject, setting Open-catalog pricing, and keeping an eye on purchases —
# without fighting Django's bare default admin.

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    Department, Category, Subject, UserProfile, Content, UserContentState,
    BlockedIP, SubscriptionPlan, Purchase, Certificate,
)
from .models_marketplace import CreatorProfile, CourseOwnership, CreatorEarning


# =====================================================================
# Department / Category
# =====================================================================

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_premium", "is_open_category", "order")
    list_editable = ("order", "is_premium", "is_open_category")
    list_filter = ("is_open_category", "is_premium")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name",)


# =====================================================================
# Subject (+ inline Content for fast chapter uploads)
# =====================================================================

class ContentInline(admin.TabularInline):
    """
    Quick-add chapters directly from the Subject page — this is the fast
    path for uploading a batch of chapters. For the long text fields
    (notes, viva questions, solution code, etc.) click through to the full
    Content edit page instead; those don't belong in a cramped inline row.
    """
    model = Content
    extra = 1
    fields = ("title", "unit_number", "content_type", "youtube_link", "price", "is_premium")
    ordering = ("unit_number", "created_at")
    show_change_link = True


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = (
        "name", "department", "access_type_badge", "price", "chapter_count",
        "is_pinned",
    )
    list_filter = ("access_type", "department", "is_pinned", "categories")
    search_fields = ("name",)
    filter_horizontal = ("categories",)
    inlines = [ContentInline]
    fieldsets = (
        (None, {"fields": ("name", "department", "syllabus")}),
        ("Organization", {"fields": ("categories", "is_pinned")}),
        ("Open Catalog", {
            "fields": ("access_type", "price", "slug"),
            "description": (
                "Set access_type to 'Open' to make this a public, paid course "
                "at /course/&lt;slug&gt;/ — separate from the college dashboard. "
                "Price here sells the WHOLE subject as a bundle; leave blank if "
                "you only want chapters sold individually."
            ),
        }),
    )

    def chapter_count(self, obj):
        return obj.contents.count()
    chapter_count.short_description = "Chapters"

    def access_type_badge(self, obj):
        color = "#0891b2" if obj.access_type == "open" else "#64748b"
        return format_html(
            '<span style="color:{}; font-weight:700;">{}</span>', color, obj.get_access_type_display()
        )
    access_type_badge.short_description = "Access"


# =====================================================================
# Content (full editor — this is where notes/viva/solution code get written)
# =====================================================================

@admin.register(Content)
class ContentAdmin(admin.ModelAdmin):
    list_display = (
        "title", "subject", "content_type", "unit_number",
        "price_display", "is_premium", "has_video", "public_link",
    )
    list_filter = ("content_type", "is_premium", "subject__department", "subject")
    search_fields = ("title", "subject__name")
    ordering = ("subject", "unit_number", "created_at")
    readonly_fields = ("created_at", "helpful_votes", "unhelpful_votes")
    fieldsets = (
        (None, {"fields": ("subject", "title", "unit_number", "content_type")}),
        ("Media & Pricing", {"fields": ("youtube_link", "is_premium", "price", "slug")}),
        ("Notes & Content", {
            "fields": ("notes", "viva_questions"),
            "description": "Rich-text notes editor is a planned upgrade — for now this is plain text.",
        }),
        ("Lab-specific (only used when Content Type = Lab)", {
            "fields": ("problem_statement", "solution_code", "explanation"),
            "classes": ("collapse",),
        }),
        ("Stats (read-only)", {
            "fields": ("helpful_votes", "unhelpful_votes", "created_at"),
            "classes": ("collapse",),
        }),
    )

    def price_display(self, obj):
        return f"₹{obj.price}" if obj.price else "—"
    price_display.short_description = "Price"

    def has_video(self, obj):
        return bool(obj.youtube_link)
    has_video.boolean = True
    has_video.short_description = "Video"

    def public_link(self, obj):
        return format_html('<a href="/c/{}/" target="_blank">/c/{}/</a>', obj.slug, obj.slug)
    public_link.short_description = "Public URL"


# =====================================================================
# User-facing state (mostly useful for support/debugging, not day-to-day editing)
# =====================================================================

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "department", "current_streak", "is_premium", "last_active_at")
    list_filter = ("is_premium", "department", "show_all_departments")
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ("user",)


@admin.register(UserContentState)
class UserContentStateAdmin(admin.ModelAdmin):
    list_display = ("user", "content", "is_completed", "marked_for_revision", "updated_at")
    list_filter = ("is_completed", "marked_for_revision")
    search_fields = ("user__username", "content__title")
    autocomplete_fields = ("user", "content")


# =====================================================================
# Anti-abuse
# =====================================================================

@admin.register(BlockedIP)
class BlockedIPAdmin(admin.ModelAdmin):
    list_display = ("identifier", "ip", "permanently_blocked", "blocked_until", "request_count", "captcha_failures", "last_seen")
    list_filter = ("permanently_blocked",)
    search_fields = ("identifier", "ip")
    actions = ["unblock_selected"]

    def unblock_selected(self, request, queryset):
        updated = queryset.update(permanently_blocked=False, blocked_until=None, request_count=0, captcha_failures=0)
        self.message_user(request, f"Unblocked {updated} entries.")
    unblock_selected.short_description = "Unblock selected (clear permanent + temp blocks)"


# =====================================================================
# Monetization
# =====================================================================

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "scope", "duration_days", "price", "discount_percent", "final_price_display", "is_active", "sort_order")
    list_editable = ("price", "discount_percent", "is_active", "sort_order")
    list_filter = ("scope", "is_active")

    def final_price_display(self, obj):
        return f"₹{obj.final_price}"
    final_price_display.short_description = "Final price"

    search_fields = ("name",)  # required: PurchaseAdmin.autocomplete_fields references this model


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    """
    This is a financial audit trail — no manual creation or deletion from
    the admin. `status` is left editable ONLY for rare manual-override
    support cases (e.g. a confirmed bank transfer outside Razorpay); don't
    use it to fabricate purchases.
    """
    list_display = ("user", "purchase_type", "target", "amount", "status", "created_at", "paid_at")
    list_filter = ("purchase_type", "status")
    search_fields = ("user__username", "razorpay_order_id", "razorpay_payment_id")
    autocomplete_fields = ("user", "content", "subject", "plan")
    readonly_fields = (
        "razorpay_order_id", "razorpay_payment_id", "razorpay_signature",
        "created_at", "paid_at",
    )

    def target(self, obj):
        return obj.content or obj.subject or obj.plan
    target.short_description = "Item"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    """
    Certificates are earned automatically (see user_is_eligible_for_certificate
    in models.py) — no manual creation here, to keep "issued" meaning
    something real.
    """
    list_display = ("user", "subject", "issued_at", "certificate_id")
    list_filter = ("subject",)
    search_fields = ("user__username", "subject__name", "certificate_id")
    autocomplete_fields = ("user", "subject")
    readonly_fields = ("certificate_id", "issued_at")

    def has_add_permission(self, request):
        return False


# =====================================================================
# Marketplace (creator applications, course ownership, payouts)
# =====================================================================

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
    access_type is already 'open' — see the exclude() filter in
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