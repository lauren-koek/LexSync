from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from backend.storage.objects import S3ObjectStorage, StorageConfigurationError


@dataclass
class FakeClient:
    puts: list
    deletes: list

    def get_object(self, **kwargs):
        self.get = kwargs
        return {"Body": SimpleNamespace(read=lambda: b"%PDF-restored")}

    def head_object(self, **kwargs):
        self.head = kwargs

    def put_object(self, **kwargs):
        self.puts.append(kwargs)

    def delete_object(self, **kwargs):
        self.deletes.append(kwargs)

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        return f"signed://{operation}/{Params['Bucket']}/{Params['Key']}?ttl={ExpiresIn}"


def configured(monkeypatch):
    values = {
        "AWS_ENDPOINT_URL": "https://storage.example",
        "S3_BUCKET_NAME": "legal-docs",
        "AWS_DEFAULT_REGION": "auto",
        "AWS_ACCESS_KEY_ID": "key",
        "AWS_SECRET_ACCESS_KEY": "secret",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)


def test_storage_uses_agreed_environment(monkeypatch):
    configured(monkeypatch)
    captured = {}
    storage = S3ObjectStorage(
        client_factory=lambda **kwargs: captured.update(kwargs) or FakeClient([], [])
    )

    assert storage.bucket == "legal-docs"
    assert captured == {
        "endpoint_url": "https://storage.example",
        "region_name": "auto",
        "aws_access_key_id": "key",
        "aws_secret_access_key": "secret",
    }


def test_storage_rejects_missing_bucket(monkeypatch):
    configured(monkeypatch)
    monkeypatch.delenv("S3_BUCKET_NAME")

    with pytest.raises(StorageConfigurationError, match="S3_BUCKET_NAME"):
        S3ObjectStorage(client_factory=lambda **kwargs: FakeClient([], []))


def test_storage_put_delete_and_presign_use_exact_object(monkeypatch):
    configured(monkeypatch)
    client = FakeClient([], [])
    storage = S3ObjectStorage(client_factory=lambda **kwargs: client)

    storage.put("internal-documents/id/policy.pdf", b"pdf", "application/pdf")
    content = storage.get("internal-documents/id/policy.pdf")
    exists = storage.exists("internal-documents/id/policy.pdf")
    url = storage.presigned_get_url("internal-documents/id/policy.pdf", 120)
    storage.delete("internal-documents/id/policy.pdf")

    assert client.puts == [{
        "Bucket": "legal-docs",
        "Key": "internal-documents/id/policy.pdf",
        "Body": b"pdf",
        "ContentType": "application/pdf",
    }]
    assert content == b"%PDF-restored"
    assert exists is True
    assert client.get == {"Bucket": "legal-docs", "Key": "internal-documents/id/policy.pdf"}
    assert client.head == {"Bucket": "legal-docs", "Key": "internal-documents/id/policy.pdf"}
    assert url == "signed://get_object/legal-docs/internal-documents/id/policy.pdf?ttl=120"
    assert client.deletes == [{"Bucket": "legal-docs", "Key": "internal-documents/id/policy.pdf"}]
