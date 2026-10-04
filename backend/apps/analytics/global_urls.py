from django.urls import path

from . import views

app_name = 'analytics_global'

urlpatterns = [
    path('overview/', views.AnalyticsOverviewView.as_view(), name='overview'),
]
