from django.urls import path

from . import views

app_name = 'video_generation'

urlpatterns = [
    path('requests/', views.VideoGenerationRequestListCreateView.as_view(), name='request-list-create'),
    path('requests/<int:pk>/', views.VideoGenerationRequestDetailView.as_view(), name='request-detail'),
    path('requests/<int:pk>/retry/', views.VideoGenerationRequestRetryView.as_view(), name='request-retry'),
    path('requests/<int:pk>/rerender/', views.VideoRerenderView.as_view(), name='request-rerender'),
    path('requests/<int:pk>/scenes/<int:scene_id>/', views.VideoSceneUpdateView.as_view(), name='scene-update'),
    path(
        'requests/<int:pk>/scenes/<int:scene_id>/regenerate-image/',
        views.VideoSceneRegenerateImageView.as_view(), name='scene-regenerate-image',
    ),
]
