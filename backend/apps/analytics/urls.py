from django.urls import path

from . import views

app_name = 'analytics'

urlpatterns = [
    path('summary/', views.AnalyticsSummaryView.as_view(), name='summary'),
    path('posts/', views.PostMetricsListView.as_view(), name='posts'),
    path('sync/', views.AnalyticsSyncView.as_view(), name='sync'),
    path('sync-logs/', views.AnalyticsSyncLogListView.as_view(), name='sync-logs'),
]
