# studypalz3/urls.py (or whatever your project folder is named)

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

# 1. Add this import for the handler
from django.conf.urls import handler404

urlpatterns = [
    path('admin/', admin.site.urls),

    # This connects your core urls to the main project
    path('', include('core.urls')),
]

# 2. Define the handler here, outside of urlpatterns
handler404 = 'core.views.custom_404'