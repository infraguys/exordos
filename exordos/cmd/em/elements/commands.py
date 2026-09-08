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

import os
import pathlib
import subprocess
import tempfile
import time
import typing as tp
import uuid as sys_uuid

from packaging import version as packaging_version
from rich.prompt import Confirm
from rich.text import Text
import rich_click as click

from exordos import utils
from exordos.clients import base_client
from exordos.cmd.base import create_entity_group
from exordos.common import compute
from exordos.common import ssh
from exordos.common import version as version_lib
from exordos.common.table import get_table
from exordos.common.table import print_table
from exordos.common.table import show_data
import exordos.constants as c
from exordos.repo import utils as repo_utils

if tp.TYPE_CHECKING:
    from exordos.clients.base import CollectionBaseClient


ENTITY = "element"
ENTITY_COLLECTION = c.ELEMENT_COLLECTION
DEFAULT_UPLOAD_REPO_NAME = "exordos-upload-repo"
DEFAULT_PRIORITY = 4096
DEFAULT_TIMEOUT = 600.0
FIELDS_MAP = {
    "UUID": "uuid",
    "Name": "name",
    "Version": "version",
    "Manifest": lambda x: (x.get("manifest") or "").split("/")[-1],
    "Status": "status",
}


ee_group = create_entity_group(
    ENTITY,
    ENTITY_COLLECTION,
    FIELDS_MAP,
    "ee",
    add_show_command=False,
    add_delete_command=False,
)


@click.command("show", help="Show element general information")
@click.argument("name")
@click.pass_context
def show_cmd(ctx: click.Context, name: str) -> None:
    """Show element general information"""
    client = base_client.get_user_api_client(ctx.obj.auth_data)
    data = base_client.get_entity(client, ENTITY_COLLECTION, name)
    show_data(data)

    resources = base_client.list_entities(
        client, f"{c.ELEMENT_COLLECTION}{data['uuid']}/resources/"
    )
    table = get_table("UUID", "Name", "Kind", "Full hash", "Status")
    for resource in resources:
        table.add_row(
            resource["uuid"],
            resource["name"],
            resource["kind"],
            resource["full_hash"],
            resource["status"],
        )
    print_table(table, msg="Resources:")

    imports = base_client.list_entities(
        client, f"{c.ELEMENT_COLLECTION}{data['uuid']}/imports/"
    )
    table = get_table("UUID", "Name", "Kind", "Link")
    for resource in imports:
        table.add_row(
            resource["uuid"],
            resource["name"],
            resource["kind"],
            resource["link"],
        )
    print_table(table, msg="Imports:")

    exports = base_client.list_entities(
        client, f"{c.ELEMENT_COLLECTION}{data['uuid']}/exports/"
    )
    table = get_table("UUID", "Name", "Kind", "Link")
    for resource in exports:
        table.add_row(
            resource["uuid"],
            resource["name"],
            resource["kind"],
            resource["link"],
        )
    print_table(table, msg="Exports:")


@ee_group.command("ips", help="Show element ips")
@click.argument("name")
@click.pass_context
def show_element_ips(ctx: click.Context, name: str) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)

    data = base_client.get_entity(client, ENTITY_COLLECTION, name)

    resources = base_client.list_entities(
        client,
        f"{c.ELEMENT_COLLECTION}{data['uuid']}/resources/",
        kind="em_core_compute_nodes",
    )
    if len(resources) == 0:
        raise click.ClickException(f"No nodes found for element {name}")
    elif len(resources) > 1:
        for resource in resources:
            node = client.get(c.NODE_COLLECTION, uuid=resource["uuid"])
            click.echo(
                f"Name: {node['name']}, IP: {node['default_network'].get('ipv4', None)}"
            )
    else:
        node = client.get(c.NODE_COLLECTION, uuid=resources[0]["uuid"])
        click.echo(node["default_network"].get("ipv4", None))


def _get_sort_key(
    element: dict[str, tp.Any], repo_priorities: dict[str, int]
) -> tuple[int, packaging_version.Version]:
    """Get sort key for element: (repository_priority, version).

    Args:
        element: Element dictionary containing version and repository reference.
        repo_priorities: Dictionary mapping repository UUID to priority value.

    Returns:
        Tuple of (repository_priority, version) for sorting.
        Higher values indicate higher priority.
    """
    version_obj = packaging_version.parse(element["version"])

    repo_priority = 0
    repository_ref = element.get("repository")
    if repository_ref:
        try:
            repo_uuid = repository_ref.rstrip("/").split("/")[-1]
            if utils.is_valid_uuid(repo_uuid):
                repo_priority = repo_priorities.get(repo_uuid, 0)
        except Exception:
            pass

    return (repo_priority, version_obj)


def _select_element_by_name(
    client: "CollectionBaseClient",
    name: str,
    version_filter: str | None,
    exclude_uuid: str | None = None,
) -> dict[str, tp.Any]:
    """Select the best element by name, sorting by (repository_priority, version).

    Filters out development versions unless version_filter is specified.
    Sorts elements by repository priority (higher is better) and version
    (higher is better), then returns the highest priority element.

    Args:
        client: API client for making requests.
        name: Element name to search for.
        version_filter: Optional version string to filter by.
            If None, only stable versions are considered.

    Returns:
        Dictionary representing the selected element.

    Raises:
        click.ClickException: If no elements found or no stable versions available.
    """
    elements = base_client.list_entities(
        client, c.REPOSITORY_ELEMENT_COLLECTION, name=name
    )

    if exclude_uuid:
        elements = [e for e in elements if e["uuid"] != exclude_uuid]

    if not elements:
        raise click.ClickException(f"No elements found with name '{name}'")

    # Fetch all repositories once to build priority cache
    repo_priorities: dict[str, int] = {}
    try:
        repositories = base_client.list_entities(client, c.REPOSITORY_COLLECTION)
        for repo in repositories:
            repo_priorities[repo["uuid"]] = repo.get("priority", 0)
    except Exception:
        pass

    # Filter out development versions unless version is explicitly provided
    if version_filter is None:
        elements = [e for e in elements if version_lib.is_stable_version(e["version"])]

    if not elements:
        raise click.ClickException(
            f"No stable versions found for element '{name}'. "
            "Use --version to install a development version."
        )

    # Filter by version if specified
    if version_filter:
        elements = [e for e in elements if e["version"] == version_filter]
        if not elements:
            raise click.ClickException(
                f"No elements found with name '{name}' and version '{version_filter}'"
            )

    # Sort by (repository_priority, version) - higher is better
    elements.sort(key=lambda e: _get_sort_key(e, repo_priorities), reverse=True)

    return elements[0]


def _select_current_element_by_name(
    client: "CollectionBaseClient", name: str
) -> dict[str, tp.Any]:
    """Select current installed element by name.

    The canonical signal that an element is the "current" one is
    ``installation_state == "INSTALLED"``. This is what the server uses to
    decide whether ``uninstall``/``upgrade`` are allowed, so selecting by it
    keeps the CLI in sync with the server even during an in-flight update,
    where the freshly-installed element is ``INSTALLED`` but its ``status`` is
    still ``NEW``/``IN_PROGRESS`` and the stale element being replaced is
    ``UNINSTALLED`` but still ``ACTIVE``.

    Falls back to ``status in (ACTIVE, IN_PROGRESS)`` when no element reports
    ``installation_state`` (e.g. an older server that does not expose the
    field), preserving the previous behavior.

    Args:
        client: API client for making requests.
        name: Element name to search for.

    Returns:
        Dictionary representing the current element.

    Raises:
        click.ClickException: If no installed element is found, or if several
            elements are installed at once (ambiguous, user must give a UUID).
    """
    elements = base_client.list_entities(
        client, c.REPOSITORY_ELEMENT_COLLECTION, name=name
    )

    installed = [e for e in elements if e.get("installation_state") == "INSTALLED"]
    if len(installed) > 1:
        raise click.ClickException(
            f"Multiple installed elements found with name '{name}'. "
            "Please specify the UUID of the element to update."
        )
    if installed:
        return installed[0]

    # Fallback for servers that do not expose installation_state: pick by
    # status, matching the historical behavior.
    active_elements = [
        e for e in elements if e.get("status") in ("ACTIVE", "IN_PROGRESS")
    ]

    if not active_elements:
        raise click.ClickException(
            f"No installed element found with name '{name}'. "
            "Use install command to install the element first."
        )

    if len(active_elements) > 1:
        raise click.ClickException(
            f"Multiple installed elements found with name '{name}'. "
            "Please specify the UUID of the element to update."
        )

    return active_elements[0]


@click.command("install", help="Install element")
@click.option(
    "-v",
    "--version",
    type=str,
    required=False,
    help="version of the element",
)
@click.option(
    "-p",
    "--project-id",
    type=click.UUID,
    default=sys_uuid.UUID(int=0),
    help="Project UUID, required only if the upload repository doesn't exist yet",
)
@click.option(
    "--timeout",
    type=float,
    default=DEFAULT_TIMEOUT,
    show_default=True,
    help="Seconds to wait for repository upload and element sync to complete",
)
@click.argument("uuid_or_name_or_path", required=False)
@click.pass_context
def install_cmd(
    ctx: click.Context,
    version: str | None,
    project_id: sys_uuid.UUID,
    timeout: float,
    uuid_or_name_or_path: str | None,
) -> None:
    """Install element from repository API by UUID, name, or manifest path"""
    import questionary

    if not uuid_or_name_or_path:
        all_elements = base_client.list_entities(
            base_client.get_user_api_client(ctx.obj.auth_data),
            c.REPOSITORY_ELEMENT_COLLECTION,
        )
        element_names = sorted(set(e["name"] for e in all_elements))
        uuid_or_name_or_path = questionary.select(
            "Select element to install",
            choices=element_names,
        ).ask()
        if not uuid_or_name_or_path:
            click.echo("No element selected, aborting")
            return

    client = base_client.get_user_api_client(ctx.obj.auth_data)

    if os.path.isfile(uuid_or_name_or_path):
        manifest_path = pathlib.Path(uuid_or_name_or_path)
        manifest_data = utils.load_yaml(str(manifest_path))
        name = manifest_data.get("name")
        e_version = manifest_data.get("version")

        driver_spec = {"kind": "database"}
        repository = repo_utils.ensure_repository(
            client,
            DEFAULT_UPLOAD_REPO_NAME,
            driver_spec,
            project_id,
            DEFAULT_PRIORITY,
            sync_mode="copy",
        )

        repo_utils.do_upload(client, DEFAULT_UPLOAD_REPO_NAME, manifest_path)

        click.echo(f"Waiting for {name} ({e_version}) to become AVAILABLE...")
        repo_element = repo_utils.wait_for_repo_element(
            client, repository["uuid"], name, e_version, "AVAILABLE", timeout
        )

        base_client.action_entity(
            client, c.REPOSITORY_ELEMENT_COLLECTION, "install", repo_element["uuid"]
        )

        installed_name = f"{name} ({e_version})"
        click.echo(
            f"Element {click.style(installed_name, fg='green')} was installed successfully"
        )
        return

    if utils.is_valid_uuid(uuid_or_name_or_path):
        element = client.get(c.REPOSITORY_ELEMENT_COLLECTION, uuid=uuid_or_name_or_path)
    else:
        element = _select_element_by_name(client, uuid_or_name_or_path, version)

    element_uuid = element["uuid"]
    base_client.action_entity(
        client, c.REPOSITORY_ELEMENT_COLLECTION, "install", element_uuid
    )

    installed_name = f"{element['name']} ({element['version']})"
    click.echo(
        f"Element {click.style(installed_name, fg='green')} was installed successfully"
    )


def _update_element_from_manifest(
    client: "CollectionBaseClient",
    manifest_path: pathlib.Path,
    y: bool,
    project_id: sys_uuid.UUID,
    timeout: float,
) -> None:
    """Update a single element from a local manifest file."""
    import questionary

    manifest_data = utils.load_yaml(str(manifest_path))
    name = manifest_data.get("name")
    e_version = manifest_data.get("version")

    current_element = _select_current_element_by_name(client, name)

    if not (
        y
        or questionary.confirm(
            f"Update {current_element['name']} "
            f"({current_element['version']} -> {e_version})?"
        ).ask()
    ):
        return

    driver_spec = {"kind": "database"}
    repository = repo_utils.ensure_repository(
        client,
        DEFAULT_UPLOAD_REPO_NAME,
        driver_spec,
        project_id,
        DEFAULT_PRIORITY,
        sync_mode="copy",
    )

    repo_utils.do_upload(client, DEFAULT_UPLOAD_REPO_NAME, manifest_path)

    click.echo(f"Waiting for {name} ({e_version}) to become AVAILABLE...")
    target_element = repo_utils.wait_for_repo_element(
        client, repository["uuid"], name, e_version, "AVAILABLE", timeout
    )

    base_client.action_entity(
        client,
        c.REPOSITORY_ELEMENT_COLLECTION,
        "upgrade",
        current_element["uuid"],
        target=target_element["uuid"],
    )

    installed_name = (
        f"{current_element['name']} ({current_element['version']} -> {e_version})"
    )
    click.echo(
        f"Element {click.style(installed_name, fg='green')} was updated successfully"
    )


def _update_element_by_uuid_or_name(
    client: "CollectionBaseClient",
    uuid_or_name: str,
    version: str | None,
    y: bool,
) -> None:
    """Update a single element selected by UUID or name."""
    import questionary

    if utils.is_valid_uuid(uuid_or_name):
        current_element = client.get(c.REPOSITORY_ELEMENT_COLLECTION, uuid=uuid_or_name)
    else:
        current_element = _select_current_element_by_name(client, uuid_or_name)

    target_element = _select_element_by_name(
        client, current_element["name"], version, exclude_uuid=current_element["uuid"]
    )

    if not (
        y
        or questionary.confirm(
            f"Update {current_element['name']} "
            f"({current_element['version']} -> {target_element['version']})?"
        ).ask()
    ):
        return

    base_client.action_entity(
        client,
        c.REPOSITORY_ELEMENT_COLLECTION,
        "upgrade",
        current_element["uuid"],
        target=target_element["uuid"],
    )

    installed_name = (
        f"{current_element['name']} ({current_element['version']}"
        f" -> {target_element['version']})"
    )
    click.echo(
        f"Element {click.style(installed_name, fg='green')} was updated successfully"
    )


@click.command("update", help="Update one or more elements")
@click.option(
    "-v",
    "--version",
    type=str,
    required=False,
    help="version of the element",
)
@click.option(
    "--yes", "-y", "y", help="Automatically answer yes for all questions", is_flag=True
)
@click.option(
    "-p",
    "--project-id",
    type=click.UUID,
    default=sys_uuid.UUID(int=0),
    help="Project UUID, required only if the upload repository doesn't exist yet",
)
@click.option(
    "--timeout",
    type=float,
    default=DEFAULT_TIMEOUT,
    show_default=True,
    help="Seconds to wait for repository upload and element sync to complete",
)
@click.argument("uuid_or_name_or_path", nargs=-1)
@click.pass_context
def update_cmd(
    ctx: click.Context,
    version: str | None,
    y: bool,
    project_id: sys_uuid.UUID,
    timeout: float,
    uuid_or_name_or_path: tuple[str, ...],
) -> None:
    """Update elements from repository API by UUID, name, or manifest path"""
    import questionary

    client = base_client.get_user_api_client(ctx.obj.auth_data)

    targets = list(uuid_or_name_or_path)
    if not targets:
        all_elements = base_client.list_entities(
            client,
            c.REPOSITORY_ELEMENT_COLLECTION,
        )
        element_names = sorted(set(e["name"] for e in all_elements))
        targets = questionary.checkbox(
            "Select elements to update",
            choices=element_names,
        ).ask()
        if not targets:
            click.echo("No element selected, aborting")
            return

    for target in targets:
        if os.path.isfile(target):
            _update_element_from_manifest(
                client, pathlib.Path(target), y, project_id, timeout
            )
        else:
            _update_element_by_uuid_or_name(client, target, version, y)


@click.command("uninstall", help="Uninstall elements by UUID or name")
@click.argument("uuid_or_name", type=str, nargs=-1, required=True)
@click.option(
    "--yes", "-y", "y", help="Automatically answer yes for all questions", is_flag=True
)
@click.pass_context
def uninstall_cmd(ctx: click.Context, uuid_or_name: tuple[str, ...], y: bool) -> None:
    """Uninstall elements by UUID or name"""
    import questionary

    client = base_client.get_user_api_client(ctx.obj.auth_data)

    for element_ref in uuid_or_name:
        if not (y or questionary.confirm(f"Delete {ENTITY} {element_ref}?").ask()):
            continue

        if utils.is_valid_uuid(element_ref):
            element = client.get(c.REPOSITORY_ELEMENT_COLLECTION, uuid=element_ref)
            element_uuid = element["uuid"]
        else:
            element = _select_current_element_by_name(client, element_ref)
            element_uuid = element["uuid"]

        base_client.action_entity(
            client, c.REPOSITORY_ELEMENT_COLLECTION, "uninstall", element_uuid
        )

        click.echo(
            f"Element {click.style(element['name'], fg='green')} was uninstalled successfully"
        )


def edit_data(data: str, editor: str = "nano") -> tp.Tuple[str, dict]:
    tf_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="a+", delete=False) as tf:
            tf.write(data)
            tf.flush()
            tf_path = tf.name
            subprocess.call([editor, tf_path])
            tf.seek(0)
            new_data = tf.read()
    finally:
        if tf_path and os.path.exists(tf_path):
            os.remove(tf_path)
    json_data = utils.load_yaml(new_data)
    return new_data, json_data


@ee_group.command(help="Edit manifest", context_settings={"show_default": True})
@click.argument("uuid_name")
@click.option(
    "-e",
    "--editor",
    default="nano",
    type=click.Choice(["nano", "vim"], case_sensitive=False),
    help="Editor (nano or vim)",
)
@click.pass_context
def edit(ctx: click.Context, uuid_name: str, editor: str) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)
    element = base_client.get_entity(client, c.ELEMENT_COLLECTION, uuid_name)
    manifest_ref = element.get("manifest", "")
    if not manifest_ref:
        raise click.ClickException(
            f"Element {element['name']} has no manifest reference"
        )
    manifest_uuid = manifest_ref.rstrip("/").split("/")[-1]
    repo_element = base_client.get_entity(
        client, c.REPOSITORY_ELEMENT_COLLECTION, manifest_uuid
    )
    manifest = repo_element.get("manifest", {})
    tf_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="a+", delete=False) as tf:
            utils.dump_yaml(manifest, tf)
            tf.flush()
            tf_path = tf.name
            subprocess.call([editor, tf_path])
            tf.seek(0)
            updated_manifest = utils.load_yaml(tf_path)
        base_client.action_entity(
            client,
            c.REPOSITORY_ELEMENT_COLLECTION,
            "edit",
            repo_element["uuid"],
            manifest=updated_manifest,
        )
    finally:
        if tf_path and os.path.exists(tf_path):
            os.remove(tf_path)
    click.echo(
        f"Element {click.style(element['name'], fg='green')} was successfully edited"
    )


@ee_group.command(
    "define", help="Add resource to manifest", context_settings={"show_default": True}
)
@click.argument("uuid_name")
@click.option(
    "-e",
    "--editor",
    default="nano",
    type=click.Choice(["nano", "vim"], case_sensitive=False),
    help="Editor (nano or vim)",
)
@click.option(
    "--resource-type",
    type=str,
    required=False,
    help="Type of resource to define",
)
@click.option(
    "--resource-name",
    type=str,
    required=False,
    help="Name of resource to define",
)
@click.pass_context
def define(
    ctx: click.Context,
    uuid_name: str,
    editor: str,
    resource_type: str,
    resource_name: str,
) -> None:
    # Get Openapi schema
    import questionary

    client = base_client.get_user_api_client(ctx.obj.auth_data)
    schema = client.filter(f"{c.MANIFEST_COLLECTION}schema/")

    # Get resource schema
    resources = schema["properties"]["resources"]["properties"]
    if not resource_type:
        resource_type = questionary.select(
            "Select resource to define",
            choices=resources.keys(),
        ).ask()
    if not resource_type:
        click.echo("No resource type selected, aborting")
        return
    if resource_type not in resources:
        click.echo(f"Resource type {resource_type} not found")
        return
    resource_ref = resources[resource_type]["additionalProperties"]["$ref"].split("/")[
        -1
    ]
    resource = schema["components"]["schemas"][resource_ref]
    resource_def = resource["properties"]
    resource_json = {
        k: v.get("example", "")
        for k, v in resource_def.items()
        if not v.get("readOnly", False)
    }
    element = base_client.get_entity(client, c.ELEMENT_COLLECTION, uuid_name)
    manifest_ref = element.get("manifest", "")
    if not manifest_ref:
        raise click.ClickException(
            f"Element {element['name']} has no manifest reference"
        )
    manifest_uuid = manifest_ref.rstrip("/").split("/")[-1]
    repo_element = base_client.get_entity(
        client, c.REPOSITORY_ELEMENT_COLLECTION, manifest_uuid
    )
    manifest = repo_element.get("manifest", {})
    if "resources" not in manifest:
        manifest["resources"] = {}
    if resource_type not in manifest["resources"]:
        manifest["resources"][resource_type] = {}
    if not resource_name:
        default_resource_name = f"{manifest.get('name', element['name'])}_{resource_ref.split('_')[0].lower()}"
        resource_name = questionary.text(
            "Enter resource name", default=default_resource_name
        ).ask()
    if not resource_name:
        click.echo("No resource name selected, aborting")
        return
    if resource_name in manifest["resources"][resource_type]:
        click.echo(f"Resource {resource_name} with type {resource_type} already exists")
        return
    if "name" in resource_json.keys():
        resource_json["name"] = resource_name
    if "description" in resource_json.keys():
        resource_json["description"] = ""
    manifest["resources"][resource_type][resource_name] = resource_json

    # Edit manifest
    tf_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="a+", delete=False) as tf:
            utils.dump_yaml(manifest, tf)
            tf.flush()
            tf.seek(0)

            line_num = 0
            for line_num, line in enumerate(tf, 1):
                if resource_name in line:
                    break

            tf_path = tf.name
            subprocess.call([editor, f"+{line_num}", tf_path])
            tf.seek(0)
            updated_manifest = utils.load_yaml(tf_path)
        base_client.action_entity(
            client,
            c.REPOSITORY_ELEMENT_COLLECTION,
            "edit",
            repo_element["uuid"],
            manifest=updated_manifest,
        )
    finally:
        if tf_path and os.path.exists(tf_path):
            os.remove(tf_path)

    click.echo(
        f"Element {click.style(element['name'], fg='green')} was successfully edited"
    )


@ee_group.command("clear", help="Uninstall all elements, except base")
@click.option(
    "--y", "-y", help="Automatically answer yes for all questions", is_flag=True
)
@click.pass_context
def clear(ctx: click.Context, y: bool) -> bool:  # pragma: no cover
    client = base_client.get_user_api_client(ctx.obj.auth_data)

    if not (y or click.confirm("Do you want to uninstall all non-base elements?")):
        return False

    def get_installed_elements():
        repo_elements = base_client.list_entities(
            client, c.REPOSITORY_ELEMENT_COLLECTION
        )
        return [
            e
            for e in repo_elements
            if e.get("status") in ("IN_PROGRESS", "ACTIVE")
            and e.get("name") not in c.BASE_ELEMENTS
        ]

    installed = get_installed_elements()
    max_attempts = len(installed) + 1

    for attempt in range(1, max_attempts + 1):
        if not installed:
            break

        click.echo(
            f"Uninstall attempt {attempt}/{max_attempts}: "
            f"{len(installed)} element(s) remaining"
        )
        for element in installed:
            uninstalled_name = f"{element['name']} ({element['version']})"
            click.echo(
                f"  Uninstalling element {click.style(uninstalled_name, fg='green')}"
            )
            try:
                base_client.action_entity(
                    client,
                    c.REPOSITORY_ELEMENT_COLLECTION,
                    "uninstall",
                    element["uuid"],
                )
            except Exception:
                pass

        time.sleep(0.2)
        installed = get_installed_elements()

    if installed:
        remaining = ", ".join(e["name"] for e in installed)
        raise click.ClickException(
            f"Failed to uninstall all elements. Remaining: {remaining}"
        )

    click.echo("All non-base elements were successfully uninstalled")
    return True


@ee_group.command(
    name="ssh",
    help="copy exordos element from local git repo to element nodes, "
    "example cmd: exordos e e ssh empty",
)
@click.option(
    "--user",
    type=str,
    required=False,
    help="ssh user name",
)
@click.option(
    "-i",
    "--public-key",
    type=click.Path(exists=True),
    required=False,
    help="key or path to it, for example: /home/user/.ssh/id_rsa.pub",
)
@click.option(
    "-p",
    "--private-key",
    type=click.Path(exists=True),
    required=False,
    help="key or path to it, for example: /home/user/.ssh/id_rsa.pub",
)
@click.option(
    "--y", "-y", help="Automatically answer yes for all questions", is_flag=True
)
@click.argument("name")
@click.pass_context
def ssh_cmd(
    ctx: click.Context,
    user: str | None,
    public_key: str | None,
    private_key: str | None,
    y: bool,
    name: str,
) -> None:
    import questionary

    client = base_client.get_user_api_client(ctx.obj.auth_data)

    element_data = base_client.get_entity(client, c.ELEMENT_COLLECTION, name)
    targets = compute.get_compute_targets_from_element(client, element_data)
    if len(targets) == 1:
        target = targets[0]
    else:
        target = {}
        target_uuid = questionary.select(
            "Select target uuid for ssh",
            choices=[t["uuid"] for t in targets],
        ).ask()
        if not target_uuid:
            return None
        for target in targets:
            if target["uuid"] == target_uuid:
                break

    if public_key:
        with open(public_key, "r") as f:
            target_public_key = f.read()
        key_pair_name = public_key.split("/")[-1].split(".")[0]
        if not private_key:
            private_key_path = public_key.replace(".pub", "")
            if os.path.exists(private_key_path):
                private_key = private_key_path
    else:
        key_pair_name = ssh.generate_random_ssh_key_name()
        with ssh.generate_keys(key_pair_name, permanent=True) as (priv_path, pub_path):
            private_key = priv_path
            public_key = pub_path
            with open(pub_path, "r") as f:
                target_public_key = f.read()

    ssh_keys = []
    ssh_key_base_data = {
        "user": str(user or c.BOOTSTRAP_USER),
        "target_public_key": target_public_key,
    }
    target_data = ssh_key_base_data.copy()
    target_data["name"] = f"{key_pair_name}_for_{target['name']}"
    target_data["uuid"] = str(sys_uuid.uuid4())
    target_data["target"] = target["target"]
    target_data["project_id"] = target["project_id"]
    ssh_key = base_client.add_entity(client, c.SSH_KEY_COLLECTION, target_data)
    ssh_keys.append(ssh_key)

    ssh.wait_for_ssh_keys(client, ssh_keys)

    for ip in target["ips"]:
        if y or Confirm.ask(Text(f"Do you want ssh to {ip}?")):
            if private_key:
                click.secho(
                    f"Your private key is {click.style(private_key, fg='green')}"
                )
                click.secho(f"Your public key is {click.style(public_key, fg='green')}")
            cmd = [
                "ssh",
                "-t",
                f"{user or c.BOOTSTRAP_USER}@{ip}",
                "-o StrictHostKeyChecking=no",
                "-o UserKnownHostsFile=/dev/null",
            ]
            if private_key:
                cmd.append("-i")
                cmd.append(private_key)
            try:
                subprocess.Popen(cmd)
            except subprocess.CalledProcessError as e:
                raise click.ClickException(e.stderr)
    return None


ee_group.add_command(show_cmd, aliases=["get", "g"])
ee_group.add_command(uninstall_cmd, aliases=["d", "delete"])
ee_group.add_command(install_cmd, aliases=["i", "add"])
ee_group.add_command(update_cmd, aliases=["u"])
