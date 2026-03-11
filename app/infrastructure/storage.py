import aioboto3
import structlog

from app.config import get_settings

logger = structlog.get_logger()


class MinioStorage:
    def __init__(self):
        settings = get_settings()
        self._session = aioboto3.Session()
        self._endpoint = f"{'https' if settings.minio_use_ssl else 'http'}://{settings.minio_endpoint}"
        self._access_key = settings.minio_access_key
        self._secret_key = settings.minio_secret_key
        self._bucket = settings.minio_bucket
        self._use_ssl = settings.minio_use_ssl

    async def download(self, storage_path: str) -> bytes:
        key = storage_path.removeprefix(f"{self._bucket}/")

        async with self._session.client(
            "s3",
            endpoint_url=self._endpoint,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            use_ssl=self._use_ssl,
        ) as s3:
            response = await s3.get_object(Bucket=self._bucket, Key=key)
            data = await response["Body"].read()

        logger.info("Downloaded from MinIO", bucket=self._bucket, key=key, size=len(data))
        return data
