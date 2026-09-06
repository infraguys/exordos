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

import sys
import typing as tp
import uuid as sys_uuid

from bazooka import exceptions as bazooka_exc
from requests.exceptions import RequestException
import rich_click as click

from exordos import exceptions as exordos_exc
from exordos.clients.base import PasswordPrompt
from exordos.cmd.aliases import ClickAliasedGroup
from exordos.cmd.auth import commands as auth_commands
from exordos.cmd.builds import commands as builds_commands
from exordos.cmd.compute import compute_group
from exordos.cmd.compute.hypervisors import commands as hypervisors_commands
from exordos.cmd.compute.nodes import commands as nodes_commands
from exordos.cmd.configs import commands as configs_commands
from exordos.cmd.dbaas import dbaas_group
from exordos.cmd.deploy import commands as deploy_commands
from exordos.cmd.dns import dns_group
from exordos.cmd.em import em_group
from exordos.cmd.em.elements import commands as elements_commands
from exordos.cmd.iam import iam_group
from exordos.cmd.initialization import commands as initialization_commands
from exordos.cmd.metapaas import metapaas_group
from exordos.cmd.network import network_group
from exordos.cmd.quota import commands as quota_commands
from exordos.cmd.realms.commands import realms_group
from exordos.cmd.repo import commands as repo_commands
from exordos.cmd.secret import secret_group
from exordos.cmd.security.commands import rules_group
from exordos.cmd.settings import commands as settings_commands
from exordos.cmd.settings import config as settings_config
from exordos.cmd.stand import commands as stand_commands
from exordos.cmd.stand import utils_commands
from exordos.cmd.ua import ua_group
from exordos.cmd.version import commands as version_commands
from exordos.cmd.vs import vs_group
from exordos.cmd.vs.vars import commands as vars_commands
from exordos.common.cmd_context import ContextObject
import exordos.constants as c

COMMANDS_WITHOUT_CONFIG = {
    builds_commands.build_cmd.name,
    initialization_commands.init_cmd.name,
    version_commands.version_cmd.name,
    version_commands.latest_cmd.name,
    version_commands.get_project_version_cmd.name,
    stand_commands.bootstrap_cmd.name,
    stand_commands.backup_cmd.name,
    stand_commands.backup_decrypt_cmd.name,
    utils_commands.autocomplete.name,
    utils_commands.autocomplete_help.name,
    utils_commands.hello.name,
    utils_commands.introduction.name,
    hypervisors_commands.init_cmd.name,
    settings_commands.settings_group.name,
    repo_commands.push_cmd.name,
}


def _get_otp_prompt(otp_code: str | None) -> str:
    if otp_code:
        return otp_code
    return click.prompt("OTP code", hide_input=False)


@click.group(
    cls=ClickAliasedGroup,
    invoke_without_command=True,
    help="Provides all the necessary tools for work with Exordos Platform",
)
@click.option(
    "--config",
    default=c.CONFIG_FILE,
    show_default=True,
    type=click.Path(exists=False, dir_okay=False),
    help="Path to YAML config file",
)
@click.option(
    "-e",
    "--endpoint",
    default="http://localhost:11010",
    show_default=True,
    help="Exordos API endpoint",
)
@click.option(
    "--ecosystem-endpoint",
    required=False,
    help="Exordos ecosystem API endpoint",
)
@click.option(
    "-u",
    "--user",
    default=None,
    help="Client user name",
)
@click.option(
    "-l",
    "--login",
    default=None,
    help="Client login",
)
@click.option(
    "-p",
    "--password",
    default=None,
    help="Password for the client user",
)
@click.option(
    "-a",
    "--access-token",
    default=None,
    help="access token for the client user",
)
@click.option(
    "--refresh-token",
    default=None,
    help="refresh token for the client user",
)
@click.option(
    "-r",
    "--realm",
    type=str,
    help="Name of the realm",
)
@click.option(
    "-c",
    "--context",
    type=str,
    help="Name of the context",
)
@click.option(
    "-P",
    "--project-id",
    default=None,
    type=click.UUID,
    help="Project ID for the client user",
)
@click.option(
    "-vvv",
    "--verbose",
    show_default=True,
    is_flag=True,
    help="Verbose logs",
)
@click.option(
    "-i",
    "--developer-key-path",
    default=None,
    help="Path to developer public key",
)
@click.option(
    "-s",
    "--silent",
    show_default=True,
    is_flag=True,
    help="Do not print messages, warnings or errors",
)
@click.option(
    "--otp-code",
    default=None,
    help="OTP code for two-factor authentication",
)
@click.option(
    "--ttl",
    type=float,
    help="Time to live for the access token",
    default=None,
)
@click.option(
    "--refresh-ttl",
    type=float,
    help="Time to live for the refresh token",
    default=None,
)
@click.option(
    "--check-updates/--no-check-updates",
    default=False,
    help="Check for updates",
)
@click.pass_context
def exordos(
    ctx: click.Context,
    config: str,
    endpoint: str,
    ecosystem_endpoint: str | None,
    user: str | None,
    login: str | None,
    password: str | None,
    access_token: str | None,
    refresh_token: str | None,
    realm: str | None,
    context: str | None,
    project_id: sys_uuid.UUID | None,
    verbose: bool | None,
    developer_key_path: str | None,
    silent: bool | None,
    otp_code: str | None,
    ttl: float | None,
    refresh_ttl: float | None,
    check_updates: bool | None,
) -> None:
    if not ctx.invoked_subcommand:
        click.echo(ctx.get_help())
        return
    if verbose:
        import logging

        logging.basicConfig(level=logging.DEBUG)
    # Load configuration from file (if exists)
    cfg_path = config if config else None
    cfg = settings_config.load_config(
        ctx,
        cfg_path,
        silent
        or any(
            [ctx.invoked_subcommand.startswith(cmd) for cmd in COMMANDS_WITHOUT_CONFIG]
        ),
    )
    current_realm = settings_config.get_current_realm(cfg)
    realm_conf = settings_config.get_realm(cfg, realm or current_realm)
    context_conf = settings_config.get_context(realm_conf, context)

    def _get_final_value(
        param_name: str, cli_value: tp.Any, base_conf: dict, direct_conf: dict
    ) -> tp.Any:
        if (
            ctx.get_parameter_source(param_name)
            == click.core.ParameterSource.COMMANDLINE
        ):
            return cli_value
        return direct_conf.get(param_name, base_conf.get(param_name, cli_value))

    final_endpoint = _get_final_value("endpoint", endpoint, cfg, realm_conf)
    final_ecosystem_endpoint = _get_final_value(
        "ecosystem_endpoint", ecosystem_endpoint, cfg, realm_conf
    )
    final_check_updates = _get_final_value(
        "check_updates", check_updates, cfg, realm_conf
    )
    final_user = _get_final_value("user", user, cfg, context_conf)
    final_login = _get_final_value("login", login, cfg, context_conf)
    final_password = _get_final_value("password", password, cfg, context_conf)
    final_access_token = _get_final_value(
        "access_token", access_token, cfg, context_conf
    )
    final_refresh_token = _get_final_value(
        "refresh_token", refresh_token, cfg, context_conf
    )
    final_developer_key_path = _get_final_value(
        "developer_key_path", developer_key_path, cfg, {}
    )
    final_ttl = _get_final_value("ttl", ttl, cfg, context_conf)
    final_refresh_ttl = _get_final_value("refresh_ttl", refresh_ttl, cfg, context_conf)

    need_update = None
    if final_check_updates and version_commands.should_check_version():
        need_update = not version_commands.check_latest_version()
        version_commands.save_last_check_time()

    final_project_id = _get_final_value("project_id", project_id, cfg, context_conf)
    scope = f"project:{final_project_id}" if final_project_id else None
    needs_password_prompt = (
        final_user
        and not final_password
        and not final_access_token
        and not final_refresh_token
    )
    password_prompt = PasswordPrompt() if needs_password_prompt else None

    # Get realm name for token caching

    auth_data = dict(
        endpoint=final_endpoint,
        ecosystem_endpoint=final_ecosystem_endpoint,
        username=final_user,
        login=final_login,
        password=final_password,
        access_token=final_access_token,
        refresh_token=final_refresh_token,
        scope=scope,
        ttl=final_ttl,
        refresh_ttl=final_refresh_ttl,
        password_prompt=password_prompt,
        otp_prompt=lambda: _get_otp_prompt(otp_code),
        realm=realm or current_realm,
    )
    ctx.obj = ContextObject(
        auth_data, config, final_developer_key_path, cfg, need_update
    )


@exordos.command(help="tool for creating docs files for cli commands", hidden=True)
def dumphelp() -> None:
    from exordos.common.md_click import dump_helper

    dump_helper(exordos)
    return None


exordos.add_command(auth_commands.auth_group)

exordos.add_command(iam_group)
exordos.add_command(secret_group, aliases=["s"])
exordos.add_command(realms_group)

exordos.add_command(vs_group)
exordos.add_command(vars_commands.vv_group)

exordos.add_command(quota_commands.limits_group, aliases=["q"])

exordos.add_command(dns_group)
exordos.add_command(dbaas_group)
exordos.add_command(metapaas_group)
exordos.add_command(network_group)

exordos.add_command(rules_group)

exordos.add_command(compute_group, aliases=["c"])
exordos.add_command(nodes_commands.cn_group)

exordos.add_command(em_group, aliases=["e"])  # exordos em e l, exordos e e l
exordos.add_command(
    elements_commands.ee_group, aliases=["elements"]
)  # exordos ee l, exordos elements l
exordos.add_command(builds_commands.build_cmd)

exordos.add_command(configs_commands.configs_group)
exordos.add_command(settings_commands.settings_group)
exordos.add_command(repo_commands.repository_group)
exordos.add_command(repo_commands.push_cmd)
exordos.add_command(deploy_commands.deploy_cmd)

exordos.add_command(initialization_commands.init_cmd)

exordos.add_command(version_commands.version_cmd)
exordos.add_command(version_commands.latest_cmd)
exordos.add_command(version_commands.get_project_version_cmd)

exordos.add_command(stand_commands.bootstrap_cmd)
exordos.add_command(stand_commands.backup_cmd)
exordos.add_command(stand_commands.backup_decrypt_cmd)

exordos.add_command(ua_group)

exordos.add_command(utils_commands.openapi_spec)
exordos.add_command(utils_commands.hello)
exordos.add_command(utils_commands.autocomplete_help)
exordos.add_command(utils_commands.autocomplete)
exordos.add_command(utils_commands.sync)
exordos.add_command(utils_commands.introduction)
exordos.add_command(utils_commands.ready_api)


if __name__ == "__main__":
    error_message = ""
    try:
        exordos()
    except bazooka_exc.BaseHTTPException as e:
        error_message = f"Error: [{e.code}] {e.cause.response.text}"
    except RequestException as e:
        if e.response is not None:
            error_message = f"Error: [{e.response.status_code}] {e.response.text}"
        else:
            error_message = f"Error: {e}"
    except (ValueError, FileNotFoundError, exordos_exc.ExordosException) as e:
        error_message = f"Error: {e}"
    except KeyboardInterrupt:
        error_message = "Error: Interrupted by user"
    finally:
        if error_message:
            click.secho(error_message, fg="red")
            sys.exit(1)
