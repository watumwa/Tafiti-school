from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.files.base import File
from django.core.files.storage import FileSystemStorage
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import FileField

from app.storage import VercelBlobStorage


class Command(BaseCommand):
    help = "Copy existing local media files to Vercel Blob and update their database URLs."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-root",
            default=str(settings.MEDIA_ROOT),
            help="Local media directory containing the existing files.",
        )
        parser.add_argument("--dry-run", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        source_storage = FileSystemStorage(location=options["source_root"])
        blob_storage = VercelBlobStorage()
        migrated = 0
        skipped = 0
        missing = 0

        for model in apps.get_models():
            file_fields = [field for field in model._meta.fields if isinstance(field, FileField)]
            if not file_fields:
                continue

            for obj in model.objects.iterator():
                for field in file_fields:
                    stored_name = str(getattr(obj, field.attname, "") or "")
                    if not stored_name or stored_name.startswith("http"):
                        skipped += 1
                        continue
                    if not source_storage.exists(stored_name):
                        missing += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"Missing {model.__name__}.{field.name}: {stored_name}"
                            )
                        )
                        continue

                    if options["dry_run"]:
                        migrated += 1
                        continue

                    with source_storage.open(stored_name, "rb") as source_file:
                        uploaded_url = blob_storage.save(
                            stored_name,
                            File(source_file, name=Path(stored_name).name),
                        )
                    setattr(obj, field.name, uploaded_url)
                    obj.save(update_fields=[field.name])
                    migrated += 1

        if options["dry_run"]:
            transaction.set_rollback(True)

        self.stdout.write(
            self.style.SUCCESS(
                f"Media migration complete: {migrated} migrated, {skipped} already remote/empty, {missing} missing."
            )
        )
