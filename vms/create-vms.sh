#!/bin/bash

set -euo pipefail

# Consts
BASE_URL="https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img" # Use Ubuntu 24.04 LTS (Noble) cloud image
POOL="${POOL:-/var/lib/libvirt/images}"
BASE="$POOL/noble-base.img"
NET=default
VIRSH="virsh -c qemu:///system"
SUDO=sudo
if [ -w "$POOL" ]; then SUDO=""; fi   # a user-writable pool needs no root
SSH_KEY="${SSH_KEY:-$HOME/.ssh/id_ed25519.pub}"

# name            cpu  mem(MiB)  disk  ip               mac
VMS=(
  "k3s-master      4    3072      20G   192.168.122.11   52:54:00:4b:a7:01"
  "k3s-worker-1    8    4096      20G   192.168.122.12   52:54:00:4b:a7:02"
  "k3s-worker-2    4    4096      20G   192.168.122.14   52:54:00:4b:a7:04"
  "k3s-siem        2    4096      30G   192.168.122.13   52:54:00:4b:a7:03"
)

[ -f "$SSH_KEY" ] || { echo "SSH public key not found: $SSH_KEY"; echo "Generate one with: ssh-keygen -t ed25519"; exit 1; }
PUBKEY=$(cat "$SSH_KEY")

if [ ! -f "$BASE" ]; then
    echo "==> Downloading Ubuntu 24.04 cloud image"
    $SUDO curl -fL --progress-bar -o "$BASE" "$BASE_URL"
fi

for spec in "${VMS[@]}"; do
    read -r NAME CPU MEM DISK IP MAC <<< "$spec"

    if $VIRSH dominfo "$NAME" &>/dev/null; then
        echo "==> $NAME already exists, skipping"
        continue
    fi

    echo "==> Creating $NAME  ($CPU vCPU, ${MEM}MiB, $DISK, $IP)"

    # Pin the IP so the Ansible inventory stays valid across reboots
    $VIRSH net-update "$NET" add ip-dhcp-host \
        "<host mac='$MAC' name='$NAME' ip='$IP'/>" --live --config 2>/dev/null || true

    $SUDO cp "$BASE" "$POOL/$NAME.qcow2"
    $SUDO qemu-img resize "$POOL/$NAME.qcow2" "$DISK"

    WORK=$(mktemp -d)
    cat > "$WORK/user-data" <<EOF
#cloud-config
hostname: $NAME
fqdn: $NAME
users:
  - name: ubuntu
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    ssh_authorized_keys:
      - $PUBKEY
ssh_pwauth: false
EOF
    echo "instance-id: $NAME" > "$WORK/meta-data"
    cloud-localds "$WORK/seed.iso" "$WORK/user-data" "$WORK/meta-data"
    $SUDO mv "$WORK/seed.iso" "$POOL/$NAME-seed.iso"
    rm -rf "$WORK"

    $SUDO virt-install --connect qemu:///system \
        --name "$NAME" \
        --memory "$MEM" --vcpus "$CPU" \
        --disk "path=$POOL/$NAME.qcow2,format=qcow2,bus=virtio" \
        --disk "path=$POOL/$NAME-seed.iso,device=cdrom" \
        --network "network=$NET,mac=$MAC,model=virtio" \
        --os-variant ubuntu24.04 \
        --graphics none --noautoconsole --import
done

echo
echo "==> Waiting for SSH on all three"
for spec in "${VMS[@]}"; do
    read -r NAME _ _ _ IP _ <<< "$spec"
    for _ in $(seq 60); do
        ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=3 \
            ubuntu@"$IP" true 2>/dev/null && break
        sleep 5
    done
    printf "  %-14s %s  " "$NAME" "$IP"
    ssh -o BatchMode=yes -o StrictHostKeyChecking=no ubuntu@"$IP" true 2>/dev/null \
        && echo "ready" || echo "NOT REACHABLE"
done
