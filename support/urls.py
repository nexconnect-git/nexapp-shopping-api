from django.urls import path
from . import views

urlpatterns = [
    path('tickets/', views.VendorTicketListCreateView.as_view(), name='support-tickets'),
    path('tickets/<uuid:pk>/', views.VendorTicketDetailView.as_view(), name='support-ticket-detail'),
]
