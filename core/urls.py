# core/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Main pages
    path('', views.home_view, name='home'),
    path('dashboard/', views.dashboard_view, name='dashboard'),

    # Auth pages
    path('signup/', views.signup_view, name='signup'),

    # Points to your custom login_view in views.py
    # (which handles the Rate Limiting + Honeypot + Auth)
    path('login/', views.login_view, name='login'),

    path('logout/', views.logout_view, name='logout'),

    # Content pages
    path('subject/<int:subject_id>/', views.subject_detail_view, name='subject_detail'),
    path('content/<int:content_id>/', views.content_detail_view, name='content_detail'),

    # Action URLs for progress tracking
    path('content/<int:content_id>/toggle_complete/', views.toggle_complete_view, name='toggle_complete'),
    path('content/<int:content_id>/toggle_revision/', views.toggle_revision_view, name='toggle_revision'),

    # Revision Hub
    path('revision-hub/', views.revision_hub_view, name='revision_hub'),
    path('content/<int:content_id>/feedback/', views.feedback_view, name='feedback'),

    path('profile/', views.profile_view, name='profile'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),

    path('subject/<int:subject_id>/toggle_pin/', views.toggle_pin_subject_view, name='toggle_pin_subject'),
    path('dashboard/update-filters/', views.update_dashboard_filters_view, name='update_dashboard_filters'),
    path('premium/', views.premium_upgrade_view, name='premium_upgrade'),
    path('verify-human/', views.verify_human_view, name='verify_human'),
]


