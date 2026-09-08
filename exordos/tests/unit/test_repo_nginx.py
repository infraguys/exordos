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
"""Unit tests for the parallel artifact upload of the nginx repo driver."""

import pathlib
import threading

import pytest
import requests

from exordos.builder import base as builder_base
from exordos.repo import base
from exordos.repo import nginx


def _element() -> builder_base.ElementInventory:
    return builder_base.ElementInventory(
        name="elem",
        version="1.0.0",
        images=[pathlib.Path("/tmp/foo.raw"), pathlib.Path("/tmp/bar.raw")],
        manifests=[pathlib.Path("/tmp/elem.yaml")],
    )


class TestUploadArtifacts:
    """Tests for NginxRepoDriver._upload_artifacts."""

    def test_upload_artifacts_uploads_every_artifact(self) -> None:
        driver = nginx.NginxRepoDriver(url="http://repo.example.com")
        uploaded: list[tuple[str, str]] = []
        driver._upload_file = lambda local, remote: uploaded.append(
            (str(local), remote)
        )

        driver._upload_artifacts(_element(), "http://repo/elem/1.0.0", "elem/1.0.0", 1)

        assert uploaded == [
            ("/tmp/foo.raw", "http://repo/elem/1.0.0/images/foo.raw"),
            ("/tmp/bar.raw", "http://repo/elem/1.0.0/images/bar.raw"),
            ("/tmp/elem.yaml", "http://repo/elem/1.0.0/manifests/elem.yaml"),
        ]

    def test_upload_artifacts_parallel_uploads_every_artifact(self) -> None:
        driver = nginx.NginxRepoDriver(url="http://repo.example.com")
        lock = threading.Lock()
        threads: set[int] = set()
        uploaded: list[str] = []

        def upload_file(local: str, remote: str) -> None:
            barrier.wait(timeout=5)
            with lock:
                threads.add(threading.get_ident())
                uploaded.append(remote)

        # All three uploads must be in flight at once, otherwise the barrier
        # times out and the test fails.
        barrier = threading.Barrier(3)
        driver._upload_file = upload_file

        driver._upload_artifacts(_element(), "http://repo/elem/1.0.0", "elem/1.0.0", 3)

        assert sorted(uploaded) == [
            "http://repo/elem/1.0.0/images/bar.raw",
            "http://repo/elem/1.0.0/images/foo.raw",
            "http://repo/elem/1.0.0/manifests/elem.yaml",
        ]
        assert len(threads) == 3


def _response(status_code: int, method: str = "PUT") -> requests.Response:
    response = requests.Response()
    response.status_code = status_code
    response.reason = "Conflict" if status_code == 409 else "Error"
    response.url = "http://repo.example.com/elements/elem/1.0.0/images/foo.raw"
    response.request = requests.Request(method=method, url=response.url).prepare()
    return response


class TestCheckResponse:
    """Tests for NginxRepoDriver._check_response."""

    def test__check_response_passes_on_success(self) -> None:
        driver = nginx.NginxRepoDriver(url="http://repo.example.com")

        assert driver._check_response(_response(201), "upload foo.raw") is None

    def test__check_response_reports_readable_error_with_hint(self) -> None:
        driver = nginx.NginxRepoDriver(url="http://repo.example.com")

        with pytest.raises(base.RepoHTTPError) as exc_info:
            driver._check_response(_response(409), "upload foo.raw")

        message = str(exc_info.value)
        assert exc_info.value.status_code == 409
        assert "Failed to upload foo.raw" in message
        assert "409 Conflict" in message
        assert (
            "PUT http://repo.example.com/elements/elem/1.0.0/images/foo.raw" in message
        )
        assert nginx.HTTP_ERROR_HINTS[409] in message
        assert "<html>" not in message

    def test__check_response_reports_error_without_hint(self) -> None:
        driver = nginx.NginxRepoDriver(url="http://repo.example.com")

        with pytest.raises(base.RepoHTTPError) as exc_info:
            driver._check_response(_response(500), "upload foo.raw")

        assert exc_info.value.status_code == 500
        assert "Failed to upload foo.raw" in str(exc_info.value)
