# docker/Dockerfile.cursor-real
FROM node:22-bookworm-slim

WORKDIR /workspace

# Install OS packages required for the installer and repo operations (include bash)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      bash ca-certificates curl git build-essential python3 jq && \
    update-ca-certificates || true && \
    rm -rf /var/lib/apt/lists/*

# Create seed dirs and copy the per-file seed artifacts (names from your repo)
RUN mkdir -p /workspace/seed/src /workspace/seed/test
COPY docker/docker_seed_package.json /workspace/seed/package.json
COPY docker/docker_seed_README.md  /workspace/seed/README.md
COPY docker/docker_seed_src_cart.js /workspace/seed/src/cart.js
# Optionally copy a test file if present:
# COPY docker/docker_seed_test_cart.js /workspace/seed/test/cart.test.js

# Copy start script which performs runtime install and runs agent
COPY docker/start-real-test.sh /usr/local/bin/start-real-test.sh
RUN chmod +x /usr/local/bin/start-real-test.sh

ENV PATH="/usr/local/bin:${PATH}"
ENV CURSOR_MODEL=auto
ENV HOME=/root

ENTRYPOINT ["/usr/local/bin/start-real-test.sh"]