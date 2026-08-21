from django.urls import path

from . import views

app_name = 'creative_generation'

urlpatterns = [
    path('requests/', views.GenerationRequestListCreateView.as_view(), name='request-list-create'),
    path('requests/<int:pk>/', views.GenerationRequestDetailView.as_view(), name='request-detail'),
    path('requests/<int:pk>/retry/', views.GenerationRequestRetryView.as_view(), name='request-retry'),
    path(
        'requests/<int:pk>/variations/<int:variation_id>/select/',
        views.VariationSelectView.as_view(), name='variation-select',
    ),
]
