from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('healthz/', views.health_check, name='health_check'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('health-profile/', views.health_profile, name='health_profile'),
    path('team/', views.team, name='team'),
    path('terms/', views.terms, name='terms'),
    path('privacy/', views.privacy_policy, name='privacy_policy'),
]
