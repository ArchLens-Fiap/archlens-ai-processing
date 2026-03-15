from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.storage import MinioStorage


class TestMinioStorage:
    @patch("app.infrastructure.storage.get_settings")
    def test_init_http_endpoint(self, mock_settings):
        settings = MagicMock()
        settings.minio_use_ssl = False
        settings.minio_endpoint = "localhost:9000"
        settings.minio_access_key = "access"
        settings.minio_secret_key = "secret"
        settings.minio_bucket = "test-bucket"
        mock_settings.return_value = settings

        storage = MinioStorage()
        assert storage._endpoint == "http://localhost:9000"
        assert storage._bucket == "test-bucket"

    @patch("app.infrastructure.storage.get_settings")
    def test_init_https_endpoint(self, mock_settings):
        settings = MagicMock()
        settings.minio_use_ssl = True
        settings.minio_endpoint = "s3.example.com"
        settings.minio_access_key = "access"
        settings.minio_secret_key = "secret"
        settings.minio_bucket = "prod-bucket"
        mock_settings.return_value = settings

        storage = MinioStorage()
        assert storage._endpoint == "https://s3.example.com"

    @patch("app.infrastructure.storage.get_settings")
    @pytest.mark.asyncio
    async def test_download_strips_bucket_prefix(self, mock_settings):
        settings = MagicMock()
        settings.minio_use_ssl = False
        settings.minio_endpoint = "localhost:9000"
        settings.minio_access_key = "access"
        settings.minio_secret_key = "secret"
        settings.minio_bucket = "archlens-diagrams"
        mock_settings.return_value = settings

        storage = MinioStorage()

        mock_body = AsyncMock()
        mock_body.read.return_value = b"file-content"
        mock_s3 = AsyncMock()
        mock_s3.get_object.return_value = {"Body": mock_body}

        mock_client_ctx = AsyncMock()
        mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_s3)
        mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

        storage._session = MagicMock()
        storage._session.client.return_value = mock_client_ctx

        data = await storage.download("archlens-diagrams/uploads/img.png")
        assert data == b"file-content"
        mock_s3.get_object.assert_called_once_with(
            Bucket="archlens-diagrams", Key="uploads/img.png"
        )

    @patch("app.infrastructure.storage.get_settings")
    @pytest.mark.asyncio
    async def test_download_key_without_bucket_prefix(self, mock_settings):
        settings = MagicMock()
        settings.minio_use_ssl = False
        settings.minio_endpoint = "localhost:9000"
        settings.minio_access_key = "access"
        settings.minio_secret_key = "secret"
        settings.minio_bucket = "archlens-diagrams"
        mock_settings.return_value = settings

        storage = MinioStorage()

        mock_body = AsyncMock()
        mock_body.read.return_value = b"data"
        mock_s3 = AsyncMock()
        mock_s3.get_object.return_value = {"Body": mock_body}

        mock_client_ctx = AsyncMock()
        mock_client_ctx.__aenter__ = AsyncMock(return_value=mock_s3)
        mock_client_ctx.__aexit__ = AsyncMock(return_value=False)

        storage._session = MagicMock()
        storage._session.client.return_value = mock_client_ctx

        data = await storage.download("some/other/path.png")
        assert data == b"data"
        mock_s3.get_object.assert_called_once_with(
            Bucket="archlens-diagrams", Key="some/other/path.png"
        )
