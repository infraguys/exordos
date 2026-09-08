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

from exordos import constants as c
from exordos.cmd.base import create_entity_group

ENTITY = "version"
ENTITY_COLLECTION = c.S3_VERSION_COLLECTION
FIELDS_MAP = {
    "UUID": "uuid",
    "Name": "name",
    "Description": "description",
    "Image": "image",
}

# Versions are provided by the s3 element itself, so they are read only here.
versions_group = create_entity_group(
    ENTITY, ENTITY_COLLECTION, FIELDS_MAP, add_delete_command=False
)
