# syntax=docker/dockerfile:1
# ------------------------------------------------------------------------------
# Stage 1: Build & Tool Fetching
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ARG GITLEAKS_VERSION=8.18.2
ARG TARGETARCH

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    tar \
    git \
    && rm -rf /var/lib/apt/lists/*

# Download and extract pinned Gitleaks binary
RUN ARCH="x64" && \
    if [ "$TARGETARCH" = "arm64" ]; then ARCH="arm64"; fi && \
    curl -sSL "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_linux_${ARCH}.tar.gz" -o gitleaks.tar.gz && \
    tar -xzf gitleaks.tar.gz -C /usr/local/bin gitleaks && \
    chmod +x /usr/local/bin/gitleaks && \
    rm gitleaks.tar.gz

# ------------------------------------------------------------------------------
# Stage 2: Runtime Container (Non-root, hardened for Cloud Run)
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runner

# SPEC-DEP-1: Non-root user with UID >= 10000
ARG USERNAME=vibeguard
ARG USER_UID=10001
ARG USER_GID=10001

RUN groupadd --gid ${USER_GID} ${USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} -m -s /bin/bash ${USERNAME}

# Install minimal runtime dependencies (git, ca-certificates)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy gitleaks binary from builder
COPY --from=builder /usr/local/bin/gitleaks /usr/local/bin/gitleaks

WORKDIR /app

# Install Python dependencies including Semgrep and Google ADK.
# The floors below must stay in step with pyproject.toml: `google-adk>=2.9.1`
# is what pulls in the a2a-sdk that `agent_executor.py` imports at module load,
# so a looser floor would resolve to an ADK without A2A and crash on startup.
COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
    "semgrep==1.70.0" \
    "google-adk>=2.9.1" \
    "a2a-sdk>=0.3.0" \
    "google-genai>=1.0.0" \
    "fastapi>=0.115.0" \
    "uvicorn>=0.30.0" \
    "pydantic>=2.7.0" \
    "pyyaml>=6.0.1" \
    "python-dotenv>=1.0.0"

# Copy application source code, rule packs, and demo fixtures
COPY src/ /app/src/
COPY rules/ /app/rules/
COPY fixtures/ /app/fixtures/
COPY vibe_guard_a2ui/ /app/vibe_guard_a2ui/

# Set working permissions for non-root user
RUN chown -R ${USERNAME}:${USERNAME} /app /tmp

# Environment configuration
# SPEC-DEP-4 & A2UI Cloud Run Deployer wiring:
# 1. PYTHONPATH exposes the agent package and the vibe_guard engine to the server
ENV PYTHONPATH="/app:/app/src:/app/vibe_guard_a2ui:$PYTHONPATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPYCACHEPREFIX=/tmp/pycache
ENV HOME=/tmp
ENV VIBE_GUARD_ENV=production
ENV TMPDIR=/tmp
ENV PORT=8080
ENV CALLER_ID="vibe-guard-auditor@gcp.sfeir.com"

# Switch to non-root user (SPEC-DEP-1)
USER ${USERNAME}

EXPOSE 8080

# Health check endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')" || exit 1

# Launch server supporting interactive Web UI and A2A protocol
ENTRYPOINT ["sh", "-c", "exec python3 -m uvicorn vibe_guard_a2ui.local_tester.server:app --host 0.0.0.0 --port ${PORT:-8080}"]
