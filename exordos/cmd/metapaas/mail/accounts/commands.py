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

ENTITY = "account"
ENTITY_COLLECTION = c.MAIL_ACCOUNT_COLLECTION
FIELDS_MAP = {
    "UUID": "uuid",
    "Project": "project_id",
    "Username": "username",
    "Instance": "instance",
    "Active": "active",
}


accounts_group = create_entity_group(
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
    help=f"UUID of the mail instance to create the {ENTITY} in",
)
@click.option(
    "--username",
    type=str,
    required=True,
    help=f"SMTP login of the {ENTITY}, the local part of the address",
)
@click.option(
    "-n",
    "--name",
    type=str,
    default=None,
    help=f"Name of the {ENTITY}",
)
@click.option(
    "--description",
    type=str,
    default=None,
    help=f"Description of the {ENTITY}",
)
@click.option(
    "--password",
    type=str,
    default=None,
    help=f"Password of the {ENTITY}, hashed by the API before it is stored",
)
@click.option(
    "--active/--no-active",
    default=None,
    help=f"Whether the {ENTITY} is allowed to authenticate",
)
def add_cmd(
    ctx: click.Context,
    uuid: sys_uuid.UUID | None,
    project_id: sys_uuid.UUID,
    instance_uuid: str,
    username: str,
    name: str | None,
    description: str | None,
    password: str | None,
    active: bool | None,
) -> None:
    import questionary

    client = base_client.get_user_api_client(ctx.obj.auth_data)
    if uuid is None:
        uuid = sys_uuid.uuid4()
    data = {
        "uuid": str(uuid),
        "project_id": str(project_id),
        "instance": f"{c.MAIL_INSTANCE_COLLECTION}{instance_uuid}",
        "username": username,
        "password_hash": password
        or questionary.password(f"Enter password for {ENTITY} {username}:").ask(),
    }
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if active is not None:
        data["active"] = active

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
    help=f"UUID of the mail instance the {ENTITY} belongs to",
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
    "--password",
    type=str,
    required=False,
    help=f"Password of the {ENTITY}, hashed by the API before it is stored",
)
@click.option(
    "--active/--no-active",
    default=None,
    help=f"Whether the {ENTITY} is allowed to authenticate",
)
def update_cmd(
    ctx: click.Context,
    uuid: str,
    instance_uuid: str,
    name: str | None,
    description: str | None,
    password: str | None,
    active: bool | None,
) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if password is not None:
        data["password_hash"] = password
    if active is not None:
        data["active"] = active

    entity = base_client.update_entity(
        client, ENTITY_COLLECTION.format(instance_uuid=instance_uuid), uuid, data
    )
    show_data(entity)


accounts_group.add_command(add_cmd, aliases=["a"])
accounts_group.add_command(update_cmd, aliases=["u"])
