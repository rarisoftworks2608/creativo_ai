"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

company = 'api/v1/companies/<int:company_id>'

urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/v1/health/', include('apps.health.urls')),
    path('api/v1/auth/', include('apps.authentication.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/v1/activity-log/', include('apps.activity_log.urls')),
    path('api/v1/platform-settings/', include('apps.platform_settings.urls')),
    path('api/v1/prompt-templates/', include('apps.prompt_templates.urls')),
    path('api/v1/approvals/', include('apps.content_calendar.approval_urls')),
    path('api/v1/publishing/', include('apps.publishing.global_urls')),
    path('api/v1/whatsapp/', include('apps.whatsapp.global_urls')),
    path('api/v1/analytics/', include('apps.analytics.global_urls')),
    path('api/v1/subscriptions/', include('apps.subscriptions.urls')),
    path('api/v1/reports/', include('apps.reports.global_urls')),
    path('api/v1/music-library/', include('apps.video_generation.music_urls')),
    path('api/v1/companies/', include('apps.companies.urls')),
    path(f'{company}/content-calendar/', include('apps.content_calendar.urls')),
    path(f'{company}/brand/', include('apps.brand.urls')),
    path(f'{company}/ai-strategy/', include('apps.ai_strategy.urls')),
    path(f'{company}/creative-generation/', include('apps.creative_generation.urls')),
    path(f'{company}/video-generation/', include('apps.video_generation.urls')),
    path(f'{company}/social-accounts/', include('apps.social_accounts.urls')),
    path(f'{company}/publishing/', include('apps.publishing.urls')),
    path(f'{company}/whatsapp/', include('apps.whatsapp.urls')),
    path(f'{company}/analytics/', include('apps.analytics.urls')),
    path(f'{company}/reports/', include('apps.reports.urls')),
    path(f'{company}/subscription/', include('apps.subscriptions.company_urls')),

    # API schema / docs (Epic 28: API documentation)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

if settings.DEBUG:
    # Brand identity images / asset uploads (Epic 03) are the first user-uploaded
    # media in this project; serve them from disk in development only, since
    # production is expected to use S3/R2 (django-storages) or Nginx instead.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
