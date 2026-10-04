from django.urls import path

from . import views

app_name = 'reports_admin'

urlpatterns = [
    path('', views.AdminReportListCreateView.as_view(), name='list-create'),
    path('<int:pk>/', views.AdminReportDetailView.as_view(), name='detail'),
    path('<int:pk>/download/', views.AdminReportDownloadView.as_view(), name='download'),
    path('<int:pk>/regenerate/', views.AdminReportRegenerateView.as_view(), name='regenerate'),
]
