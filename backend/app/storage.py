from django.core.files.storage import Storage
from django.core.exceptions import ImproperlyConfigured
from vercel.blob import BlobClient


class VercelBlobStorage(Storage):
    """Django storage backend for a public Vercel Blob store."""

    @property
    def token(self):
        from django.conf import settings

        token = getattr(settings, "VERCEL_BLOB_READ_WRITE_TOKEN", "")
        if not token:
            raise ImproperlyConfigured(
                "VERCEL_BLOB_READ_WRITE_TOKEN must be configured for production media storage."
            )
        return token

    def _save(self, name, content):
        pathname = str(name).lstrip("/")
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
            overwrite=True,
        )
        return uploaded.url

    def exists(self, name):
        return False

    def url(self, name):
        return str(name)

    def delete(self, name):
        if not name or not str(name).startswith("http"):
            return
        BlobClient(token=self.token).delete(str(name))

    def size(self, name):
        return BlobClient(token=self.token).head(self.url(name)).size
