FROM jenkins/jenkins:lts

USER root

# ── Docker CLI + Compose plugin ────────────────────────────────────────────
RUN apt-get update \
    && apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg \
       | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && echo \
       "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
        https://download.docker.com/linux/debian $(lsb_release -cs) stable" \
       > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# ── Node.js 20 (vitest + Cypress) ──────────────────────────────────────────
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# ── Python 3 + pip (suite.py, performance scripts) ─────────────────────────
RUN apt-get update \
    && apt-get install -y python3 python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Allow jenkins user to run Docker commands via the host socket
RUN groupadd -f docker && usermod -aG docker jenkins

# ── Pre-install Jenkins plugins ────────────────────────────────────────────
# workflow-aggregator pulls in the full Pipeline suite (declarative + scripted)
# git is required for Pipeline script from SCM
# pipeline-stage-view adds the classic stage visualisation in the UI
USER jenkins
RUN jenkins-plugin-cli --plugins \
    workflow-aggregator \
    git \
    pipeline-stage-view \
    docker-workflow
