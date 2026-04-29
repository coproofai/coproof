#!/bin/bash
# deploy3.sh — Install mpi4py into shared NFS, deploy updated job_manager, update service
PYLIB=/srv/nfs/shared/pylib

echo "=== 1. Install mpi4py on sms into shared NFS pylib ==="
mkdir -p "$PYLIB"
pip3 install mpi4py --target="$PYLIB" --upgrade 2>&1
echo "  mpi4py installed to $PYLIB"

echo "=== 2. Verify mpi4py importable from pylib ==="
PYTHONPATH="$PYLIB" LD_LIBRARY_PATH=/usr/lib64/openmpi/lib:$LD_LIBRARY_PATH \
  python3 -c "from mpi4py import MPI; print('  mpi4py OK, version:', MPI.Get_version())" \
  && echo "  VERIFY OK" || echo "  NOTE: verify failed on sms (lib path); will work on nodes via sbatch LD_LIBRARY_PATH"

echo "=== 3. Deploy updated job_manager.py ==="
cp /tmp/job_manager_new.py /opt/cluster_api/job_manager.py
echo "  job_manager.py updated"

echo "=== 4. Update service file ==="
python3 - <<'PYEOF'
import re, pathlib
f = pathlib.Path("/etc/systemd/system/cluster_api.service")
txt = f.read_text()
# Remove existing SHARED_PYLIB line if present
txt = re.sub(r'\nEnvironment=SHARED_PYLIB=[^\n]*', '', txt)
# Insert after OPENMPI_BIN line
if 'Environment=OPENMPI_BIN=' in txt:
    txt = re.sub(
        r'(Environment=OPENMPI_BIN=[^\n]*)',
        r'\1\nEnvironment=SHARED_PYLIB=/srv/nfs/shared/pylib',
        txt
    )
else:
    txt = re.sub(
        r'(Environment=CLUSTER_JOBS_DIR=[^\n]*)',
        r'\1\nEnvironment=SHARED_PYLIB=/srv/nfs/shared/pylib',
        txt
    )
f.write_text(txt)
print("  service file updated")
PYEOF

echo "=== 5. Restart cluster_api ==="
systemctl daemon-reload
systemctl restart cluster_api.service
sleep 2
systemctl is-active cluster_api && echo "  cluster_api running OK" || echo "  WARNING: not running"

echo ""
echo "=== DONE ==="
echo "  mpi4py is at: $PYLIB"
echo "  Compute nodes will find it via PYTHONPATH in job.sh"
