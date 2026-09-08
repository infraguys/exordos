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

import typing as tp

from click.testing import CliRunner
import rich_click as click

from exordos.cmd import metapaas
from exordos.common.cmd_context import ContextObject


def _invoke(endpoint: str, *args: str) -> dict[str, tp.Any]:
    """Run a no-op subcommand of the metapaas group and return its auth_data."""
    auth_data: dict[str, tp.Any] = {"endpoint": endpoint}

    @click.command("noop")
    def noop_cmd() -> None:
        pass

    metapaas.metapaas_group.add_command(noop_cmd)
    try:
        result = CliRunner().invoke(
            metapaas.metapaas_group,
            [*args, "noop"],
            obj=ContextObject(
                auth_data=auth_data,
                cfg_path=None,
                developer_key_path=None,
                cfg={},
                need_update=None,
            ),
        )
        assert result.exit_code == 0, result.output
    finally:
        del metapaas.metapaas_group.commands["noop"]
    return auth_data


class TestMetapaasGroup:
    def test_metapaas_group_derives_service_endpoint(self) -> None:
        auth_data = _invoke("http://10.20.0.2/api/core")
        assert auth_data["service_endpoint"] == "http://10.20.0.2/api/metapaas"

    def test_metapaas_group_derives_service_endpoint_with_port(self) -> None:
        auth_data = _invoke("http://localhost:11010")
        assert auth_data["service_endpoint"] == "http://localhost:11010/api/metapaas"

    def test_metapaas_group_uses_explicit_endpoint(self) -> None:
        auth_data = _invoke(
            "http://10.20.0.2/api/core",
            "--metapaas-endpoint",
            "http://metapaas-cp:8080",
        )
        assert auth_data["service_endpoint"] == "http://metapaas-cp:8080"
