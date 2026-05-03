# =============================================================================
# Dockerfile — Jenkins with Docker-in-Docker (DinD)
# =============================================================================
# This image extends Jenkins LTS and adds Docker CLI so pipelines can build
# and run Docker containers from within Jenkins.
#
# Build:  docker build -t sentiment-jenkins -f infra/jenkins/Dockerfile infra/jenkins/
# Run:    docker run -d -p 8080:8080 -p 50000:50000 \
#           -v jenkins_home:/var/jenkins_home \
#           -v /var/run/docker.sock:/var/run/docker.sock \
#           sentiment-jenkins
# =============================================================================

FROM jenkins/jenkins:lts-jdk17

USER root

# Install Docker CLI + dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
    && install -m 0755 -d /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg -o /etc/apt/keyrings/docker.asc \
    && chmod a+r /etc/apt/keyrings/docker.asc \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
        https://download.docker.com/linux/debian $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
        > /etc/apt/sources.list.d/docker.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends docker-ce-cli docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

# Install docker-compose standalone (for compatibility)
RUN curl -SL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$(uname -m)" \
        -o /usr/local/bin/docker-compose \
    && chmod +x /usr/local/bin/docker-compose

# Drop back to jenkins user
USER jenkins

# Pre-install useful Jenkins plugins
RUN jenkins-plugin-cli --plugins \
    workflow-aggregator \
    git \
    pipeline-stage-view \
    docker-workflow \
    blueocean \
    timestamper
