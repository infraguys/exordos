#    Copyright 2026 Genesis Corporation.
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

import importlib.resources as resources
import shlex
import subprocess
import sys

import pytest


@pytest.mark.skipif(sys.platform != "linux", reason="Image cleanup uses GNU find")
@pytest.mark.parametrize("profile", ["exordos_custom", "exordos_base"])
def test_shutdown_log_cleanup_preserves_directories_and_symlinks(tmp_path, profile):
    template = resources.files(f"exordos.packer.{profile}").joinpath(
        f"{profile.replace('_', '-')}.pkr.hcl"
    )
    shutdown = template.read_text().split("shutdown_command", 1)[1]
    cleanup = shutdown.split("# Logs\n", 1)[1].split("\n# Remove temporary keys", 1)[0]
    assert "/var/log" in cleanup

    log_dir = tmp_path / "var" / "log"
    directories = [log_dir / "nginx", log_dir / "apt", log_dir / "journal" / "machine"]
    if profile == "exordos_custom":
        directories.append(log_dir / "app" / "2026" / "09")
    for directory in directories:
        directory.mkdir(parents=True)
        directory.chmod(0o750)
    before = {directory: directory.stat() for directory in directories}
    logs = [log_dir / "syslog", log_dir / ".hidden"] + [
        directory / "build.log" for directory in directories
    ]
    for log in logs:
        log.write_text("build-time log\n")

    outside = tmp_path / "outside"
    outside.mkdir()
    outside_log = outside / "keep.log"
    outside_log.write_text("outside log tree\n")
    links = [log_dir / "linked-dir", log_dir / "linked-file"]
    links[0].symlink_to(outside, target_is_directory=True)
    links[1].symlink_to(outside_log)

    # Run the shipped cleanup command without sudo against an isolated log tree.
    cleanup = cleanup.replace("sudo ", "").replace(
        "/var/log", shlex.quote(str(log_dir))
    )
    subprocess.run(["sh", "-ec", cleanup], check=True)

    for directory, original in before.items():
        assert directory.is_dir()
        current = directory.stat()
        assert (current.st_mode, current.st_uid, current.st_gid) == (
            original.st_mode,
            original.st_uid,
            original.st_gid,
        )
    assert all(not log.exists() for log in logs)
    assert all(link.is_symlink() for link in links)
    assert outside_log.read_text() == "outside log tree\n"
