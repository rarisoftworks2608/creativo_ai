from django.urls import path

from . import views

app_name = 'approvals'

urlpatterns = [
    path('', views.ApprovalQueueView.as_view(), name='queue'),
    path('stats/', views.ApprovalStatsView.as_view(), name='stats'),
]
