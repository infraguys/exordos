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

import abc
import typing as tp

from exordos import constants as c
from exordos import exceptions
from exordos.builder import base as builder_base


class RepoAlreadyExistsError(exceptions.ExordosException):
    """Repo already exists."""


class RepoNotFoundError(exceptions.ExordosException):
    """Repo not found."""


class ElementAlreadyExistsError(exceptions.ExordosException):
    """Element already exists in the repo."""


class RepoHTTPError(exceptions.ExordosException):
    """A request to the repo server failed."""

    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class UnableLoadDriverError(exceptions.ExordosException):
    """Unable to load driver."""


class RepoMetaV1(tp.NamedTuple):
    schema_version: int = 1
    name: str = c.ELEMENT_REPO_PATH

    def to_dict(self) -> dict[str, tp.Any]:
        return {"schema_version": self.schema_version, "name": self.name}

    @classmethod
    def from_dict(cls, data: dict[str, tp.Any]) -> "RepoMetaV1":
        return cls(schema_version=data["schema_version"], name=data["name"])


class AbstractRepoDriver(abc.ABC):
    @property
    def name(self) -> str:
        """Return the name of the repo."""
        ...

    @property
    @abc.abstractmethod
    def elements_path(self) -> str:
        """Return the base path/URL for elements in the repo."""
        ...

    @abc.abstractmethod
    def init_repo(self) -> None:
        """Initialize the repo."""

    @abc.abstractmethod
    def delete_repo(self) -> None:
        """Delete the repo."""

    @abc.abstractmethod
    def push(
        self,
        element: builder_base.ElementInventory,
        latest: bool = False,
        workers: int = 1,
    ) -> None:
        """Push the element to the repo.

        ``workers`` is the number of artifacts to upload in parallel. Drivers
        that do not transfer artifacts over the network may ignore it.
        """

    @abc.abstractmethod
    def pull(self, element: builder_base.ElementInventory, dst_path: str) -> None:
        """Pull the element from the repo."""

    @abc.abstractmethod
    def remove(self, element: builder_base.ElementInventory) -> None:
        """Remove the element from the repo."""

    @abc.abstractmethod
    def list(self) -> dict[str, list[str]]:
        """List the elements in the repo."""

    def inventories(self) -> dict:
        """Return the repo inventory."""
        return {}
