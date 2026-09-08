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
import base64
import configparser
import contextlib
import getpass
from unittest.mock import MagicMock
from unittest.mock import call as mock_call
from unittest.mock import patch

import click
from click.testing import CliRunner
import pytest

from exordos.cmd.compute.hypervisors import commands as hv_commands
from exordos.common import crypto
from exordos.common.cmd_context import ContextObject


def _obj(auth_data: dict | None = None) -> ContextObject:
    return ContextObject(
        auth_data=auth_data or {},
        cfg_path=None,
        developer_key_path=None,
        cfg={},
        need_update=None,
    )


_FAKE_AGENT_TARGET = hv_commands.AgentInstallTarget(
    venv_path="/opt/universal_agent/.venv",
    exec_path="/usr/bin/exordos-universal-agent",
    config_path="/etc/exordos_universal_agent/exordos_universal_agent.conf",
    meta_file="/var/lib/exordos/universal_agent/pool_meta.json",
    default_private_key_path="/var/lib/exordos/universal_agent/private_key",
    unit_path="/etc/systemd/system/exordos-universal-agent.service",
    unit_name="exordos-universal-agent.service",
)


@contextlib.contextmanager
def _patch_common_init_deps():
    """Patch the init_cmd dependencies almost every test below mocks but
    never asserts on by name, bundled into one context manager to stay
    under Python's nested `with (...)` item limit."""
    with (
        patch.object(hv_commands, "_check_debian_like", return_value=True),
        patch("subprocess.call", return_value=0),
        patch.object(hv_commands, "_install_packages"),
        patch.object(hv_commands, "_add_user_to_groups"),
        patch.object(hv_commands, "_create_storage_pool"),
        patch.object(hv_commands, "_ensure_local_networks"),
        patch.object(
            hv_commands,
            "_download_rom_file",
            return_value="/usr/share/qemu/1af41041.rom",
        ),
    ):
        yield


class TestDetectLocalResources:
    """Tests for exordos.cmd.compute.hypervisors.commands._detect_local_cores
    and _detect_local_ram_mb.
    """

    def test_detect_local_cores_uses_os_cpu_count(self) -> None:
        with patch.object(hv_commands.os, "cpu_count", return_value=4):
            assert hv_commands._detect_local_cores() == 4

    def test_detect_local_cores_falls_back_to_one(self) -> None:
        with patch.object(hv_commands.os, "cpu_count", return_value=None):
            assert hv_commands._detect_local_cores() == 1

    def test_detect_local_ram_mb_parses_meminfo(self, tmp_path) -> None:
        meminfo = tmp_path / "meminfo"
        meminfo.write_text("MemTotal:       16384000 kB\nMemFree:        1000 kB\n")

        assert hv_commands._detect_local_ram_mb(str(meminfo)) == 16384000 // 1024

    def test_detect_local_ram_mb_raises_when_missing(self, tmp_path) -> None:
        meminfo = tmp_path / "meminfo"
        meminfo.write_text("MemFree:        1000 kB\n")

        with pytest.raises(click.ClickException, match="Unable to determine"):
            hv_commands._detect_local_ram_mb(str(meminfo))


class TestDefaultHypervisorUuid:
    """Tests for
    exordos.cmd.compute.hypervisors.commands._default_hypervisor_uuid.
    """

    def test_derives_stable_uuid_from_product_uuid(self, tmp_path) -> None:
        product_uuid_path = tmp_path / "product_uuid"
        product_uuid_path.write_text("4c4c4544-0034-3010-8035-b9c04f503432\n")

        result = hv_commands._default_hypervisor_uuid(str(product_uuid_path))

        assert result == hv_commands.sys_uuid.uuid5(
            hv_commands._HYPERVISOR_UUID_NAMESPACE,
            "4c4c4544-0034-3010-8035-b9c04f503432",
        )

    def test_same_product_uuid_yields_the_same_uuid(self, tmp_path) -> None:
        product_uuid_path = tmp_path / "product_uuid"
        product_uuid_path.write_text("4c4c4544-0034-3010-8035-b9c04f503432")

        first = hv_commands._default_hypervisor_uuid(str(product_uuid_path))
        second = hv_commands._default_hypervisor_uuid(str(product_uuid_path))

        assert first == second

    def test_falls_back_to_random_uuid_when_missing(self, tmp_path) -> None:
        missing_path = tmp_path / "does-not-exist"

        result = hv_commands._default_hypervisor_uuid(str(missing_path))

        assert isinstance(result, hv_commands.sys_uuid.UUID)

    def test_yields_a_valid_uuid_even_for_a_placeholder_dmi_value(
        self, tmp_path
    ) -> None:
        # Some hypervisors/BIOSes report a placeholder like this instead
        # of a real product UUID - it must still hash into a valid UUID
        # rather than crash the command.
        product_uuid_path = tmp_path / "product_uuid"
        product_uuid_path.write_text("Not Settable")

        result = hv_commands._default_hypervisor_uuid(str(product_uuid_path))

        assert isinstance(result, hv_commands.sys_uuid.UUID)

    def test_falls_back_to_sudo_cat_on_permission_error(self, tmp_path) -> None:
        # product_uuid is typically root-only readable; this command runs
        # as a regular sudo-capable user, not root.
        product_uuid_path = tmp_path / "product_uuid"
        product_uuid_path.write_text("4c4c4544-0034-3010-8035-b9c04f503432\n")

        fake_result = MagicMock(stdout="4c4c4544-0034-3010-8035-b9c04f503432\n")
        with (
            patch.object(hv_commands, "open", side_effect=PermissionError, create=True),
            patch.object(
                hv_commands, "run_command", return_value=fake_result
            ) as run_mock,
        ):
            result = hv_commands._default_hypervisor_uuid(str(product_uuid_path))

        assert result == hv_commands.sys_uuid.uuid5(
            hv_commands._HYPERVISOR_UUID_NAMESPACE,
            "4c4c4544-0034-3010-8035-b9c04f503432",
        )
        run_mock.assert_called_once_with(["sudo", "cat", str(product_uuid_path)])

    def test_falls_back_to_random_uuid_when_sudo_cat_also_fails(self, tmp_path) -> None:
        # A hardened system where even sudo can't read the file must fall
        # back too, rather than crashing the command.
        product_uuid_path = tmp_path / "product_uuid"
        product_uuid_path.write_text("4c4c4544-0034-3010-8035-b9c04f503432")

        with (
            patch.object(hv_commands, "open", side_effect=PermissionError, create=True),
            patch.object(
                hv_commands,
                "run_command",
                side_effect=hv_commands.exceptions.RunException("sudo cat failed"),
            ),
        ):
            result = hv_commands._default_hypervisor_uuid(str(product_uuid_path))

        assert isinstance(result, hv_commands.sys_uuid.UUID)


class TestDefaultHypervisorName:
    """Tests for
    exordos.cmd.compute.hypervisors.commands._default_hypervisor_name.
    """

    def test_uses_hostname(self) -> None:
        with patch.object(hv_commands.socket, "gethostname", return_value="host-1"):
            assert hv_commands._default_hypervisor_name() == "host-1"

    def test_falls_back_when_hostname_empty(self) -> None:
        with patch.object(hv_commands.socket, "gethostname", return_value=""):
            assert hv_commands._default_hypervisor_name() == "hypervisor"


class TestLocalAgentNodeUuid:
    """Tests for local_agent_node_uuid: node-id file, DMI product_uuid
    fallback, and the case where neither exists.
    """

    def test_reads_node_id_file_when_present(self, tmp_path) -> None:
        node_id_path = tmp_path / "node-id"
        node_id_path.write_text("some-node-uuid\n")

        result = hv_commands.local_agent_node_uuid(
            node_id_path=str(node_id_path),
            product_uuid_path=str(tmp_path / "product_uuid"),
        )

        assert result == "some-node-uuid"

    def test_falls_back_to_product_uuid_when_node_id_missing(self, tmp_path) -> None:
        product_uuid_path = tmp_path / "product_uuid"
        product_uuid_path.write_text("some-product-uuid\n")

        result = hv_commands.local_agent_node_uuid(
            node_id_path=str(tmp_path / "node-id"),
            product_uuid_path=str(product_uuid_path),
        )

        assert result == "some-product-uuid"

    def test_falls_back_to_sudo_cat_on_permission_error(self, tmp_path) -> None:
        # product_uuid is typically root-only readable; this command runs
        # as a regular sudo-capable user, not root.
        product_uuid_path = tmp_path / "product_uuid"
        product_uuid_path.write_text("some-product-uuid\n")

        fake_result = MagicMock(stdout="some-product-uuid\n")
        with (
            patch.object(hv_commands, "open", side_effect=PermissionError, create=True),
            patch.object(
                hv_commands, "run_command", return_value=fake_result
            ) as run_mock,
        ):
            result = hv_commands.local_agent_node_uuid(
                node_id_path=str(tmp_path / "node-id"),
                product_uuid_path=str(product_uuid_path),
            )

        assert result == "some-product-uuid"
        run_mock.assert_called_once_with(["sudo", "cat", str(product_uuid_path)])

    def test_raises_a_clean_error_when_neither_path_exists(self, tmp_path) -> None:
        with pytest.raises(click.ClickException, match="Unable to determine"):
            hv_commands.local_agent_node_uuid(
                node_id_path=str(tmp_path / "node-id"),
                product_uuid_path=str(tmp_path / "product_uuid"),
            )


class TestInitCmdRegistration:
    """Tests for exordos.cmd.compute.hypervisors.commands.init_cmd: the
    always-on dependency install, and the --add-gated registration step.
    """

    def test_install_agent_venv_always_called(self) -> None:
        """install_agent_venv() must run regardless of --add: installing
        gcl_sdk[libvirt] is plain dependency setup, it doesn't need an
        orchestrator connection.
        """
        runner = CliRunner()
        with (
            _patch_common_init_deps(),
            patch.object(hv_commands, "install_agent_venv") as venv_mock,
            patch.object(
                hv_commands,
                "resolve_agent_install_target",
                return_value=_FAKE_AGENT_TARGET,
            ),
            patch.object(hv_commands, "_configure_libvirt"),
            patch.object(hv_commands.base_client, "add_entity"),
        ):
            result = runner.invoke(
                hv_commands.init_cmd,
                [],
                obj=_obj(auth_data={"endpoint": "http://10.20.0.2/api/core"}),
            )

        assert result.exit_code == 0, result.output
        venv_mock.assert_called_once_with(_FAKE_AGENT_TARGET.venv_path)

    def test_without_add_skips_registration_and_libvirt_config(self) -> None:
        runner = CliRunner()
        with (
            _patch_common_init_deps(),
            patch.object(hv_commands, "install_agent_venv"),
            patch.object(
                hv_commands,
                "resolve_agent_install_target",
                return_value=_FAKE_AGENT_TARGET,
            ),
            patch.object(hv_commands, "_configure_libvirt") as configure_libvirt_mock,
            patch.object(hv_commands.base_client, "add_entity") as add_entity_mock,
        ):
            result = runner.invoke(
                hv_commands.init_cmd,
                [],
                obj=_obj(auth_data={"endpoint": "http://10.20.0.2/api/core"}),
            )

        assert result.exit_code == 0, result.output
        configure_libvirt_mock.assert_not_called()
        add_entity_mock.assert_not_called()

    def test_add_invokes_add_cmd_directly(self) -> None:
        """`init --add` must work like `init && add`: it forwards straight
        to add_cmd, with no get-then-update-if-exists indirection.
        """
        runner = CliRunner()
        with (
            _patch_common_init_deps(),
            patch.object(hv_commands, "install_agent_venv"),
            patch.object(
                hv_commands,
                "resolve_agent_install_target",
                return_value=_FAKE_AGENT_TARGET,
            ),
            patch.object(hv_commands, "_configure_libvirt"),
            patch.object(hv_commands, "_detect_local_cores", return_value=8),
            patch.object(hv_commands, "_detect_local_ram_mb", return_value=16384),
            patch.object(
                hv_commands, "local_agent_node_uuid", return_value="node-uuid"
            ),
            patch.object(hv_commands, "add_cmd") as add_cmd_mock,
            patch.object(hv_commands.base_client, "get_user_api_client"),
            patch.object(hv_commands, "reset_agent_meta_file"),
            patch.object(hv_commands, "write_agent_config"),
            patch.object(hv_commands.base_client, "register_agent_and_write_key"),
            patch.object(hv_commands, "install_agent_systemd_unit"),
        ):
            result = runner.invoke(
                hv_commands.init_cmd,
                ["--add"],
                obj=_obj(auth_data={"endpoint": "http://10.20.0.2/api/core"}),
            )

        assert result.exit_code == 0, result.output
        add_cmd_mock.assert_called_once()
        kwargs = add_cmd_mock.call_args.kwargs
        assert kwargs["avail_cores"] == 8
        assert kwargs["avail_ram"] == 16384
        assert "kind=exordos_local_hyper" in kwargs["driver_spec"]

    def test_add_local_hyper_fetches_and_deploys_agent_private_key(self) -> None:
        """A local hypervisor's `init --add` must register this host's
        universal agent and deploy its node's encryption key to the
        local agent, same as `bootstrap` does, so the agent can talk
        to orch/status over encrypted communication.
        """
        runner = CliRunner()
        entity_uuid = "8d10a674-b454-4edb-a94f-f46b38b910d2"
        fake_client = MagicMock()
        auth_data = {"endpoint": "http://10.100.0.2/api/core", "username": "admin"}
        with (
            _patch_common_init_deps(),
            patch.object(hv_commands, "install_agent_venv"),
            patch.object(
                hv_commands,
                "resolve_agent_install_target",
                return_value=_FAKE_AGENT_TARGET,
            ),
            patch.object(hv_commands, "_configure_libvirt"),
            patch.object(hv_commands, "_detect_local_cores", return_value=8),
            patch.object(hv_commands, "_detect_local_ram_mb", return_value=16384),
            patch.object(
                hv_commands, "local_agent_node_uuid", return_value="node-uuid"
            ),
            patch.object(
                hv_commands.base_client,
                "get_user_api_client",
                return_value=fake_client,
            ),
            patch.object(
                hv_commands.base_client,
                "add_entity",
                return_value={"uuid": entity_uuid},
            ),
            patch.object(
                hv_commands.base_client, "register_agent_and_write_key"
            ) as register_and_write_mock,
            patch.object(hv_commands, "show_data"),
            patch.object(hv_commands, "reset_agent_meta_file") as reset_meta_mock,
            patch.object(
                hv_commands,
                "write_agent_config",
                return_value="/var/lib/exordos/universal_agent/private_key",
            ) as write_config_mock,
            patch.object(
                hv_commands, "install_agent_systemd_unit"
            ) as install_unit_mock,
        ):
            result = runner.invoke(
                hv_commands.init_cmd,
                ["--add", "--uuid", entity_uuid],
                obj=_obj(auth_data=auth_data),
            )

        assert result.exit_code == 0, result.output
        reset_meta_mock.assert_called_once_with(_FAKE_AGENT_TARGET.meta_file)
        write_config_mock.assert_called_once_with(
            orch_endpoint=f"http://10.100.0.2:{hv_commands.ORCH_API_PORT}",
            status_endpoint=f"http://10.100.0.2:{hv_commands.STATUS_API_PORT}",
            config_path=_FAKE_AGENT_TARGET.config_path,
            meta_file=_FAKE_AGENT_TARGET.meta_file,
            default_private_key_path=_FAKE_AGENT_TARGET.default_private_key_path,
        )
        register_and_write_mock.assert_called_once_with(
            fake_client,
            "node-uuid",
            "/var/lib/exordos/universal_agent/private_key",
            capabilities=hv_commands.LOCAL_POOL_AGENT_CAPABILITIES,
        )
        install_unit_mock.assert_called_once_with(
            exec_path=_FAKE_AGENT_TARGET.exec_path,
            config_path=_FAKE_AGENT_TARGET.config_path,
            unit_path=_FAKE_AGENT_TARGET.unit_path,
            unit_name=_FAKE_AGENT_TARGET.unit_name,
        )

    def test_add_without_connection_uri_or_name_uses_defaults(self) -> None:
        runner = CliRunner()
        with (
            _patch_common_init_deps(),
            patch.object(hv_commands, "install_agent_venv"),
            patch.object(
                hv_commands,
                "resolve_agent_install_target",
                return_value=_FAKE_AGENT_TARGET,
            ),
            patch.object(hv_commands, "_configure_libvirt") as configure_libvirt_mock,
            patch.object(hv_commands, "_detect_local_cores", return_value=8),
            patch.object(hv_commands, "_detect_local_ram_mb", return_value=16384),
            patch.object(
                hv_commands, "local_agent_node_uuid", return_value="node-uuid"
            ),
            patch.object(
                hv_commands.socket, "gethostname", return_value="my-hyper-host"
            ),
            patch.object(
                hv_commands.base_client, "get_user_api_client"
            ) as get_client_mock,
            patch.object(
                hv_commands.base_client, "add_entity", return_value={"uuid": "x"}
            ) as add_entity_mock,
            patch.object(hv_commands, "show_data"),
            patch.object(hv_commands, "reset_agent_meta_file"),
            patch.object(hv_commands, "write_agent_config"),
            patch.object(hv_commands.base_client, "register_agent_and_write_key"),
            patch.object(hv_commands, "install_agent_systemd_unit"),
        ):
            auth_data = {"endpoint": "http://orch:11010", "username": "admin"}
            result = runner.invoke(
                hv_commands.init_cmd,
                ["--add"],
                obj=_obj(auth_data=auth_data),
            )

        assert result.exit_code == 0, result.output
        configure_libvirt_mock.assert_not_called()
        add_entity_mock.assert_called_once()
        data = add_entity_mock.call_args[0][2]
        assert data["driver_spec"]["connection_uri"] == "qemu:///system"
        assert data["driver_spec"]["kind"] == "exordos_local_hyper"
        assert data["driver_spec"]["node"] == "node-uuid"
        assert data["avail_cores"] == 8
        assert data["avail_ram"] == 16384
        assert data["name"] == "my-hyper-host"
        for call in get_client_mock.call_args_list:
            assert call.args[0] == auth_data

    def test_add_with_explicit_avail_cores_and_ram_skips_detection(self) -> None:
        runner = CliRunner()
        with (
            _patch_common_init_deps(),
            patch.object(hv_commands, "install_agent_venv"),
            patch.object(
                hv_commands,
                "resolve_agent_install_target",
                return_value=_FAKE_AGENT_TARGET,
            ),
            patch.object(hv_commands, "_configure_libvirt"),
            patch.object(hv_commands, "_detect_local_cores") as detect_cores_mock,
            patch.object(hv_commands, "_detect_local_ram_mb") as detect_ram_mock,
            patch.object(
                hv_commands, "local_agent_node_uuid", return_value="node-uuid"
            ),
            patch.object(hv_commands.base_client, "get_user_api_client"),
            patch.object(
                hv_commands.base_client, "add_entity", return_value={"uuid": "x"}
            ) as add_entity_mock,
            patch.object(hv_commands, "show_data"),
            patch.object(hv_commands, "reset_agent_meta_file"),
            patch.object(hv_commands, "write_agent_config"),
            patch.object(hv_commands.base_client, "register_agent_and_write_key"),
            patch.object(hv_commands, "install_agent_systemd_unit"),
        ):
            result = runner.invoke(
                hv_commands.init_cmd,
                ["--add", "--avail-cores", "2", "--avail-ram", "4096"],
                obj=_obj(auth_data={"endpoint": "http://10.20.0.2/api/core"}),
            )

        assert result.exit_code == 0, result.output
        detect_cores_mock.assert_not_called()
        detect_ram_mock.assert_not_called()
        data = add_entity_mock.call_args[0][2]
        assert data["avail_cores"] == 2
        assert data["avail_ram"] == 4096

    def test_add_forwards_all_hypervisor_entity_options(self) -> None:
        entity_uuid = "8d10a674-b454-4edb-a94f-f46b38b910d2"
        runner = CliRunner()
        with (
            _patch_common_init_deps(),
            patch.object(hv_commands, "install_agent_venv"),
            patch.object(
                hv_commands,
                "resolve_agent_install_target",
                return_value=_FAKE_AGENT_TARGET,
            ),
            patch.object(hv_commands, "_configure_libvirt"),
            patch.object(
                hv_commands, "local_agent_node_uuid", return_value="node-uuid"
            ),
            patch.object(hv_commands.base_client, "get_user_api_client"),
            patch.object(
                hv_commands.base_client, "add_entity", return_value={"uuid": "x"}
            ) as add_entity_mock,
            patch.object(hv_commands, "show_data"),
            patch.object(hv_commands, "reset_agent_meta_file"),
            patch.object(hv_commands, "write_agent_config"),
            patch.object(hv_commands.base_client, "register_agent_and_write_key"),
            patch.object(hv_commands, "install_agent_systemd_unit"),
        ):
            result = runner.invoke(
                hv_commands.init_cmd,
                [
                    "--add",
                    "--uuid",
                    entity_uuid,
                    "--name",
                    "hv-1",
                    "--description",
                    "my hypervisor",
                    "--avail-cores",
                    "2",
                    "--avail-ram",
                    "4096",
                    "--cores-ratio",
                    "1.5",
                    "--ram-ratio",
                    "2.0",
                    "--machine-type",
                    "HW",
                ],
                obj=_obj(auth_data={"endpoint": "http://10.20.0.2/api/core"}),
            )

        assert result.exit_code == 0, result.output
        add_entity_mock.assert_called_once()
        data = add_entity_mock.call_args[0][2]
        assert data["uuid"] == entity_uuid
        assert data["name"] == "hv-1"
        assert data["description"] == "my hypervisor"
        assert data["cores_ratio"] == 1.5
        assert data["ram_ratio"] == 2.0
        assert data["machine_type"] == "HW"

    def test_remote_connection_uri_configures_libvirt(self) -> None:
        runner = CliRunner()
        with (
            _patch_common_init_deps(),
            patch.object(hv_commands, "install_agent_venv"),
            patch.object(
                hv_commands,
                "resolve_agent_install_target",
                return_value=_FAKE_AGENT_TARGET,
            ),
            patch.object(hv_commands, "_configure_libvirt") as configure_libvirt_mock,
        ):
            result = runner.invoke(
                hv_commands.init_cmd,
                ["--connection-uri", "qemu+tcp://10.0.0.5/system"],
                obj=_obj(auth_data={"endpoint": "http://10.20.0.2/api/core"}),
            )

        assert result.exit_code == 0, result.output
        configure_libvirt_mock.assert_called_once()

    def test_add_reuses_the_global_exordos_credentials(self) -> None:
        """--add must authenticate with the same ctx.obj.auth_data the root
        `exordos --endpoint/--user/--password` options already resolved,
        not a separate credential source."""
        runner = CliRunner()
        auth_data = {
            "endpoint": "http://10.20.0.2/api/core",
            "username": "admin",
            "password": "secret",
        }
        with (
            _patch_common_init_deps(),
            patch.object(hv_commands, "install_agent_venv"),
            patch.object(
                hv_commands,
                "resolve_agent_install_target",
                return_value=_FAKE_AGENT_TARGET,
            ),
            patch.object(hv_commands, "_configure_libvirt"),
            patch.object(hv_commands, "_detect_local_cores", return_value=8),
            patch.object(hv_commands, "_detect_local_ram_mb", return_value=16384),
            patch.object(
                hv_commands, "local_agent_node_uuid", return_value="node-uuid"
            ),
            patch.object(
                hv_commands.base_client, "get_user_api_client"
            ) as get_client_mock,
            patch.object(hv_commands.base_client, "add_entity", return_value={}),
            patch.object(hv_commands, "show_data"),
            patch.object(hv_commands, "reset_agent_meta_file"),
            patch.object(hv_commands, "write_agent_config"),
            patch.object(hv_commands.base_client, "register_agent_and_write_key"),
            patch.object(hv_commands, "install_agent_systemd_unit"),
        ):
            result = runner.invoke(
                hv_commands.init_cmd,
                ["--add"],
                obj=_obj(auth_data=auth_data),
            )

        assert result.exit_code == 0, result.output
        for call in get_client_mock.call_args_list:
            assert call.args[0] == auth_data


class TestAgentConfigContent:
    """Tests for the pure content-building helpers:
    _agent_config_content, _agent_systemd_unit_content.
    """

    def test_agent_config_content(self) -> None:
        content = hv_commands._agent_config_content(
            "http://10.20.0.2:11011",
            "http://10.20.0.2:11012",
            "/opt/exordos-hyper-agent/pool_meta.json",
            "/etc/exordos_universal_agent/node_private_key",
        )
        assert "orch_secure_communication = True" in content
        assert "orch_endpoint = http://10.20.0.2:11011" in content
        assert "status_endpoint = http://10.20.0.2:11012" in content
        assert (
            "private_key_path = /etc/exordos_universal_agent/node_private_key"
            in content
        )
        assert "caps_drivers = LocalPoolAgentDriver" in content
        assert "verify_node_on_register = False" in content
        assert "meta_file = /opt/exordos-hyper-agent/pool_meta.json" in content

    def test_agent_systemd_unit_content(self) -> None:
        content = hv_commands._agent_systemd_unit_content(
            "/opt/universal_agent/.venv/bin/exordos-universal-agent",
            "/etc/exordos_universal_agent/exordos_universal_agent.conf",
        )
        assert (
            "ExecStart=/opt/universal_agent/.venv/bin/exordos-universal-agent "
            "--config-file /etc/exordos_universal_agent/exordos_universal_agent.conf"
            in content
        )


class TestEnsureLocalNetworks:
    """Tests for _ensure_local_networks. `network`/`boot_network` are
    logical libvirt network names the orchestrator itself assigns ports
    by (set up once by the stand's original bootstrap, never renamed
    per-hypervisor) - a hypervisor added via `init`/`init --add` needs
    matching local libvirt networks by those exact names, or scheduled
    machines immediately fail to start.

    On a 'network'-type hypervisor (single-host/local testing), only
    the boot network is auto-created (isolated); the main network is
    left to the operator, as before.

    On a 'bridge'-type hypervisor, neither network is local/transient:
    both the iPXE ROM's `dhcp` and the main network need a real L2 path
    to wherever the core's centrally-served DHCP/traffic actually flows
    - ISC dhcpd matches a request to a subnet by the interface it
    arrived on, and the stand's original bootstrap host typically uses
    a separate NIC/bridge per network. --network-bridge/--boot-bridge
    name those bridges explicitly; each falls back to --network's
    bridge when not given, for a simpler single-bridge setup.
    """

    def test_creates_missing_boot_network(self) -> None:
        with (
            patch.object(hv_commands.libvirt, "has_net", return_value=False),
            patch.object(
                hv_commands.libvirt, "create_isolated_network"
            ) as isolated_mock,
        ):
            hv_commands._ensure_local_networks(
                "network", "exordos-core-net", None, "exordos-core-boot-net", None
            )

        isolated_mock.assert_called_once_with(name="exordos-core-boot-net")

    def test_skips_boot_network_that_already_exists(self) -> None:
        with (
            patch.object(hv_commands.libvirt, "has_net", return_value=True),
            patch.object(
                hv_commands.libvirt, "create_isolated_network"
            ) as isolated_mock,
            patch.object(
                hv_commands.libvirt, "create_bridge_forward_network"
            ) as bridge_mock,
        ):
            hv_commands._ensure_local_networks(
                "network", "exordos-core-net", None, "exordos-core-boot-net", None
            )

        isolated_mock.assert_not_called()
        bridge_mock.assert_not_called()

    def test_network_type_network_does_not_auto_create_main_network(self) -> None:
        """On a 'network'-type hypervisor, --network is deliberately left
        to the operator - only the boot network is auto-created."""
        with (
            patch.object(hv_commands.libvirt, "has_net", return_value=False),
            patch.object(hv_commands.libvirt, "create_isolated_network"),
            patch.object(
                hv_commands.libvirt, "create_bridge_forward_network"
            ) as bridge_mock,
        ):
            hv_commands._ensure_local_networks(
                "network", "exordos-core-net", None, "exordos-core-boot-net", None
            )

        bridge_mock.assert_not_called()

    def test_creates_bridge_forwarding_main_and_boot_networks(self) -> None:
        """On a bridge-type hypervisor without separate bridge overrides,
        both the main and boot logical networks fall back to
        --network's own value as the underlying bridge device."""
        with (
            patch.object(hv_commands.libvirt, "has_net", return_value=False),
            patch.object(
                hv_commands.libvirt, "create_bridge_forward_network"
            ) as bridge_mock,
        ):
            hv_commands._ensure_local_networks(
                "bridge", "exordos-core-net", None, "exordos-core-boot-net", None
            )

        bridge_mock.assert_has_calls(
            [
                mock_call(name="exordos-core-net", bridge="exordos-core-net"),
                mock_call(name="exordos-core-boot-net", bridge="exordos-core-net"),
            ],
            any_order=True,
        )

    def test_creates_bridge_forwarding_networks_on_explicit_bridges(self) -> None:
        """--network-bridge/--boot-bridge, when given, win over
        --network's own value - e.g. the boot subnet is reachable over a
        separate L2/NIC from the main one."""
        with (
            patch.object(hv_commands.libvirt, "has_net", return_value=False),
            patch.object(
                hv_commands.libvirt, "create_bridge_forward_network"
            ) as bridge_mock,
        ):
            hv_commands._ensure_local_networks(
                "bridge",
                "exordos-core-net",
                "br-core",
                "exordos-core-boot-net",
                "br-boot",
            )

        bridge_mock.assert_has_calls(
            [
                mock_call(name="exordos-core-net", bridge="br-core"),
                mock_call(name="exordos-core-boot-net", bridge="br-boot"),
            ],
            any_order=True,
        )

    def test_boot_bridge_falls_back_to_network_bridge_not_network_name(
        self,
    ) -> None:
        """Without --boot-bridge, the boot network rides --network-bridge
        (the real device) rather than --network (the logical name)."""
        with (
            patch.object(hv_commands.libvirt, "has_net", return_value=False),
            patch.object(
                hv_commands.libvirt, "create_bridge_forward_network"
            ) as bridge_mock,
        ):
            hv_commands._ensure_local_networks(
                "bridge",
                "exordos-core-net",
                "br-core",
                "exordos-core-boot-net",
                None,
            )

        bridge_mock.assert_has_calls(
            [
                mock_call(name="exordos-core-net", bridge="br-core"),
                mock_call(name="exordos-core-boot-net", bridge="br-core"),
            ],
            any_order=True,
        )


class TestAgentSetup:
    """Tests for the local universal agent setup helpers:
    install_agent_venv, write_agent_config, install_agent_systemd_unit.

    All privileged filesystem/systemctl operations must go through sudo:
    `exordos bootstrap` runs as a regular, sudo-capable user, not root.
    """

    def test_generate_node_private_key_base64_produces_32_byte_key(self) -> None:
        key_base64 = hv_commands.generate_node_private_key_base64()

        assert len(base64.b64decode(key_base64)) == 32

    def test_reset_agent_meta_file_removes_it_via_sudo(self) -> None:
        with patch.object(hv_commands, "run_command") as run_mock:
            hv_commands.reset_agent_meta_file("/opt/exordos-hyper-agent/pool_meta.json")

        run_mock.assert_called_once_with(
            ["sudo", "rm", "-f", "/opt/exordos-hyper-agent/pool_meta.json"]
        )

    def test_install_agent_venv_creates_venv_and_symlinks_when_standard(
        self, tmp_path
    ) -> None:
        """No venv at the standard path yet: create one fresh, owned by
        the current user, plus the /usr/bin symlink."""
        venv_path = str(tmp_path / "agent-home" / "venv")
        with (
            patch.object(hv_commands, "run_command") as run_mock,
            patch.object(hv_commands, "STANDARD_AGENT_VENV_PATH", venv_path),
            patch.object(hv_commands, "STANDARD_AGENT_BIN_SYMLINK", "/usr/bin/fake"),
        ):
            hv_commands.install_agent_venv(venv_path)

        assert run_mock.call_args_list == [
            mock_call(["sudo", "mkdir", "-p", str(tmp_path / "agent-home")]),
            mock_call(
                ["sudo", "chown", getpass.getuser(), str(tmp_path / "agent-home")]
            ),
            mock_call(["python3", "-m", "venv", venv_path]),
            mock_call([f"{venv_path}/bin/pip", "install", "gcl_sdk[libvirt]"]),
            mock_call(
                [
                    "sudo",
                    "ln",
                    "-sf",
                    f"{venv_path}/bin/exordos-universal-agent",
                    "/usr/bin/fake",
                ]
            ),
        ]

    def test_install_agent_venv_creates_venv_without_symlink_when_custom(
        self, tmp_path
    ) -> None:
        """A custom-named agent's fresh venv must not hijack the
        standard agent's /usr/bin symlink - it may belong to an agent
        this code isn't managing."""
        venv_path = str(tmp_path / "agent-home" / "venv")
        with (
            patch.object(hv_commands, "run_command") as run_mock,
            patch.object(hv_commands, "STANDARD_AGENT_VENV_PATH", "/opt/other/.venv"),
        ):
            hv_commands.install_agent_venv(venv_path)

        assert run_mock.call_args_list == [
            mock_call(["sudo", "mkdir", "-p", str(tmp_path / "agent-home")]),
            mock_call(
                ["sudo", "chown", getpass.getuser(), str(tmp_path / "agent-home")]
            ),
            mock_call(["python3", "-m", "venv", venv_path]),
            mock_call([f"{venv_path}/bin/pip", "install", "gcl_sdk[libvirt]"]),
        ]

    def test_install_agent_venv_extends_existing_venv_via_sudo_pip(
        self, tmp_path
    ) -> None:
        """A venv already exists at this path (this host already runs the
        standard universal agent): just add libvirt-python to it via
        sudo, don't touch ownership or recreate anything."""
        venv_path = tmp_path / "agent-home" / "venv"
        venv_path.mkdir(parents=True)

        with patch.object(hv_commands, "run_command") as run_mock:
            hv_commands.install_agent_venv(str(venv_path))

        run_mock.assert_called_once_with(
            ["sudo", f"{venv_path}/bin/pip", "install", "gcl_sdk[libvirt]"]
        )

    def test_install_agent_systemd_unit_writes_enables_and_restarts(
        self, tmp_path
    ) -> None:
        unit_path = str(tmp_path / "systemd" / "agent.service")
        with (
            patch.object(hv_commands, "write_root_owned_file") as write_mock,
            patch.object(hv_commands, "run_command") as run_mock,
        ):
            hv_commands.install_agent_systemd_unit(
                config_path="/etc/exordos_universal_agent/exordos_universal_agent.conf",
                unit_path=unit_path,
                unit_name="exordos-universal-agent.service",
            )

        write_call = write_mock.call_args[0]
        assert write_call[1] == unit_path
        assert write_mock.call_args.kwargs == {"mode": "644"}
        assert run_mock.call_args_list == [
            mock_call(["sudo", "systemctl", "daemon-reload"]),
            mock_call(
                ["sudo", "systemctl", "enable", "exordos-universal-agent.service"]
            ),
            mock_call(
                ["sudo", "systemctl", "restart", "exordos-universal-agent.service"]
            ),
        ]

    def test_install_agent_systemd_unit_overwrites_a_stale_existing_unit(
        self, tmp_path
    ) -> None:
        """A unit already exists at this path - from either a genuinely
        pre-existing standard agent or a stale earlier run of this same
        code - either way it gets rewritten with the current template
        rather than left untouched."""
        unit_path = tmp_path / "systemd" / "agent.service"
        unit_path.parent.mkdir(parents=True)
        unit_path.write_text("[Unit]\nold stale content\n")

        with (
            patch.object(hv_commands, "write_root_owned_file") as write_mock,
            patch.object(hv_commands, "run_command") as run_mock,
        ):
            hv_commands.install_agent_systemd_unit(
                config_path="/etc/exordos_universal_agent/exordos_universal_agent.conf",
                unit_path=str(unit_path),
                unit_name="exordos-universal-agent.service",
            )

        write_call = write_mock.call_args[0]
        assert write_call[1] == str(unit_path)
        assert write_mock.call_args.kwargs == {"mode": "644"}
        assert run_mock.call_args_list == [
            mock_call(["sudo", "systemctl", "daemon-reload"]),
            mock_call(
                ["sudo", "systemctl", "enable", "exordos-universal-agent.service"]
            ),
            mock_call(
                ["sudo", "systemctl", "restart", "exordos-universal-agent.service"]
            ),
        ]


class TestReadExistingConfig:
    """Tests for _read_existing_config: missing vs present vs root-only
    readable (falls back to sudo cat, matching local_agent_node_uuid's
    established pattern for a root-only-readable path).
    """

    def test_returns_none_when_missing(self, tmp_path) -> None:
        assert hv_commands._read_existing_config(str(tmp_path / "missing")) is None

    def test_reads_content_directly_when_readable(self, tmp_path) -> None:
        config_path = tmp_path / "exordos_universal_agent.conf"
        config_path.write_text("[universal_agent]\n")

        assert (
            hv_commands._read_existing_config(str(config_path)) == "[universal_agent]\n"
        )

    def test_falls_back_to_sudo_cat_on_permission_error(self, tmp_path) -> None:
        config_path = tmp_path / "exordos_universal_agent.conf"
        config_path.write_text("[universal_agent]\n")

        fake_result = MagicMock(stdout="[universal_agent]\nfrom sudo cat\n")
        with (
            patch.object(hv_commands, "open", side_effect=PermissionError, create=True),
            patch.object(
                hv_commands, "run_command", return_value=fake_result
            ) as run_mock,
        ):
            content = hv_commands._read_existing_config(str(config_path))

        assert content == "[universal_agent]\nfrom sudo cat\n"
        run_mock.assert_called_once_with(["sudo", "cat", str(config_path)])


class TestWriteAgentConfig:
    """Tests for write_agent_config: fresh-install vs merge-into-existing."""

    def test_writes_fresh_config_when_none_exists(self, tmp_path) -> None:
        config_path = str(tmp_path / "exordos_universal_agent.conf")
        written = {}

        def fake_run(cmd):
            if cmd[:2] == ["sudo", "install"]:
                written["content"] = open(cmd[4]).read()

        with patch.object(crypto, "run_command", side_effect=fake_run):
            private_key_path = hv_commands.write_agent_config(
                orch_endpoint="http://10.20.0.2:11011",
                status_endpoint="http://10.20.0.2:11012",
                config_path=config_path,
                meta_file="/var/lib/exordos/universal_agent/pool_meta.json",
            )

        assert private_key_path == hv_commands.AGENT_PRIVATE_KEY_PATH
        assert "caps_drivers = LocalPoolAgentDriver" in written["content"]
        assert "orch_endpoint = http://10.20.0.2:11011" in written["content"]

    def test_merges_local_pool_driver_into_existing_config(self, tmp_path) -> None:
        """This host already runs the standard agent for other
        capabilities (it's also a registered compute node): add
        LocalPoolAgentDriver to its caps_drivers, leave orch_endpoint
        and its own private_key_path untouched."""
        config_path = tmp_path / "exordos_universal_agent.conf"
        config_path.write_text(
            "[universal_agent]\n"
            "orch_endpoint = http://core.local.genesis-core.tech:11011\n"
            "status_endpoint = http://core.local.genesis-core.tech:11012\n"
            "private_key_path = /var/lib/exordos/universal_agent/private_key\n"
            "caps_drivers = \n"
            "    SSHKeyCapabilityDriver,\n"
            "    GuestMachineCapabilityDriver\n"
        )
        written = {}

        def fake_run(cmd):
            if cmd[:2] == ["sudo", "install"]:
                written["content"] = open(cmd[4]).read()

        with patch.object(crypto, "run_command", side_effect=fake_run):
            private_key_path = hv_commands.write_agent_config(
                orch_endpoint="http://10.20.0.2:11011",
                status_endpoint="http://10.20.0.2:11012",
                config_path=str(config_path),
                meta_file="/var/lib/exordos/universal_agent/pool_meta.json",
            )

        assert private_key_path == "/var/lib/exordos/universal_agent/private_key"
        content = written["content"]
        assert "SSHKeyCapabilityDriver" in content
        assert "GuestMachineCapabilityDriver" in content
        assert "LocalPoolAgentDriver" in content
        assert "core.local.genesis-core.tech" in content
        assert "[LocalPoolAgentDriver]" in content
        assert "meta_file = /var/lib/exordos/universal_agent/pool_meta.json" in content

    def test_merge_is_idempotent_if_local_pool_driver_already_present(
        self, tmp_path
    ) -> None:
        config_path = tmp_path / "exordos_universal_agent.conf"
        config_path.write_text(
            "[universal_agent]\n"
            "caps_drivers = SSHKeyCapabilityDriver, LocalPoolAgentDriver\n"
        )
        written = {}

        def fake_run(cmd):
            if cmd[:2] == ["sudo", "install"]:
                written["content"] = open(cmd[4]).read()

        with patch.object(crypto, "run_command", side_effect=fake_run):
            hv_commands.write_agent_config(
                orch_endpoint="http://10.20.0.2:11011",
                status_endpoint="http://10.20.0.2:11012",
                config_path=str(config_path),
                meta_file="/var/lib/exordos/universal_agent/pool_meta.json",
            )

        parser = configparser.ConfigParser()
        parser.read_string(written["content"])
        drivers = [
            d.strip()
            for d in parser.get("universal_agent", "caps_drivers").split(",")
            if d.strip()
        ]
        assert drivers.count("LocalPoolAgentDriver") == 1


class TestAgentNamingHelpers:
    """Tests for the per-agent-name path builders."""

    def test_standard_name_maps_to_the_exordos_base_conventions(self) -> None:
        assert (
            hv_commands._agent_venv_path(hv_commands.DEFAULT_AGENT_NAME)
            == "/opt/universal_agent/.venv"
        )
        assert (
            hv_commands._agent_config_path(hv_commands.DEFAULT_AGENT_NAME)
            == "/etc/exordos_universal_agent/exordos_universal_agent.conf"
        )
        assert (
            hv_commands._agent_unit_name(hv_commands.DEFAULT_AGENT_NAME)
            == "exordos-universal-agent.service"
        )
        assert (
            hv_commands._agent_exec_path(hv_commands.DEFAULT_AGENT_NAME, "/x/.venv")
            == hv_commands.STANDARD_AGENT_BIN_SYMLINK
        )

    def test_custom_name_gets_parallel_paths_and_no_symlink(self) -> None:
        assert hv_commands._agent_venv_path("hyper1_pool") == "/opt/hyper1_pool/.venv"
        assert (
            hv_commands._agent_config_path("hyper1_pool")
            == "/etc/exordos_universal_agent/exordos_hyper1_pool.conf"
        )
        assert (
            hv_commands._agent_unit_name("hyper1_pool") == "exordos-hyper1-pool.service"
        )
        assert (
            hv_commands._agent_exec_path("hyper1_pool", "/opt/hyper1_pool/.venv")
            == "/opt/hyper1_pool/.venv/bin/exordos-universal-agent"
        )


class TestEndpointIdentity:
    """Tests for _endpoint_identity: resolving a URL's host to an IP so
    a DNS name and the literal IP it resolves to compare equal.
    """

    def test_resolves_hostname_to_ip(self) -> None:
        with patch.object(
            hv_commands.socket, "gethostbyname", return_value="10.100.0.2"
        ):
            assert hv_commands._endpoint_identity(
                "http://core.local.genesis-core.tech:11011"
            ) == ("10.100.0.2", 11011)

    def test_falls_back_to_raw_hostname_when_resolution_fails(self) -> None:
        with patch.object(hv_commands.socket, "gethostbyname", side_effect=OSError):
            assert hv_commands._endpoint_identity("http://unresolvable:11011") == (
                "unresolvable",
                11011,
            )

    def test_empty_host_is_not_resolved(self) -> None:
        # socket.gethostbyname("") resolves to "0.0.0.0" instead of
        # raising - resolving it would make two differently-broken
        # (hostless) endpoints compare equal, defeating the "erring
        # towards different core" default.
        with patch.object(hv_commands.socket, "gethostbyname") as gethostbyname_mock:
            identity = hv_commands._endpoint_identity("http:///no-host-here")

        gethostbyname_mock.assert_not_called()
        assert identity == ("", None)


class TestResolveAgentInstallTarget:
    """Tests for resolve_agent_install_target: fresh/matching vs a
    foreign agent already configured for a different core.
    """

    def test_no_existing_config_resolves_the_named_paths(self, tmp_path) -> None:
        config_path = str(tmp_path / "exordos_universal_agent.conf")
        with patch.object(hv_commands, "AGENT_CONFIG_DIR", str(tmp_path)):
            target = hv_commands.resolve_agent_install_target(
                agent_name=hv_commands.DEFAULT_AGENT_NAME,
                orch_endpoint="http://10.20.0.2:11011",
                status_endpoint="http://10.20.0.2:11012",
            )

        assert target.config_path == config_path
        assert target.venv_path == "/opt/universal_agent/.venv"
        assert target.exec_path == hv_commands.STANDARD_AGENT_BIN_SYMLINK

    def test_existing_config_for_the_same_core_is_accepted(self, tmp_path) -> None:
        config_path = tmp_path / "exordos_universal_agent.conf"
        config_path.write_text(
            "[universal_agent]\n"
            "orch_endpoint = http://10.20.0.2:11011\n"
            "status_endpoint = http://10.20.0.2:11012\n"
        )
        with patch.object(hv_commands, "AGENT_CONFIG_DIR", str(tmp_path)):
            target = hv_commands.resolve_agent_install_target(
                agent_name=hv_commands.DEFAULT_AGENT_NAME,
                orch_endpoint="http://10.20.0.2:11011",
                status_endpoint="http://10.20.0.2:11012",
            )

        assert target.config_path == str(config_path)

    def test_dns_name_and_literal_ip_for_the_same_core_are_accepted(
        self, tmp_path
    ) -> None:
        """The exordos-base image's own agent config points at a DNS
        name (e.g. core.local.genesis-core.tech); this code computes a
        literal IP from --endpoint. Both must be recognized as the same
        core when the name resolves to that IP, not rejected as a
        string mismatch."""
        config_path = tmp_path / "exordos_universal_agent.conf"
        config_path.write_text(
            "[universal_agent]\n"
            "orch_endpoint = http://core.local.genesis-core.tech:11011\n"
            "status_endpoint = http://core.local.genesis-core.tech:11012\n"
        )
        with (
            patch.object(hv_commands, "AGENT_CONFIG_DIR", str(tmp_path)),
            patch.object(
                hv_commands.socket, "gethostbyname", return_value="10.100.0.2"
            ),
        ):
            target = hv_commands.resolve_agent_install_target(
                agent_name=hv_commands.DEFAULT_AGENT_NAME,
                orch_endpoint="http://10.100.0.2:11011",
                status_endpoint="http://10.100.0.2:11012",
            )

        assert target.config_path == str(config_path)

    def test_existing_config_for_a_different_core_raises(self, tmp_path) -> None:
        """A machine that's also a compute node of some other, unrelated
        exordos deployment must not have its agent silently
        reconfigured to point at our core instead."""
        config_path = tmp_path / "exordos_universal_agent.conf"
        config_path.write_text(
            "[universal_agent]\n"
            "orch_endpoint = http://core.local.genesis-core.tech:11011\n"
            "status_endpoint = http://core.local.genesis-core.tech:11012\n"
        )
        with (
            patch.object(hv_commands, "AGENT_CONFIG_DIR", str(tmp_path)),
            patch.object(hv_commands.socket, "gethostbyname", side_effect=OSError),
            pytest.raises(click.ClickException, match="different core"),
        ):
            hv_commands.resolve_agent_install_target(
                agent_name=hv_commands.DEFAULT_AGENT_NAME,
                orch_endpoint="http://10.20.0.2:11011",
                status_endpoint="http://10.20.0.2:11012",
            )
