from django.urls import path

from . import views

urlpatterns = [
    path('<int:notification_id>/open/', views.notification_open, name='notification_open'),
    path('', views.notification_list, name='notification_list'),
]
