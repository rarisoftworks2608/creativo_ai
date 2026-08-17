from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = 'authentication'

urlpatterns = [
    # Auth
    path('login/', views.LoginView.as_view(), name='login'),
    path('refresh/', TokenRefreshView.as_view(), name='refresh'),
    path('logout/', views.LogoutView.as_view(), name='logout'),

    # Password management
    path('change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('forgot-password/', views.ForgotPasswordView.as_view(), name='forgot-password'),
    path('reset-password/', views.ResetPasswordView.as_view(), name='reset-password'),

    # Profile
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('login-history/', views.MyLoginHistoryView.as_view(), name='my-login-history'),

    # Admin: user management
    path('users/', views.UserListCreateView.as_view(), name='user-list-create'),
    path('users/<int:pk>/', views.UserDetailView.as_view(), name='user-detail'),
    path('users/<int:pk>/login-history/', views.UserLoginHistoryView.as_view(), name='user-login-history'),
]
