from django.core.management.base import BaseCommand, CommandError

from vendors.actions import BackfillVendorFulfillmentNodesAction


class Command(BaseCommand):
    help = "Create vendor-store fulfillment nodes and node inventory from existing vendors/products."

    def add_arguments(self, parser):
        parser.add_argument(
            "--vendor-id",
            default=None,
            help="Backfill a single vendor UUID instead of all approved vendors.",
        )
        parser.add_argument(
            "--include-unapproved",
            action="store_true",
            help="Include non-approved vendors. Their nodes are created paused and not accepting orders.",
        )
        parser.add_argument(
            "--sync-existing",
            action="store_true",
            help="Update existing vendor-store node details and node inventory from current vendor/product data.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the expected changes without writing to the database.",
        )

    def handle(self, *args, **options):
        if options["vendor_id"] and options["include_unapproved"]:
            raise CommandError("--include-unapproved is not needed when --vendor-id is provided.")

        summary = BackfillVendorFulfillmentNodesAction().execute(
            vendor_id=options["vendor_id"],
            include_unapproved=options["include_unapproved"],
            sync_existing=options["sync_existing"],
            dry_run=options["dry_run"],
        )
        mode = "dry-run" if options["dry_run"] else "applied"
        self.stdout.write(self.style.SUCCESS(f"Fulfillment node backfill {mode}: {summary}"))
