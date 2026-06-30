import json

from django.core.management.base import BaseCommand, CommandError

from vendors.actions import (
    BackfillVendorFulfillmentNodesAction,
    FulfillmentReadinessAuditAction,
)


class Command(BaseCommand):
    help = "Backfill fulfillment nodes, run readiness audit, and gate rollout."

    def add_arguments(self, parser):
        parser.add_argument(
            "--vendor-id",
            default=None,
            help="Prepare a single vendor UUID instead of all approved vendors.",
        )
        parser.add_argument(
            "--include-unapproved",
            action="store_true",
            help="Include non-approved vendors during backfill.",
        )
        parser.add_argument(
            "--sync-existing",
            action="store_true",
            help="Update existing vendor-store node details and node inventory from current data.",
        )
        parser.add_argument(
            "--skip-backfill",
            action="store_true",
            help="Only run readiness audit without creating or updating fulfillment data.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview backfill changes and run a read-only readiness audit.",
        )
        parser.add_argument(
            "--sample-limit",
            type=int,
            default=20,
            help="Maximum sample rows to include per readiness issue category.",
        )
        parser.add_argument(
            "--fail-on-issues",
            action="store_true",
            help="Fail even during dry-run when critical readiness issues exist.",
        )
        parser.add_argument(
            "--allow-blocked",
            action="store_true",
            help="Do not fail the command when the post-run readiness audit is blocked.",
        )

    def handle(self, *args, **options):
        if options["vendor_id"] and options["include_unapproved"]:
            raise CommandError("--include-unapproved is not needed when --vendor-id is provided.")
        if options["allow_blocked"] and options["fail_on_issues"]:
            raise CommandError("--allow-blocked and --fail-on-issues cannot be used together.")

        backfill_result = None
        if not options["skip_backfill"]:
            backfill_result = BackfillVendorFulfillmentNodesAction().execute(
                vendor_id=options["vendor_id"],
                include_unapproved=options["include_unapproved"],
                sync_existing=options["sync_existing"],
                dry_run=options["dry_run"],
            )

        readiness = FulfillmentReadinessAuditAction().execute(
            sample_limit=options["sample_limit"],
        )
        result = {
            "mode": "dry_run" if options["dry_run"] else "applied",
            "backfill": backfill_result,
            "readiness": readiness,
        }
        self.stdout.write(json.dumps(result, indent=2, default=str))

        should_fail = False
        if options["fail_on_issues"] and readiness["critical_issue_count"] > 0:
            should_fail = True
        if (
            not options["dry_run"]
            and not options["allow_blocked"]
            and readiness["critical_issue_count"] > 0
        ):
            should_fail = True
        if should_fail:
            raise CommandError(
                f"Fulfillment rollout blocked by {readiness['critical_issue_count']} critical issue(s)."
            )
