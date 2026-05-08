from __future__ import annotations

import asyncio
import dataclasses
import json
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from .base import PluginRecord, SourceRecord


def _default_serializer(obj: object) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _record_to_json(record: object) -> bytes:
    return json.dumps(dataclasses.asdict(record), default=_default_serializer).encode()  # type: ignore[call-overload]


def _plugin_from_dict(data: dict[str, Any]) -> PluginRecord:
    data["updated_at"] = datetime.fromisoformat(data["updated_at"])
    return PluginRecord(**data)


def _source_from_dict(data: dict[str, Any]) -> SourceRecord:
    if data.get("last_indexed_at") is not None:
        data["last_indexed_at"] = datetime.fromisoformat(data["last_indexed_at"])
    return SourceRecord(**data)


class S3Repository:
    def __init__(
        self,
        endpoint_url: str | None,
        bucket: str,
        access_key: str | None,
        secret_key: str | None,
    ) -> None:
        self._endpoint_url = endpoint_url
        self._bucket = bucket
        self._access_key = access_key
        self._secret_key = secret_key
        self._client: Any = None
        self._index: dict[str, list[str]] = {"plugins": [], "sources": []}

    def _make_sync_client(self) -> Any:
        kwargs: dict[str, Any] = {"region_name": "us-east-1"}
        if self._endpoint_url is not None:
            kwargs["endpoint_url"] = self._endpoint_url
        if self._access_key is not None:
            kwargs["aws_access_key_id"] = self._access_key
        if self._secret_key is not None:
            kwargs["aws_secret_access_key"] = self._secret_key
        return boto3.client("s3", **kwargs)

    async def init(self) -> None:
        self._client = await asyncio.to_thread(self._make_sync_client)

        def _setup() -> dict[str, list[str]]:
            try:
                self._client.head_bucket(Bucket=self._bucket)
            except ClientError:
                self._client.create_bucket(Bucket=self._bucket)
            try:
                resp = self._client.get_object(Bucket=self._bucket, Key="index.json")
                return json.loads(resp["Body"].read())  # type: ignore[no-any-return]
            except ClientError as exc:
                if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                    empty: dict[str, list[str]] = {"plugins": [], "sources": []}
                    self._client.put_object(
                        Bucket=self._bucket,
                        Key="index.json",
                        Body=json.dumps(empty).encode(),
                        ContentType="application/json",
                    )
                    return empty
                raise

        self._index = await asyncio.to_thread(_setup)

    def _sync_put_index(self) -> None:
        self._client.put_object(
            Bucket=self._bucket,
            Key="index.json",
            Body=json.dumps(self._index).encode(),
            ContentType="application/json",
        )

    def _sync_get_json(self, key: str) -> dict[str, Any] | None:
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
            return json.loads(resp["Body"].read())  # type: ignore[no-any-return]
        except ClientError as exc:
            if exc.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise

    async def list_plugins(
        self,
        type_filter: str | None = None,
        tags: list[str] | None = None,
        query: str | None = None,
    ) -> list[PluginRecord]:
        names = list(self._index["plugins"])

        results = await asyncio.gather(
            *[asyncio.to_thread(self._sync_get_json, f"plugins/{n}.json") for n in names]
        )
        records = [_plugin_from_dict(d) for d in results if d is not None]

        if type_filter is not None:
            records = [r for r in records if r.type == type_filter]
        if tags:
            records = [r for r in records if all(t in r.tags for t in tags)]
        if query:
            q = query.lower()
            records = [r for r in records if q in r.name.lower() or q in r.description.lower()]
        return records

    async def get_plugin(self, name: str) -> PluginRecord | None:
        data = await asyncio.to_thread(self._sync_get_json, f"plugins/{name}.json")
        if data is None:
            return None
        return _plugin_from_dict(data)

    async def upsert_plugin(self, record: PluginRecord) -> None:
        def _do() -> None:
            self._client.put_object(
                Bucket=self._bucket,
                Key=f"plugins/{record.name}.json",
                Body=_record_to_json(record),
                ContentType="application/json",
            )
            if record.name not in self._index["plugins"]:
                self._index["plugins"].append(record.name)
            self._sync_put_index()

        await asyncio.to_thread(_do)

    async def delete_plugin(self, name: str) -> None:
        def _do() -> None:
            self._client.delete_object(Bucket=self._bucket, Key=f"plugins/{name}.json")
            if name in self._index["plugins"]:
                self._index["plugins"].remove(name)
            self._sync_put_index()

        await asyncio.to_thread(_do)

    async def list_sources(self) -> list[SourceRecord]:
        ids = list(self._index["sources"])
        results = await asyncio.gather(
            *[asyncio.to_thread(self._sync_get_json, f"sources/{i}.json") for i in ids]
        )
        return [_source_from_dict(d) for d in results if d is not None]

    async def get_source(self, id: str) -> SourceRecord | None:
        data = await asyncio.to_thread(self._sync_get_json, f"sources/{id}.json")
        if data is None:
            return None
        return _source_from_dict(data)

    async def upsert_source(self, record: SourceRecord) -> None:
        def _do() -> None:
            self._client.put_object(
                Bucket=self._bucket,
                Key=f"sources/{record.id}.json",
                Body=_record_to_json(record),
                ContentType="application/json",
            )
            if record.id not in self._index["sources"]:
                self._index["sources"].append(record.id)
            self._sync_put_index()

        await asyncio.to_thread(_do)

    async def delete_source(self, id: str) -> None:
        def _do() -> None:
            self._client.delete_object(Bucket=self._bucket, Key=f"sources/{id}.json")
            if id in self._index["sources"]:
                self._index["sources"].remove(id)
            self._sync_put_index()

        await asyncio.to_thread(_do)


__all__ = ["S3Repository"]
