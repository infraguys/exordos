locals {
  cd_content = {
    "meta-data" = yamlencode({
      instance-id = "iid-local01"
    })
    "user-data" = join("\n", [
      "#cloud-config",
      yamlencode({
        ssh_authorized_keys = [
          data.sshkey.install.public_key
        ]
      })
    ])
  }
}

variable cpus {
  type    = number
  default = 2
}

variable memory {
  type    = number
  default = 2048
}

variable disk_size {
  type    = string
  default = "4500M"
}

variable img_format {
  type    = string
  default = "raw"
}

variable base_image_url {
  type    = string
  default = "https://repo.exordos.com/exordos-base/latest/exordos-base.qcow2"
}

variable base_image_checksum {
  type    = string
  default = "file:https://repo.exordos.com/exordos-base/latest/SHA256SUMS"
}

data "sshkey" "install" {
  name = "packer"
}

source "qemu" "exordos-custom" {
  iso_url                   = var.base_image_url
  iso_checksum              = var.base_image_checksum
  accelerator               = "kvm"
  cpu_model                 = "host"
  boot_wait                 = "5s"
  boot_command              = ["<enter>"]
  cpus                      = var.cpus
  memory                    = var.memory
  disk_image                = true
  disk_size                 = var.disk_size
  disk_interface            = "virtio-scsi"
  disk_cache                = "unsafe"
  disk_discard              = "unmap"
  disk_detect_zeroes        = "unmap"
  disk_compression          = true
  format                    = var.img_format
  net_device                = "virtio-net"
  headless                  = true
  qemu_binary               = "qemu-system-x86_64"
  ssh_timeout               = "30s"
  ssh_username              = "ubuntu"
  ssh_clear_authorized_keys = true
  temporary_key_pair_name   = "packer"
  qemuargs                  = [["-serial", "stdio"]]
  # It's quite unstable to use shrink so uncomment it if you need it very much
  # qemu_img_args {
  #   resize  = ["--shrink"]
  # }
  output_directory          = var.output_directory
  vm_name                   = "${source.name}.${var.img_format}"
  ssh_private_key_file      = data.sshkey.install.private_key_path
  cd_label                  = "cidata"
  cd_content                = local.cd_content
  shutdown_command        = <<EOF
set -ex

# Logs
sudo find /var/log -type f -delete

# Remove temporary keys
# Disable removing host keys temporarily
# sudo rm -f /etc/ssh/*host*key*

# Add developer keys
sudo mkdir -p /home/ubuntu/.ssh
[[ -f /tmp/__dev_keys ]] && sudo mv /tmp/__dev_keys /home/ubuntu/.ssh/authorized_keys

# Tmp files
sudo rm -rf /tmp/* /var/tmp/*

# clear machine-id
sudo rm -f /etc/machine-id /var/lib/dbus/machine-id
sudo touch /etc/machine-id
sudo touch /var/lib/dbus/machine-id

# Shell history
history -c

# Cloud-init clean
sudo cloud-init clean --log --seed

# Sync FS
sudo sync

# Minify orphan space
sudo fstrim -a

# Stop update services; `systemctl stop` waits for an in-flight
# apt transaction to finish instead of killing it.
sudo systemctl stop unattended-upgrades.service apt-daily.service apt-daily-upgrade.service 2>/dev/null || true

# Shutdown machine
sudo systemctl poweroff
EOF
}
