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

import base64
import configparser
import getpass
import io
import os
import secrets
import socket
import typing as tp
from urllib.parse import urlparse
import uuid as sys_uuid

import rich_click as click

from exordos import constants as c
from exordos import exceptions
from exordos import utils
from exordos.clients import base_client
from exordos.cmd.base import create_entity_group
from exordos.common.crypto import write_root_owned_file
from exordos.common.run import run_command
from exordos.common.run import runsh
from exordos.common.table import show_data
from exordos.infra.libvirt import libvirt
from exordos.logger import ClickLogger

DEFAULT_LOCAL_CONNECTION_URI = "qemu:///system"

# Namespace this command's derived UUIDs from, so they can't collide with
# UUIDs some other exordos component derives from the same source string
# (e.g. a DMI product UUID) via its own uuid5 namespace.
_HYPERVISOR_UUID_NAMESPACE = sys_uuid.UUID("6f7c9b0e-6e0a-4b7a-9b1e-6b6b8f3a2c1d")

# The universal agent that runs LocalPoolAgentDriver so this hypervisor's
# pool is actually managed. Named "universal_agent" by default, matching
# the exordos-base image's own standard agent - if this host is also a
# registered compute node, LocalPoolAgentDriver is merged into that
# existing agent instead of running a second, competing one. A custom
# --pool-agent-name runs a separate, dedicated agent under parallel paths
# instead (see _agent_*_path below), e.g. when the standard agent here
# is already configured for a different core and isn't ours to touch.
DEFAULT_AGENT_NAME = "universal_agent"
AGENT_CONFIG_DIR = "/etc/exordos_universal_agent"
STANDARD_AGENT_BIN_SYMLINK = "/usr/bin/exordos-universal-agent"

# Must match gcl_sdk's LocalPoolAgentDriver.get_capabilities() - pre-declaring
# them here lets the scheduler (which only considers agents already
# reporting the "pool" capability) place pools onto this agent right away,
# instead of waiting for its first self-registration after the systemd
# unit actually starts.
LOCAL_POOL_AGENT_CAPABILITIES = ["pool", "pool_volume", "pool_machine", "local_pool"]


def _agent_venv_path(agent_name: str) -> str:
    return f"/opt/{agent_name}/.venv"


def _agent_config_path(agent_name: str) -> str:
    return f"{AGENT_CONFIG_DIR}/exordos_{agent_name}.conf"


def _agent_work_dir(agent_name: str) -> str:
    return f"/var/lib/exordos/{agent_name}"


def _agent_unit_name(agent_name: str) -> str:
    return f"exordos-{agent_name.replace('_', '-')}.service"


def _agent_exec_path(agent_name: str, venv_path: str) -> str:
    # The standard agent is reached through its stable /usr/bin symlink
    # (matching the exordos-base image's own unit); a custom-named one
    # runs straight out of its own venv - it has no symlink to rely on,
    # and mustn't hijack the standard one since it may belong to an
    # agent this code isn't managing.
    if agent_name == DEFAULT_AGENT_NAME:
        return STANDARD_AGENT_BIN_SYMLINK
    return f"{venv_path}/bin/exordos-universal-agent"


STANDARD_AGENT_VENV_PATH = _agent_venv_path(DEFAULT_AGENT_NAME)
AGENT_CONFIG_PATH = _agent_config_path(DEFAULT_AGENT_NAME)
AGENT_WORK_DIR = _agent_work_dir(DEFAULT_AGENT_NAME)
AGENT_META_FILE = f"{AGENT_WORK_DIR}/pool_meta.json"
AGENT_PRIVATE_KEY_PATH = f"{AGENT_WORK_DIR}/private_key"
AGENT_SYSTEMD_UNIT_NAME = _agent_unit_name(DEFAULT_AGENT_NAME)
AGENT_SYSTEMD_UNIT_PATH = f"/etc/systemd/system/{AGENT_SYSTEMD_UNIT_NAME}"

# Ports the core's Orch/Status APIs are reachable on (exordos_core.conf.j2:
# [orch_api] bind_port = 11011, [status_api] bind_port = 11012; both bind
# 0.0.0.0, so reachable from this host over the main network).
ORCH_API_PORT = 11011
STATUS_API_PORT = 11012

ENTITY = "hypervisor"
ENTITY_COLLECTION = c.HYPERVISOR_COLLECTION

FIELDS_MAP = {
    "UUID": "uuid",
    "Name": "name",
    "Machine type": "machine_type",
    "All cores": "all_cores",
    "Avail cores": "avail_cores",
    "All ram": "all_ram",
    "Avail ram": "avail_ram",
    "Status": "status",
}


hypervisors_group = create_entity_group(ENTITY, ENTITY_COLLECTION, FIELDS_MAP)


@click.command("add", help="Add a new hypervisor")
@click.pass_context
@click.option(
    "-u",
    "--uuid",
    type=click.UUID,
    default=None,
    help="UUID of the hypervisor",
)
@click.option(
    "-n",
    "--name",
    type=str,
    default="hypervisor",
    help="Name of the hypervisor",
)
@click.option(
    "-D",
    "--description",
    type=str,
    default="",
    help="Description of the hypervisor",
)
@click.option(
    "--avail-cores",
    type=int,
    required=False,
)
@click.option(
    "--avail-ram",
    type=int,
    required=False,
)
@click.option(
    "--cores-ratio",
    type=float,
    required=False,
)
@click.option(
    "--ram-ratio",
    type=float,
    required=False,
)
@click.option(
    "-m",
    "--machine-type",
    required=False,
    type=click.Choice(["VM", "HW"], case_sensitive=False),
)
@click.option(
    "--driver-spec",
    multiple=True,
    help=(
        "Additional filters to pass to the api. "
        "The format is 'key=value'. For example: --driver-spec "
        "a=b --driver-spec e=f"
    ),
)
def add_cmd(
    ctx: click.Context,
    uuid: sys_uuid.UUID | None,
    name: str,
    description: str,
    avail_cores: int | None,
    avail_ram: int | None,
    cores_ratio: float | None,
    ram_ratio: float | None,
    machine_type: str | None,
    driver_spec: tuple[str, ...],
) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)
    if uuid is None:
        uuid = sys_uuid.uuid4()
    driver_spec = utils.convert_input_multiply(driver_spec)
    data: dict = {
        "uuid": str(uuid),
        "name": name,
        "description": description,
        "driver_spec": driver_spec,
    }
    if avail_cores is not None:
        data["avail_cores"] = avail_cores
    if avail_ram is not None:
        data["avail_ram"] = avail_ram
    if cores_ratio is not None:
        data["cores_ratio"] = cores_ratio
    if ram_ratio is not None:
        data["ram_ratio"] = ram_ratio
    if machine_type is not None:
        data["machine_type"] = machine_type
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
    default=None,
    help=f"Name of the {ENTITY}",
)
@click.option(
    "-D",
    "--description",
    type=str,
    default=None,
    help=f"Description of the {ENTITY}",
)
@click.option(
    "--avail-cores",
    type=int,
    required=False,
)
@click.option(
    "--avail-ram",
    type=int,
    required=False,
)
@click.option(
    "--cores-ratio",
    type=float,
    required=False,
)
@click.option(
    "--ram-ratio",
    type=float,
    required=False,
)
@click.option(
    "-m",
    "--machine-type",
    required=False,
    type=click.Choice(["VM", "HW"], case_sensitive=False),
)
@click.option(
    "--driver-spec",
    multiple=True,
    help=(
        "Driver Specification. "
        "The format is 'key=value'. For example: --driver-spec "
        "a=b --driver-spec e=f"
    ),
)
@click.option(
    "--driver-spec-full",
    multiple=True,
    help=(
        "Full Driver Specification. "
        "The format is 'key=value'. For example: --driver-spec-full "
        "a=b --driver-spec-full e=f"
    ),
)
def update_cmd(
    ctx: click.Context,
    uuid: sys_uuid.UUID,
    name: str | None,
    description: str,
    avail_cores: int | None,
    avail_ram: int | None,
    cores_ratio: float | None,
    ram_ratio: float | None,
    machine_type: str | None,
    driver_spec: tuple[str, ...],
    driver_spec_full: tuple[str, ...],
) -> None:
    client = base_client.get_user_api_client(ctx.obj.auth_data)
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    if avail_cores is not None:
        data["avail_cores"] = avail_cores
    if avail_ram is not None:
        data["avail_ram"] = avail_ram
    if cores_ratio is not None:
        data["cores_ratio"] = cores_ratio
    if ram_ratio is not None:
        data["ram_ratio"] = ram_ratio
    if machine_type is not None:
        data["machine_type"] = machine_type

    driver_spec = utils.convert_input_multiply(driver_spec)
    driver_spec_full = utils.convert_input_multiply(driver_spec_full)
    if driver_spec and driver_spec_full:
        raise click.ClickException(
            "Both --driver-spec and --driver-spec-full are set. Use only one."
        )
    if driver_spec_full:
        data["driver_spec"] = driver_spec_full
    elif driver_spec:
        hypervisor_data = base_client.get_entity(client, ENTITY_COLLECTION, uuid)
        current_spec = hypervisor_data.get("driver_spec") or {}
        data["driver_spec"] = {**current_spec, **driver_spec}

    entity = base_client.update_entity(client, ENTITY_COLLECTION, uuid, data)
    show_data(entity)


def is_root() -> bool:
    # os.geteuid() returns 0 if running as root/sudo
    return os.geteuid() == 0


def _install_packages(add_sudo: bool = False) -> None:
    """Install required Debian packages."""
    packages = [
        "qemu-system-x86",
        # qemu-system-x86 alone doesn't pull this in, but LibvirtPoolDriver's
        # generated domain XML uses spice graphics + qxl video - without
        # it libvirt rejects domain creation outright ("unsupported
        # configuration: domain configuration does not support video
        # model 'qxl'"), since QEMU itself doesn't report the device.
        "qemu-system-modules-spice",
        "qemu-utils",
        "libvirt-daemon-system",
        "libvirt-dev",
        "genisoimage",
        "unzip",
        "python3-venv",
        "libev-dev",
    ]
    cmd = ["apt-get", "update"]
    run_command(cmd, sudo=add_sudo)
    cmd = ["apt-get", "install", "-y"]
    cmd.extend(packages)
    run_command(cmd, env=dict(DEBIAN_FRONTEND="noninteractive"), sudo=add_sudo)


def generate_node_private_key_base64() -> str:
    """Generate a node encryption key for the local agent.

    Matches gcl_sdk's `agents.universal.api.crypto.generate_key_base64`
    (32 random bytes, base64-encoded) without depending on gcl_sdk itself,
    which the exordos CLI doesn't otherwise install.
    """
    return base64.b64encode(secrets.token_bytes(32)).decode()


def _agent_config_content(
    orch_endpoint: str,
    status_endpoint: str,
    meta_file: str,
    private_key_path: str,
) -> str:
    return f"""[universal_agent]
orch_secure_communication = True
orch_endpoint = {orch_endpoint}
status_endpoint = {status_endpoint}
private_key_path = {private_key_path}
caps_drivers = LocalPoolAgentDriver
verify_node_on_register = False

[LocalPoolAgentDriver]
meta_file = {meta_file}
"""


def read_with_sudo(path: str) -> str:
    """Read a file's content, falling back to `sudo cat` on PermissionError.

    Some files this command reads (e.g. an agent config containing a
    private_key_path, or product_uuid) may be root-only readable; this
    command is expected to run as a regular sudo-capable user, not as root.
    """
    try:
        with open(path) as f:
            return f.read()
    except PermissionError:
        return run_command(["sudo", "cat", path]).stdout


def _read_existing_config(config_path: str) -> str | None:
    """Return the agent config's content, or None if not installed yet."""
    if not os.path.exists(config_path):
        return None
    return read_with_sudo(config_path)


def _config_value(content: str, section: str, option: str, fallback: str) -> str:
    parser = configparser.ConfigParser()
    parser.read_string(content)
    return parser.get(section, option, fallback=fallback)


def _merge_local_pool_into_config(existing_content: str, meta_file: str) -> str:
    """Add LocalPoolAgentDriver to an already-installed agent's config.

    This host already runs the standard universal agent (it's also a
    registered compute node, provisioned from the exordos-base image),
    so the pool capability is appended to its existing caps_drivers and
    everything else (orch_endpoint, its own private_key_path, other
    drivers) is left untouched - one shared agent identity, not a
    second, competing one.
    """
    raw = _config_value(existing_content, "universal_agent", "caps_drivers", "")
    drivers = [d.strip() for d in raw.replace("\n", ",").split(",") if d.strip()]
    if "LocalPoolAgentDriver" not in drivers:
        drivers.append("LocalPoolAgentDriver")

    parser = configparser.ConfigParser()
    parser.read_string(existing_content)
    parser.set("universal_agent", "caps_drivers", ", ".join(drivers))
    if not parser.has_section("LocalPoolAgentDriver"):
        parser.add_section("LocalPoolAgentDriver")
    parser.set("LocalPoolAgentDriver", "meta_file", meta_file)

    buf = io.StringIO()
    parser.write(buf)
    return buf.getvalue()


def _agent_systemd_unit_content(exec_path: str, config_path: str) -> str:
    # ExecStart uses exec_path's full path rather than a bare command
    # name: relying on $PATH is fragile if some other
    # exordos-universal-agent happens to resolve first (e.g. a dev
    # checkout installed under /usr/local/bin, which typically precedes
    # /usr/bin in systemd's default PATH).
    return f"""[Unit]
Description=Exordos Universal Agent Service
After=network-online.target

[Service]
Restart=on-failure
RestartSec=5s
TimeoutStopSec=5
ExecStart={exec_path} --config-file {config_path}

[Install]
WantedBy=multi-user.target
"""


class AgentInstallTarget(tp.NamedTuple):
    venv_path: str
    exec_path: str
    config_path: str
    meta_file: str
    default_private_key_path: str
    unit_path: str
    unit_name: str


def _endpoint_identity(url: str) -> tuple[str, int | None]:
    """Resolve a URL's host to an IP, paired with its port.

    Lets an endpoint given as a DNS name (the exordos-base image's own
    convention, e.g. core.local.genesis-core.tech) and one given as a
    literal IP compare equal when they're actually the same core,
    instead of comparing the raw strings. Falls back to the raw
    hostname if resolution fails - erring towards "different core"
    (the safer default) rather than silently treating an unresolvable
    host as a match.
    """
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if host:
        try:
            host = socket.gethostbyname(host)
        except OSError:
            pass
    return host, parsed.port


def resolve_agent_install_target(
    agent_name: str, orch_endpoint: str, status_endpoint: str
) -> AgentInstallTarget:
    """Resolve the venv/config/unit paths for the named universal agent.

    Refuses (raises ClickException) if an agent config already exists
    under this name but for a *different* core - e.g. --pool-agent-name
    defaulted to the standard agent, but this host is a compute node
    managed by some other, unrelated exordos deployment. That agent
    isn't ours to reconfigure; the caller should pass --pool-agent-name
    to target a separate, dedicated agent instead.
    """
    venv_path = _agent_venv_path(agent_name)
    config_path = _agent_config_path(agent_name)
    work_dir = _agent_work_dir(agent_name)
    unit_name = _agent_unit_name(agent_name)

    existing = _read_existing_config(config_path)
    if existing is not None:
        existing_orch = _config_value(existing, "universal_agent", "orch_endpoint", "")
        existing_status = _config_value(
            existing, "universal_agent", "status_endpoint", ""
        )
        if _endpoint_identity(existing_orch) != _endpoint_identity(
            orch_endpoint
        ) or _endpoint_identity(existing_status) != _endpoint_identity(status_endpoint):
            raise click.ClickException(
                f"Agent '{agent_name}' ({config_path}) is already configured "
                f"for a different core (orch_endpoint={existing_orch!r}, "
                f"expected {orch_endpoint!r}). Pass --pool-agent-name to use "
                "a separate, dedicated agent instead of reconfiguring this one."
            )

    return AgentInstallTarget(
        venv_path=venv_path,
        exec_path=_agent_exec_path(agent_name, venv_path),
        config_path=config_path,
        meta_file=f"{work_dir}/pool_meta.json",
        default_private_key_path=f"{work_dir}/private_key",
        unit_path=f"/etc/systemd/system/{unit_name}",
        unit_name=unit_name,
    )


def install_agent_venv(venv_path: str = STANDARD_AGENT_VENV_PATH) -> None:
    """Install (or extend) the universal agent's venv with gcl_sdk[libvirt].

    A venv may already exist at this path - either the standard agent's
    (this host is also a registered compute node, provisioned from the
    exordos-base image) or a previous isolated install - in which case
    libvirt-python just needs adding, via sudo since the standard venv
    is root-owned. Otherwise a fresh one is created, owned by the
    current (non-root) user so future pip runs don't need elevation.
    The /usr/bin symlink is only (re)pointed at it when installing to
    the standard path - an isolated install must not hijack it, since
    it may belong to an agent this code isn't managing.
    """
    if os.path.isdir(venv_path):
        run_command(["sudo", f"{venv_path}/bin/pip", "install", "gcl_sdk[libvirt]"])
        return

    agent_home = os.path.dirname(venv_path)
    run_command(["sudo", "mkdir", "-p", agent_home])
    run_command(["sudo", "chown", getpass.getuser(), agent_home])
    run_command(["python3", "-m", "venv", venv_path])
    run_command([f"{venv_path}/bin/pip", "install", "gcl_sdk[libvirt]"])
    if venv_path == STANDARD_AGENT_VENV_PATH:
        run_command(
            [
                "sudo",
                "ln",
                "-sf",
                f"{venv_path}/bin/exordos-universal-agent",
                STANDARD_AGENT_BIN_SYMLINK,
            ]
        )


def write_agent_config(
    orch_endpoint: str,
    status_endpoint: str,
    config_path: str = AGENT_CONFIG_PATH,
    meta_file: str = AGENT_META_FILE,
    default_private_key_path: str = AGENT_PRIVATE_KEY_PATH,
) -> str:
    """Configure the universal agent to (also) run LocalPoolAgentDriver.

    If a config already exists here (this host already runs an agent
    for the same core), LocalPoolAgentDriver is merged into its
    caps_drivers instead of replacing the file. Otherwise a fresh,
    pool-only config is written; `verify_node_on_register` is disabled
    since a bare hypervisor host isn't itself a registered compute node.

    Returns the private_key_path this config ends up using, so the
    caller writes the key to the right place.
    """
    existing = _read_existing_config(config_path)

    if existing is None:
        private_key_path = default_private_key_path
        content = _agent_config_content(
            orch_endpoint, status_endpoint, meta_file, private_key_path
        )
    else:
        private_key_path = _config_value(
            existing, "universal_agent", "private_key_path", default_private_key_path
        )
        content = _merge_local_pool_into_config(existing, meta_file)

    # Explicit mode, not left to `sudo cp`'s default: a brand-new
    # destination inherits the source tempfile's mode (mkstemp -> 0600,
    # root-only - unreadable by this non-root process on the next run),
    # while an already-existing one keeps its own mode unchanged either
    # way. Relying on either makes the outcome depend on whether this
    # is the first write, so set it explicitly every time instead.
    write_root_owned_file(content, config_path, mode="644")
    return private_key_path


def reset_agent_meta_file(meta_file: str = AGENT_META_FILE) -> None:
    """Drop the local agent's cached pool/volume/machine state.

    A fresh `bootstrap` means a fresh core, so any resources the agent
    previously tracked (pool_machine/pool_volume uuids, pool references)
    belong to a core that no longer exists. Left in place, the agent
    tries to reconcile them against the new core and fails.
    """
    run_command(["sudo", "rm", "-f", meta_file])


def install_agent_systemd_unit(
    exec_path: str = STANDARD_AGENT_BIN_SYMLINK,
    config_path: str = AGENT_CONFIG_PATH,
    unit_path: str = AGENT_SYSTEMD_UNIT_PATH,
    unit_name: str = AGENT_SYSTEMD_UNIT_NAME,
) -> None:
    """Install (or re-install) and (re)start the universal agent's
    systemd service.

    Always (re)written: this template is a faithful, more robust
    version of the exordos-base image's own unit (same Restart/
    RestartSec/TimeoutStopSec, just a fully-qualified ExecStart), so
    overwriting a genuinely pre-existing standard unit is a no-op past
    that one difference - and skipping the write when a *stale* one
    from an earlier run of this same code is already in place would
    leave it stuck on outdated content instead of picking up fixes.
    """
    write_root_owned_file(
        _agent_systemd_unit_content(exec_path, config_path), unit_path, mode="644"
    )
    run_command(["sudo", "systemctl", "daemon-reload"])
    run_command(["sudo", "systemctl", "enable", unit_name])
    run_command(["sudo", "systemctl", "restart", unit_name])


def _add_user_to_groups(user: str | None, add_sudo: bool = False) -> None:
    """Add current user to libvirt and kvm groups."""
    users = []
    if user:
        users.append(user)
    current_username = os.environ.get("USER")
    if current_username and current_username not in users:
        users.append(current_username)

    for username in users:
        click.echo(f"Adding user {username} to libvirt and kvm groups")
        cmd = ["usermod", "-a", "-G", "libvirt", username]
        run_command(cmd, sudo=add_sudo)
        cmd = ["usermod", "-a", "-G", "kvm", username]
        run_command(cmd, sudo=add_sudo)


def _create_storage_pool(pool_name: str, add_sudo: bool = False) -> None:
    """Create libvirt storage pool if it doesn't exist."""
    # Check if pool exists
    result = runsh("virsh pool-list --all", sudo=add_sudo).raise_on_result()
    if pool_name not in result.output:
        # Create storage pool
        cmd = [
            "virsh",
            "pool-define-as",
            pool_name,
            "dir",
            "--target",
            "/var/lib/libvirt/images",
        ]
        run_command(cmd, sudo=add_sudo)
        cmd = ["virsh", "pool-build", pool_name]
        run_command(cmd, sudo=add_sudo)
        cmd = ["virsh", "pool-start", pool_name]
        run_command(cmd, sudo=add_sudo)
        cmd = ["virsh", "pool-autostart", pool_name]
        run_command(cmd, sudo=add_sudo)


def _ensure_local_networks(
    network_type: str,
    network: str,
    network_bridge: str | None,
    boot_network: str,
    boot_bridge: str | None,
) -> None:
    """Create this hypervisor's libvirt networks if missing.

    On a plain 'network'-type hypervisor (single-host/local testing, not
    reachable from the rest of the realm anyway), only the boot network
    is auto-created here, as an isolated network - the main network is
    left to the operator, same as before. Only 'bridge'-type creates
    both.

    `network` and `boot_network` are logical libvirt network names the
    orchestrator itself tracks and assigns to ports by (see
    exordos_core.compute.dm.models.Port.from_boot_network and the
    core's main-network Subnet, both created once by the stand's
    original bootstrap and never renamed per-hypervisor) - a machine
    scheduled to this hypervisor gets a port whose `source` is one of
    these exact names, regardless of what this hypervisor calls its own
    devices. Without a same-named local libvirt network, such machines
    immediately fail to start.

    On a 'bridge'-type hypervisor neither network is local/transient:
    the iPXE ROM's plain `dhcp` and the main network both need a real L2
    path to wherever the core's centrally-served DHCP actually listens.
    ISC dhcpd matches a request to a subnet declaration by the address
    of the interface it arrived on, and on the stand's original
    bootstrap host that's typically a dedicated NIC/bridge per network -
    so each logical network here is defined as a libvirt network that
    forwards onto its own bridge device (--network-bridge/--boot-bridge;
    each falls back to --network's bridge when not given, for a simpler
    single-bridge setup where they do share one L2).
    """
    if network_type != "bridge":
        if not libvirt.has_net(boot_network):
            libvirt.create_isolated_network(name=boot_network)
        return

    if not libvirt.has_net(network):
        libvirt.create_bridge_forward_network(
            name=network, bridge=network_bridge or network
        )

    if not libvirt.has_net(boot_network):
        libvirt.create_bridge_forward_network(
            name=boot_network, bridge=boot_bridge or network_bridge or network
        )


def _download_rom_file(version: str, add_sudo: bool = False) -> str:
    """Download ROM file if it doesn't exist."""
    rom_filename = "1af41041.rom"
    rom_path = f"/usr/share/qemu/{rom_filename}"
    if not os.path.exists(rom_path):
        runsh(
            f"wget -O {rom_path} --timeout=30 https://repo.exordos.com/seed_os/{version}/{rom_filename}",
            sudo=add_sudo,
        ).raise_on_result()

    else:
        click.echo(f"ROM file {rom_path} already exists")

    return rom_path


def _configure_libvirt(add_sudo: bool = False) -> None:
    """Configure libvirt to enable TCP connection."""
    config_file = "/etc/libvirt/libvirtd.conf"

    # Read existing config
    try:
        content = run_command(["cat", config_file], sudo=add_sudo).stdout
    except FileNotFoundError:
        raise click.ClickException(f"Config file not found: {config_file}")

    # Add required lines if not present
    required_lines = ["listen_tcp = 1", 'listen_addr = "0.0.0.0"', 'auth_tcp = "none"']

    for line in required_lines:
        if line not in content:
            content += f"\n{line}"

    # Write back to file
    run_command(["tee", config_file], sudo=add_sudo, run_input=content)

    # Restart services
    cmd = ["systemctl", "stop", "libvirtd"]
    run_command(cmd, sudo=add_sudo)
    cmd = ["systemctl", "enable", "--now", "libvirtd-tcp.socket"]
    run_command(cmd, sudo=add_sudo)
    cmd = ["systemctl", "start", "libvirtd"]
    run_command(cmd, sudo=add_sudo)


def _check_debian_like():
    """Check if the OS is Debian-like."""
    try:
        with open("/etc/os-release", "r") as f:
            content = f.read()
            if "Debian" in content or "Ubuntu" in content or "Kali" in content:
                return True
    except FileNotFoundError:
        pass

    try:
        with open("/etc/debian_version", "r") as f:
            f.read()
            return True
    except FileNotFoundError:
        pass

    return False


def _install_packer(add_sudo: bool = False) -> None:
    """Install packer."""

    try:
        run_command(["which", "packer"], sudo=add_sudo)
        click.echo("Packer is already installed")
        return None
    except Exception:
        pass

    cmd = ["mkdir", "-p", "/opt/packer"]
    run_command(cmd, sudo=add_sudo)
    # Version 1.9.2 is the latest free
    cmd = [
        "wget",
        "https://hashicorp-releases.yandexcloud.net/packer/1.9.2/packer_1.9.2_linux_amd64.zip",
        "-P",
        "/opt/packer",
    ]
    run_command(cmd, sudo=add_sudo)
    cmd = ["unzip", "/opt/packer/packer_1.9.2_linux_amd64.zip", "-d", "/opt/packer"]
    run_command(cmd, sudo=add_sudo)
    cmd = ["mv", "/opt/packer/packer", "/usr/local/bin/"]
    run_command(cmd, sudo=add_sudo)
    cmd = ["/usr/local/bin/packer", "-version"]
    run_command(cmd, sudo=add_sudo)
    return None


def _detect_local_cores() -> int:
    """Detect the number of logical CPU cores available on this machine."""
    return os.cpu_count() or 1


def _detect_local_ram_mb(meminfo_path: str = "/proc/meminfo") -> int:
    """Detect the total RAM, in Mb, available on this machine."""
    with open(meminfo_path) as f:
        for line in f:
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) // 1024

    raise click.ClickException(f"Unable to determine total RAM from {meminfo_path}")


def _default_hypervisor_uuid(
    product_uuid_path: str = "/sys/class/dmi/id/product_uuid",
) -> sys_uuid.UUID:
    """Derive a stable UUID for this machine from its DMI product UUID.

    Used when --uuid isn't given, so this machine always registers under
    the same hypervisor UUID. /etc/machine-id doesn't work for this once
    baremetal nodes are image-provisioned too: nodes cloned from the same
    image end up with the same machine-id. The DMI product UUID is
    burned into hardware/firmware instead, so it stays distinct per host
    - and it's convenient for debugging, since it's also the value an
    operator can read straight off the hardware. It's re-hashed through
    uuid5 (rather than parsed as a UUID directly) so an oddly-formatted
    or placeholder DMI value still yields a valid, stable UUID.

    This only distinguishes physical hosts: a VM cloned from a shared
    template/snapshot can carry the same product UUID as its siblings
    (the hypervisor copies it into the guest's SMBIOS from the image),
    so this doesn't dedupe image-provisioned VMs, only image-provisioned
    baremetal.
    """
    try:
        product_uuid = read_with_sudo(product_uuid_path).strip()
        return sys_uuid.uuid5(_HYPERVISOR_UUID_NAMESPACE, product_uuid)
    except (OSError, exceptions.RunException):
        return sys_uuid.uuid4()


def _default_hypervisor_name() -> str:
    """Default hypervisor name: this machine's hostname."""
    return socket.gethostname() or "hypervisor"


def local_agent_node_uuid(
    node_id_path: str = "/var/lib/exordos/node-id",
    product_uuid_path: str = "/sys/class/dmi/id/product_uuid",
) -> str:
    """Return this machine's node uuid.

    Matches gcl_sdk.agents.universal.utils.node_uuid(), so a local pool's
    driver_spec.node lines up with the node uuid the local universal agent
    (LocalPoolAgentDriver) will report for itself.
    """
    path = node_id_path if os.path.exists(node_id_path) else product_uuid_path
    try:
        return read_with_sudo(path).strip()
    except FileNotFoundError:
        raise click.ClickException(
            f"Unable to determine this machine's node uuid: neither "
            f"{node_id_path} nor {product_uuid_path} exists."
        )


@hypervisors_group.command("init", help="Initialize hypervisor")
@click.option(
    "--romfile-version",
    type=str,
    default="latest",
    help="version of the rom file",
)
@click.option(
    "--pool-name",
    type=str,
    default="default",
    help="storage pool name",
)
@click.option(
    "-p",
    "--packer",
    show_default=True,
    is_flag=True,
    default=False,
    help="Install packer",
)
@click.option(
    "--user",
    type=str,
    required=False,
    help="username",
)
@click.option(
    "--add",
    show_default=True,
    is_flag=True,
    default=False,
    help=(
        "After initialization, register the hypervisor in the orchestrator "
        "(same as running `hypervisors add`), using the top-level "
        "`exordos --endpoint/--user/--password` credentials. --uuid/--name/"
        "--description/--avail-cores/--avail-ram/--cores-ratio/--ram-ratio/"
        "--machine-type/--iface-mtu/--machine-prefix only apply in this "
        "mode. --network/--network-type/--network-bridge/--boot-network/"
        "--boot-bridge always set up this host's local libvirt networks "
        "regardless of --add, and additionally feed the registered "
        "driver_spec when combined with it."
    ),
)
@click.option(
    "-u",
    "--uuid",
    type=click.UUID,
    default=None,
    help=(
        "UUID of the hypervisor. Defaults to a UUID derived from "
        "/etc/machine-id, so this machine always registers under the same "
        "hypervisor UUID."
    ),
)
@click.option(
    "-n",
    "--name",
    type=str,
    default=None,
    help="Name of the hypervisor. Defaults to this machine's hostname.",
)
@click.option(
    "-D",
    "--description",
    type=str,
    default="",
    help="Description of the hypervisor",
)
@click.option(
    "--avail-cores",
    type=int,
    default=None,
    help=(
        "Number of CPU cores available for VMs on this hypervisor. "
        "Auto-detected from the local machine if not set."
    ),
)
@click.option(
    "--avail-ram",
    type=int,
    default=None,
    help=(
        "Amount of RAM in Mb available for VMs on this hypervisor. "
        "Auto-detected from the local machine if not set."
    ),
)
@click.option(
    "--cores-ratio",
    type=float,
    default=None,
)
@click.option(
    "--ram-ratio",
    type=float,
    default=None,
)
@click.option(
    "-m",
    "--machine-type",
    type=click.Choice(["VM", "HW"], case_sensitive=False),
    default=None,
)
@click.option(
    "--connection-uri",
    type=str,
    default=DEFAULT_LOCAL_CONNECTION_URI,
    show_default=True,
    help=(
        "Connection URI the orchestrator will use to reach this hypervisor. "
        "Hypervisors are expected to only run VMs local to themselves, so "
        "the default connects over the local libvirt Unix socket. Override "
        "only for backward compatibility or exotic setups, e.g. "
        "'qemu+tcp://10.0.0.1/system' for remote access."
    ),
)
@click.option(
    "--network",
    type=str,
    default="exordos-core-net",
    show_default=True,
    help=(
        "Name of the libvirt network used for VMs on this hypervisor - "
        "this is the logical name the orchestrator itself assigns ports "
        "by (see the stand's original bootstrap), not necessarily a "
        "literal host device. Don't rename it unless the orchestrator's "
        "own main network is actually named differently. For "
        "--network-type bridge, --network-bridge names the real "
        "underlying device."
    ),
)
@click.option(
    "--network-type",
    type=click.Choice(["network", "bridge"], case_sensitive=False),
    default="network",
    show_default=True,
    help="Type of the libvirt network used for VMs on this hypervisor",
)
@click.option(
    "--network-bridge",
    type=str,
    default=None,
    help=(
        "Host bridge device --network forwards onto. Only used when "
        "--network-type is 'bridge'; defaults to --network's own value "
        "if not given (i.e. the local libvirt network and the host "
        "bridge device happen to share one name)."
    ),
)
@click.option(
    "--boot-network",
    type=str,
    default="exordos-core-boot-net",
    show_default=True,
    help=(
        "Name of the libvirt network new machines PXE-boot on before "
        "getting their real network port. DHCP (with the PXE next-server "
        "option) for it is served centrally over the realm's shared L2, "
        "the same way as for --network - not by anything local to this "
        "host."
    ),
)
@click.option(
    "--boot-bridge",
    type=str,
    default=None,
    help=(
        "Host bridge device the boot network forwards onto, if it's a "
        "different L2 than --network's bridge (e.g. the stand's bootstrap "
        "host reaches the boot subnet's DHCP over a separate NIC from the "
        "main one). Only used when --network-type is 'bridge'; defaults "
        "to --network's bridge if not given."
    ),
)
@click.option(
    "--iface-mtu",
    type=int,
    default=1500,
    show_default=True,
    help="MTU for the VM network interface",
)
@click.option(
    "--machine-prefix",
    type=str,
    default="vm-",
    show_default=True,
    help="Prefix for VM names created on this hypervisor",
)
@click.option(
    "--pool-agent-name",
    "agent_name",
    type=str,
    default=DEFAULT_AGENT_NAME,
    show_default=True,
    help=(
        "Name of the universal agent to run LocalPoolAgentDriver under. "
        "The default targets the standard agent (merging in if this host "
        "is also a registered compute node). Use a different name to run "
        "a separate, dedicated agent instead - required if the standard "
        "agent here is already configured for a different core."
    ),
)
@click.pass_context
def init_cmd(
    ctx: click.Context,
    romfile_version: str,
    pool_name: str,
    packer: bool,
    user: str | None,
    add: bool,
    uuid: sys_uuid.UUID | None,
    name: str | None,
    description: str,
    avail_cores: int | None,
    avail_ram: int | None,
    cores_ratio: float | None,
    ram_ratio: float | None,
    machine_type: str | None,
    connection_uri: str,
    network: str,
    network_type: str,
    network_bridge: str | None,
    boot_network: str,
    boot_bridge: str | None,
    iface_mtu: int,
    machine_prefix: str,
    agent_name: str,
) -> None:
    """Initialize hypervisor with all required components."""

    if not _check_debian_like():
        raise click.ClickException(
            "This command is only supported on Debian-based systems."
        )

    import subprocess

    if subprocess.call(["sudo", "-n", "true"], stderr=subprocess.DEVNULL) != 0:
        click.secho("Sudo privileges are required to proceed.", fg="yellow")
        if subprocess.call(["sudo", "-v"]) != 0:
            raise click.ClickException("Failed to obtain sudo privileges. Aborting.")

    log = ClickLogger()

    log.info("Installing required packages...")

    add_sudo = not is_root()

    _install_packages(add_sudo)

    core_host = urlparse(ctx.obj.auth_data["endpoint"]).hostname
    orch_endpoint = f"http://{core_host}:{ORCH_API_PORT}"
    status_endpoint = f"http://{core_host}:{STATUS_API_PORT}"
    agent_target = resolve_agent_install_target(
        agent_name=agent_name,
        orch_endpoint=orch_endpoint,
        status_endpoint=status_endpoint,
    )

    log.info("Setting up the local universal agent's virtualenv...")
    install_agent_venv(agent_target.venv_path)

    log.info("Adding user to required groups...")
    _add_user_to_groups(user, add_sudo)

    log.info("Setting up storage pool...")
    _create_storage_pool(pool_name, add_sudo)

    log.info("Setting up the local boot network...")
    _ensure_local_networks(
        network_type, network, network_bridge, boot_network, boot_bridge
    )

    log.info("Checking ROM file...")
    rom_path = _download_rom_file(romfile_version)

    if connection_uri != DEFAULT_LOCAL_CONNECTION_URI:
        log.info("Configuring libvirt for remote access...")
        _configure_libvirt(add_sudo)
    else:
        log.info("Using the local libvirt socket, skipping remote TCP setup.")

    if packer:
        log.info("Configuring packer...")
        _install_packer()

    if add:
        log.info("Registering hypervisor...")
        final_avail_cores = (
            avail_cores if avail_cores is not None else _detect_local_cores()
        )
        final_avail_ram = avail_ram if avail_ram is not None else _detect_local_ram_mb()
        final_uuid = uuid if uuid is not None else _default_hypervisor_uuid()
        final_name = name if name is not None else _default_hypervisor_name()
        if connection_uri == DEFAULT_LOCAL_CONNECTION_URI:
            # This machine is the hypervisor: pin the pool to the local
            # universal agent (LocalPoolAgentDriver) by node uuid, since
            # exordos_local_hyper pools are only scheduled to the agent
            # whose node matches (compute/scheduler/service.py).
            kind_fields = (
                "kind=exordos_local_hyper",
                f"node={local_agent_node_uuid()}",
            )
        else:
            kind_fields = ("kind=libvirt",)
        driver_spec = kind_fields + (
            f"network={network}",
            f"iface_mtu={iface_mtu}",
            f"network_type={network_type}",
            f"storage_pool={pool_name}",
            f"connection_uri={connection_uri}",
            f"iface_rom_file={rom_path}",
            f"machine_prefix={machine_prefix}",
        )
        # Same as running `hypervisors add` right after `init`.
        ctx.invoke(
            add_cmd,
            uuid=final_uuid,
            name=final_name,
            description=description,
            driver_spec=driver_spec,
            avail_cores=final_avail_cores,
            avail_ram=final_avail_ram,
            cores_ratio=cores_ratio,
            ram_ratio=ram_ratio,
            machine_type=machine_type,
        )

        if connection_uri == DEFAULT_LOCAL_CONNECTION_URI:
            log.info("Setting up the local universal agent...")
            client = base_client.get_user_api_client(ctx.obj.auth_data)
            node_uuid = local_agent_node_uuid()
            reset_agent_meta_file(agent_target.meta_file)
            private_key_path = write_agent_config(
                orch_endpoint=orch_endpoint,
                status_endpoint=status_endpoint,
                config_path=agent_target.config_path,
                meta_file=agent_target.meta_file,
                default_private_key_path=agent_target.default_private_key_path,
            )
            base_client.register_agent_and_write_key(
                client,
                node_uuid,
                private_key_path,
                capabilities=LOCAL_POOL_AGENT_CAPABILITIES,
            )
            install_agent_systemd_unit(
                exec_path=agent_target.exec_path,
                config_path=agent_target.config_path,
                unit_path=agent_target.unit_path,
                unit_name=agent_target.unit_name,
            )

    log.important("Hypervisor environment initialized successfully")


hypervisors_group.add_command(add_cmd, aliases=["a"])
hypervisors_group.add_command(update_cmd, aliases=["u"])
