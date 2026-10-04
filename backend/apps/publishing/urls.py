from django.urls import path

from . import views

app_name = 'publishing'

urlpatterns = [
    path('jobs/', views.PublishJobListCreateView.as_view(), name='job-list-create'),
    path('jobs/<int:pk>/', views.PublishJobDetailView.as_view(), name='job-detail'),
    path('jobs/<int:pk>/cancel/', views.PublishJobActionView.as_view(action='cancel'), name='job-cancel'),
    path('jobs/<int:pk>/retry/', views.PublishJobActionView.as_view(action='retry'), name='job-retry'),
    path('jobs/<int:pk>/publish-now/', views.PublishJobActionView.as_view(action='publish-now'), name='job-publish-now'),
    path('ready/', views.ReadyToPublishView.as_view(), name='ready'),
    path('preview/<int:item_id>/', views.PublishPreviewView.as_view(), name='preview'),
    path('stats/', views.PublishingStatsView.as_view(), name='stats'),
]
