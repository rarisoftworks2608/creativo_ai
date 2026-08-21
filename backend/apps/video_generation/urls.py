from django.urls import path

from . import views

app_name = 'video_generation'

urlpatterns = [
    path('requests/', views.VideoGenerationRequestListCreateView.as_view(), name='request-list-create'),
    path('requests/<int:pk>/', views.VideoGenerationRequestDetailView.as_view(), name='request-detail'),
    path('requests/<int:pk>/retry/', views.VideoGenerationRequestRetryView.as_view(), name='request-retry'),
]
