from django.urls import path

from . import views

app_name = 'social_accounts'

urlpatterns = [
    path('accounts/', views.SocialAccountListCreateView.as_view(), name='account-list-create'),
    path('accounts/<int:pk>/', views.SocialAccountDetailView.as_view(), name='account-detail'),
    path('accounts/<int:pk>/disconnect/', views.SocialAccountDisconnectView.as_view(), name='account-disconnect'),
]
