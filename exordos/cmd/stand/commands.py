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

import fnmatch
import hashlib
import ipaddress
import json
import os
import pathlib
import secrets
import shutil
import subprocess
import time
import typing as tp
import urllib.parse

import requests
import rich.panel
import rich.progress
import rich.status
import rich.table
import rich_click as click
import yaml

from exordos import utils
from exordos.backup import base as backup_base
from exordos.backup import local as backup_local
from exordos.builder import base as base_builder
from exordos.cmd.compute.hypervisors import commands as hv_commands
from exordos.cmd.settings import config as settings_config
from exordos.cmd.stand.constants import BackupPeriod
from exordos.cmd.stand.constants import Profile
from exordos.common import ssh
from exordos.common import status as status_lib
from exordos.common import version as version_lib
from exordos.common.crypto import write_agent_private_key
import exordos.constants as c
from exordos.infra.driver import libvirt as libvirt_infra
from exordos.infra.libvirt import libvirt
from exordos.logger import ClickLogger
from exordos.repo import fs as repo_fs
from exordos.stand import models as stand_models


def _print_bootstrap_summary(
    installation_name: str,
    core_version: str,
    admin_password: str,
    core_ip: ipaddress.IPv4Address | None,
    ssh_public_key_path: str,
    ssh_private_key_path: str | None,
    realm_updated: bool = False,
) -> None:
    console = rich.console.Console()
    table = rich.table.Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", no_wrap=True)
    table.add_column()

    table.add_row("Realm", installation_name)
    table.add_row("Version", core_version)
    table.add_row("Username", "admin")
    table.add_row("Password", admin_password)

    if core_ip is not None:
        table.add_row("Connection", f"[green]ssh ubuntu@{core_ip}[/green]")

    if ssh_private_key_path is not None:
        table.add_row("SSH private key", f"[green]{ssh_private_key_path}[/green]")

    table.add_row("SSH public key", f"[green]{ssh_public_key_path}[/green]")

    if realm_updated:
        table.add_row(
            "Settings",
            f"[green]Realm '{installation_name}' saved to "
            f"~/.exordos/exordosctl.yaml[/green]",
        )

    console.print(
        rich.panel.Panel(
            table,
            title="[bold green]Exordos Bootstrap Summary[/bold green]",
            border_style="green",
            expand=False,
        )
    )


BOOTSTRAP_TAG = "bootstrap"
LaunchModeType = tp.Literal["core", "element", "custom"]
_INVENTORY_CACHE_BASE = pathlib.Path.home() / ".cache" / "exordos"


def _is_url(value: str) -> bool:
    """Return True if *value* looks like an HTTP(S) URL."""
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in ("http", "https")


def _inventory_cache_dir(base_url: str) -> pathlib.Path:
    """Return the local cache directory for a given inventory base URL.

    The path is ``~/.cache/exordos/exordos-elements/<name>/<version>/`` derived from the
    last two segments of *base_url*'s path.  Falls back to a SHA-256 hash
    when the URL has fewer than two path segments.
    """
    url_parts = [
        p for p in urllib.parse.urlparse(base_url).path.split("/") if p and p != ".."
    ]
    if len(url_parts) >= 2:
        element_name = url_parts[-2]
        element_version = url_parts[-1]
    else:
        url_hash = hashlib.sha256(base_url.encode()).hexdigest()[:16]
        element_name = "unknown"
        element_version = url_hash
    return (
        element_name,
        element_version,
        _INVENTORY_CACHE_BASE / c.ELEMENT_REPO_PATH / element_name / element_version,
    )


def _download_inventory_json(session: requests.Session, base_url: str) -> dict:
    """Fetch ``inventory.json`` from *base_url* and return its parsed content."""
    inventory_url = f"{base_url}/inventory.json"
    with rich.progress.Progress(
        rich.progress.SpinnerColumn(),
        rich.progress.TextColumn("[progress.description]{task.description}"),
        rich.progress.BarColumn(),
        rich.progress.DownloadColumn(),
        rich.progress.TransferSpeedColumn(),
        rich.progress.TimeRemainingColumn(),
        transient=True,
    ) as progress:
        task = progress.add_task(
            f"Downloading inventory.json from {base_url}", total=None
        )
        response = session.get(inventory_url)
        response.raise_for_status()
        progress.update(task, completed=1, total=1)
    return response.json()


def _download_inventory_files(
    session: requests.Session,
    base_url: str,
    raw: dict,
    cache_dir: pathlib.Path,
    images_suffix_filter: tp.Optional[str] = None,
) -> None:
    """Download all artefact files referenced in *raw* inventory to *cache_dir*.

    Remote layout:  ``base_url/<category>/<filename>``
    Local layout:   ``cache_dir/<category>/<filename>``

    Already-cached files are skipped.  On completion, *raw* is mutated in-place
    so that every category list contains absolute local paths, and the final
    ``inventory.json`` is written to *cache_dir*.

    Args:
        images_suffix_filter: When set, only image files whose name ends with
            this suffix (e.g. ``'.qcow2'``) are downloaded and kept in the
            cached inventory.  All other categories are unaffected.
    """
    inventories = raw if isinstance(raw, list) else [raw]

    # rel_path in inventory.json is a bare filename (no category subdir).
    # Remote: base_url/<category>/<filename>  (Nginx layout with subdirs)
    # Local:  cache_dir/<category>/<filename>  (matches ElementInventory.load)
    all_files: list[tuple[str, pathlib.Path, str]] = []
    for inv in inventories:
        for category in base_builder.ElementInventory.categories():
            rel_paths = inv.get(category, [])
            if images_suffix_filter and category == "images":
                rel_paths = [
                    p
                    for p in rel_paths
                    if pathlib.Path(p).name.endswith(images_suffix_filter)
                ]
            for rel_path in rel_paths:
                file_name = pathlib.Path(rel_path).name
                remote_url = f"{base_url}/{category}/{file_name}"
                local_file = cache_dir / category / file_name
                all_files.append((remote_url, local_file, file_name))

    with rich.progress.Progress(
        rich.progress.SpinnerColumn(),
        rich.progress.TextColumn("[progress.description]{task.description}"),
        rich.progress.BarColumn(),
        rich.progress.DownloadColumn(),
        rich.progress.TransferSpeedColumn(),
        rich.progress.TimeRemainingColumn(),
    ) as progress:
        for remote_url, local_file, file_name in all_files:
            task = progress.add_task(f"Downloading {file_name}", total=None)
            local_file.parent.mkdir(parents=True, exist_ok=True)
            if local_file.exists():
                progress.update(
                    task,
                    description=f"[dim]Cached[/dim] {file_name}",
                    completed=1,
                    total=1,
                )
                continue
            temp_file = local_file.with_suffix(".tmp")
            with session.get(remote_url, stream=True) as resp:
                resp.raise_for_status()
                content_length = resp.headers.get("Content-Length")
                total = int(content_length) if content_length else None
                progress.update(task, total=total)
                downloaded = 0
                with open(temp_file, "wb") as fh:
                    for chunk in resp.iter_content(chunk_size=1024 * 64):
                        fh.write(chunk)
                        downloaded += len(chunk)
                        progress.update(task, completed=downloaded)
            temp_file.replace(local_file)

    for inv in inventories:
        for category in base_builder.ElementInventory.categories():
            rel_paths = inv.get(category, [])
            if images_suffix_filter and category == "images":
                rel_paths = [
                    p
                    for p in rel_paths
                    if pathlib.Path(p).name.endswith(images_suffix_filter)
                ]
            inv[category] = [
                str(cache_dir / category / pathlib.Path(rel_path).name)
                for rel_path in rel_paths
            ]

    inventory_local = cache_dir / "inventory.json"
    inventory_local.write_text(json.dumps(raw, indent=2))


def _init_cache_repo(repo_driver: repo_fs.FSRepoDriver) -> None:
    # TODO(akremenetsky): It's internal logic of repository and it should be
    # moved into repository models one day.
    repo_inventory_path = _INVENTORY_CACHE_BASE / c.ELEMENT_REPO_PATH / "inventory.json"
    if not repo_inventory_path.exists():
        repo_driver.init_repo()
        with open(repo_inventory_path, "w") as f:
            json.dump({"elements": {}}, f)


def get_element_inventory_from_url(url: str) -> base_builder.ElementInventory:
    """Download inventory and all artefacts from an Nginx URL, with caching.

    Args:
        url: URL of the inventory directory or ``inventory.json`` file.

    Returns:
        Local cache directory path accepted by :py:meth:`ElementInventory.load`.
    """
    repo_driver = repo_fs.FSRepoDriver(_INVENTORY_CACHE_BASE)
    _init_cache_repo(repo_driver)

    base_url = url.rstrip("/")
    if base_url.endswith("/inventory.json"):
        base_url = base_url[: -len("/inventory.json")]

    name, version, cache_dir = _inventory_cache_dir(base_url)
    inventory_local = cache_dir / "inventory.json"

    if inventory_local.exists():
        click.secho(f"Using cached inventory from {cache_dir}", fg="cyan")
        return repo_driver.inventory(name, version)

    cache_dir.mkdir(parents=True, exist_ok=True)
    with requests.Session() as session:
        try:
            raw = _download_inventory_json(session, base_url)
            _download_inventory_files(
                session, base_url, raw, cache_dir, images_suffix_filter=".qcow2"
            )
        except:
            shutil.rmtree(cache_dir)
            raise

    # TODO(akremenetsky): It's internal logic of repository and it should be
    # moved into repository models one day.
    inventories = repo_driver.inventories()
    with open(inventory_local) as f:
        inventories.setdefault(name, {})[version] = json.load(f)

    repo_inventory_path = _INVENTORY_CACHE_BASE / c.ELEMENT_REPO_PATH / "inventory.json"
    with open(repo_inventory_path, "w") as f:
        json.dump({"elements": inventories}, f, indent=2, sort_keys=True)

    return repo_driver.inventory(name, version)


def _get_core_image_uri_from_manifest(manifest_path: str) -> str:
    """Get image URI from manifest file."""
    if not os.path.exists(manifest_path):
        raise click.UsageError(f"Manifest file {manifest_path} does not exist")

    with open(manifest_path, "r") as f:
        manifest = yaml.safe_load(f)

    # Determine image URI from manifest
    try:
        return manifest["resources"]["$core.compute.sets"]["core_set"]["disk_spec"][
            "disks"
        ][0]["image"]
    except (KeyError, IndexError):
        click.secho("Failed to get image URI from manifest", fg="red")
        raise


def _bootstrap_element(
    image_path: tp.Optional[str],
    cores: int,
    memory: int,
    name: str,
    cidr: ipaddress.IPv4Network,
    force: bool,
    no_wait: bool,
) -> None:
    logger = ClickLogger()

    net_name = utils.installation_net_name(name)
    default_stand_network = stand_models.Network(
        name=net_name,
        cidr=cidr,
        managed_network=True,
        dhcp=True,
    )

    bootstrap_domain_name = utils.installation_bootstrap_name(name)

    # Single bootstrap stand
    dev_stand = stand_models.Stand.single_bootstrap_stand(
        name=name,
        image=image_path,
        cores=cores,
        memory=memory,
        network=default_stand_network,
        bootstrap_name=bootstrap_domain_name,
    )

    if not dev_stand.is_valid():
        logger.error("Invalid stand for element")
        return

    infra = libvirt_infra.LibvirtInfraDriver()

    # Check if the target stand already exists
    for stand in infra.list_stands():
        if stand.name != dev_stand.name:
            continue

        # Without `force` flag, unable to proceed with the installation
        if not force:
            logger.warning(
                f"Exordos element {dev_stand.name} is already running. "
                "Use '--force' flag to force rerun exordos element.",
            )
            return

        infra.delete_stand(stand)
        logger.info(f"Destroyed old exordos element: {dev_stand.name}")

    infra.create_stand(dev_stand)
    logger.info(f"Launched exordos element {name}")

    # Wait for the installation to start
    if no_wait:
        return

    utils.wait_for(
        lambda: bool(libvirt.get_domain_ip(bootstrap_domain_name)),
        title=f"Waiting for element {name}",
    )

    ip = libvirt.get_domain_ip(bootstrap_domain_name)
    logger.important(f"The element {name} is ready at:\nssh ubuntu@{ip}")


def _register_core(
    ecosystem_endpoint: str,
    disable_telemetry: bool,
    org_token: str | None,
) -> tuple[str, str, str]:
    from exordos.clients import ecosystem

    logger = ClickLogger()
    logger.info("Registering realm in ecosystem...")

    realm_uuid, realm_secret, tokens_dict = ecosystem.register_realm(
        ecosystem_endpoint=ecosystem_endpoint,
        org_token=org_token,
    )

    if tokens_dict:
        logger.info("Realm registered successfully")
    else:
        logger.info("Realm registered successfully in anonymous mode")

    return realm_uuid, realm_secret, tokens_dict


REALM_SPEC_REQUIRED_KEYS = (
    "realm_uuid",
    "realm_secret",
    "realm_tokens",
    "ecosystem_endpoint",
    "admin_password",
)


def _load_realm_spec(path: str) -> dict:
    """Load and validate a realm spec delivered by the exordos ecosystem.

    Managed realm nodes receive `/etc/exordos/realm_spec.json` from the
    ecosystem builder agent (see exordos_ecosystem `docs/realm-manager.md`).
    The file carries a pre-assigned realm identity, so bootstrap must use
    it instead of self-registering a new realm.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            spec = json.load(f)
    except json.JSONDecodeError as e:
        raise click.UsageError(f"Realm spec {path} is not a valid JSON file: {e}")
    except OSError as e:
        raise click.ClickException(f"Failed to read realm spec {path}: {e}")

    if not isinstance(spec, dict):
        raise click.UsageError(f"Realm spec {path} must be a JSON object")

    spec_version = spec.get("version", 1)
    if spec_version != 1:
        raise click.UsageError(f"Unsupported realm spec version: {spec_version}")

    # realm_tokens may legitimately be an empty object; only enforce that
    # it is present. The remaining keys must be non-empty.
    missing = [
        key
        for key in REALM_SPEC_REQUIRED_KEYS
        if spec.get(key) is None or (key != "realm_tokens" and not spec.get(key))
    ]
    if missing:
        raise click.UsageError(
            f"Realm spec {path} misses required keys: {', '.join(missing)}"
        )

    return spec


def _iam_default_client_settings() -> dict:
    return {
        "default_client_uuid": "00000000-0000-0000-0000-000000000000",
        "default_client_id": "Exordos",
        "default_client_secret": secrets.token_urlsafe(32),
    }


def _save_admin_password_file(
    path: str, admin_password: str, logger: ClickLogger
) -> None:
    password_path = pathlib.Path(path)
    if ".." in password_path.parts:
        logger.error("Invalid password file path (contains '..'). Skipping save.")
        return

    try:
        password_path.parent.mkdir(parents=True, exist_ok=True)

        def secure_opener(file_path: str, flags: int) -> int:
            return os.open(file_path, flags, 0o600)

        with open(
            password_path, "x", encoding="utf-8", opener=secure_opener
        ) as password_file:
            password_file.write(admin_password)
        logger.info(f"Admin password saved to {password_path}")
    except FileExistsError:
        logger.warning(
            f"Admin password file {password_path} already exists. "
            "Skipping saving the password."
        )
    except OSError as e:
        logger.error(f"Failed to save admin password to {password_path}: {e}")


def _bootstrap_core(
    image_path: str | None,
    image_uri: str | None,
    profile: Profile,
    name: str,
    stand_spec: tp.Dict[str, tp.Any] | None,
    stand_main_network: stand_models.Network,
    stand_boot_network: stand_models.Network,
    disks: list[int] | None,
    force: bool,
    core_ip: ipaddress.IPv4Address,
    repository: tp.Tuple[str, ...],
    admin_password: str,
    save_admin_password_file: str | None,
    manifest_path: str,
    eco_manifest_path: str,
    hypervisors: tp.Collection[stand_models.Hypervisor],
    no_start: bool,
    ecosystem_endpoint: str,
    disable_telemetry: bool,
    realm_uuid: str,
    realm_secret: str,
    realm_tokens: dict,
    realm_id: str | None = None,
    realm_domain: str | None = None,
    ssh_public_key: str | None = None,
    elements: list[str] | None = None,
) -> ipaddress.IPv4Address | None:
    logger = ClickLogger()
    logger.info("Starting exordos bootstrap in 'core' mode")

    if not hypervisors:
        logger.error("No hypervisors provided")
        return None

    # Single bootstrap stand
    if stand_spec is None:
        bootstrap_domain_name = utils.installation_bootstrap_name(name)
        dev_stand = stand_models.Stand.single_bootstrap_stand(
            name=name,
            image=image_path,
            image_uri=image_uri,
            cores=profile.cores,
            memory=profile.ram,
            disks=disks,
            core_ip=core_ip,
            network=stand_main_network,
            boot_network=stand_boot_network,
            bootstrap_name=bootstrap_domain_name,
            hypervisors=hypervisors,
        )
    else:
        dev_stand = stand_models.Stand.from_spec(stand_spec)
        if dev_stand.network.is_dummy:
            dev_stand.network = stand_main_network

        if dev_stand.boot_network.is_dummy:
            dev_stand.boot_network = stand_boot_network

        # Assign the image to bootstraps if it wasn't specified
        # in the specification.
        for b in dev_stand.bootstraps:
            if b.image is None:
                b.image = image_path

    if not dev_stand.is_valid():
        logger.error(f"Invalid stand {dev_stand} from spec {stand_spec}")
        return None

    infra = libvirt_infra.LibvirtInfraDriver()

    # Check if the target stand already exists
    for stand in infra.list_stands():
        if stand.name != dev_stand.name:
            continue

        # Without `force` flag, unable to proceed with the installation
        if not force:
            logger.warning(
                f"Exordos installation {dev_stand.name} is already running. "
                "Use '--force' flag to force rerun Exordos installation.",
            )
            return None

        infra.delete_stand(stand)
        logger.info(f"Destroyed old Exordos installation: {dev_stand.name}")

    # list_stands discovers stands via their domains, so a network left
    # behind without a domain (e.g. a previous bootstrap interrupted
    # before the domain was created, or a domain removed manually
    # without its networks) isn't visible there. Without this, --force
    # wouldn't clean it and create_stand would raise
    # "Network ... already exists". delete_stand is idempotent and only
    # touches networks named after this stand.
    if force:
        infra.delete_stand(dev_stand)

    # Prepare IAM settings
    iam = _iam_default_client_settings()
    iam["admin_password"] = admin_password

    try:
        infra.create_stand(
            dev_stand,
            manifest_path=manifest_path,
            eco_manifest_path=eco_manifest_path,
            no_start=no_start,
            repository=repository,
            admin_password=admin_password,
            profile=profile.value,
            ecosystem_endpoint=ecosystem_endpoint,
            disable_telemetry=disable_telemetry,
            realm_uuid=realm_uuid,
            realm_secret=realm_secret,
            realm_tokens=realm_tokens,
            realm_id=realm_id,
            realm_domain=realm_domain,
            developer_keys=ssh_public_key,
            iam=iam,
            elements=elements,
        )
        logger.info(f"Launched Exordos installation in `{profile.value}` profile")

        if save_admin_password_file:
            _save_admin_password_file(save_admin_password_file, admin_password, logger)
    except Exception:
        infra.delete_stand(dev_stand)
        logger.error(f"Failed to launch Exordos installation {dev_stand.name}")
        raise

    if no_start:
        return None
    return dev_stand.network.cidr[2]


def _update_realm_config(
    realm_name: str,
    realm_ip: ipaddress.IPv4Address,
    cidr: ipaddress.IPv4Network,
    admin_password: str,
    cfg_path: str = c.CONFIG_FILE,
) -> None:
    """Update the realm entry in exordosctl.yaml after bootstrap."""
    logger = ClickLogger()

    try:
        with open(cfg_path, "r") as f:
            config = yaml.safe_load(f) or {}
    except FileNotFoundError:
        config = {}

    if "realms" not in config:
        config["realms"] = {}

    existing = config["realms"].get(realm_name, {})
    existing_meta = existing.get("meta", {})

    config["realms"][realm_name] = {
        "endpoint": f"http://{realm_ip}/api/core",
        "check_updates": existing.get("check_updates", True),
        "skip_tls_verify": existing.get("skip_tls_verify", True),
        "local": True,
        "meta": {**existing_meta, "cidr": str(cidr)},
        "contexts": existing.get("contexts", {}),
        "current-context": existing.get("current-context"),
    }

    if not config["realms"][realm_name]["contexts"]:
        config["realms"][realm_name]["contexts"] = {
            "admin": {
                "user": "admin",
                "password": admin_password,
            }
        }
        config["realms"][realm_name]["current-context"] = "admin"

    if not config.get("current-realm"):
        config["current-realm"] = realm_name

    settings_config.save_config(config, cfg_path)
    logger.info(f"Realm '{realm_name}' configuration updated in {cfg_path}")


def _resolve_hypervisor_placement(
    pool_agent_placement: str,
    hyper_connection_uri: str,
    cidr: ipaddress.IPv4Network,
) -> tp.Tuple[str, str]:
    """Resolve the hypervisor's connection URI and driver kind.

    Returns (connection_uri, driver_kind). Kind "libvirt" means the pool
    agent lives in core and reaches libvirt over the network; kind
    "exordos_local_hyper" means a dedicated local agent on this host
    talks to the local libvirt socket directly.
    """
    if pool_agent_placement == "local":
        if hyper_connection_uri:
            raise click.UsageError(
                "--hyper-connection-uri is not supported together with "
                "--pool-agent-placement=local; the local agent always "
                "talks to the local libvirt socket directly."
            )
        return hv_commands.DEFAULT_LOCAL_CONNECTION_URI, "exordos_local_hyper"

    return hyper_connection_uri or f"qemu+tcp://{cidr[1]}/system", "libvirt"


@click.command("bootstrap", help="Bootstrap exordos locally")
@click.option(
    "-i",
    "--inventory",
    envvar="INVENTORY",
    help=(
        "Path to the inventory directory containing inventory.json, "
        "or an HTTP(S) URL pointing to an Nginx-served directory. "
        "When a URL is given, inventory.json and all referenced artefacts are "
        "downloaded and cached under ~/.cache/exordos/<name>/<version>/. "
        "Trailing /inventory.json in the URL is accepted and treated identically "
        "to the bare directory URL. "
        "A bare version string (e.g. '0.0.6') is expanded automatically to "
        f"{c.ELEMENT_REPO_URL}/core/<version>/. "
        "Examples: "
        "0.0.6  "
        "/path/to/core/0.0.6  "
        "https://repository.example.com/exordos-elements/core/0.0.6/  "
    ),
)
@click.option(
    "--profile",
    default=Profile.SMALL.value,
    show_default=True,
    help="Profile for the installation.",
    type=click.Choice([p.value for p in Profile]),
)
@click.option(
    "--root-disk-size",
    default=10,
    show_default=True,
    type=int,
    help="Root disk size in GB",
)
@click.option(
    "--data-disk-size",
    default=10,
    show_default=True,
    type=int,
    help="Data disk size in GB",
)
@click.option(
    "--name",
    default="exordos-core",
    help="Name of the installation",
)
# It's a temporary option, will be removed in the future but now it's
# convenient to run elements and cores slightly differently
@click.option(
    "-m",
    "--launch-mode",
    default="element",
    type=click.Choice([s for s in tp.get_args(LaunchModeType)]),
    show_default=True,
    help="Launch mode for start element, core or custom configuration",
)
@click.option(
    "-s",
    "--stand-spec",
    default=None,
    type=click.Path(exists=True),
    help="Additional stand specification for core mode.",
)
@click.option(
    "--cidr",
    default=c.GC_CIDR,
    help="The main network CIDR",
    show_default=True,
    type=ipaddress.IPv4Network,
)
@click.option(
    "--core-ip",
    default=None,
    help=(
        "The IP address for the core VM. If `None` is provided, "
        "second IP address from the main network will be used."
    ),
    show_default=True,
    type=ipaddress.IPv4Address,
)
@click.option(
    "--bridge",
    default=None,
    help=(
        "Name of the linux bridge for the main network, it will be created if not set."
    ),
)
@click.option(
    "--boot-cidr",
    default=c.GC_BOOT_CIDR,
    help="The bootstrap network CIDR",
    show_default=True,
    type=ipaddress.IPv4Network,
)
@click.option(
    "--boot-bridge",
    default=None,
    help=(
        "Name of the linux bridge for the bootstrap network, "
        "it will be created if not set."
    ),
)
@click.option(
    "-f",
    "--force",
    show_default=True,
    is_flag=True,
    help="Rebuild if the output already exists",
)
@click.option(
    "--no-wait",
    show_default=True,
    is_flag=True,
    help="Cancel waiting for the installation to start",
)
@click.option(
    "-r",
    "--repository",
    multiple=True,
    default=(f"{c.ELEMENT_REPO_URL}/",),
    type=str,
    help="Default element repository (can be specified multiple times)",
    show_default=True,
)
@click.option(
    "--admin-password",
    default=None,
    type=str,
    help=(
        "A password for the admin user in. If not provided, "
        "the password will be generated."
    ),
    show_default=True,
)
@click.option(
    "--save-admin-password-file",
    default=None,
    type=str,
    help=(
        "If the option is specified the admin password is saved "
        "to the file. Otherwise it's printed to the console."
    ),
    show_default=True,
)
@click.option(
    "--pool-agent-placement",
    type=click.Choice(["core", "local"]),
    default="core",
    show_default=True,
    help=(
        "Where the pool agent that drives the hypervisor's libvirt runs. "
        "'core' runs it inside core's own services, reaching libvirt over "
        "the network (see --hyper-connection-uri). 'local' installs a "
        "dedicated universal agent on this host that talks to the local "
        "libvirt socket directly (matching `exordos compute hypervisors "
        "init`); --hyper-connection-uri is not supported in this mode."
    ),
)
@click.option(
    "--hyper-connection-uri",
    default="",
    type=str,
    help=(
        "Connection URI for the hypervisor, "
        "e.g. 'qemu+tcp://10.0.0.1/system' or "
        "'qemu+ssh://user@10.0.0.1/system'. Only used with "
        "--pool-agent-placement=core; if not set there, the main "
        "network's first address is used (qemu+tcp)."
    ),
)
@click.option(
    "--hyper-storage-pool",
    default="default",
    type=str,
    help="Storage pool for the hypervisor.",
    show_default=True,
)
@click.option(
    "--hyper-machine-prefix",
    default="vm-",
    type=str,
    help="A prefix for new VMs.",
    show_default=True,
)
@click.option(
    "--hyper-iface-rom-file",
    default="/usr/share/qemu/1af41041.rom",
    type=str,
    help="A path to the custom ROM file of a network interface.",
    show_default=True,
)
@click.option(
    "--no-start",
    show_default=True,
    is_flag=True,
    help="Do not start the stand after creation",
)
# Ecosystem
@click.option(
    "--no-registration",
    is_flag=True,
    envvar="NO_REGISTRATION",
    help="Don't register in ecosystem.",
)
@click.option(
    "--disable-telemetry",
    is_flag=True,
    envvar="DISABLE_TELEMETRY",
    help="Disable telemetry. Anonymized data only is sent by default.",
)
@click.option(
    "--org-token",
    prompt=False,
    hide_input=True,
    type=str,
    envvar="ORG_TOKEN",
    help="Organization token, used to register stand in ecosystem",
)
@click.option(
    "--ecosystem-endpoint",
    default=c.ECOSYSTEM_ENDPOINT,
    type=str,
    envvar="ECOSYSTEM_ENDPOINT",
    help="Ecosystem's endpoint to connect to",
)
@click.option(
    "--realm-spec",
    default=None,
    type=click.Path(exists=True),
    envvar="REALM_SPEC",
    help=(
        "Path to a realm spec file (realm_spec.json) delivered by the "
        "exordos ecosystem to managed realm nodes. Provides a pre-assigned "
        "realm identity (uuid, secret, tokens), the ecosystem endpoint and "
        "the admin password; self-registration is skipped."
    ),
)
@click.option(
    "--download-only",
    is_flag=True,
    help=(
        "Only resolve and download the element inventories (populating "
        "the local cache), then exit without bootstrapping."
    ),
)
@click.option(
    "--settings",
    show_default=True,
    is_flag=True,
    help="Interactively create a exordos settings file",
)
@click.option(
    "--ssh-public-key",
    envvar="SSH_PUBLIC_KEY",
    multiple=True,
    type=click.Path(exists=True, file_okay=True, dir_okay=False),
    help=(
        "Path to a public SSH key file to inject into the VM "
        "after bootstrap. Can be specified multiple times. If not provided, a key pair is generated in ~/.ssh/."
    ),
)
@click.option(
    "--elements",
    multiple=True,
    type=str,
    help=(
        "Elements to install. Can be specified multiple times. "
        "Example: --elements empty --elements dbaas"
    ),
)
@click.option(
    "--no-update-realm",
    is_flag=True,
    default=False,
    help="Do not update the realm configuration in exordosctl.yaml after bootstrap",
)
@click.option(
    "--pool-agent-name",
    "agent_name",
    type=str,
    default=hv_commands.DEFAULT_AGENT_NAME,
    show_default=True,
    help=(
        "Name of the universal agent to run LocalPoolAgentDriver under on "
        "this host. The default targets the standard agent (merging in "
        "if this host is also a registered compute node). Use a different "
        "name to run a separate, dedicated agent instead - required if "
        "the standard agent here is already configured for a different "
        "core."
    ),
)
@click.pass_context
def bootstrap_cmd(
    ctx: click.Context,
    inventory: str,
    profile: str,
    root_disk_size: int,
    data_disk_size: int,
    name: str,
    launch_mode: LaunchModeType,
    stand_spec: str | None,
    cidr: ipaddress.IPv4Network,
    core_ip: ipaddress.IPv4Address | None,
    bridge: str | None,
    boot_cidr: ipaddress.IPv4Network,
    boot_bridge: str | None,
    force: bool,
    no_wait: bool,
    repository: tp.Tuple[str, ...],
    admin_password: str | None,
    save_admin_password_file: str | None,
    pool_agent_placement: str,
    hyper_connection_uri: str,
    hyper_storage_pool: str,
    hyper_machine_prefix: str,
    hyper_iface_rom_file: str,
    no_start: bool,
    no_registration: bool,
    disable_telemetry: bool,
    org_token: str | None,
    ecosystem_endpoint: str,
    realm_spec: str | None,
    download_only: bool,
    settings: bool,
    ssh_public_key: tp.Tuple[str, ...],
    elements: tp.Tuple[str, ...],
    no_update_realm: bool,
    agent_name: str,
) -> None:
    if not inventory:
        raise click.UsageError("No inventory specified")

    if _is_url(inventory):
        inventory = inventory[:-1] if inventory.endswith("/") else inventory
        # Detect version
        inventory = inventory.split("/")[-1]

    if version_lib.is_version(inventory):
        element_repo_url = (
            repository[0].rstrip("/") if repository else c.ELEMENT_REPO_URL
        )
        inventory_instance = get_element_inventory_from_url(
            f"{element_repo_url}/core/{inventory.strip()}/"
        )
        inventory_eco_instance = get_element_inventory_from_url(
            f"{element_repo_url}/ecosystem_realm/{inventory.strip()}/"
        )
        eco_manifest_path = str(inventory_eco_instance.manifests[0])
    else:
        # Load inventories
        repo_driver = repo_fs.FSRepoDriver(inventory)
        inventory_instance = repo_driver.inventory("core")
        inventory_eco_instance = repo_driver.inventory("ecosystem_realm")
        eco_manifest_path = str(inventory_eco_instance.manifests[0])

    if download_only:
        click.secho(
            "Element inventories are downloaded and cached. Exiting (--download-only).",
            fg="green",
        )
        return None

    realm_spec_data = None
    if realm_spec is not None:
        if org_token or no_registration:
            raise click.UsageError(
                "--realm-spec cannot be combined with --org-token or --no-registration"
            )
        if launch_mode != "core":
            raise click.UsageError(
                "--realm-spec is only supported in 'core' launch mode"
            )
        realm_spec_data = _load_realm_spec(realm_spec)
        admin_password = realm_spec_data["admin_password"]
        ecosystem_endpoint = realm_spec_data["ecosystem_endpoint"]
        disable_telemetry = bool(realm_spec_data.get("disable_telemetry", False))

    profile = Profile[profile.upper()]

    # Determine the IP address for the core VM
    if core_ip is None:
        core_ip = cidr[2]

    if core_ip not in cidr:
        raise click.UsageError("Core IP is not in the main network")

    # Generate admin password if not provided
    if not admin_password:
        import secrets

        admin_password = secrets.token_urlsafe(16)

    if not inventory_instance.images:
        raise click.UsageError("No images found in the inventory")

    if not inventory_instance.manifests:
        raise click.UsageError("No manifests found in the inventory")

    # NOTE(akremenetsky): The core element has one image and manifest at the moment
    image_path = str(inventory_instance.images[0])
    manifest_path = str(inventory_instance.manifests[0])
    image_uri = _get_core_image_uri_from_manifest(manifest_path)

    if launch_mode not in ("element", "core"):
        raise click.UsageError(f"Unknown launch mode {launch_mode}")

    if image_path and not os.path.isabs(image_path):
        image_path = os.path.abspath(image_path)

    # DEPRECATED(akremenetsky): The 'element' mode is deprecated
    if launch_mode == "element":
        if stand_spec is not None:
            raise click.UsageError("Stand spec is not supported in 'element' mode")

        return _bootstrap_element(
            image_path=image_path,
            cores=profile.cores,
            memory=profile.ram,
            name=name,
            force=force,
            no_wait=no_wait,
            cidr=cidr,
        )

    # Validate org-token requirement based on no-registration flag
    if no_registration:
        org_token = None
    # TODO: re-enable after preparations
    #     elif not org_token:
    #         click.secho(
    #             click.style(
    #                 """\

    # Register your realm in the exordos ecosystem to get access to additional features and support.
    # You can skip registration by using --no-registration flag.

    # """,
    #                 bold=True,
    #                 fg="yellow",
    #             ),
    #             bold=True,
    #             # Underline makes the text more visible
    #             underline=True,
    #         )

    #         org_token = click.prompt("Organization token", hide_input=True)

    if stand_spec is not None:
        with open(stand_spec) as f:
            stand_spec = yaml.safe_load(f)

    net_name = utils.installation_net_name(name)
    stand_main_network = stand_models.Network(
        name=bridge if bridge else net_name,
        cidr=cidr,
        managed_network=False if bridge else True,
    )
    boot_net_name = utils.installation_boot_net_name(name)
    stand_boot_network = stand_models.Network(
        name=boot_bridge if boot_bridge else boot_net_name,
        cidr=boot_cidr,
        managed_network=False if boot_bridge else True,
    )

    if subprocess.call(["sudo", "-n", "true"], stderr=subprocess.DEVNULL) != 0:
        click.secho("Sudo privileges are required to proceed.", fg="yellow")
        if subprocess.call(["sudo", "-v"]) != 0:
            raise click.ClickException("Failed to obtain sudo privileges. Aborting.")

    hypervisors = []

    hyper_connection_uri, hyper_kind = _resolve_hypervisor_placement(
        pool_agent_placement, hyper_connection_uri, cidr
    )

    hyper_node = None
    hyper_private_key = None
    if hyper_kind == "exordos_local_hyper":
        # This machine is the hypervisor, reachable over the local
        # libvirt socket by the local universal agent (LocalPoolAgentDriver)
        # only, matched by node uuid.
        hyper_node = hv_commands.local_agent_node_uuid()
        # Generated here (rather than left for the core to generate) so
        # the same key can be written to the agent below, right after
        # the core seeds its matching NodeEncryptionKey at bootstrap.
        hyper_private_key = hv_commands.generate_node_private_key_base64()

    # Single hypervisor at bootstrap time is supported at the moment
    hypervisor = stand_models.Hypervisor(
        network=stand_main_network.name,
        network_type="bridge" if bridge else "network",
        connection_uri=hyper_connection_uri,
        storage_pool=hyper_storage_pool,
        kind=hyper_kind,
        node=hyper_node,
        private_key=hyper_private_key,
        machine_prefix=hyper_machine_prefix,
        iface_rom_file=hyper_iface_rom_file,
    )
    hypervisors.append(hypervisor)

    if realm_spec_data is not None:
        # Managed realm: the identity was pre-assigned by the ecosystem
        # and the parent realm row already exists there. The child flips
        # it to ACTIVE by self-reporting with this uuid+secret.
        realm_uuid = realm_spec_data["realm_uuid"]
        realm_secret = realm_spec_data["realm_secret"]
        realm_tokens = realm_spec_data["realm_tokens"]
        realm_id = realm_spec_data.get("realm_id")
        realm_domain = realm_spec_data.get("realm_domain")
        click.secho(
            "Using pre-assigned realm identity from the realm spec",
            fg="cyan",
        )
    else:
        realm_id = None
        realm_domain = None
        with status_lib.status_done("Registering realm in ecosystem..."):
            realm_uuid, realm_secret, realm_tokens = _register_core(
                ecosystem_endpoint=ecosystem_endpoint,
                disable_telemetry=disable_telemetry,
                org_token=org_token,
            )

    if ssh_public_key:
        ssh_private_key_path = None
        ssh_public_key_path = ", ".join([key_path for key_path in ssh_public_key])
        key_parts = []
        for key_path in ssh_public_key:
            with open(key_path, encoding="utf-8") as f:
                key_content = f.read().strip()
                key_parts.append(key_content + "\n")
        ssh_public_key_content = "".join(key_parts)
    elif realm_spec_data is not None and realm_spec_data.get("ssh_public_key"):
        ssh_public_key_content = ssh_public_key_path = realm_spec_data["ssh_public_key"]
        ssh_private_key_path = None
    else:
        with ssh.generate_keys(name.replace("-", "_"), permanent=True) as (
            private_key_path,
            public_key_path,
        ):
            ssh_private_key_path = private_key_path
            ssh_public_key_path = public_key_path
            with open(public_key_path, encoding="utf-8") as f:
                ssh_public_key_content = f.read().strip()

    with status_lib.status_done(f"Launching Exordos installation '{name}'... "):
        core_ip_result = _bootstrap_core(
            image_path=image_path,
            image_uri=image_uri,
            profile=profile,
            name=name,
            stand_spec=stand_spec,
            stand_main_network=stand_main_network,
            stand_boot_network=stand_boot_network,
            disks=[root_disk_size, data_disk_size],
            force=force,
            core_ip=core_ip,
            repository=repository,
            admin_password=admin_password,
            save_admin_password_file=save_admin_password_file,
            manifest_path=manifest_path,
            eco_manifest_path=eco_manifest_path,
            hypervisors=hypervisors,
            no_start=no_start,
            ecosystem_endpoint=ecosystem_endpoint,
            disable_telemetry=disable_telemetry,
            realm_uuid=realm_uuid,
            realm_secret=realm_secret,
            realm_tokens=realm_tokens,
            realm_id=realm_id,
            realm_domain=realm_domain,
            ssh_public_key=ssh_public_key_content,
            elements=list(elements) if elements else None,
        )

    if hyper_kind == "exordos_local_hyper":
        # The local agent must be configured regardless of --no-start: the
        # core's IP is fixed at network-creation time (not discovered once
        # it boots), and the core needs to find the agent already
        # configured the first time it does start.
        if core_ip_result is not None:
            agent_ip = core_ip_result
        elif core_ip is not None:
            agent_ip = core_ip
        else:
            agent_ip = cidr[2]
        with status_lib.status_done("Setting up the local universal agent..."):
            orch_endpoint = f"http://{agent_ip}:{hv_commands.ORCH_API_PORT}"
            status_endpoint = f"http://{agent_ip}:{hv_commands.STATUS_API_PORT}"
            agent_target = hv_commands.resolve_agent_install_target(
                agent_name=agent_name,
                orch_endpoint=orch_endpoint,
                status_endpoint=status_endpoint,
            )
            hv_commands.install_agent_venv(agent_target.venv_path)
            hv_commands.reset_agent_meta_file(agent_target.meta_file)
            private_key_path = hv_commands.write_agent_config(
                orch_endpoint=orch_endpoint,
                status_endpoint=status_endpoint,
                config_path=agent_target.config_path,
                meta_file=agent_target.meta_file,
                default_private_key_path=agent_target.default_private_key_path,
            )
            write_agent_private_key(hyper_private_key, key_path=private_key_path)
            hv_commands.install_agent_systemd_unit(
                exec_path=agent_target.exec_path,
                config_path=agent_target.config_path,
                unit_path=agent_target.unit_path,
                unit_name=agent_target.unit_name,
            )

    realm_updated = False
    if not no_update_realm:
        realm_ip = core_ip_result if core_ip_result is not None else core_ip
        if realm_ip is not None:
            _update_realm_config(
                realm_name=name,
                realm_ip=realm_ip,
                cidr=cidr,
                admin_password=admin_password,
                cfg_path=ctx.obj.cfg_path,
            )
            realm_updated = True

    _print_bootstrap_summary(
        installation_name=name,
        core_version=inventory_instance.version,
        admin_password=admin_password,
        core_ip=core_ip_result,
        ssh_public_key_path=ssh_public_key_path,
        ssh_private_key_path=ssh_private_key_path,
        realm_updated=realm_updated,
    )

    if settings:
        from exordos.cmd.settings.commands import init_config

        ctx.invoke(
            init_config,
        )
    return None


def _start_validation_type(start: str | None) -> time.struct_time | None:
    if start is None:
        return None

    try:
        return time.strptime(start, "%H:%M:%S")
    except ValueError:
        raise click.UsageError("Invalid '--start' format. Use HH:MM:SS, e.g., 16:00:00")


def _domains_for_backup(
    names: tp.List[str] | None = None,
    exclude_names: tp.List[str] | None = None,
    raise_on_domain_absence: bool = False,
) -> tp.List[str]:
    domains = set(libvirt.list_domains())
    names = set(names or [])
    exclude_names = set(exclude_names or [])

    # Check if the specified domains exist
    if raise_on_domain_absence and (names - domains):
        diff = ", ".join(names - domains)
        raise click.UsageError(f"Domains {diff} not found")

    if names:
        domains &= names

    if exclude_names:
        domains = {
            d
            for d in domains
            if not any(fnmatch.fnmatch(d, pattern) for pattern in exclude_names)
        }

    return list(domains)


@click.command("backup", help="Backup the current installation")
@click.option(
    "--config",
    default=None,
    type=click.Path(),
    help="Path to the backuper configuration file",
)
@click.option(
    "-n",
    "--name",
    default=None,
    multiple=True,
    help="Name of the libvirt domain, if not provided, all will be backed up",
)
@click.option(
    "-d",
    "--backup-dir",
    default=".",
    type=click.Path(),
    help="Directory where backups will be stored",
)
@click.option(
    "-p",
    "--period",
    default=BackupPeriod.D1.value,
    type=click.Choice([p.value for p in BackupPeriod]),
    show_default=True,
    help="the regularity of backups",
)
@click.option(
    "-o",
    "--offset",
    default=None,
    type=click.Choice([p.value for p in BackupPeriod]),
    show_default=True,
    help=(
        "The time offset of the first backup. If not provided, "
        "the same value as the period will be used"
    ),
)
@click.option(
    "--start",
    default=None,
    type=_start_validation_type,
    help=(
        "Time of day to start backup in format HH:MM:SS. "
        "Cannot be used together with --offset. If provided, "
        "period must be >= 1d."
    ),
)
@click.option(
    "--oneshot",
    show_default=True,
    is_flag=True,
    help="Do a backup once and exit",
)
@click.option(
    "-c",
    "--compress",
    show_default=True,
    is_flag=True,
    help="Compress the backup.",
)
@click.option(
    "-e",
    "--encrypt",
    show_default=True,
    is_flag=True,
    help=(
        "Encrypt the backup. Works only with the compress flag. "
        "Use environment variable to specify the encryption key "
        "and the initialization vector: "
        "GEN_DEV_BACKUP_KEY and GEN_DEV_BACKUP_IV"
    ),
)
@click.option(
    "-s",
    "--min-free-space",
    default=50,
    type=int,
    show_default=True,
    help=(
        "Free disk space shouldn't be lower than this threshold. "
        "If the space becomes lower, the backup process is stopped. "
        "The value is in GB."
    ),
)
@click.option(
    "-r",
    "--rotate",
    default=5,
    type=int,
    show_default=True,
    help=(
        "Maximum number of backups to keep. The oldest backups are deleted. "
        "`0` means no rotation."
    ),
)
@click.option(
    "--no",
    "--exclude-name",
    "exclude_name",
    multiple=True,
    help="Name or pattern of libvirt domains to exclude from backup",
)
def backup_cmd(
    config: str | None,
    name: tp.List[str] | None,
    exclude_name: tp.List[str] | None,
    backup_dir: str,
    period: str,
    offset: str | None,
    start: time.struct_time | None,
    oneshot: bool,
    compress: bool,
    encrypt: bool,
    min_free_space: int,
    rotate: int,
) -> None:
    period = BackupPeriod(period)
    if offset:
        offset = BackupPeriod(offset)

    # Forbid using both include and exclude options
    if name and exclude_name:
        raise click.UsageError(
            "Cannot specify both --name and --no/--exclude-name options at the same time."
        )

    # Default local backuper if no config is provided
    if config is None:
        backuper = backup_local.LocalQcowBackuper(
            backup_dir=backup_dir,
            min_free_disk_space_gb=min_free_space,
        )
    else:
        backuper = utils.load_driver(config)

    # Need to specify encryption key and initialization vector via
    # environment variables.
    if encrypt:
        try:
            backup_base.EncryptionCreds.validate_env()
        except ValueError:
            raise click.UsageError(
                (
                    "Define environment variables GEN_DEV_BACKUP_KEY "
                    "and GEN_DEV_BACKUP_IV. "
                    "Key and IV must be greater or equal than "
                    f"{backup_base.EncryptionCreds.MIN_LEN} bytes and less "
                    f"or equal to {backup_base.EncryptionCreds.LEN} bytes."
                )
            )

        encryption = backup_base.EncryptionCreds.from_env()
    else:
        encryption = None

    # Do a single backup and exit
    if oneshot:
        domains = _domains_for_backup(name, exclude_name, raise_on_domain_absence=True)
        backuper.backup(domains, compress, encryption)
        return

    # Do periodic backups
    click.secho(f"Current time: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    # The `start` option validation
    if start is None:
        # Default behavior: use offset (or period if offset not provided)
        offset = offset or period
        ts = time.time() + offset.timeout
        click.secho(
            f"Next backup at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))}"
        )
        time.sleep(offset.timeout)
    else:
        # Validate mutually exclusive options: --start and --offset
        if offset is not None:
            raise click.UsageError(
                "Options '--start' and '--offset' cannot be used together. "
                "Choose one. By default, --offset is used."
            )

        # If --start is specified, period must be at least daily
        if period.timeout < BackupPeriod.D1.timeout:
            raise click.UsageError(
                "The '--start' option requires the period to be at least 1 day (1d)."
            )

        start_sec = start.tm_hour * 3600 + start.tm_min * 60 + start.tm_sec
        now_ts = time.time()
        now = time.localtime(now_ts)
        now_sec = now.tm_hour * 3600 + now.tm_min * 60 + now.tm_sec

        if now_sec < start_sec:
            delta = start_sec - now_sec
        else:
            delta = 24 * 3600 - now_sec + start_sec

        ts = now_ts + delta
        click.secho(
            f"Next backup at: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ts))}"
        )
        time.sleep(delta)

    # Next runs happen every 'period' seconds from the aligned start
    next_ts = time.time() + period.timeout

    # Do periodic backups
    while True:
        # Need to refresh the list of domains since it could have changed
        domains = _domains_for_backup(name, exclude_name)

        click.secho(f"Backup started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        backuper.backup(domains, compress, encryption)
        click.secho(
            "Next backup at: "
            f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(next_ts))}"
        )

        # Rotate old backups
        backuper.rotate(rotate)

        timeout = next_ts - time.time()
        timeout = 0 if timeout < 0 else timeout
        next_ts += period.timeout

        time.sleep(timeout)


@click.command("backup-decrypt", help="Decrypt a backup file")
@click.argument("path", type=click.Path(exists=True))
def backup_decrypt_cmd(path: str) -> None:
    # Need to specify encryption key and initialization vector via
    # environment variables.

    try:
        backup_base.EncryptionCreds.validate_env()
    except ValueError:
        raise click.UsageError(
            (
                "Define environment variables GEN_DEV_BACKUP_KEY "
                "and GEN_DEV_BACKUP_IV. "
                "Key and IV must be greater or equal than "
                f"{backup_base.EncryptionCreds.MIN_LEN} bytes and less or "
                f"equal to {backup_base.EncryptionCreds.LEN} bytes."
            )
        )

    encryption = backup_base.EncryptionCreds.from_env()

    if os.path.isdir(path):
        for file in os.listdir(path):
            _path = os.path.join(path, file)
            utils.decrypt_file(
                _path,
                encryption.key,
                encryption.iv,
            )
            click.secho(f"The {_path} file has been decrypted.", fg="green")
        return

    utils.decrypt_file(
        path,
        encryption.key,
        encryption.iv,
    )
    click.secho(f"The {path} file has been decrypted.", fg="green")
