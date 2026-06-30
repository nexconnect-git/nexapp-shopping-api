import json

from django.core.management.base import BaseCommand, CommandError

from vendors.actions import FulfillmentReadinessAuditAction


class Command(BaseCommand):
    help = "Run a read-only fulfillment-node launch readiness audit."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sample-limit",
            type=int,
            default=20,
            help="Maximum sample rows to include per issue category.",
        )
        parser.add_argument(
            "--fail-on-issues",
            action="store_true",
            help="Exit with a command error when critical readiness issues exist.",
        )

    def handle(self, *args, **options):
        result = FulfillmentReadinessAuditAction().execute(
            sample_limit=options["sample_limit"],
        )
        self.stdout.write(json.dumps(result, indent=2, default=str))
        if options["fail_on_issues"] and result["critical_issue_count"] > 0:
            raise CommandError(
                f"Fulfillment readiness blocked by {result['critical_issue_count']} critical issue(s)."
            )
