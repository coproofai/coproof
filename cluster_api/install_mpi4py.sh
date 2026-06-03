#!/bin/bash
# Install mpi4py on all compute nodes
set -e

for n in node1 node2 node3; do
  echo "=== $n ==="
  ssh "$n" bash -s <<'NODEEOF'
set -e
echo "[python] $(python3 --version)"
# Install pip if missing
if ! python3 -c "import pip" 2>/dev/null; then
  dnf install -y python3-pip 2>&1
fi
# Install mpi4py (needs OpenMPI headers)
dnf install -y python3-mpi4py-openmpi 2>&1 || \
  pip3 install mpi4py 2>&1
echo "[verify] $(python3 -c 'from mpi4py import MPI; print(\"mpi4py OK, version:\", MPI.Get_version())')"
NODEEOF
  echo "EXIT: $?"
done
