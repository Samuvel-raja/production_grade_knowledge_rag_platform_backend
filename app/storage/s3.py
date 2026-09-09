import anyio
import boto3
from botocore.config import Config as BotoConfig
from botocore.exceptions import BotoCoreError, ClientError

from app.storage.base import StorageError


class S3Storage:
    """S3-compatible object storage (AWS S3, MinIO, Cloudflare R2, ...).

    boto3 is sync, so every call is pushed to a worker thread.
    ponytail: sync boto3 in threadpool; switch to aioboto3 only if upload throughput matters.
    """

    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str,
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint or None,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
            region_name=region or None,
            config=BotoConfig(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._client.create_bucket(Bucket=self._bucket)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        def _put() -> None:
            self._client.put_object(
                Bucket=self._bucket, Key=key, Body=data, ContentType=content_type
            )

        await self._run(_put)

    async def get(self, key: str) -> bytes:
        def _get() -> bytes:
            return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

        return await self._run(_get)

    async def delete(self, key: str) -> None:
        await self._run(lambda: self._client.delete_object(Bucket=self._bucket, Key=key))

    def presigned_get_url(self, key: str, expires: int = 3600) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket, "Key": key},
            ExpiresIn=expires,
        )

    @staticmethod
    async def _run(fn):
        try:
            return await anyio.to_thread.run_sync(fn)
        except (BotoCoreError, ClientError) as exc:
            raise StorageError(str(exc)) from exc
