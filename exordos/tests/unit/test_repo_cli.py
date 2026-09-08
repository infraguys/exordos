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
from unittest.mock import MagicMock
from unittest.mock import patch
import uuid as sys_uuid

import click
from click.testing import CliRunner
import pytest

from exordos import utils
from exordos.cmd.em.elements import commands as em_elements
from exordos.cmd.repo import commands as repo_commands
from exordos.cmd.repo.elements import commands as repo_elements
from exordos.common.cmd_context import ContextObject


class TestUrn:
    """Tests for exordos.utils.urn."""

    def test_urn_format(self) -> None:
        assert utils.urn("images", "abc-123") == "urn:images:abc-123"

    def test_urn_namespace(self) -> None:
        assert utils.urn("foo", "bar") == "urn:foo:bar"


class TestBuildDriverSpec:
    """Tests for exordos.cmd.repo.commands._build_driver_spec."""

    def test_none_url_returns_none(self) -> None:
        assert repo_commands._build_driver_spec(None, "u", "p") is None

    def test_url_only(self) -> None:
        spec = repo_commands._build_driver_spec("https://example.com/", None, None)
        assert spec == {"kind": "nginx", "url": "https://example.com/"}

    def test_url_with_username(self) -> None:
        spec = repo_commands._build_driver_spec("https://example.com/", "bob", None)
        assert spec == {
            "kind": "nginx",
            "url": "https://example.com/",
            "username": "bob",
        }

    def test_url_with_password(self) -> None:
        spec = repo_commands._build_driver_spec("https://example.com/", None, "secret")
        assert spec == {
            "kind": "nginx",
            "url": "https://example.com/",
            "password": "secret",
        }

    def test_url_with_credentials(self) -> None:
        spec = repo_commands._build_driver_spec("https://example.com/", "bob", "secret")
        assert spec == {
            "kind": "nginx",
            "url": "https://example.com/",
            "username": "bob",
            "password": "secret",
        }


class TestExtractRepositoryUuid:
    """Tests for exordos.cmd.repo.elements.commands._extract_repository_uuid."""

    def test_empty_when_no_repository(self) -> None:
        assert repo_elements._extract_repository_uuid({}) == ""

    def test_empty_when_repository_empty(self) -> None:
        assert repo_elements._extract_repository_uuid({"repository": ""}) == ""

    def test_extracts_uuid_from_ref(self) -> None:
        u = "12345678-1234-1234-1234-123456789abc"
        ref = f"/v1/repo/repositories/{u}"
        result = repo_elements._extract_repository_uuid({"repository": ref})
        assert result == str(sys_uuid.UUID(u))

    def test_returns_raw_when_not_uuid(self) -> None:
        # A non-UUID tail is returned as-is
        result = repo_elements._extract_repository_uuid({"repository": "some-name"})
        assert result == "some-name"


class TestFilterAndSortElements:
    """Tests for exordos.cmd.repo.elements.commands._filter_and_sort_elements."""

    def _elem(self, name, version, status=None):
        elem = {"name": name, "version": version, "uuid": str(sys_uuid.uuid4())}
        if status is not None:
            elem["status"] = status
        return elem

    def test_filters_dev_versions_by_default(self) -> None:
        entities = [
            self._elem("a", "1.0.0"),
            self._elem("a", "1.0.0-dev+abc.12345678"),
            self._elem("b", "2.0.0"),
        ]
        result = repo_elements._filter_and_sort_elements(entities, {})
        versions = [e["version"] for e in result]
        assert "1.0.0-dev+abc.12345678" not in versions
        assert set(versions) == {"1.0.0", "2.0.0"}

    def test_dev_flag_keeps_all(self) -> None:
        entities = [
            self._elem("a", "1.0.0"),
            self._elem("a", "1.0.0-dev+abc.12345678"),
        ]
        result = repo_elements._filter_and_sort_elements(entities, {"dev": True})
        assert len(result) == 2

    def test_sorted_by_name_then_version(self) -> None:
        entities = [
            self._elem("b", "1.0.0"),
            self._elem("a", "2.0.0"),
            self._elem("a", "1.0.0"),
        ]
        result = repo_elements._filter_and_sort_elements(entities, {})
        assert [(e["name"], e["version"]) for e in result] == [
            ("a", "1.0.0"),
            ("a", "2.0.0"),
            ("b", "1.0.0"),
        ]

    def test_keeps_non_release_with_non_hidden_status(self) -> None:
        entities = [
            self._elem("a", "1.0.0-dev+abc", status="ERROR"),
            self._elem("a", "1.0.0-dev+def", status="ACTIVE"),
            self._elem("a", "1.0.0-dev+ghi", status="IN_PROGRESS"),
        ]
        result = repo_elements._filter_and_sort_elements(entities, {})
        assert {e["version"] for e in result} == {
            "1.0.0-dev+abc",
            "1.0.0-dev+def",
            "1.0.0-dev+ghi",
        }

    def test_filters_non_release_with_new_or_available_status(self) -> None:
        entities = [
            self._elem("a", "1.0.0-dev+abc", status="NEW"),
            self._elem("a", "1.0.0-dev+def", status="AVAILABLE"),
            self._elem("a", "1.0.0"),
        ]
        result = repo_elements._filter_and_sort_elements(entities, {})
        assert [e["version"] for e in result] == ["1.0.0"]

    def test_keeps_release_regardless_of_status(self) -> None:
        entities = [
            self._elem("a", "1.0.0", status="NEW"),
            self._elem("a", "2.0.0", status="AVAILABLE"),
        ]
        result = repo_elements._filter_and_sort_elements(entities, {})
        assert {e["version"] for e in result} == {"1.0.0", "2.0.0"}


class TestGetSortKey:
    """Tests for exordos.cmd.em.elements.commands._get_sort_key."""

    def test_priority_from_repository_ref(self) -> None:
        u = "12345678-1234-1234-1234-123456789abc"
        element = {
            "version": "1.0.0",
            "repository": f"/v1/repo/repositories/{u}",
        }
        repo_priorities = {u: 100}
        priority, version = em_elements._get_sort_key(element, repo_priorities)
        assert priority == 100
        assert str(version) == "1.0.0"

    def test_default_priority_zero(self) -> None:
        element = {"version": "2.0.0"}
        priority, _ = em_elements._get_sort_key(element, {})
        assert priority == 0

    def test_unknown_repo_uuid_defaults_to_zero(self) -> None:
        u = "12345678-1234-1234-1234-123456789abc"
        element = {
            "version": "1.0.0",
            "repository": f"/v1/repo/repositories/{u}",
        }
        priority, _ = em_elements._get_sort_key(element, {})
        assert priority == 0

    def test_invalid_repository_ref_defaults_to_zero(self) -> None:
        element = {"version": "1.0.0", "repository": "not-a-uuid"}
        priority, _ = em_elements._get_sort_key(element, {})
        assert priority == 0

    def test_priority_outranks_version(self) -> None:
        u = "12345678-1234-1234-1234-123456789abc"
        newer = {"version": "0.0.35", "repository": ""}
        older = {"version": "0.0.6", "repository": f"/v1/repo/repositories/{u}"}
        repo_priorities = {u: 4096}
        assert em_elements._get_sort_key(
            older, repo_priorities
        ) > em_elements._get_sort_key(newer, repo_priorities)


class TestSelectElementByName:
    """Tests for exordos.cmd.em.elements.commands._select_element_by_name."""

    def _client(self, elements, repositories=None):
        client = MagicMock()

        def fake_filter(collection, **filters):
            if collection.endswith("/repositories/"):
                return repositories or []
            return elements

        client.filter.side_effect = fake_filter
        return client

    def test_no_elements_raises(self) -> None:
        client = self._client([])
        with pytest.raises(click.ClickException, match="No elements found"):
            em_elements._select_element_by_name(client, "foo", None)

    def test_no_stable_versions_raises(self) -> None:
        client = self._client(
            [{"name": "foo", "version": "1.0.0-dev+abc.12345678", "uuid": "u"}]
        )
        with pytest.raises(click.ClickException, match="No stable versions"):
            em_elements._select_element_by_name(client, "foo", None)

    def _patch_select(self, chosen):
        select_mock = MagicMock()
        select_mock.return_value.ask.return_value = chosen
        return patch("questionary.select", select_mock), select_mock

    def test_asks_user_when_several_versions_available(self) -> None:
        elements = [
            {"name": "foo", "version": "1.0.0", "uuid": "u1", "repository": ""},
            {"name": "foo", "version": "2.0.0", "uuid": "u2", "repository": ""},
            {"name": "foo", "version": "1.5.0", "uuid": "u3", "repository": ""},
        ]
        client = self._client(elements)
        patcher, select_mock = self._patch_select(elements[2])
        with patcher:
            selected = em_elements._select_element_by_name(client, "foo", None)
        assert selected["uuid"] == "u3"
        offered = [c.value["version"] for c in select_mock.call_args.kwargs["choices"]]
        assert offered == ["2.0.0", "1.5.0", "1.0.0"]

    def test_aborts_when_version_selection_is_cancelled(self) -> None:
        elements = [
            {"name": "foo", "version": "1.0.0", "uuid": "u1", "repository": ""},
            {"name": "foo", "version": "2.0.0", "uuid": "u2", "repository": ""},
        ]
        client = self._client(elements)
        patcher, _ = self._patch_select(None)
        with patcher, pytest.raises(click.Abort):
            em_elements._select_element_by_name(client, "foo", None)

    def test_auto_select_takes_highest_priority_repo(self) -> None:
        u_low = "11111111-1111-1111-1111-111111111111"
        u_high = "22222222-2222-2222-2222-222222222222"
        elements = [
            {
                "name": "foo",
                "version": "2.0.0",
                "uuid": "u1",
                "repository": f"/v1/repo/repositories/{u_low}",
            },
            {
                "name": "foo",
                "version": "1.0.0",
                "uuid": "u2",
                "repository": f"/v1/repo/repositories/{u_high}",
            },
        ]
        repositories = [
            {"uuid": u_low, "priority": 10},
            {"uuid": u_high, "priority": 4096},
        ]
        client = self._client(elements, repositories)
        selected = em_elements._select_element_by_name(
            client, "foo", None, auto_select=True
        )
        assert selected["uuid"] == "u2"

    def test_newer_than_drops_older_candidates(self) -> None:
        elements = [
            {"name": "foo", "version": "1.0.0", "uuid": "u1", "repository": ""},
            {"name": "foo", "version": "2.0.0", "uuid": "u2", "repository": ""},
        ]
        client = self._client(elements)
        selected = em_elements._select_element_by_name(
            client, "foo", None, newer_than="1.0.0"
        )
        assert selected["uuid"] == "u2"

    def test_newer_than_returns_none_without_candidates(self) -> None:
        elements = [
            {"name": "foo", "version": "1.0.0", "uuid": "u1", "repository": ""},
            {"name": "foo", "version": "2.0.0", "uuid": "u2", "repository": ""},
        ]
        client = self._client(elements)
        assert (
            em_elements._select_element_by_name(client, "foo", None, newer_than="2.0.0")
            is None
        )

    def test_selects_higher_priority_repo(self) -> None:
        u_low = "11111111-1111-1111-1111-111111111111"
        u_high = "22222222-2222-2222-2222-222222222222"
        elements = [
            {
                "name": "foo",
                "version": "1.0.0",
                "uuid": "u1",
                "repository": f"/v1/repo/repositories/{u_low}",
            },
            {
                "name": "foo",
                "version": "1.0.0",
                "uuid": "u2",
                "repository": f"/v1/repo/repositories/{u_high}",
            },
        ]
        repositories = [
            {"uuid": u_low, "priority": 10},
            {"uuid": u_high, "priority": 100},
        ]
        client = self._client(elements, repositories)
        selected = em_elements._select_element_by_name(client, "foo", None)
        assert selected["uuid"] == "u2"

    def test_asks_user_about_newer_version_in_lower_priority_repo(self) -> None:
        u_low = "11111111-1111-1111-1111-111111111111"
        u_high = "22222222-2222-2222-2222-222222222222"
        elements = [
            {
                "name": "foo",
                "version": "0.0.35",
                "uuid": "u1",
                "repository": f"/v1/repo/repositories/{u_low}",
            },
            {
                "name": "foo",
                "version": "0.0.6",
                "uuid": "u2",
                "repository": f"/v1/repo/repositories/{u_high}",
            },
        ]
        repositories = [
            {"uuid": u_low, "priority": 10, "name": "extra"},
            {"uuid": u_high, "priority": 4096, "name": "main"},
        ]
        client = self._client(elements, repositories)
        patcher, select_mock = self._patch_select(elements[0])
        with patcher:
            selected = em_elements._select_element_by_name(client, "foo", None)
        assert selected["uuid"] == "u1"
        titles = [c.title for c in select_mock.call_args.kwargs["choices"]]
        assert titles == ["0.0.35 (repo: extra)", "0.0.6 (repo: main)"]

    def test_version_filter_exact_match(self) -> None:
        elements = [
            {"name": "foo", "version": "1.0.0", "uuid": "u1", "repository": ""},
            {"name": "foo", "version": "2.0.0", "uuid": "u2", "repository": ""},
        ]
        client = self._client(elements)
        selected = em_elements._select_element_by_name(client, "foo", "1.0.0")
        assert selected["uuid"] == "u1"

    def test_version_filter_no_match_raises(self) -> None:
        elements = [
            {"name": "foo", "version": "1.0.0", "uuid": "u1", "repository": ""},
        ]
        client = self._client(elements)
        with pytest.raises(click.ClickException, match="No elements found"):
            em_elements._select_element_by_name(client, "foo", "9.9.9")

    def test_version_filter_allows_dev(self) -> None:
        """Explicit version filter allows selecting development versions."""
        elements = [
            {
                "name": "foo",
                "version": "1.0.0-dev+abc.12345678",
                "uuid": "u1",
                "repository": "",
            },
        ]
        client = self._client(elements)
        selected = em_elements._select_element_by_name(
            client, "foo", "1.0.0-dev+abc.12345678"
        )
        assert selected["uuid"] == "u1"


class TestSelectCurrentElementByName:
    """Tests for exordos.cmd.em.elements.commands._select_current_element_by_name."""

    def _client(self, elements):
        client = MagicMock()
        client.filter.return_value = elements
        return client

    def test_no_installed_raises(self) -> None:
        client = self._client(
            [{"name": "foo", "version": "1.0.0", "uuid": "u1", "status": "NEW"}]
        )
        with pytest.raises(click.ClickException, match="No installed element"):
            em_elements._select_current_element_by_name(client, "foo")

    def test_selects_active(self) -> None:
        client = self._client(
            [{"name": "foo", "version": "1.0.0", "uuid": "u1", "status": "ACTIVE"}]
        )
        selected = em_elements._select_current_element_by_name(client, "foo")
        assert selected["uuid"] == "u1"

    def test_selects_in_progress(self) -> None:
        client = self._client(
            [{"name": "foo", "version": "1.0.0", "uuid": "u1", "status": "IN_PROGRESS"}]
        )
        selected = em_elements._select_current_element_by_name(client, "foo")
        assert selected["uuid"] == "u1"

    def test_selects_by_installation_state(self) -> None:
        client = self._client(
            [
                {
                    "name": "foo",
                    "version": "1.0.0",
                    "uuid": "u1",
                    "status": "NEW",
                    "installation_state": "INSTALLED",
                }
            ]
        )
        selected = em_elements._select_current_element_by_name(client, "foo")
        assert selected["uuid"] == "u1"

    def test_multiple_installed_raises(self) -> None:
        client = self._client(
            [
                {"name": "foo", "version": "1.0.0", "uuid": "u1", "status": "ACTIVE"},
                {"name": "foo", "version": "2.0.0", "uuid": "u2", "status": "ACTIVE"},
            ]
        )
        with pytest.raises(click.ClickException, match="Multiple installed"):
            em_elements._select_current_element_by_name(client, "foo")

    def test_prefers_installed_over_active_status(self) -> None:
        # Reproduces #589 Window 1: right after `ee update`, the freshly
        # installed element is INSTALLED but status=NEW, while the stale
        # element being replaced is UNINSTALLED but still status=ACTIVE.
        client = self._client(
            [
                {
                    "name": "foo",
                    "version": "0.0.12",
                    "uuid": "u_old",
                    "status": "ACTIVE",
                    "installation_state": "UNINSTALLED",
                },
                {
                    "name": "foo",
                    "version": "0.0.11",
                    "uuid": "u_new",
                    "status": "NEW",
                    "installation_state": "INSTALLED",
                },
            ]
        )
        selected = em_elements._select_current_element_by_name(client, "foo")
        assert selected["uuid"] == "u_new"

    def test_prefers_installed_in_progress_over_active(self) -> None:
        # Reproduces #589 Window 2: new element is now IN_PROGRESS, old one
        # is still ACTIVE but UNINSTALLED.
        client = self._client(
            [
                {
                    "name": "foo",
                    "version": "0.0.12",
                    "uuid": "u_old",
                    "status": "ACTIVE",
                    "installation_state": "UNINSTALLED",
                },
                {
                    "name": "foo",
                    "version": "0.0.11",
                    "uuid": "u_new",
                    "status": "IN_PROGRESS",
                    "installation_state": "INSTALLED",
                },
            ]
        )
        selected = em_elements._select_current_element_by_name(client, "foo")
        assert selected["uuid"] == "u_new"

    def test_multiple_installed_by_state_raises(self) -> None:
        client = self._client(
            [
                {
                    "name": "foo",
                    "version": "1.0.0",
                    "uuid": "u1",
                    "status": "ACTIVE",
                    "installation_state": "INSTALLED",
                },
                {
                    "name": "foo",
                    "version": "2.0.0",
                    "uuid": "u2",
                    "status": "ACTIVE",
                    "installation_state": "INSTALLED",
                },
            ]
        )
        with pytest.raises(click.ClickException, match="Multiple installed"):
            em_elements._select_current_element_by_name(client, "foo")


class TestPushCmd:
    """Tests for exordos.cmd.repo.commands.push_cmd."""

    def _obj(self) -> ContextObject:
        return ContextObject(
            auth_data={},
            cfg_path=None,
            developer_key_path=None,
            cfg={},
            need_update=None,
        )

    def _invoke(self, args: list[str]) -> MagicMock:
        with (
            patch.object(
                repo_commands.repo_utils,
                "load_repo_driver",
                return_value=MagicMock(),
            ),
            patch.object(repo_commands.repo_utils, "do_push") as do_push_mock,
        ):
            result = CliRunner().invoke(repo_commands.push_cmd, args, obj=self._obj())
        assert result.exit_code == 0, result.output
        return do_push_mock

    def test_push_cmd_default_jobs(self) -> None:
        do_push_mock = self._invoke([])
        assert do_push_mock.call_args.args[-1] == 1

    def test_push_cmd_jobs_option(self) -> None:
        do_push_mock = self._invoke(["-j", "4"])
        assert do_push_mock.call_args.args[-1] == 4

    def test_push_cmd_rejects_zero_jobs(self) -> None:
        result = CliRunner().invoke(
            repo_commands.push_cmd, ["-j", "0"], obj=self._obj()
        )
        assert result.exit_code != 0


class TestUpdateCmd:
    """Tests for exordos.cmd.em.elements.commands.update_cmd."""

    def _obj(self) -> ContextObject:
        return ContextObject(
            auth_data={},
            cfg_path=None,
            developer_key_path=None,
            cfg={},
            need_update=None,
        )

    def _invoke(self, args: list[str], current: dict, target: dict):
        with (
            patch.object(em_elements.base_client, "get_user_api_client"),
            patch.object(
                em_elements,
                "_select_current_element_by_name",
                return_value=current,
            ),
            patch.object(em_elements, "_select_element_by_name", return_value=target),
            patch.object(em_elements.base_client, "action_entity") as action_mock,
        ):
            result = CliRunner().invoke(em_elements.update_cmd, args, obj=self._obj())
        assert result.exit_code == 0, result.output
        return result, action_mock

    def test_update_cmd_without_newer_candidate_is_not_proposed(self) -> None:
        # Only strictly newer candidates are considered, so the selection
        # returns nothing when the installed element is the newest one.
        current = {"name": "foo", "version": "0.0.34", "uuid": "u_cur"}
        result, action_mock = self._invoke(["foo"], current, None)
        assert "already up to date" in result.output
        action_mock.assert_not_called()

    def test_update_cmd_limits_candidates_to_newer_versions(self) -> None:
        current = {"name": "foo", "version": "0.0.33", "uuid": "u_cur"}
        target = {"name": "foo", "version": "0.0.34", "uuid": "u_new"}
        with (
            patch.object(em_elements.base_client, "get_user_api_client"),
            patch.object(
                em_elements,
                "_select_current_element_by_name",
                return_value=current,
            ),
            patch.object(
                em_elements, "_select_element_by_name", return_value=target
            ) as select_mock,
            patch.object(em_elements.base_client, "action_entity"),
        ):
            result = CliRunner().invoke(
                em_elements.update_cmd, ["-y", "foo"], obj=self._obj()
            )
        assert result.exit_code == 0, result.output
        assert select_mock.call_args.kwargs["newer_than"] == "0.0.33"
        assert select_mock.call_args.kwargs["auto_select"] is True

    def test_update_cmd_newer_candidate_upgrades(self) -> None:
        current = {"name": "foo", "version": "0.0.33", "uuid": "u_cur"}
        target = {"name": "foo", "version": "0.0.34", "uuid": "u_new"}
        _, action_mock = self._invoke(["-y", "foo"], current, target)
        assert action_mock.call_args.kwargs["target"] == "u_new"

    def test_update_cmd_explicit_version_allows_downgrade(self) -> None:
        current = {"name": "foo", "version": "0.0.34", "uuid": "u_cur"}
        target = {"name": "foo", "version": "0.0.33", "uuid": "u_old"}
        _, action_mock = self._invoke(["-y", "-v", "0.0.33", "foo"], current, target)
        assert action_mock.call_args.kwargs["target"] == "u_old"
