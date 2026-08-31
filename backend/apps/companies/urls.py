from django.urls import path

from . import views

app_name = 'companies'

urlpatterns = [
    path('', views.CompanyListCreateView.as_view(), name='company-list-create'),
    path('me/', views.MyCompanyView.as_view(), name='my-company'),
    path('dashboard-stats/', views.AdminDashboardStatsView.as_view(), name='dashboard-stats'),
    path('<int:pk>/', views.CompanyDetailView.as_view(), name='company-detail'),
    path('<int:pk>/activate/', views.CompanyStatusView.as_view(), {'action': 'activate'}, name='company-activate'),
    path('<int:pk>/deactivate/', views.CompanyStatusView.as_view(), {'action': 'deactivate'}, name='company-deactivate'),

    path('<int:company_id>/clients/', views.CompanyClientListCreateView.as_view(), name='company-client-list-create'),
    path('<int:company_id>/clients/<int:pk>/', views.CompanyClientDetailView.as_view(), name='company-client-detail'),
    path('<int:company_id>/media-library/', views.MediaLibraryView.as_view(), name='media-library'),
]
