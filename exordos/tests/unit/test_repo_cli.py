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
import json
import pathlib
from unittest.mock import MagicMock
from unittest.mock import patch
import uuid as sys_uuid

import click
from click.testing import CliRunner
import pytest

from exordos import constants as c
from exordos import utils
from exordos.builder import base as builder_base
from exordos.cmd.em.elements import commands as em_elements
from exordos.cmd.repo import commands as repo_commands
from exordos.cmd.repo.elements import commands as repo_elements
from exordos.common.cmd_context import ContextObject
from exordos.repo import utils as repo_utils


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

    def test_selects_highest_version(self) -> None:
        elements = [
            {"name": "foo", "version": "1.0.0", "uuid": "u1", "repository": ""},
            {"name": "foo", "version": "2.0.0", "uuid": "u2", "repository": ""},
            {"name": "foo", "version": "1.5.0", "uuid": "u3", "repository": ""},
        ]
        client = self._client(elements)
        selected = em_elements._select_element_by_name(client, "foo", None)
        assert selected["uuid"] == "u2"

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


class TestDoPush:
    """Tests for exordos.repo.utils.do_push."""

    def _element_dir(self, tmp_path: pathlib.Path) -> pathlib.Path:
        inventory = builder_base.ElementInventory(name="elem", version="1.0.0")
        elements_dir = tmp_path / c.ELEMENT_REPO_PATH
        elements_dir.mkdir(parents=True)
        (elements_dir / "inventory.json").write_text(
            json.dumps({"elements": {"elem": {"1.0.0": inventory.to_dict()}}})
        )
        return tmp_path

    def test_do_push_prints_pushed_element_without_tty(
        self, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        driver = MagicMock()
        driver.name = "exordos_repo"

        repo_utils.do_push(driver, self._element_dir(tmp_path), False, False)

        assert "Push elem to exordos_repo..." in capsys.readouterr().out
        driver.push.assert_called_once()

    def test_do_push_uses_spinner_on_tty(
        self, tmp_path: pathlib.Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        driver = MagicMock()
        driver.name = "exordos_repo"

        with patch.object(repo_utils.sys.stdout, "isatty", return_value=True):
            repo_utils.do_push(driver, self._element_dir(tmp_path), False, False)

        # The spinner owns the output, nothing is echoed as a plain line.
        assert "Push elem to exordos_repo..." not in capsys.readouterr().out
        driver.push.assert_called_once()
