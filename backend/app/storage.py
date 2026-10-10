from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import Storage
from vercel.blob import BlobClient


class VercelBlobStorage(Storage):
    """Django storage backend for the public Tafiti Vercel Blob store.

    Django ``FileField``/``ImageField`` values are commonly limited to about
    100 characters.  A Vercel Blob URL plus a user supplied filename can easily
    exceed that limit and make the database save fail after the upload succeeds.
    Store uploads under a compact generated pathname so the returned public URL
    remains short enough for the existing school database schema.
    """

    @property
    def token(self):
        from django.conf import settings

        token = getattr(settings, "VERCEL_BLOB_READ_WRITE_TOKEN", "")
        if not token:
            raise ImproperlyConfigured(
                "VERCEL_BLOB_READ_WRITE_TOKEN must be configured for production media storage."
            )
        return token

    @staticmethod
    def _compact_path(name: str) -> str:
        # Keep only a short, harmless extension.  The original upload_to path
        # and filename are deliberately not used because they can make the
        # final Blob URL longer than legacy ImageField database columns allow.
        suffix = Path(str(name)).suffix.lower()
        if len(suffix) > 10 or not suffix.replace(".", "").isalnum():
            suffix = ""
        return f"m/{uuid4().hex[:20]}{suffix}"

    def _save(self, name, content):
        pathname = self._compact_path(str(name).lstrip("/"))
        content_type = getattr(content, "content_type", None) or "application/octet-stream"

        if hasattr(content, "seek"):
            content.seek(0)
        elif hasattr(content, "file") and hasattr(content.file, "seek"):
            content.file.seek(0)

        body = content.read() if hasattr(content, "read") else content.file.read()
        uploaded = BlobClient(token=self.token).put(
            pathname,
            body,
            access="public",
            content_type=content_type,
            overwrite=False,
        )
        return uploaded.url

    def exists(self, name):
        # Every upload gets a generated pathname, so collision checks are not
        # required and would add an unnecessary network request.
        return False

    def url(self, name):
        # Production records store the public Blob URL directly.
        return str(name)

    def delete(self, name):
        if not name or not str(name).startswith("http"):
            return
        BlobClient(token=self.token).delete(str(name))

    def size(self, name):
        return BlobClient(token=self.token).head(self.url(name)).size
