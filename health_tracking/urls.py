from django.urls import path

from . import views

urlpatterns = [
    path('', views.tracking_home, name='tracking_home'),
    path('<int:measurement_id>/', views.measurement_detail, name='measurement_detail'),
]
