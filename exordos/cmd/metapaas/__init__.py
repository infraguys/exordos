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

from urllib.parse import urljoin

import rich_click as click

from exordos import utils
from exordos.cmd.aliases import ClickAliasedGroup
from exordos.cmd.metapaas.mail import mail_group
from exordos.cmd.metapaas.s3 import s3_group
from exordos.cmd.metapaas.types import commands as types_commands

METAPAAS_URL_PART = "/api/metapaas"


@click.group(
    "metapaas",
    cls=ClickAliasedGroup,
    help="metapaas group in the Exordos installation",
)
@click.option(
    "--metapaas-endpoint",
    default=None,
    help=(
        "Exordos metapaas API endpoint, defaults to the metapaas element "
        "behind the endpoint"
    ),
)
@click.pass_context
def metapaas_group(ctx: click.Context, metapaas_endpoint: str | None) -> None:
    # The metapaas element serves its own API, published by the core load
    # balancer next to the core API itself.
    ctx.obj.auth_data["service_endpoint"] = metapaas_endpoint or urljoin(
        utils.get_base_url(ctx.obj.auth_data.get("endpoint", "")), METAPAAS_URL_PART
    )


metapaas_group.add_command(types_commands.types_group, aliases=["t"])
metapaas_group.add_command(mail_group, aliases=["m"])
metapaas_group.add_command(s3_group)
