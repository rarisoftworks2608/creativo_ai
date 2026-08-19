from django.urls import path

from . import views

app_name = 'brand'

urlpatterns = [
    path('', views.BrandProfileView.as_view(), name='brand-profile'),

    path('logo/', views.BrandIdentityImageView.as_view(), {'slot': 'logo'}, name='brand-logo'),
    path('secondary-logo/', views.BrandIdentityImageView.as_view(), {'slot': 'secondary_logo'}, name='brand-secondary-logo'),
    path('favicon/', views.BrandIdentityImageView.as_view(), {'slot': 'favicon'}, name='brand-favicon'),

    path('assets/', views.BrandAssetListCreateView.as_view(), name='brand-asset-list-create'),
    path('assets/<int:pk>/', views.BrandAssetDetailView.as_view(), name='brand-asset-detail'),
]
