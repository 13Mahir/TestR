"""
core/gcs.py
Google Cloud Storage utility functions.
"""

from google.cloud import storage
import datetime

from core.config import settings


def _get_client() -> storage.Client:
    """Returns an authenticated GCS client."""
    if settings.GOOGLE_APPLICATION_CREDENTIALS:
        try:
            return storage.Client.from_service_account_json(
                settings.GOOGLE_APPLICATION_CREDENTIALS
            )
        except Exception:
            # Fallback to default if JSON path is invalid/missing
            pass
    return storage.Client()
    # In Cloud Run: uses Workload Identity automatically.
    # Locally: uses GOOGLE_APPLICATION_CREDENTIALS from settings/env.


async def upload_file(
    bucket: str,
    destination_path: str,
    file_bytes: bytes,
    content_type: str = "application/octet-stream",
) -> str:
    """
    Uploads bytes to GCS. Returns the GCS URI (not signed URL).
    Runs in a thread executor to avoid blocking the event loop.
    """
    import asyncio
    loop = asyncio.get_event_loop()

    def _upload():
        client = _get_client()
        bkt    = client.bucket(bucket)
        blob   = bkt.blob(destination_path)
        blob.upload_from_string(file_bytes, content_type=content_type)
        return f"gs://{bucket}/{destination_path}"

    return await loop.run_in_executor(None, _upload)


async def delete_file(bucket: str, file_path: str) -> bool:
    """Deletes a file from GCS. Returns True on success."""
    import asyncio
    loop = asyncio.get_event_loop()

    def _delete():
        client = _get_client()
        bkt    = client.bucket(bucket)
        blob   = bkt.blob(file_path)
        blob.delete()
        return True

    try:
        return await loop.run_in_executor(None, _delete)
    except Exception:
        return False


async def generate_signed_url(
    bucket: str,
    file_path: str,
    expiry_minutes: int = 60,
) -> str:
    """
    Generates a time-limited signed URL for a GCS object.
    Used when serving proctor snapshots to teachers.
    """
    import asyncio
    loop = asyncio.get_event_loop()

    def _sign():
        client = _get_client()
        bkt    = client.bucket(bucket)
        blob   = bkt.blob(file_path)

        # For V4 signing to work without a service account key (on Cloud Run),
        # we need to provide the service account email and ensure the 
        # SA has "Service Account Token Creator" role on itself.
        try:
            url = blob.generate_signed_url(
                expiration=datetime.timedelta(minutes=expiry_minutes),
                method="GET",
                version="v4",
            )
            return url
        except Exception as e:
            # If signing fails (likely missing private key), 
            # we return a public URL if the bucket is public,
            # or log a warning.
            import logging
            logging.warning(f"GCS Signing failed: {e}. Falling back to public URL.")
            return f"https://storage.googleapis.com/{bucket}/{file_path}"

    return await loop.run_in_executor(None, _sign)
