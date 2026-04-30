from django.db.models import Q

from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminRole, IsApprovedVendor
from products.actions import (
    ApproveCatalogProposalItemAction,
    CreateInheritedProductDraftBatchAction,
    CreateCatalogProposalAction,
    CreateVendorProductFromCatalogAction,
    DuplicateInheritedProductAction,
    RejectCatalogProposalItemAction,
    ReviewVendorProductAction,
    SubmitInheritedProductBatchAction,
)
from products.data.catalog_repository import CatalogProductRepository, CatalogProposalRepository, VendorCatalogGrantRepository
from products.models import CatalogProduct, CatalogProductImage, CatalogProposal, CatalogProposalItem, Product, VendorCatalogGrant
from products.serializers import ProductSerializer
from products.serializers.catalog_serializers import (
    AdminVendorProductRejectSerializer,
    CatalogProductImageSerializer,
    CatalogProductSerializer,
    CatalogProposalReviewSerializer,
    CatalogProposalSerializer,
    CreateVendorProductFromCatalogSerializer,
    InheritedProductDraftBatchSerializer,
    InheritedProductImagePolicySerializer,
    InheritedProductSubmitSerializer,
    VendorCatalogGrantSerializer,
)
from vendors.models import Vendor


class CatalogPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class AdminCatalogProductListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = CatalogProduct.objects.select_related("category").prefetch_related("images").order_by("name")
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(brand__icontains=search)
                | Q(barcode__icontains=search)
                | Q(category__name__icontains=search)
            )
        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category_id=category)
        is_active = request.query_params.get("is_active")
        if is_active is not None:
            qs = qs.filter(is_active=is_active.lower() == "true")
        paginator = CatalogPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(CatalogProductSerializer(page, many=True, context={"request": request}).data)

    def post(self, request):
        serializer = CatalogProductSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class AdminCatalogProductDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        product = CatalogProductRepository().get_by_id(pk, select_related=["category"], prefetch=["images"])
        if not product:
            return Response({"error": "Catalog product not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CatalogProductSerializer(product, context={"request": request}).data)

    def patch(self, request, pk):
        product = CatalogProductRepository().get_by_id(pk)
        if not product:
            return Response({"error": "Catalog product not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = CatalogProductSerializer(product, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        product = CatalogProductRepository().get_by_id(pk)
        if not product:
            return Response({"error": "Catalog product not found."}, status=status.HTTP_404_NOT_FOUND)
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AdminCatalogProductGrantVendorView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        product = CatalogProductRepository().get_by_id(pk)
        if not product:
            return Response({"error": "Catalog product not found."}, status=status.HTTP_404_NOT_FOUND)
        vendor_id = request.data.get("vendor_id")
        if not vendor_id:
            return Response({"vendor_id": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        try:
            vendor = Vendor.objects.get(pk=vendor_id)
        except Vendor.DoesNotExist:
            return Response({"error": "Vendor not found."}, status=status.HTTP_404_NOT_FOUND)
        grant = VendorCatalogGrantRepository().grant(vendor, product, request.user)
        return Response(VendorCatalogGrantSerializer(grant, context={"request": request}).data, status=status.HTTP_201_CREATED)


class AdminCatalogProductImagesView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request, pk):
        product = CatalogProductRepository().get_by_id(pk)
        if not product:
            return Response({"error": "Catalog product not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CatalogProductImageSerializer(product.images.all(), many=True, context={"request": request}).data)

    def post(self, request, pk):
        product = CatalogProductRepository().get_by_id(pk)
        if not product:
            return Response({"error": "Catalog product not found."}, status=status.HTTP_404_NOT_FOUND)
        image_file = request.FILES.get("image")
        if not image_file:
            return Response({"image": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)
        is_primary = str(request.data.get("is_primary", "false")).lower() == "true"
        if is_primary or not product.images.exists():
            product.images.update(is_primary=False)
            is_primary = True
        image = CatalogProductImage.objects.create(
            catalog_product=product,
            image=image_file,
            is_primary=is_primary,
            display_order=request.data.get("display_order") or product.images.count(),
        )
        return Response(CatalogProductImageSerializer(image, context={"request": request}).data, status=status.HTTP_201_CREATED)


class AdminCatalogProductImageDetailView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def delete(self, request, pk, image_id):
        try:
            image = CatalogProductImage.objects.get(pk=image_id, catalog_product_id=pk)
        except CatalogProductImage.DoesNotExist:
            return Response({"error": "Catalog image not found."}, status=status.HTTP_404_NOT_FOUND)
        image.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VendorAvailableCatalogProductsView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request):
        qs = CatalogProductRepository().available_for_vendor(request.user.vendor_profile)
        search = request.query_params.get("search")
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(brand__icontains=search))
        paginator = CatalogPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(CatalogProductSerializer(page, many=True, context={"request": request}).data)


class VendorCatalogProductDetailView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request, pk):
        product = CatalogProductRepository().get_by_id(pk, select_related=["category"], prefetch=["images"])
        if not product or not product.is_active:
            return Response({"error": "Catalog product not found."}, status=status.HTTP_404_NOT_FOUND)
        if not VendorCatalogGrantRepository().has_grant(request.user.vendor_profile, product):
            return Response({"error": "Catalog product not available for this vendor."}, status=status.HTTP_403_FORBIDDEN)
        return Response(CatalogProductSerializer(product, context={"request": request}).data)


class VendorCreateProductFromCatalogView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request):
        serializer = CreateVendorProductFromCatalogSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        catalog_product_id = data.pop("catalog_product_id")
        try:
            product = CreateVendorProductFromCatalogAction().execute(
                vendor=request.user.vendor_profile,
                catalog_product_id=catalog_product_id,
                selling_data=data,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ProductSerializer(product, context={"request": request}).data, status=status.HTTP_201_CREATED)


class VendorInheritedProductDraftBatchCreateView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request):
        serializer = InheritedProductDraftBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            batch_id, created = CreateInheritedProductDraftBatchAction().execute(
                vendor=request.user.vendor_profile,
                catalog_product_ids=serializer.validated_data["catalog_product_ids"],
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            {
                "batch_id": str(batch_id),
                "variants": ProductSerializer(created, many=True, context={"request": request}).data,
            },
            status=status.HTTP_201_CREATED,
        )


class VendorInheritedProductListView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request):
        status_filter = request.query_params.get("approval_status")
        qs = Product.objects.filter(vendor=request.user.vendor_profile, catalog_product__isnull=False).select_related(
            "catalog_product", "category", "reviewed_by"
        )
        if status_filter:
            qs = qs.filter(approval_status=status_filter)
        return Response(ProductSerializer(qs.order_by("-updated_at"), many=True, context={"request": request}).data)


class VendorInheritedProductDetailView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def patch(self, request, pk):
        try:
            product = Product.objects.get(pk=pk, vendor=request.user.vendor_profile, catalog_product__isnull=False)
        except Product.DoesNotExist:
            return Response({"error": "Variant not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = CreateVendorProductFromCatalogSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        data.pop("catalog_product_id", None)
        for field, value in data.items():
            setattr(product, field, value)
        product.approval_status = Product.APPROVAL_STATUS_DRAFT
        product.rejection_reason = ""
        product.save()
        return Response(ProductSerializer(product, context={"request": request}).data)


class VendorInheritedProductDuplicateView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk, vendor=request.user.vendor_profile, catalog_product__isnull=False)
        except Product.DoesNotExist:
            return Response({"error": "Variant not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            duplicate = DuplicateInheritedProductAction().execute(request.user.vendor_profile, product)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ProductSerializer(duplicate, context={"request": request}).data, status=status.HTTP_201_CREATED)


class VendorInheritedProductSubmitView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request):
        serializer = InheritedProductSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            variants = SubmitInheritedProductBatchAction().execute(
                request.user.vendor_profile,
                serializer.validated_data["product_ids"],
            )
        except ValueError as exc:
            payload = exc.args[0] if exc.args else "Validation failed."
            return Response({"error": payload}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ProductSerializer(variants, many=True, context={"request": request}).data)


class VendorInheritedProductImagePolicyView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def post(self, request, pk):
        serializer = InheritedProductImagePolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            product = Product.objects.get(pk=pk, vendor=request.user.vendor_profile, catalog_product__isnull=False)
        except Product.DoesNotExist:
            return Response({"error": "Variant not found."}, status=status.HTTP_404_NOT_FOUND)
        product.inheritance_mode = serializer.validated_data["inheritance_mode"]
        product.save(update_fields=["inheritance_mode", "updated_at"])
        return Response(ProductSerializer(product, context={"request": request}).data)


class VendorCatalogProposalListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsApprovedVendor]

    def get(self, request):
        qs = CatalogProposalRepository().list_for_vendor(request.user.vendor_profile)
        paginator = CatalogPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(CatalogProposalSerializer(page, many=True, context={"request": request}).data)

    def post(self, request):
        serializer = CatalogProposalSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            proposal = CreateCatalogProposalAction().execute(
                vendor=request.user.vendor_profile,
                items=serializer.validated_data["items"],
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        proposal = CatalogProposal.objects.prefetch_related("items__category").get(pk=proposal.pk)
        return Response(CatalogProposalSerializer(proposal, context={"request": request}).data, status=status.HTTP_201_CREATED)


class AdminCatalogProposalListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = CatalogProposalRepository().list_for_admin()
        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)
        paginator = CatalogPagination()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(CatalogProposalSerializer(page, many=True, context={"request": request}).data)


class AdminCatalogProposalItemApproveView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, proposal_id, item_id):
        serializer = CatalogProposalReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = ApproveCatalogProposalItemAction().execute(
                proposal_id=proposal_id,
                item_id=item_id,
                admin_user=request.user,
                catalog_product_id=serializer.validated_data.get("catalog_product_id"),
                admin_notes=serializer.validated_data.get("admin_notes", ""),
            )
        except (CatalogProposal.DoesNotExist, CatalogProposalItem.DoesNotExist, CatalogProduct.DoesNotExist):
            return Response({"error": "Proposal item or catalog product not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CatalogProposalSerializer(item.proposal, context={"request": request}).data)


class AdminCatalogProposalItemRejectView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, proposal_id, item_id):
        serializer = CatalogProposalReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = RejectCatalogProposalItemAction().execute(
                proposal_id=proposal_id,
                item_id=item_id,
                admin_user=request.user,
                rejection_reason=serializer.validated_data.get("rejection_reason", ""),
                admin_notes=serializer.validated_data.get("admin_notes", ""),
            )
        except (CatalogProposal.DoesNotExist, CatalogProposalItem.DoesNotExist):
            return Response({"error": "Proposal item not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CatalogProposalSerializer(item.proposal, context={"request": request}).data)


class AdminPendingVendorProductListView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get(self, request):
        qs = Product.objects.filter(
            catalog_product__isnull=False,
            approval_status=Product.APPROVAL_STATUS_PENDING,
        ).select_related("vendor", "catalog_product", "category")
        return Response(ProductSerializer(qs.order_by("-updated_at"), many=True, context={"request": request}).data)


class AdminApproveVendorProductView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        try:
            product = Product.objects.get(pk=pk, catalog_product__isnull=False)
        except Product.DoesNotExist:
            return Response({"error": "Variant not found."}, status=status.HTTP_404_NOT_FOUND)
        updated = ReviewVendorProductAction().approve(request.user, product)
        return Response(ProductSerializer(updated, context={"request": request}).data)


class AdminRejectVendorProductView(APIView):
    permission_classes = [IsAuthenticated, IsAdminRole]

    def post(self, request, pk):
        serializer = AdminVendorProductRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            product = Product.objects.get(pk=pk, catalog_product__isnull=False)
        except Product.DoesNotExist:
            return Response({"error": "Variant not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            updated = ReviewVendorProductAction().reject(request.user, product, serializer.validated_data["reason"])
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(ProductSerializer(updated, context={"request": request}).data)
