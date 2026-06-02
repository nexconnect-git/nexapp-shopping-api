from django.urls import path

from delivery.views import AdminDeliveryReassignView
from products.views import (
    AdminApproveVendorProductView,
    AdminCatalogProductDetailView,
    AdminCatalogProductListCreateView,
    AdminCatalogProposalItemApproveView,
    AdminCatalogProposalItemRejectView,
    AdminCatalogProposalListView,
    AdminPendingVendorProductListView,
    AdminRejectVendorProductView,
)


urlpatterns = [
    path("parent-catalog/", AdminCatalogProductListCreateView.as_view(), name="admin-alias-parent-catalog"),
    path("parent-catalog/<uuid:pk>/", AdminCatalogProductDetailView.as_view(), name="admin-alias-parent-catalog-detail"),
    path("catalog-requests/", AdminCatalogProposalListView.as_view(), name="admin-alias-catalog-requests"),
    path(
        "catalog-requests/<uuid:proposal_id>/items/<uuid:item_id>/approve/",
        AdminCatalogProposalItemApproveView.as_view(),
        name="admin-alias-catalog-request-approve",
    ),
    path(
        "catalog-requests/<uuid:proposal_id>/items/<uuid:item_id>/reject/",
        AdminCatalogProposalItemRejectView.as_view(),
        name="admin-alias-catalog-request-reject",
    ),
    path("vendor-products/", AdminPendingVendorProductListView.as_view(), name="admin-alias-vendor-products"),
    path("vendor-products/<uuid:pk>/approve/", AdminApproveVendorProductView.as_view(), name="admin-alias-vendor-product-approve"),
    path("vendor-products/<uuid:pk>/reject/", AdminRejectVendorProductView.as_view(), name="admin-alias-vendor-product-reject"),
    path("delivery/reassign/<uuid:pk>/", AdminDeliveryReassignView.as_view(), name="admin-alias-delivery-reassign"),
]
