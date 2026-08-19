from django.urls import path

from . import views

app_name = 'ai_strategy'

urlpatterns = [
    path('brand-context/', views.BrandContextView.as_view(), name='brand-context'),
    path('brand-context/generate/', views.BrandContextGenerateView.as_view(), name='brand-context-generate'),

    path('outputs/', views.StrategyOutputListView.as_view(), name='output-list'),
    path('outputs/<int:pk>/', views.StrategyOutputDetailView.as_view(), name='output-detail'),
    path('outputs/generate/<str:kind>/', views.StrategyOutputGenerateView.as_view(), name='output-generate'),
]
