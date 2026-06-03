#!/bin/bash
set -e

# At container start, the mounted /var/run/docker.sock may have a different GID
# than the 'docker' group created at image build time. Realign them so the
# jenkins user can reach the Docker API without running as root.
if [ -S /var/run/docker.sock ]; then
    SOCK_GID=$(stat -c '%g' /var/run/docker.sock)
    # -o allows reusing a GID already assigned to another group (e.g. root=0)
    groupmod -o -g "${SOCK_GID}" docker 2>/dev/null \
        || groupadd -o -g "${SOCK_GID}" docker 2>/dev/null \
        || true
    usermod -aG docker jenkins
fi

# Drop privileges and hand off to the official Jenkins init
exec gosu jenkins /usr/bin/tini -- /usr/local/bin/jenkins.sh "$@"
