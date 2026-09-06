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

import ipaddress
import os
import typing as tp

PKG_NAME = "exordos"
GITHUB_RELEASES_URL = f"https://api.github.com/repos/infraguys/{PKG_NAME}/releases"
EXORDOS_REPO_URL = "https://repo.exordos.com"
ECOSYSTEM_ENDPOINT = "https://exordos.com"
ELEMENT_REPO_PATH = "exordos-elements"
ELEMENT_REPO_URL = f"{EXORDOS_REPO_URL}/{ELEMENT_REPO_PATH}"
LIBVIRT_DEF_POOL_PATH = "/var/lib/libvirt/images"
DEF_GEN_CFG_FILE_NAME = "exordos.yaml"
DEF_GEN_WORK_DIR_NAME = "exordos"
DEF_GEN_OUTPUT_DIR_NAME = "output"
RC_BRANCHES = ("master", "main")
ENCRYPTED_EXTENSION = ".encrypted"
EP_BACKUP_DRIVERS = "exordos.backup.drivers"
EP_REPO_DRIVERS = "exordos.repo.drivers"
GB_SHIFT = 30

# IAM constants
DEFAULT_IAM_TTL = 15 * 60
DEFAULT_IAM_REFRESH_TTL = 60 * 60
DEFAULT_IAM_SCOPE = "profile"

# ENV vars
ENV_GEN_DEV_KEYS = "GEN_DEV_KEYS"

# Types
ImageProfileType = tp.Literal["ubuntu_24", "exordos_base", "exordos_base_minimal"]
ImageFormatType = tp.Literal["raw", "qcow2", "gz", "zst"]
NetType = tp.Literal["network", "bridge"]
VersionSuffixType = tp.Literal["latest", "none", "element"]
DomainState = tp.Literal["all", "inactive", "state-paused"]
NodeType = tp.Literal["bootstrap", "baremetal"]

ENV_FILE_FORMAT = tp.Literal["json", "env"]

MANIFEST_COLLECTION = "/v1/em/manifests/"
ELEMENT_COLLECTION = "/v1/em/elements/"
SERVICE_COLLECTION = "/v1/em/services/"
RESOURCE_COLLECTION = "/v1/em/resources/"
IMPORTS_COLLECTION = "/v1/em/imports/"
EXPORTS_COLLECTION = "/v1/em/exports/"

REPOSITORY_COLLECTION = "/v1/repo/repositories/"
REPOSITORY_ELEMENT_COLLECTION = "/v1/repo/elements/"
REPOSITORY_STORE_COLLECTION = "/v1/repo/store/"
REPOSITORY_STORE_ELEMENT_COLLECTION = "/v1/repo/store/elements/"

PROFILE_COLLECTION = "/v1/vs/profiles/"
VALUE_COLLECTION = "/v1/vs/values/"
VARIABLE_COLLECTION = "/v1/vs/variables/"

LIMIT_COLLECTION = "/v1/quota/limits/"

CERTIFICATE_COLLECTION = "/v1/secret/certificates/"
PASSWORD_COLLECTION = "/v1/secret/passwords/"
SSH_KEY_COLLECTION = "/v1/secret/ssh_keys/"
RSA_KEY_COLLECTION = "/v1/secret/rsa_keys/"

NODE_COLLECTION = "/v1/compute/nodes/"
HYPERVISOR_COLLECTION = "/v1/compute/hypervisors/"
SET_COLLECTION = "/v1/compute/sets/"

USER_COLLECTION = "/v1/iam/users/"
IDP_COLLECTION = "/v1/iam/idp/"
CLIENT_COLLECTION = "/v1/iam/clients/"
ORGANIZATION_COLLECTION = "/v1/iam/organizations/"
PROJECT_COLLECTION = "/v1/iam/projects/"
ROLE_COLLECTION = "/v1/iam/roles/"
PERMISSION_COLLECTION = "/v1/iam/permissions/"
ROLE_BINDING_COLLECTION = "/v1/iam/role_bindings/"
PERMISSION_BINDING_COLLECTION = "/v1/iam/permission_bindings/"
ORGANIZATION_MEMBER_COLLECTION = "/v1/iam/organizations/{organization_uuid}/members/"

CONFIG_COLLECTION = "/v1/config/configs/"

SECURITY_RULES_COLLECTION = "/v1/security/rules/"

DOMAIN_COLLECTION = "/v1/dns/domains/"
RECORD_COLLECTION = "/v1/dns/domains/{domain_uuid}/records/"

PG_VERSION_COLLECTION = "/v1/types/postgres/versions/"
PG_INSTANCE_COLLECTION = "/v1/types/postgres/instances/"
PG_DATABASE_COLLECTION = "/v1/types/postgres/instances/{instance_uuid}/databases/"
PG_USER_COLLECTION = "/v1/types/postgres/instances/{instance_uuid}/users/"

# Served by the metapaas element itself, not by core.
METAPAAS_TYPE_COLLECTION = "/v1/types/"

# Served by the mail PaaS plugin, mounted by metapaas under /v1/types/mail/.
MAIL_VERSION_COLLECTION = "/v1/types/mail/versions/"
MAIL_INSTANCE_COLLECTION = "/v1/types/mail/instances/"
MAIL_ACCOUNT_COLLECTION = "/v1/types/mail/instances/{instance_uuid}/accounts/"

AGENT_COLLECTION = "/v1/ua/agents/"
ACTUAL_RESOURCE_COLLECTION = "/v1/ua/resources/"
TARGET_RESOURCE_COLLECTION = "/v1/ua/target_resources/"

LB_COLLECTION = "/v1/network/lb/"
BACKEND_POOL_COLLECTION = "/v1/network/lb/{lb_uuid}/backend_pools/"
VHOST_COLLECTION = "/v1/network/lb/{lb_uuid}/vhosts/"
ROUTE_COLLECTION = "/v1/network/lb/{lb_uuid}/vhosts/{vhost_uuid}/routes/"

# SNAT/DNAT rules are inline on the border resource (no sub-collections).
BORDER_COLLECTION = "/v1/network/border/"

# Cli
CONFIG_DIR = "~/.exordos"
CONFIG_FILE = os.path.expanduser(f"{CONFIG_DIR}/exordosctl.yaml")
LAST_CHECK_FILE = os.path.expanduser(f"{CONFIG_DIR}/exordosctl.last_version_check")
BOOTSTRAP_USER = "ubuntu"
UPDATE_CHECK_INTERVAL = 60 * 60  # 1 hour in seconds

CORE_ELEMENT = "core"
BASE_ELEMENTS = [CORE_ELEMENT, "ecosystem_realm"]

DEFAULT_TABLE_FORMAT = "table"
TABLE_FORMATS = ["json", "html", DEFAULT_TABLE_FORMAT, "yaml"]

GC_CIDR = ipaddress.IPv4Network("10.20.0.0/22")
GC_BOOT_CIDR = ipaddress.IPv4Network("10.30.0.0/24")
GC_ADDRESS = ipaddress.IPv4Address("10.20.0.1")
