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

import datetime
import json
import os
import pathlib
import sys
import time
import typing as tp
import uuid as sys_uuid

import rich_click as click
import yaml

from exordos import utils
from exordos.builder import base as base_builder
from exordos.clients import base_client
import exordos.constants as c
from exordos.repo import base as base_repo
from exordos.repo import fs as repo_fs

POLL_INTERVAL = 2.0
STABLE_CHECKS = 10


def get_published() -> str:
    """Return the current UTC timestamp in ISO format with trailing Z."""
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )


def load_repo_driver_from_settings(
    exordosctl_cfg_file: str,
    target: str,
) -> base_repo.AbstractRepoDriver:
    """Build a repo driver from a repository entry in the settings file.

    Returns None if no matching repository is found in settings.
    """
    if not exordosctl_cfg_file or not os.path.exists(exordosctl_cfg_file):
        raise base_repo.UnableLoadDriverError(
            f"Settings file {exordosctl_cfg_file} not found"
        )

    with open(exordosctl_cfg_file, "r") as f:
        config = yaml.safe_load(f) or {}

    repos = config.get("repositories", {})
    if not repos or target not in repos:
        raise base_repo.UnableLoadDriverError(
            f"Repository {target} not found in settings"
        )
    repo = repos[target]

    driver_kind = repo.get("driver")
    if not driver_kind:
        raise base_repo.UnableLoadDriverError(
            f"Driver not specified for repository {target}"
        )

    driver_class = utils.load_from_entry_point(c.EP_REPO_DRIVERS, driver_kind)
    params: dict = dict(repo)
    params.pop("driver", None)
    params["name"] = target
    return driver_class(**params)


def load_repo_driver(
    exordos_cfg_file: str,
    target: str | None,
    project_dir: str,
    exordosctl_cfg_file: str = c.CONFIG_FILE,
    driver_kind: str | None = None,
    driver_params: tuple[str, ...] | None = None,
) -> base_repo.AbstractRepoDriver:
    if driver_kind:
        params = utils.convert_input_multiply(driver_params or ())
        driver_class = utils.load_from_entry_point(c.EP_REPO_DRIVERS, driver_kind)
        return driver_class(name=target, **params)

    try:
        gen_config, _ = utils.get_exordos_config(project_dir, exordos_cfg_file)
    except FileNotFoundError:
        return load_repo_driver_from_settings(exordosctl_cfg_file, target)

    if not gen_config or "push" not in gen_config or not gen_config["push"]:
        return load_repo_driver_from_settings(exordosctl_cfg_file, target)

    pushes = gen_config["push"]

    # Select push target
    if target:
        if target not in pushes:
            raise base_repo.UnableLoadDriverError(
                f"Target {target} not found in the configuration"
            )
        push: dict = pushes[target]
    elif len(pushes) == 1:
        target, push = next(iter(pushes.items()))
    else:
        raise base_repo.UnableLoadDriverError(
            f"Multiple push targets found ({list(pushes.keys())}) in the "
            "configuration. Please specify target."
        )

    if "driver" not in push:
        raise base_repo.UnableLoadDriverError(
            "No driver specified in the configuration"
        )

    # Load driver from entry points
    driver_kind = push.pop("driver")
    driver_class = utils.load_from_entry_point(c.EP_REPO_DRIVERS, driver_kind)
    driver: base_repo.AbstractRepoDriver = driver_class(name=target, **push)

    return driver


def do_push(
    repo_driver: base_repo.AbstractRepoDriver,
    element_dir: pathlib.Path,
    force: bool,
    latest: bool,
    workers: int = 1,
) -> None:
    """Push every element found in a local build output dir to a repo driver.

    Shared by `push_cmd` and `deploy_cmd` so both go through the exact same
    push logic.
    """
    import rich.status as rich_status

    # Every build creates a local repo with built elements into it.
    build_repo = repo_fs.FSRepoDriver(element_dir)
    build_repo_dir = pathlib.Path(build_repo.elements_path)

    with open(build_repo_dir / "inventory.json") as f:
        repo_inventory = json.load(f)
        repo_elements = repo_inventory["elements"]

    def push_element(
        inventory: base_builder.ElementInventory,
    ) -> None:
        message = f"Push {inventory.name} to {repo_driver.name}..."
        # The spinner draws nothing on a non-interactive output (CI logs),
        # so the element being pushed is printed as a plain line there.
        if workers > 1 or not sys.stdout.isatty():
            click.echo(message)
            repo_driver.push(inventory, latest=latest, workers=workers)
            return

        with rich_status.Status(message, spinner="dots"):
            repo_driver.push(inventory, latest=latest, workers=workers)

    for e_name in repo_elements:
        # FIXME(akremenetsky): In the build repo only single version is available
        e_version = tuple(repo_elements[e_name].keys())[0]
        e_dir = build_repo_dir / e_name / e_version
        e_inventory = base_builder.ElementInventory.from_dict(
            repo_elements[e_name][e_version]
        )
        e_inventory = e_inventory.replace_with_abspath(e_dir)

        try:
            push_element(e_inventory)
        except base_repo.ElementAlreadyExistsError:
            if force:
                repo_driver.remove(e_inventory)
                push_element(e_inventory)
                continue

            click.secho(
                f"Element {e_inventory.name} version "
                f"{e_inventory.version} already exists.",
                fg="red",
            )


def do_upload(
    client: tp.Any,
    repository: str,
    manifest: pathlib.Path,
) -> None:
    """Upload an element manifest to a repository via the API.

    Shared logic for `repository_upload_cmd` so the upload can be reused
    from other commands (e.g. `deploy`).
    """
    if not manifest.exists():
        raise click.ClickException(f"Manifest file {manifest} does not exist")

    entity_uuid = base_client._get_entity_uuid(
        client, c.REPOSITORY_COLLECTION, repository
    )

    manifest_data = utils.load_yaml(str(manifest))
    if not isinstance(manifest_data, dict):
        raise click.ClickException("Manifest file must be a valid YAML dictionary")
    name = manifest_data.get("name")
    version = manifest_data.get("version")
    description = manifest_data.get("description", "")

    if not name:
        raise click.ClickException("Manifest must contain 'name' field")
    if not version:
        raise click.ClickException("Manifest must contain 'version' field")

    base_client.action_entity(
        client,
        c.REPOSITORY_COLLECTION,
        "upload",
        entity_uuid,
        element_name=name,
        element_version=version,
        manifest=manifest_data,
        description=description,
    )
    click.echo(
        f"Element {click.style(f'{name}:{version}', fg='green')} was uploaded "
        f"successfully to repository {click.style(repository, fg='green')}"
    )


def extract_repository_uuid(element: dict[str, tp.Any]) -> str:
    """Extract repository UUID from a repository element."""
    repo_ref = element.get("repository")
    if not repo_ref or not isinstance(repo_ref, str):
        return ""
    return repo_ref.rstrip("/").split("/")[-1]


def wait_for_repo_element(
    client: tp.Any,
    repository_uuid: str,
    name: str,
    version: str,
    status: str | list[str],
    timeout: float,
) -> dict[str, tp.Any]:
    """Wait for a repository element with the given name and version to appear."""
    deadline = time.monotonic() + timeout
    status = {status} if isinstance(status, str) else set(status)

    while True:
        elements = base_client.list_entities(
            client, c.REPOSITORY_ELEMENT_COLLECTION, name=name, version=version
        )
        for element in elements:
            if (
                extract_repository_uuid(element) == str(repository_uuid)
                and element.get("status") in status
            ):
                return element

        if time.monotonic() > deadline:
            raise click.ClickException(
                f"Timed out waiting for element '{name}' ({version}) to become "
                f"{status} in the repository catalog. Check `exordos repo show "
                f"{repository_uuid}` for sync errors."
            )
        time.sleep(POLL_INTERVAL)


def wait_for_element_active(
    client: tp.Any,
    name: str,
    version: str,
    timeout: float,
    stable_checks: int = 1,
) -> None:
    """Wait for an element to reach ACTIVE status.

    The backend may briefly flip status ACTIVE -> IN_PROGRESS -> ACTIVE.
    ``stable_checks`` requires the status to be ACTIVE for that many
    consecutive polls before returning.  Any non-ACTIVE status resets
    the counter.
    """
    deadline = time.monotonic() + timeout
    active_streak = 0
    while True:
        elements = base_client.list_entities(
            client, c.ELEMENT_COLLECTION, name=name, version=version
        )
        if elements:
            status = elements[0].get("status")
            if status == "ACTIVE":
                active_streak += 1
                if active_streak >= stable_checks:
                    return
            else:
                active_streak = 0
                if status == "ERROR":
                    raise click.ClickException(
                        f"Element '{name}' failed to install (status ERROR)"
                    )

        if time.monotonic() > deadline:
            raise click.ClickException(
                f"Timed out waiting for element '{name}' to become ACTIVE"
            )
        time.sleep(POLL_INTERVAL)


def find_repository(client: tp.Any, name: str) -> dict[str, tp.Any] | None:
    filters: dict[str, tp.Any] = {"name": name}
    entities = base_client.list_entities(client, c.REPOSITORY_COLLECTION, **filters)
    if not entities:
        return None
    if len(entities) > 1:
        raise click.ClickException(
            f"Multiple repositories found with name '{name}'. Please clean "
            "them up manually (`exordos repo list` / `exordos repo delete`) "
            "before deploying."
        )
    return entities[0]


def ensure_repository(
    client: tp.Any,
    name: str,
    driver_spec: dict[str, tp.Any],
    project_id: sys_uuid.UUID,
    priority: int,
    sync_mode: str,
) -> dict[str, tp.Any]:
    """Point the well-known dev repository at `driver_spec`, creating it if needed.

    A single stable repository is reused across deploys (rather than
    creating/deleting an ephemeral one each time) so an already-installed
    element's provenance never depends on a repository that no longer
    exists.
    """
    existing = find_repository(client, name)

    if existing is not None:
        return base_client.update_entity(
            client,
            c.REPOSITORY_COLLECTION,
            existing["uuid"],
            {
                "driver_spec": driver_spec,
                "priority": priority,
                "sync_mode": sync_mode,
                "refresh_rate": 31536000,
            },
        )

    return base_client.add_entity(
        client,
        c.REPOSITORY_COLLECTION,
        {
            "uuid": str(sys_uuid.uuid4()),
            "project_id": str(project_id),
            "name": name,
            "description": "Managed by `exordos deploy`",
            "priority": priority,
            "refresh_rate": 31536000,
            "sync_mode": sync_mode,
            "driver_spec": driver_spec,
        },
    )
