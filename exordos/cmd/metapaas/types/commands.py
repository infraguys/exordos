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

ENTITY = "type"
ENTITY_COLLECTION = c.METAPAAS_TYPE_COLLECTION
FIELDS_MAP = {
    "UUID": "uuid",
    "Project": "project_id",
    "Name": "name",
    "Element": "element_name",
    "Package": "package",
    "Version": "version",
    "Index URL": "index_url",
    "Status": "status",
}


types_group = create_entity_group(ENTITY, ENTITY_COLLECTION, FIELDS_MAP)


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
    help=f"UUID of the project in which to register the {ENTITY}",
)
@click.option(
    "-n",
    "--name",
    type=str,
    required=True,
    help=f"Name of the {ENTITY}, the PaaS slug, for example: s3",
)
@click.option(
    "--description",
    type=str,
    default=None,
    help=f"Description of the {ENTITY}",
)
@click.option(
    "-e",
    "--element-name",
    type=str,
    required=True,
    help="Name of the element the PaaS is exposed under, for example: s3aas",
)
@click.option(
    "--package",
    type=str,
    required=True,
    help="Pip distribution name, a wheel/sdist URL or an urn:artifacts:<uuid>",
)
@click.option(
    "-v",
    "--version",
    type=str,
    default=None,
    help="Version pin of the package",
)
@click.option(
    "--index-url",
    type=str,
    default=None,
    help="Pip index URL to install the package from",
)
def add_cmd(
    ctx: click.Context,
    uuid: sys_uuid.UUID | None,
    project_id: sys_uuid.UUID,
    name: str,
    description: str | None,
    element_name: str,
    package: str,
    version: str | None,
    index_url: str | None,
) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)
    if uuid is None:
        uuid = sys_uuid.uuid4()
    data = {
        "uuid": str(uuid),
        "project_id": str(project_id),
        "name": name,
        "element_name": element_name,
        "package": package,
    }
    if description is not None:
        data["description"] = description
    if version is not None:
        data["version"] = version
    if index_url is not None:
        data["index_url"] = index_url

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
    "--description",
    type=str,
    required=False,
    help=f"Description of the {ENTITY}",
)
@click.option(
    "--package",
    type=str,
    required=False,
    help="Pip distribution name, a wheel/sdist URL or an urn:artifacts:<uuid>",
)
@click.option(
    "-v",
    "--version",
    type=str,
    required=False,
    help="Version pin of the package",
)
@click.option(
    "--index-url",
    type=str,
    required=False,
    help="Pip index URL to install the package from",
)
def update_cmd(
    ctx: click.Context,
    uuid: str,
    description: str | None,
    package: str | None,
    version: str | None,
    index_url: str | None,
) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)
    data = {}
    if description is not None:
        data["description"] = description
    if package is not None:
        data["package"] = package
    if version is not None:
        data["version"] = version
    if index_url is not None:
        data["index_url"] = index_url

    entity = base_client.update_entity(client, ENTITY_COLLECTION, uuid, data)
    show_data(entity)


types_group.add_command(add_cmd, aliases=["a"])
types_group.add_command(update_cmd, aliases=["u"])
