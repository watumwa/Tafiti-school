from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from app.models.results import (
    Result,
    ResultBatch,
    ResultVerificationNotification,
    VerificationSample,
)


class Command(BaseCommand):
    help = "Release all pending result batches directly to reports when verification is disabled."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Release pending batches even when RESULT_VERIFICATION_ENABLED is true.",
        )

    def handle(self, *args, **options):
        if getattr(settings, "RESULT_VERIFICATION_ENABLED", True) and not options["force"]:
            raise CommandError(
                "Verification is enabled. Disable RESULT_VERIFICATION_ENABLED or use --force."
            )

        pending_batches = ResultBatch.objects.filter(status="PENDING")
        batch_ids = list(pending_batches.values_list("id", flat=True))
        if not batch_ids:
            self.stdout.write(self.style.SUCCESS("No pending result batches found."))
            return

        now = timezone.now()
        with transaction.atomic():
            result_count = Result.objects.filter(batch_id__in=batch_ids).update(status="VERIFIED")
            VerificationSample.objects.filter(result__batch_id__in=batch_ids).delete()
            ResultVerificationNotification.objects.filter(
                batch_id__in=batch_ids,
                read=False,
            ).update(read=True, read_at=now)
            pending_batches.update(
                status="VERIFIED",
                verified_by=None,
                verified_at=now,
                rejection_reason=None,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Released {len(batch_ids)} pending batch(es) and {result_count} result(s) to reports."
            )
        )
