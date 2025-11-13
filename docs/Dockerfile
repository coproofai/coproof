FROM debian:bookworm-slim

LABEL maintainer="Emiliano Flores"
ENV DEBIAN_FRONTEND=noninteractive

# ============================================================
#  Dependencias base
# ============================================================
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget gnupg ca-certificates lsb-release apt-transport-https \
    build-essential git python3 python3-pip openjdk-17-jdk \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
#  Node.js + Angular CLI
# ============================================================
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get update && apt-get install -y nodejs \
    && npm install -g @angular/cli \
    && rm -rf /var/lib/apt/lists/*

# ============================================================
#  Lean4
# ============================================================
RUN curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh \
    | bash -s -- -y --default-toolchain leanprover/lean4:stable
ENV PATH="/root/.elan/bin:${PATH}"

# ============================================================
# ️ Jenkins y Plugin Installation Manager
# ============================================================
ENV JENKINS_HOME=/var/jenkins_home
ENV JENKINS_WAR=/opt/jenkins/jenkins.war
ENV JENKINS_PLUGIN_CLI_JAR=/usr/local/bin/jenkins-plugin-cli.jar

RUN set -eux; \
    mkdir -p /opt/jenkins ${JENKINS_HOME}; \
    wget -q -O ${JENKINS_WAR} https://updates.jenkins.io/download/war/latest/jenkins.war; \
    LATEST_VERSION=$(curl -s https://api.github.com/repos/jenkinsci/plugin-installation-manager-tool/releases/latest \
        | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/'); \
    wget -q -O ${JENKINS_PLUGIN_CLI_JAR} \
        https://github.com/jenkinsci/plugin-installation-manager-tool/releases/download/${LATEST_VERSION}/jenkins-plugin-manager-${LATEST_VERSION}.jar; \
    echo '#!/bin/sh' > /usr/local/bin/jenkins-plugin-cli; \
    echo "exec java -jar ${JENKINS_PLUGIN_CLI_JAR} \"\$@\"" >> /usr/local/bin/jenkins-plugin-cli; \
    chmod +x /usr/local/bin/jenkins-plugin-cli

# ============================================================
#  Copiar archivos de configuración y plugins
# ============================================================
COPY plugins.txt /opt/jenkins/plugins.txt
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# ============================================================
#  Instalar plugins automáticamente
# ============================================================
RUN jenkins-plugin-cli --war ${JENKINS_WAR} --plugin-file /opt/jenkins/plugins.txt

# ============================================================
#  Crear usuario admin automático
# ============================================================
RUN mkdir -p ${JENKINS_HOME}/init.groovy.d && \
    echo 'import jenkins.model.*; import hudson.security.*; \
    def instance = Jenkins.getInstance(); \
    def hudsonRealm = new HudsonPrivateSecurityRealm(false); \
    hudsonRealm.createAccount("admin", "admin"); \
    instance.setSecurityRealm(hudsonRealm); \
    def strategy = new FullControlOnceLoggedInAuthorizationStrategy(); \
    instance.setAuthorizationStrategy(strategy); \
    instance.save();' > ${JENKINS_HOME}/init.groovy.d/basic-security.groovy

# ============================================================
#  Limpieza
# ============================================================
RUN apt-get clean && rm -rf /tmp/* /var/tmp/*

# ============================================================
#  Puertos y ejecución
# ============================================================
EXPOSE 8080 50000
VOLUME ["/var/jenkins_home"]

WORKDIR /workspace
CMD ["/usr/bin/supervisord"]

