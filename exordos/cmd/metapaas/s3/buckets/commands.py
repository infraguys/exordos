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

import uuid as sys_uuid

import rich_click as click

from exordos import constants as c
from exordos.clients import base_client
from exordos.cmd.base import create_entity_group
from exordos.common.table import show_data

ENTITY = "bucket"
ENTITY_COLLECTION = c.S3_BUCKET_COLLECTION
RETENTION_MODES = ["GOVERNANCE", "COMPLIANCE"]
FIELDS_MAP = {
    "UUID": "uuid",
    "Project": "project_id",
    "Name": "name",
    "Instance": "instance",
    "Status": "status",
    "Versioning": "versioning_enabled",
    "Object lock": "object_lock_enabled",
    "Public": "public",
    "Quota": "quota_bytes",
}


buckets_group = create_entity_group(
    ENTITY, ENTITY_COLLECTION, FIELDS_MAP, parents=["instance"]
)


@click.command("add", help=f"Add a new {ENTITY}")
@click.pass_context
@click.option(
    "-u",
    "--uuid",
    type=click.UUID,
    default=None,
    help=f"UUID of the {ENTITY}",
)
@click.option(
    "-p",
    "--project-id",
    type=click.UUID,
    required=True,
    help=f"UUID of the project in which to create the {ENTITY}",
)
@click.option(
    "-i",
    "--instance-uuid",
    type=str,
    required=True,
    help=f"UUID of the instance to create the {ENTITY} in",
)
@click.option(
    "-n",
    "--name",
    type=str,
    required=True,
    help=f"Name of the {ENTITY}",
)
@click.option(
    "--description",
    type=str,
    default=None,
    help=f"Description of the {ENTITY}",
)
@click.option(
    "--versioning/--no-versioning",
    "versioning_enabled",
    default=None,
    help=f"Keep object versions in the {ENTITY}, cannot be changed later",
)
@click.option(
    "--object-lock/--no-object-lock",
    "object_lock_enabled",
    default=None,
    help=f"Enable object lock on the {ENTITY}, cannot be changed later",
)
@click.option(
    "--public/--no-public",
    "public",
    default=None,
    help=f"Allow anonymous read access to the {ENTITY}",
)
@click.option(
    "--quota-bytes",
    type=click.IntRange(0, 2**63 - 1),
    default=None,
    help=f"Size limit of the {ENTITY} in bytes, 0 means unlimited",
)
@click.option(
    "--default-retention-mode",
    type=click.Choice(RETENTION_MODES, case_sensitive=False),
    default=None,
    help="Default object lock retention mode",
)
@click.option(
    "--default-retention-days",
    type=click.IntRange(1, 365000),
    default=None,
    help="Default object lock retention period in days",
)
def add_cmd(
    ctx: click.Context,
    uuid: sys_uuid.UUID | None,
    project_id: sys_uuid.UUID,
    instance_uuid: str,
    name: str,
    description: str | None,
    versioning_enabled: bool | None,
    object_lock_enabled: bool | None,
    public: bool | None,
    quota_bytes: int | None,
    default_retention_mode: str | None,
    default_retention_days: int | None,
) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)
    if uuid is None:
        uuid = sys_uuid.uuid4()
    data = {
        "uuid": str(uuid),
        "project_id": str(project_id),
        "name": name,
        "instance": f"{c.S3_INSTANCE_COLLECTION}{instance_uuid}",
    }
    if description is not None:
        data["description"] = description
    if versioning_enabled is not None:
        data["versioning_enabled"] = versioning_enabled
    if object_lock_enabled is not None:
        data["object_lock_enabled"] = object_lock_enabled
    if public is not None:
        data["public"] = public
    if quota_bytes is not None:
        data["quota_bytes"] = quota_bytes
    if default_retention_mode is not None:
        data["default_retention_mode"] = default_retention_mode.upper()
    if default_retention_days is not None:
        data["default_retention_days"] = default_retention_days

    entity = base_client.add_entity(
        client, ENTITY_COLLECTION.format(instance_uuid=instance_uuid), data
    )
    show_data(entity)


@click.command("update", help=f"Update {ENTITY}")
@click.pass_context
@click.argument(
    "uuid",
    type=str,
    required=True,
)
@click.option(
    "-i",
    "--instance-uuid",
    type=str,
    required=True,
    help=f"UUID of the instance the {ENTITY} belongs to",
)
@click.option(
    "--description",
    type=str,
    required=False,
    help=f"Description of the {ENTITY}",
)
@click.option(
    "--public/--no-public",
    "public",
    default=None,
    help=f"Allow anonymous read access to the {ENTITY}",
)
@click.option(
    "--quota-bytes",
    type=click.IntRange(0, 2**63 - 1),
    required=False,
    help=f"Size limit of the {ENTITY} in bytes, 0 means unlimited",
)
@click.option(
    "--default-retention-mode",
    type=click.Choice(RETENTION_MODES, case_sensitive=False),
    required=False,
    help="Default object lock retention mode",
)
@click.option(
    "--default-retention-days",
    type=click.IntRange(1, 365000),
    required=False,
    help="Default object lock retention period in days",
)
def update_cmd(
    ctx: click.Context,
    uuid: str,
    instance_uuid: str,
    description: str | None,
    public: bool | None,
    quota_bytes: int | None,
    default_retention_mode: str | None,
    default_retention_days: int | None,
) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)
    data = {}
    if description is not None:
        data["description"] = description
    if public is not None:
        data["public"] = public
    if quota_bytes is not None:
        data["quota_bytes"] = quota_bytes
    if default_retention_mode is not None:
        data["default_retention_mode"] = default_retention_mode.upper()
    if default_retention_days is not None:
        data["default_retention_days"] = default_retention_days

    entity = base_client.update_entity(
        client, ENTITY_COLLECTION.format(instance_uuid=instance_uuid), uuid, data
    )
    show_data(entity)


buckets_group.add_command(add_cmd, aliases=["a"])
buckets_group.add_command(update_cmd, aliases=["u"])
