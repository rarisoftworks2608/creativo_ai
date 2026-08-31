"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/v1/auth/', include('apps.authentication.urls')),
    path('api/v1/notifications/', include('apps.notifications.urls')),
    path('api/v1/companies/', include('apps.companies.urls')),
    path('api/v1/companies/<int:company_id>/content-calendar/', include('apps.content_calendar.urls')),
    path('api/v1/companies/<int:company_id>/brand/', include('apps.brand.urls')),
    path('api/v1/companies/<int:company_id>/ai-strategy/', include('apps.ai_strategy.urls')),
    path('api/v1/companies/<int:company_id>/creative-generation/', include('apps.creative_generation.urls')),
    path('api/v1/companies/<int:company_id>/video-generation/', include('apps.video_generation.urls')),
    path('api/v1/companies/<int:company_id>/social-accounts/', include('apps.social_accounts.urls')),

    # API schema / docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
]

if settings.DEBUG:
    # Brand identity images / asset uploads (Epic 03) are the first user-uploaded
    # media in this project; serve them from disk in development only, since
    # production is expected to use S3/R2 (django-storages) instead.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
