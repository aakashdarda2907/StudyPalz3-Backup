from django.contrib import admin
from django.db.models import Count
from .models import Subject, Content, UserContentState, Department, UserProfile, BlockedIP


class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'user_count', 'subject_count')
    search_fields = ('name',)

    def user_count(self, obj):
        return obj.users.count()
    user_count.short_description = 'Number of Users'

    def subject_count(self, obj):
        return obj.subjects.count()
    subject_count.short_description = 'Number of Subjects'


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'username', 'department', 'is_premium', 'current_streak', 'last_active_at', 'completed_content_count')
    list_filter = ('department', 'is_premium', 'current_streak')
    list_editable = ('is_premium',)
    search_fields = ('user__username', 'user__email', 'user__first_name', 'user__last_name')
    raw_id_fields = ('user',)

    def username(self, obj):
        return obj.user.username
    username.short_description = 'Username'
    username.admin_order_field = 'user__username'

    def completed_content_count(self, obj):
        return UserContentState.objects.filter(user=obj.user, is_completed=True).count()
    completed_content_count.short_description = 'Completed Content'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'department')


class ContentInline(admin.TabularInline):
    model = Content
    extra = 1


class SubjectAdmin(admin.ModelAdmin):
    inlines = [ContentInline]
    list_display = ('name', 'department', 'is_pinned', 'created_at', 'content_count')
    list_filter = ('department', 'is_pinned')
    list_editable = ('is_pinned',)
    search_fields = ('name',)
    ordering = ('-is_pinned', '-created_at')

    def content_count(self, obj):
        return obj.contents.count()
    content_count.short_description = 'Number of Content Items'


# ↓↓↓ MUST be defined before ContentAdmin uses it ↓↓↓
class SubjectFilter(admin.SimpleListFilter):
    title = 'subject'
    parameter_name = 'subject'

    def lookups(self, request, model_admin):
        subjects = Subject.objects.all().order_by('-is_pinned', '-created_at')
        return [(s.id, str(s)) for s in subjects]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(subject__id=self.value())
        return queryset


class ContentAdmin(admin.ModelAdmin):
    list_display = ('title', 'unit_number', 'subject', 'content_type', 'is_premium', 'created_at', 'helpful_votes', 'unhelpful_votes')
    list_filter = ('subject__department', SubjectFilter, 'content_type', 'is_premium', 'created_at')
    search_fields = ('title', 'notes', 'problem_statement')
    ordering = ('subject', 'unit_number')
    list_editable = ('is_premium', 'unit_number')
    fieldsets = (
        ('General Information', {
            'fields': ('subject', 'title', 'unit_number', 'content_type', 'is_premium')
        }),
        ('Theory Content (Leave blank if Lab)', {
            'fields': ('youtube_link', 'notes', 'viva_questions')
        }),
        ('Lab Content (Leave blank if Theory)', {
            'fields': ('problem_statement', 'solution_code', 'explanation')
        }),
    )


class UserContentStateAdmin(admin.ModelAdmin):
    list_display = ('user', 'content', 'content_subject', 'is_completed', 'marked_for_revision')
    list_filter = ('is_completed', 'marked_for_revision', 'content__subject__department', 'content__subject')
    search_fields = ('user__username', 'content__title')
    raw_id_fields = ('user', 'content')

    def content_subject(self, obj):
        return obj.content.subject.name
    content_subject.short_description = 'Subject'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('user', 'content', 'content__subject', 'content__subject__department')


class BlockedIPAdmin(admin.ModelAdmin):
    list_display = ('ip', 'permanently_blocked', 'request_count', 'window_start', 'first_seen', 'last_seen')
    list_filter = ('permanently_blocked',)
    search_fields = ('ip',)
    ordering = ('-last_seen',)


admin.site.register(Department, DepartmentAdmin)
admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(Subject, SubjectAdmin)
admin.site.register(Content, ContentAdmin)
admin.site.register(UserContentState, UserContentStateAdmin)
admin.site.register(BlockedIP, BlockedIPAdmin)