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

ENTITY = "instance"
ENTITY_COLLECTION = c.MAIL_INSTANCE_COLLECTION
FIELDS_MAP = {
    "UUID": "uuid",
    "Project": "project_id",
    "Name": "name",
    "Domain": "domain",
    "Status": "status",
    "CPU": "cpu",
    "RAM": "ram",
    "Disk": "disk_size",
    "IPs": lambda x: ", ".join(x.get("ipsv4", [])),
    "Version": "version",
}


instances_group = create_entity_group(ENTITY, ENTITY_COLLECTION, FIELDS_MAP)


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
    help=f"UUID of the project in which to deploy the {ENTITY}",
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
    "-d",
    "--domain",
    type=str,
    required=True,
    help="Mail domain to serve, for example: example.com",
)
@click.option(
    "-v",
    "--version",
    type=str,
    required=True,
    help="UUID or name of the mail version",
)
@click.option(
    "--cpu",
    type=click.IntRange(1, 128),
    required=True,
    help="Number of CPU cores per node",
)
@click.option(
    "--ram",
    type=click.IntRange(512, 1024**3),
    required=True,
    help="RAM per node in MB",
)
@click.option(
    "--disk-size",
    type=click.IntRange(8, 1024**3),
    required=True,
    help="Disk size per node in GB",
)
def add_cmd(
    ctx: click.Context,
    uuid: sys_uuid.UUID | None,
    project_id: sys_uuid.UUID,
    name: str,
    description: str | None,
    domain: str,
    version: str,
    cpu: int,
    ram: int,
    disk_size: int,
) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)
    if uuid is None:
        uuid = sys_uuid.uuid4()
    version_uuid = base_client.get_entity(client, c.MAIL_VERSION_COLLECTION, version)[
        "uuid"
    ]
    data = {
        "uuid": str(uuid),
        "project_id": str(project_id),
        "name": name,
        "domain": domain,
        "version": f"{c.MAIL_VERSION_COLLECTION}{version_uuid}",
        "cpu": cpu,
        "ram": ram,
        "disk_size": disk_size,
    }
    if description is not None:
        data["description"] = description

    entity = base_client.add_entity(client, ENTITY_COLLECTION, data)
    show_data(entity)


@click.command("update", help=f"Update {ENTITY}")
@click.pass_context
@click.argument(
    "uuid",
    type=str,
    required=True,
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
    "--cpu",
    type=click.IntRange(1, 128),
    required=False,
    help="Number of CPU cores per node",
)
@click.option(
    "--ram",
    type=click.IntRange(512, 1024**3),
    required=False,
    help="RAM per node in MB",
)
@click.option(
    "--disk-size",
    type=click.IntRange(8, 1024**3),
    required=False,
    help="Disk size per node in GB, shrink is not supported",
)
def update_cmd(
    ctx: click.Context,
    uuid: str,
    name: str | None,
    description: str | None,
    cpu: int | None,
    ram: int | None,
    disk_size: int | None,
) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if cpu is not None:
        data["cpu"] = cpu
    if ram is not None:
        data["ram"] = ram
    if disk_size is not None:
        data["disk_size"] = disk_size

    entity = base_client.update_entity(client, ENTITY_COLLECTION, uuid, data)
    show_data(entity)


instances_group.add_command(add_cmd, aliases=["a"])
instances_group.add_command(update_cmd, aliases=["u"])
