from django.urls import path

from . import views

app_name = 'platform_settings'

urlpatterns = [
    path('', views.PlatformSettingsView.as_view(), name='detail'),
]
