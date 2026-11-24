from django.urls import path

from . import views

app_name = 'creative_generation'

urlpatterns = [
    path('options/', views.CreativeOptionsView.as_view(), name='options'),
    path('requests/', views.GenerationRequestListCreateView.as_view(), name='request-list-create'),
    path('requests/<int:pk>/', views.GenerationRequestDetailView.as_view(), name='request-detail'),
    path('requests/<int:pk>/retry/', views.GenerationRequestRetryView.as_view(), name='request-retry'),
    path('requests/<int:pk>/download/', views.GenerationRequestDownloadView.as_view(), name='request-download'),
    path(
        'requests/<int:pk>/variations/<int:variation_id>/select/',
        views.VariationSelectView.as_view(), name='variation-select',
    ),
    path('requests/<int:pk>/variations/<int:variation_id>/', views.VariationEditView.as_view(), name='variation-edit'),
    path(
        'requests/<int:pk>/variations/<int:variation_id>/regenerate/',
        views.VariationRegenerateView.as_view(), name='variation-regenerate',
    ),
]
