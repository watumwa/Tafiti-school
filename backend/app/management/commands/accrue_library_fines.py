from django.core.management.base import BaseCommand

from app.services.library_automation import accrue_overdue_library_fines


class Command(BaseCommand):
    help = "Accrue overdue library fines and update matching student ledger charges."

    def handle(self, *args, **options):
        result = accrue_overdue_library_fines(actor=None)
        self.stdout.write(self.style.SUCCESS(
            f"Library fine accrual complete: checked={result['checked']} updated={result['updated']} notifications={result['notifications']}"
        ))
