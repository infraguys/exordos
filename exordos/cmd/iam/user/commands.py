#    Copyright 2025 Genesis Corporation.
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

ENTITY = "user"
ENTITY_COLLECTION = c.USER_COLLECTION
FIELDS_MAP = {
    "UUID": "uuid",
    "Username": "username",
    "First Name": lambda x: x.get("first_name") or "",
    "Last Name": lambda x: x.get("last_name") or "",
    "Email": "email",
    "Status": "status",
}

users_group = create_entity_group(ENTITY, ENTITY_COLLECTION, FIELDS_MAP)


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
    "-n",
    "--name",
    type=str,
    default=f"test_{ENTITY}",
    help=f"Name of the {ENTITY}",
)
@click.option(
    "-p",
    "--password",
    type=str,
    required=False,
    help=f"Password of the {ENTITY}. If not provided, will be asked interactively",
    hide_input=True,
)
@click.option(
    "-D",
    "--description",
    type=str,
    default="",
    help=f"Description of the {ENTITY}",
)
@click.option(
    "--first_name",
    type=str,
    required=False,
)
@click.option(
    "--last_name",
    type=str,
    required=False,
)
@click.option(
    "--surname",
    type=str,
    required=False,
)
@click.option(
    "--phone",
    type=str,
    required=False,
)
@click.option(
    "--email",
    type=str,
    required=True,
)
@click.option(
    "--email_verified",
    type=bool,
    is_flag=True,
    default=False,
)
@click.option(
    "--confirmation_code",
    type=str,
    required=False,
)
@click.option(
    "--confirmation_code_made_at",
    type=str,
    required=False,
)
@click.option(
    "--otp_secret",
    type=str,
    required=False,
)
@click.option(
    "--otp_enabled",
    type=bool,
    is_flag=True,
    default=False,
)
def add_cmd(
    ctx: click.Context,
    uuid: sys_uuid.UUID | None,
    name: str,
    password: str | None,
    description: str,
    first_name: str | None,
    last_name: str | None,
    surname: str | None,
    phone: str | None,
    email: str | None,
    email_verified: bool,
    confirmation_code: str | None,
    confirmation_code_made_at: str | None,
    otp_secret: str | None,
    otp_enabled: bool,
) -> None:
    import questionary

    client = base_client.get_user_api_client(ctx.obj.auth_data)
    if uuid is None:
        uuid = sys_uuid.uuid4()

    data = {
        "uuid": str(uuid),
        "username": name,
        "password": password
        or questionary.password(f"Enter password for {ENTITY} {name}:").ask(),
        "description": description,
        "email": email,
        "email_verified": email_verified,
        "otp_enabled": otp_enabled,
    }

    if first_name is not None:
        data["first_name"] = first_name
    if last_name is not None:
        data["last_name"] = last_name
    if surname is not None:
        data["surname"] = surname
    if phone is not None:
        data["phone"] = phone
    if confirmation_code is not None:
        data["confirmation_code"] = confirmation_code
    if confirmation_code_made_at is not None:
        data["confirmation_code_made_at"] = confirmation_code_made_at
    if otp_secret is not None:
        data["otp_secret"] = otp_secret

    entity = base_client.add_entity(client, ENTITY_COLLECTION, data)
    show_data(entity)


@users_group.command("reset_password", help=f"Reset password of the {ENTITY}")
@click.pass_context
@click.argument(
    "user",
    type=click.UUID,
    required=True,
    help=f"{ENTITY} UUID",
)
@click.option(
    "-c",
    "--code",
    type=str,
    required=False,
    help=f"Verification code for the {ENTITY}",
)
@click.option(
    "-n",
    "--new-password",
    type=str,
    required=False,
    help=f"New password of the {ENTITY}. If not provided, will be asked interactively",
    hide_input=True,
)
def reset_password_cmd(
    ctx: click.Context,
    user: sys_uuid.UUID,
    code: str | None,
    new_password: str | None,
) -> None:
    import questionary

    client = base_client.get_user_api_client(ctx.obj.auth_data)

    new_password = (
        new_password
        or questionary.password(f"Enter new password for {ENTITY} {user}:").ask()
    )
    if new_password is None:
        click.echo("Password not provided")
        return
    data = {
        "new_password": new_password,
    }

    if code is not None:
        data["code"] = code

    base_client.action_entity(client, ENTITY_COLLECTION, "reset_password", user, **data)
    click.echo(f"Password reset for {ENTITY} {user}")


@users_group.command("change_password", help=f"Change password of the {ENTITY}")
@click.pass_context
@click.argument(
    "user",
    type=click.UUID,
    required=True,
    help=f"{ENTITY} UUID or username",
)
@click.option(
    "-o",
    "--old-password",
    type=str,
    required=True,
    help=f"Old password of the {ENTITY}",
)
@click.option(
    "-n",
    "--new-password",
    type=str,
    required=False,
    help=f"New password of the {ENTITY}. If not provided, will be asked interactively",
)
def change_password_cmd(
    ctx: click.Context,
    uuid: sys_uuid.UUID,
    old_password: str,
    new_password: str | None,
) -> None:
    import questionary

    client = base_client.get_user_api_client(ctx.obj.auth_data)

    data = {
        "old_password": old_password,
        "new_password": new_password
        or questionary.password(f"Enter new_password for {ENTITY} {uuid}:").ask(),
    }

    base_client.action_entity(
        client, ENTITY_COLLECTION, "change_password", uuid, **data
    )
    click.echo(f"Password changed for {ENTITY} {uuid}")


@users_group.command("info", help=f"Show detailed information about the {ENTITY}")
@click.pass_context
@click.argument(
    "user",
    type=str,
    required=True,
    help=f"{ENTITY} UUID or username",
)
@click.option(
    "--output",
    "-o",
    default=c.DEFAULT_TABLE_FORMAT,
    type=click.Choice(c.TABLE_FORMATS, case_sensitive=False),
    help="the output format, defaults to table",
)
def info_cmd(ctx: click.Context, user: str, output: str) -> None:
    user_fields = ["uuid", "username", "email", "first_name", "last_name", "status"]
    project_fields = ["uuid", "name", "organization"]
    role_binding_fields = ["uuid", "role", "project", "user"]
    organization_fields = ["uuid", "name"]
    org_member_fields = ["uuid", "user", "organization", "role"]

    client = base_client.get_user_api_client(ctx.obj.auth_data)
    user_data = base_client.get_entity(client, ENTITY_COLLECTION, user)
    user_uuid = user_data["uuid"]
    role_bindings = base_client.list_entities(
        client, c.ROLE_BINDING_COLLECTION, user=user_uuid
    )

    organizations = base_client.list_entities(client, c.ORGANIZATION_COLLECTION)
    org_members = []
    user_organizations = []

    for organization in organizations:
        members = base_client.list_entities(
            client,
            c.ORGANIZATION_MEMBER_COLLECTION.format(
                organization_uuid=organization["uuid"]
            ),
            user=user_uuid,
        )
        if members:
            user_organizations.append(organization)
            org_members.extend(members)

    projects = []
    for organization in user_organizations:
        projects.extend(
            base_client.list_entities(
                client,
                c.PROJECT_COLLECTION,
                organization=organization["uuid"],
            )
        )
    projects = [
        {k: v for k, v in project.items() if k in project_fields}
        for project in projects
    ]
    role_bindings = [
        {k: v for k, v in role_binding.items() if k in role_binding_fields}
        for role_binding in role_bindings
    ]
    org_members = [
        {k: v for k, v in org_member.items() if k in org_member_fields}
        for org_member in org_members
    ]
    user_organizations = [
        {k: v for k, v in organization.items() if k in organization_fields}
        for organization in user_organizations
    ]
    roles_uuids = [
        role_binding["role"].split("/")[-1] for role_binding in role_bindings
    ]
    roles = base_client.list_entities(client, c.ROLE_COLLECTION)
    roles = [role for role in roles if role["uuid"] in roles_uuids]

    show_data(
        {
            "user": {k: v for k, v in user_data.items() if k in user_fields},
            "orgs": user_organizations,
            "projects": projects,
            "role_bindings": role_bindings,
            "roles": roles,
            "org_members": org_members,
        },
        output,
    )


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
    default=None,
    help=f"Username of the {ENTITY}",
)
@click.option(
    "-D",
    "--description",
    type=str,
    default=None,
    help=f"Description of the {ENTITY}",
)
@click.option(
    "--first-name",
    type=str,
    default=None,
)
@click.option(
    "--last-name",
    type=str,
    default=None,
)
@click.option(
    "--surname",
    type=str,
    default=None,
)
@click.option(
    "--phone",
    type=str,
    default=None,
)
@click.option(
    "--email",
    type=str,
    default=None,
)
def update_cmd(
    ctx: click.Context,
    uuid: str,
    name: str | None,
    description: str | None,
    first_name: str | None,
    last_name: str | None,
    surname: str | None,
    phone: str | None,
    email: str | None,
) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)
    data = {}
    if name is not None:
        data["username"] = name
    if description is not None:
        data["description"] = description
    if first_name is not None:
        data["first_name"] = first_name
    if last_name is not None:
        data["last_name"] = last_name
    if surname is not None:
        data["surname"] = surname
    if phone is not None:
        data["phone"] = phone
    if email is not None:
        data["email"] = email

    if not data:
        click.echo("No data to update")
        return

    entity = base_client.update_entity(client, ENTITY_COLLECTION, uuid, data)
    show_data(entity)


@users_group.command("confirm_email", help=f"Confirm email of the {ENTITY}")
@click.pass_context
@click.argument(
    "user",
    type=click.UUID,
    required=True,
    help=f"{ENTITY} UUID",
)
@click.option(
    "-f",
    "--force",
    show_default=True,
    is_flag=True,
)
def confirm_email(
    ctx: click.Context,
    user: sys_uuid.UUID,
    force: bool,
) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)

    data = {}

    base_client.action_entity(
        client,
        ENTITY_COLLECTION,
        "force_confirm_email" if force else "confirm_email",
        user,
        **data,
    )
    click.echo(f"Email {'force' if force else ''} confirmed for {ENTITY} {user}")


@users_group.command(
    "resend_email_confirmation", help=f"Resend email confirmation for the {ENTITY}"
)
@click.pass_context
@click.argument(
    "user",
    type=click.UUID,
    required=True,
    help=f"{ENTITY} UUID",
)
def resend_email_confirmation(
    ctx: click.Context,
    user: sys_uuid.UUID,
) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)

    data = {}

    base_client.action_entity(
        client,
        ENTITY_COLLECTION,
        "resend_email_confirmation",
        user,
        **data,
    )
    click.echo(f"Email confirmation resent for {ENTITY} {user}")


users_group.add_command(add_cmd, aliases=["a"])
users_group.add_command(update_cmd, aliases=["u"])
