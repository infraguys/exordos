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

ENTITY = "policy attachment"
ENTITY_COLLECTION = c.S3_USER_POLICY_COLLECTION
FIELDS_MAP = {
    "UUID": "uuid",
    "Project": "project_id",
    "Instance": "instance",
    "User": "user",
    "Policy": "policy",
}


user_policies_group = create_entity_group(
    ENTITY,
    ENTITY_COLLECTION,
    FIELDS_MAP,
    group_name="user-policies",
    parents=["instance", "user"],
)


@click.command("add", help="Attach a policy to a user")
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
    help="UUID of the instance the user and the policy belong to",
)
@click.option(
    "--user-uuid",
    type=str,
    required=True,
    help="UUID of the user to attach the policy to",
)
@click.option(
    "--policy",
    type=str,
    required=True,
    help="UUID or name of the policy to attach",
)
def add_cmd(
    ctx: click.Context,
    uuid: sys_uuid.UUID | None,
    project_id: sys_uuid.UUID,
    instance_uuid: str,
    user_uuid: str,
    policy: str,
) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)
    if uuid is None:
        uuid = sys_uuid.uuid4()
    policy_uuid = base_client.get_entity(
        client, c.S3_POLICY_COLLECTION.format(instance_uuid=instance_uuid), policy
    )["uuid"]
    instance_url = f"{c.S3_INSTANCE_COLLECTION}{instance_uuid}"
    data = {
        "uuid": str(uuid),
        "project_id": str(project_id),
        "instance": instance_url,
        "user": f"{instance_url}/users/{user_uuid}",
        "policy": f"{instance_url}/policies/{policy_uuid}",
    }

    entity = base_client.add_entity(
        client,
        ENTITY_COLLECTION.format(instance_uuid=instance_uuid, user_uuid=user_uuid),
        data,
    )
    show_data(entity)


user_policies_group.add_command(add_cmd, aliases=["a"])
