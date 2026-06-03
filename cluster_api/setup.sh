#!/usr/bin/env bash
# setup.sh — one-shot bootstrap for the cluster REST API on the RPI manager node.
#
# Usage (run as root — on this cluster: ssh rocky@192.168.0.17, then sudo su):
#   sudo bash setup.sh
#
# Assumes: Rocky Linux, mpiuser account, Slurm + OpenMPI already installed.
#
# What it does:
#   1. Creates a Python venv and installs dependencies.
#   2. Generates a random API key if one does not already exist.
#   3. Installs and enables a systemd service unit.
#   4. Creates the jobs working directory with safe permissions.
#   5. Prints the API key so you can paste it into the Docker .env file.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Install to /opt so mpiuser (non-root) can access the working directory.
# The source checkout stays in /home/rocky; /opt/cluster_api is the live install.
INSTALL_DIR="/opt/cluster_api"
VENV_DIR="$INSTALL_DIR/venv"
API_KEY_FILE="$INSTALL_DIR/.api_key"
SERVICE_TEMPLATE="$SCRIPT_DIR/systemd/cluster_api.service"
INSTALLED_UNIT="/etc/systemd/system/cluster_api.service"
JOBS_DIR="/tmp/cluster_jobs"
RUN_USER="${SERVICE_USER:-mpiuser}"

# --- sync source to install dir --------------------------------------
echo "==> Syncing files to $INSTALL_DIR ..."
mkdir -p "$INSTALL_DIR"
cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
chown -R "$RUN_USER":"$RUN_USER" "$INSTALL_DIR"
chmod 750 "$INSTALL_DIR"
echo "    OK"

# --- venv ----------------------------------------------------------------
echo "==> Creating Python virtual environment..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip --quiet
"$VENV_DIR/bin/pip" install -r "$INSTALL_DIR/requirements.txt" --quiet
chown -R "$RUN_USER":"$RUN_USER" "$VENV_DIR"
echo "    OK"

# mpi4py needs libmpi; check mpirun is present
if ! command -v mpirun &>/dev/null; then
    echo ""
    echo "WARNING: mpirun not found on PATH."
    echo "         Install OpenMPI first:  sudo dnf install -y openmpi openmpi-devel"
    echo "         Then add to PATH:        module load mpi  (or add /usr/lib64/openmpi/bin to PATH)"
    echo ""
fi

# On Rocky Linux, mpirun may live under the module system; make sure it is on PATH
# for the mpiuser when launched from systemd (EnvironmentFile or ExecStartPre can load it).
if command -v mpirun &>/dev/null; then
    MPIRUN_PATH="$(command -v mpirun)"
    echo "==> Found mpirun at: $MPIRUN_PATH"
fi

# --- API key -------------------------------------------------------------
# Key file lives in INSTALL_DIR (not SCRIPT_DIR) so mpiuser owns it.
# If a key was already generated in SCRIPT_DIR, preserve it.
if [ -f "$SCRIPT_DIR/.api_key" ] && [ ! -f "$API_KEY_FILE" ]; then
    cp "$SCRIPT_DIR/.api_key" "$API_KEY_FILE"
    chown "$RUN_USER":"$RUN_USER" "$API_KEY_FILE"
    chmod 600 "$API_KEY_FILE"
fi
if [ ! -f "$API_KEY_FILE" ]; then
    echo "==> Generating API key..."
    python3 -c "import secrets; print(secrets.token_hex(32))" > "$API_KEY_FILE"
    chown "$RUN_USER":"$RUN_USER" "$API_KEY_FILE"
    chmod 600 "$API_KEY_FILE"
fi
API_KEY="$(cat "$API_KEY_FILE")"
echo "==> API key read from $API_KEY_FILE"

# --- jobs directory ------------------------------------------------------
echo "==> Creating jobs directory $JOBS_DIR ..."
mkdir -p "$JOBS_DIR"
chown "$RUN_USER":"$RUN_USER" "$JOBS_DIR"
chmod 700 "$JOBS_DIR"

# --- systemd unit --------------------------------------------------------
echo "==> Installing systemd service..."
sed \
    -e "s|__SCRIPT_DIR__|$INSTALL_DIR|g" \
    -e "s|__VENV_DIR__|$VENV_DIR|g" \
    -e "s|__API_KEY__|$API_KEY|g" \
    -e "s|__RUN_USER__|$RUN_USER|g" \
    "$SERVICE_TEMPLATE" > "$INSTALLED_UNIT"

systemctl daemon-reload
systemctl enable cluster_api.service
systemctl restart cluster_api.service
echo "==> Service started."

# --- summary -------------------------------------------------------------
echo ""
echo "============================================================"
echo "  cluster_api is running on port 8765 (user: $RUN_USER)"
echo ""
echo "  If mpirun is not on PATH for systemd, edit the unit:"
echo "    /etc/systemd/system/cluster_api.service  -> Environment=PATH=..."
echo "  Rocky Linux prerequisite (if not already installed):"
echo "    sudo dnf install -y openmpi openmpi-devel python3-devel"
echo ""
# Prefer the LAN IP on the 192.168.0.x network (the Docker host network)
LAN_IP=$(ip -4 addr show | awk '/inet / && /192\.168\.0\./{gsub(/\/.*/, "", $2); print $2}' | head -1)
LAN_IP="${LAN_IP:-$(hostname -I | awk '{print $1}')}"
echo "  Add these to your Docker stack .env file:"
echo "    CLUSTER_API_URL=http://$LAN_IP:8765"
echo "    CLUSTER_API_KEY=$API_KEY"
echo "============================================================"
echo ""
systemctl status cluster_api.service --no-pager || true
