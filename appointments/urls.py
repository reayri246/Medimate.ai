from django.urls import path

from . import views

urlpatterns = [
    path('', views.appointment_list, name='appointment_list'),
    path('request/', views.appointment_request, name='appointment_request'),
    path('staff/', views.staff_appointment_queue, name='staff_appointment_queue'),
    path('<int:appointment_id>/letter/', views.appointment_letter, name='appointment_letter'),
    path('<int:appointment_id>/decision/', views.staff_appointment_decision, name='staff_appointment_decision'),
]
