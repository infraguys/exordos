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

import rich_click as click

from exordos.cmd.aliases import ClickAliasedGroup
from exordos.cmd.metapaas.mail.accounts import commands as accounts_commands
from exordos.cmd.metapaas.mail.instances import commands as instances_commands
from exordos.cmd.metapaas.mail.versions import commands as versions_commands


@click.group(
    "mail",
    cls=ClickAliasedGroup,
    help="mail PaaS group in the Exordos installation",
)
def mail_group() -> None:
    pass


mail_group.add_command(instances_commands.instances_group, aliases=["i"])
mail_group.add_command(accounts_commands.accounts_group, aliases=["a"])
mail_group.add_command(versions_commands.versions_group, aliases=["v"])
