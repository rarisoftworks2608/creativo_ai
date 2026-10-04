from django.urls import path

from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.CompanyReportListCreateView.as_view(), name='list-create'),
    path('<int:pk>/', views.CompanyReportDetailView.as_view(), name='detail'),
    path('<int:pk>/download/', views.CompanyReportDownloadView.as_view(), name='download'),
    path('<int:pk>/regenerate/', views.CompanyReportActionView.as_view(action='regenerate'), name='regenerate'),
    path('<int:pk>/send/', views.CompanyReportActionView.as_view(action='send'), name='send'),
]
