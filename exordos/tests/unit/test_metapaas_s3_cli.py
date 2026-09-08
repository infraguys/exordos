#    Copyright 2026 Genesis Corporation.
#
#    All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
from __future__ import annotations

import typing as tp
from unittest import mock

from click.testing import CliRunner

from exordos.cmd import metapaas
from exordos.common.cmd_context import ContextObject

INSTANCE_UUID = "11111111-1111-1111-1111-111111111111"
USER_UUID = "22222222-2222-2222-2222-222222222222"
POLICY_UUID = "33333333-3333-3333-3333-333333333333"
PROJECT_ID = "44444444-4444-4444-4444-444444444444"
VERSION_UUID = "55555555-5555-5555-5555-555555555555"


def _run(*args: str, lookup: dict | None = None) -> tuple[tp.Any, mock.MagicMock]:
    """Invoke an s3 command with the API client calls mocked out."""
    with (
        mock.patch("exordos.clients.base_client.get_user_api_client"),
        mock.patch("exordos.clients.base_client.get_entity", return_value=lookup or {}),
        mock.patch(
            "exordos.clients.base_client.add_entity", return_value={}
        ) as add_entity,
    ):
        result = CliRunner().invoke(
            metapaas.metapaas_group,
            ["s3", *args],
            obj=ContextObject(
                auth_data={"endpoint": "http://10.20.0.2/api/core"},
                cfg_path=None,
                developer_key_path=None,
                cfg={},
                need_update=None,
            ),
        )
    return result, add_entity


class TestS3Instances:
    def test_add_cmd_resolves_version_and_builds_payload(self) -> None:
        result, add_entity = _run(
            "instances",
            "add",
            "-p",
            PROJECT_ID,
            "-n",
            "store",
            "-v",
            "minio-2025",
            "--cpu",
            "2",
            "--ram",
            "2048",
            "--disk-size",
            "20",
            lookup={"uuid": VERSION_UUID},
        )
        assert result.exit_code == 0, result.output
        _, collection, data = add_entity.call_args[0]
        assert collection == "/v1/types/s3/instances/"
        assert data["name"] == "store"
        assert data["version"] == f"/v1/types/s3/versions/{VERSION_UUID}"
        assert data["nodes_number"] == 1
        assert "description" not in data


class TestS3Buckets:
    def test_add_cmd_builds_nested_collection_and_payload(self) -> None:
        result, add_entity = _run(
            "buckets",
            "add",
            "-p",
            PROJECT_ID,
            "-i",
            INSTANCE_UUID,
            "-n",
            "backups",
            "--versioning",
            "--quota-bytes",
            "1024",
        )
        assert result.exit_code == 0, result.output
        _, collection, data = add_entity.call_args[0]
        assert collection == f"/v1/types/s3/instances/{INSTANCE_UUID}/buckets/"
        assert data["instance"] == f"/v1/types/s3/instances/{INSTANCE_UUID}"
        assert data["versioning_enabled"] is True
        assert data["quota_bytes"] == 1024
        assert "public" not in data
        assert "object_lock_enabled" not in data

    def test_add_cmd_uppercases_retention_mode(self) -> None:
        result, add_entity = _run(
            "buckets",
            "add",
            "-p",
            PROJECT_ID,
            "-i",
            INSTANCE_UUID,
            "-n",
            "backups",
            "--object-lock",
            "--default-retention-mode",
            "governance",
            "--default-retention-days",
            "30",
        )
        assert result.exit_code == 0, result.output
        _, _, data = add_entity.call_args[0]
        assert data["default_retention_mode"] == "GOVERNANCE"
        assert data["default_retention_days"] == 30


class TestS3Policies:
    def test_add_cmd_parses_content(self) -> None:
        content = '{"Version": "2012-10-17", "Statement": []}'
        result, add_entity = _run(
            "policies",
            "add",
            "-p",
            PROJECT_ID,
            "-i",
            INSTANCE_UUID,
            "-n",
            "read-only",
            "--content",
            content,
        )
        assert result.exit_code == 0, result.output
        _, collection, data = add_entity.call_args[0]
        assert collection == f"/v1/types/s3/instances/{INSTANCE_UUID}/policies/"
        assert data["content"] == {"Version": "2012-10-17", "Statement": []}

    def test_add_cmd_rejects_invalid_content(self) -> None:
        result, add_entity = _run(
            "policies",
            "add",
            "-p",
            PROJECT_ID,
            "-i",
            INSTANCE_UUID,
            "-n",
            "read-only",
            "--content",
            "not json",
        )
        assert result.exit_code != 0
        assert "Invalid JSON string" in result.output
        add_entity.assert_not_called()


class TestS3Users:
    def test_add_cmd_builds_nested_collection_and_payload(self) -> None:
        result, add_entity = _run(
            "users",
            "add",
            "-p",
            PROJECT_ID,
            "-i",
            INSTANCE_UUID,
            "-n",
            "app",
        )
        assert result.exit_code == 0, result.output
        _, collection, data = add_entity.call_args[0]
        assert collection == f"/v1/types/s3/instances/{INSTANCE_UUID}/users/"
        assert data["instance"] == f"/v1/types/s3/instances/{INSTANCE_UUID}"
        assert data["name"] == "app"


class TestS3Keys:
    def test_add_cmd_builds_nested_collection_and_payload(self) -> None:
        result, add_entity = _run(
            "keys",
            "add",
            "-p",
            PROJECT_ID,
            "-i",
            INSTANCE_UUID,
            "--user-uuid",
            USER_UUID,
        )
        assert result.exit_code == 0, result.output
        _, collection, data = add_entity.call_args[0]
        assert collection == (
            f"/v1/types/s3/instances/{INSTANCE_UUID}/users/{USER_UUID}/keys/"
        )
        assert data["user"] == (
            f"/v1/types/s3/instances/{INSTANCE_UUID}/users/{USER_UUID}"
        )
        assert "secret_key" not in data

    def test_add_cmd_passes_explicit_secret_key(self) -> None:
        result, add_entity = _run(
            "keys",
            "add",
            "-p",
            PROJECT_ID,
            "-i",
            INSTANCE_UUID,
            "--user-uuid",
            USER_UUID,
            "--secret-key",
            "s3cret",
        )
        assert result.exit_code == 0, result.output
        _, _, data = add_entity.call_args[0]
        assert data["secret_key"] == "s3cret"


class TestS3UserPolicies:
    def test_add_cmd_resolves_policy_and_builds_payload(self) -> None:
        result, add_entity = _run(
            "user-policies",
            "add",
            "-p",
            PROJECT_ID,
            "-i",
            INSTANCE_UUID,
            "--user-uuid",
            USER_UUID,
            "--policy",
            "read-only",
            lookup={"uuid": POLICY_UUID},
        )
        assert result.exit_code == 0, result.output
        _, collection, data = add_entity.call_args[0]
        assert collection == (
            f"/v1/types/s3/instances/{INSTANCE_UUID}/users/{USER_UUID}/policies/"
        )
        assert data["user"] == (
            f"/v1/types/s3/instances/{INSTANCE_UUID}/users/{USER_UUID}"
        )
        assert data["policy"] == (
            f"/v1/types/s3/instances/{INSTANCE_UUID}/policies/{POLICY_UUID}"
        )


class TestS3Versions:
    def test_versions_group_is_read_only(self) -> None:
        versions = metapaas.s3_group.commands["versions"]
        assert set(versions.commands) == {"list", "show"}
