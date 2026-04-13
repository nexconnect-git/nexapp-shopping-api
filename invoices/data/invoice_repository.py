"""
InvoiceRepository — all ORM queries for the Invoice model live here.
"""
from django.db.models import Q, QuerySet
from invoices.models import Invoice


class InvoiceRepository:
    """Data-access layer for Invoice. Views and actions must never query the
    ORM directly — they go through this class."""

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    def get_by_id(invoice_id) -> Invoice | None:
        """Return an Invoice by primary key, or None if not found."""
        try:
            return Invoice.objects.get(pk=invoice_id)
        except Invoice.DoesNotExist:
            return None

    @staticmethod
    def get_all() -> QuerySet:
        """Return all invoices (unfiltered)."""
        return Invoice.objects.all()

    @staticmethod
    def filter(**kwargs) -> QuerySet:
        """Return invoices matching the given keyword filters."""
        return Invoice.objects.filter(**kwargs)

    @staticmethod
    def get_for_user(user) -> QuerySet:
        """Return invoices where the user is either the recipient or the owner
        of the associated vendor profile."""
        qs = Invoice.objects.filter(recipient=user)
        if hasattr(user, 'vendor_profile'):
            qs = qs | Invoice.objects.filter(vendor=user.vendor_profile)
        return qs.order_by('-issued_at')

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    @staticmethod
    def create(**kwargs) -> Invoice:
        """Create and return a new Invoice."""
        return Invoice.objects.create(**kwargs)

    @staticmethod
    def update(invoice: Invoice, **kwargs) -> Invoice:
        """Apply keyword updates to an existing Invoice and save."""
        for attr, value in kwargs.items():
            setattr(invoice, attr, value)
        invoice.save()
        return invoice

    @staticmethod
    def delete(invoice: Invoice) -> None:
        """Delete the given Invoice."""
        invoice.delete()
