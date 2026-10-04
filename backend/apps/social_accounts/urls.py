from django.urls import path

from . import views

app_name = 'social_accounts'

urlpatterns = [
    path('accounts/', views.SocialAccountListCreateView.as_view(), name='account-list-create'),
    path('accounts/<int:pk>/', views.SocialAccountDetailView.as_view(), name='account-detail'),
    path('accounts/<int:pk>/disconnect/', views.SocialAccountDisconnectView.as_view(), name='account-disconnect'),
    path('accounts/<int:pk>/test-connection/', views.SocialAccountTestConnectionView.as_view(), name='account-test-connection'),
    path('accounts/<int:pk>/refresh-token/', views.SocialAccountRefreshTokenView.as_view(), name='account-refresh-token'),

    # OAuth (Epic 10: Connect / Page selection / Organization selection)
    path('oauth/status/', views.OAuthStatusView.as_view(), name='oauth-status'),
    path('oauth/<str:provider>/start/', views.OAuthStartView.as_view(), name='oauth-start'),
    path('oauth/<str:provider>/complete/', views.OAuthCompleteView.as_view(), name='oauth-complete'),
    path('oauth/sessions/<uuid:session_id>/connect/', views.OAuthConnectView.as_view(), name='oauth-connect'),
]
