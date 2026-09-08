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
from exordos.cmd.metapaas.s3.buckets import commands as buckets_commands
from exordos.cmd.metapaas.s3.instances import commands as instances_commands
from exordos.cmd.metapaas.s3.keys import commands as keys_commands
from exordos.cmd.metapaas.s3.policies import commands as policies_commands
from exordos.cmd.metapaas.s3.user_policies import commands as user_policies_commands
from exordos.cmd.metapaas.s3.users import commands as users_commands
from exordos.cmd.metapaas.s3.versions import commands as versions_commands


@click.group(
    "s3",
    cls=ClickAliasedGroup,
    help="Manage the s3 PaaS served by the metapaas element",
)
def s3_group() -> None:
    pass


s3_group.add_command(instances_commands.instances_group, aliases=["i"])
s3_group.add_command(buckets_commands.buckets_group, aliases=["b"])
s3_group.add_command(users_commands.users_group, aliases=["u"])
s3_group.add_command(keys_commands.keys_group, aliases=["k"])
s3_group.add_command(policies_commands.policies_group, aliases=["p"])
s3_group.add_command(user_policies_commands.user_policies_group, aliases=["up"])
s3_group.add_command(versions_commands.versions_group, aliases=["v"])
