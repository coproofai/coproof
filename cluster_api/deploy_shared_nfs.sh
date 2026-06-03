#!/bin/bash
# deploy_shared_nfs.sh — Set up a shared NFS dir visible to sms + all compute nodes.
#
# Architecture:
#   sms serves /srv/nfs/shared as a regular local dir.
#   Each compute node mounts 192.168.1.1:/srv/nfs/shared at /srv/nfs/shared
#   (same absolute path), so WORKDIR in runner.py resolves identically everywhere.
#
# Run as root on sms.
set -e

SHARED_DIR=/srv/nfs/shared
JOBS_DIR=$SHARED_DIR/cluster_jobs
SMS_INTERNAL_IP=192.168.1.1
MOUNT_POINT=/srv/nfs/shared
NODES=(node1 node2 node3)
NODE_IPS=(192.168.1.11 192.168.1.12 192.168.1.13)

echo "=== 1. Creating shared directory on sms ==="
mkdir -p "$JOBS_DIR"
chown -R mpiuser:mpiuser "$SHARED_DIR"
chmod 755 "$SHARED_DIR"

echo "=== 2. Adding NFS exports ==="
for ip in "${NODE_IPS[@]}"; do
    if ! grep -q "$SHARED_DIR.*$ip" /etc/exports 2>/dev/null; then
        echo "$SHARED_DIR $ip(rw,sync,no_root_squash,no_subtree_check)" >> /etc/exports
        echo "  added export for $ip"
    else
        echo "  export for $ip already present"
    fi
done

echo "=== 3. Re-exporting NFS ==="
exportfs -ra
exportfs -v | grep shared || echo "WARNING: shared not appearing in exportfs output"

echo "=== 4. Configuring each compute node ==="
for i in "${!NODES[@]}"; do
    node="${NODES[$i]}"
    node_root="/srv/nfs/$node"
    fstab="$node_root/etc/fstab"

    echo "--- $node ---"

    # Create mount point inside node's NFS root (so it exists when they boot)
    mkdir -p "$node_root$MOUNT_POINT"
    echo "  created $node_root$MOUNT_POINT"

    # Add persistent fstab entry (affects next boot)
    if ! grep -q "$SMS_INTERNAL_IP:$SHARED_DIR" "$fstab" 2>/dev/null; then
        echo "$SMS_INTERNAL_IP:$SHARED_DIR  $MOUNT_POINT  nfs  defaults,_netdev  0  0" >> "$fstab"
        echo "  added fstab entry"
    else
        echo "  fstab entry already present"
    fi

    # Live-mount on the running node (idempotent)
    if ssh -o ConnectTimeout=5 "$node" "mountpoint -q $MOUNT_POINT" 2>/dev/null; then
        echo "  already mounted"
    else
        ssh -o ConnectTimeout=5 "$node" "mkdir -p $MOUNT_POINT && mount $SMS_INTERNAL_IP:$SHARED_DIR $MOUNT_POINT" \
            && echo "  mounted successfully" \
            || echo "  WARNING: live mount failed (will work after reboot)"
    fi

    # Verify shared dir is visible from compute node
    ssh -o ConnectTimeout=5 "$node" "ls $JOBS_DIR" >/dev/null 2>&1 \
        && echo "  VERIFY OK: $JOBS_DIR visible from $node" \
        || echo "  WARNING: $JOBS_DIR not yet visible from $node"
done

echo "=== 5. Updating cluster_api service ==="
SERVICE=/etc/systemd/system/cluster_api.service
if [ -f "$SERVICE" ]; then
    sed -i "s|Environment=CLUSTER_JOBS_DIR=.*|Environment=CLUSTER_JOBS_DIR=$JOBS_DIR|" "$SERVICE"
    echo "  CLUSTER_JOBS_DIR set to $JOBS_DIR"
    systemctl daemon-reload
    systemctl restart cluster_api
    sleep 2
    systemctl is-active cluster_api && echo "  cluster_api running OK" || echo "  WARNING: cluster_api not running"
else
    echo "  WARNING: $SERVICE not found — update CLUSTER_JOBS_DIR manually"
fi

echo ""
echo "=== DONE ==="
echo "  Shared NFS:    $SMS_INTERNAL_IP:$SHARED_DIR"
echo "  Jobs dir:      $JOBS_DIR (on sms and all nodes at same path)"
echo "  CLUSTER_JOBS_DIR updated in cluster_api.service"
