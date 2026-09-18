#!/bin/bash
# Installs the native scanners Vibe Guard shells out to, inside the Agent Engine
# container image. Agent Engine runs installation scripts as root at build time.
#
# Mirrors deploy/Dockerfile (Cloud Run): git for repository ingestion, gitleaks
# for the SECRETS family. Semgrep ships its own binary through the pip package.
set -euxo pipefail

GITLEAKS_VERSION="${GITLEAKS_VERSION:-8.30.1}"

apt-get update
apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    tar

curl -sSL \
    "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_x64.tar.gz" \
    -o /tmp/gitleaks.tar.gz
tar -xzf /tmp/gitleaks.tar.gz -C /usr/local/bin gitleaks
chmod +x /usr/local/bin/gitleaks
rm -f /tmp/gitleaks.tar.gz
rm -rf /var/lib/apt/lists/*

# Fail the build early if either scanner is unusable at runtime (SPEC-ENG-7).
git --version
gitleaks version
