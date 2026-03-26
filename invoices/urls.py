from django.urls import path
from . import views

urlpatterns = [
    path('', views.UserInvoiceListView.as_view(), name='invoice-list'),
    path('generate/', views.InvoiceGenerateView.as_view(), name='invoice-generate'),
    path('<uuid:pk>/download/', views.InvoiceDownloadView.as_view(), name='invoice-download'),
]
