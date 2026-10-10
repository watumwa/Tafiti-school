from django.core.management.base import BaseCommand

from app.services.outbound_messages import process_outbound_messages


class Command(BaseCommand):
    help = "Send queued SMS/email deliveries with retry tracking."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        result = process_outbound_messages(limit=max(1, options["limit"]))
        self.stdout.write(self.style.SUCCESS(
            f"Outbound processing complete: processed={result['processed']} sent={result['sent']} failed={result['failed']}"
        ))
