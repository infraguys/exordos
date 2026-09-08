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

import json
import uuid as sys_uuid

import rich_click as click

from exordos import constants as c
from exordos.clients import base_client
from exordos.cmd.base import create_entity_group
from exordos.common.table import show_data

ENTITY = "policy"
ENTITY_COLLECTION = c.S3_POLICY_COLLECTION
FIELDS_MAP = {
    "UUID": "uuid",
    "Project": "project_id",
    "Name": "name",
    "Instance": "instance",
    "Status": "status",
}


policies_group = create_entity_group(
    ENTITY,
    ENTITY_COLLECTION,
    FIELDS_MAP,
    entity_plural="policies",
    parents=["instance"],
)


def _parse_content(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        raise click.ClickException(f"Invalid JSON string: '{content}': {e}")


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
    "--content",
    type=str,
    required=True,
    help="JSON string with the IAM policy document",
)
def add_cmd(
    ctx: click.Context,
    uuid: sys_uuid.UUID | None,
    project_id: sys_uuid.UUID,
    instance_uuid: str,
    name: str,
    description: str | None,
    content: str,
) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)
    if uuid is None:
        uuid = sys_uuid.uuid4()
    data = {
        "uuid": str(uuid),
        "project_id": str(project_id),
        "name": name,
        "instance": f"{c.S3_INSTANCE_COLLECTION}{instance_uuid}",
        "content": _parse_content(content),
    }
    if description is not None:
        data["description"] = description

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
    "-n",
    "--name",
    type=str,
    required=False,
    help=f"Name of the {ENTITY}",
)
@click.option(
    "--description",
    type=str,
    required=False,
    help=f"Description of the {ENTITY}",
)
@click.option(
    "--content",
    type=str,
    required=False,
    help="JSON string with the IAM policy document",
)
def update_cmd(
    ctx: click.Context,
    uuid: str,
    instance_uuid: str,
    name: str | None,
    description: str | None,
    content: str | None,
) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if content is not None:
        data["content"] = _parse_content(content)

    entity = base_client.update_entity(
        client, ENTITY_COLLECTION.format(instance_uuid=instance_uuid), uuid, data
    )
    show_data(entity)


policies_group.add_command(add_cmd, aliases=["a"])
policies_group.add_command(update_cmd, aliases=["u"])
