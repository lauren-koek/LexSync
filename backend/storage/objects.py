"""Private object storage for original internal PDFs."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Protocol


class ObjectStorageError(RuntimeError):
    pass


class StorageConfigurationError(ObjectStorageError):
    pass


class ObjectStorage(Protocol):
    def put(self, key: str, content: bytes, content_type: str) -> None: ...
    def delete(self, key: str) -> None: ...
    def presigned_get_url(self, key: str, expires_seconds: int = 900) -> str: ...


class S3ObjectStorage:
    _REQUIRED = (
        "AWS_ENDPOINT_URL",
        "S3_BUCKET_NAME",
        "AWS_DEFAULT_REGION",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
    )

    def __init__(self, client_factory=None):
        missing = [name for name in self._REQUIRED if not os.environ.get(name)]
        if missing:
            raise StorageConfigurationError(
                "Missing object-storage configuration: " + ", ".join(missing)
            )

        self.bucket = os.environ["S3_BUCKET_NAME"]
        options = {
            "endpoint_url": os.environ["AWS_ENDPOINT_URL"],
            "region_name": os.environ["AWS_DEFAULT_REGION"],
            "aws_access_key_id": os.environ["AWS_ACCESS_KEY_ID"],
            "aws_secret_access_key": os.environ["AWS_SECRET_ACCESS_KEY"],
        }
        if client_factory is None:
            import boto3
            from botocore.config import Config

            self._client = boto3.client(
                "s3", **options, config=Config(s3={"addressing_style": "virtual"})
            )
        else:
            self._client = client_factory(**options)

    def put(self, key: str, content: bytes, content_type: str) -> None:
        try:
            self._client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=content,
                ContentType=content_type,
            )
        except Exception as exc:
            raise ObjectStorageError("Unable to store the uploaded PDF") from exc

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            response = getattr(exc, "response", {})
            code = response.get("Error", {}).get("Code")
            if code in {"NoSuchKey", "404", "NotFound"}:
                return
            raise ObjectStorageError("Unable to delete the stored PDF") from exc

    def presigned_get_url(self, key: str, expires_seconds: int = 900) -> str:
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires_seconds,
            )
        except Exception as exc:
            raise ObjectStorageError("Unable to create a PDF access URL") from exc


@lru_cache(maxsize=1)
def get_object_storage() -> ObjectStorage:
    return S3ObjectStorage()
