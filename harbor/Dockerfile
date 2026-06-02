# wanderbench-runtime:1.0 — shared base image for every Harbor task in this repo.
#
# Design choice (per Harbor convention): one base image carries the env package
# and all heavy Python deps; per-task Dockerfiles do `FROM wanderbench-runtime:1.0`
# and only need to COPY task.toml + source.json. This matches deep-swe's pattern
# (one repo-pinned image, many lightweight task layers) and keeps per-task build
# time near zero.
#
# Build:
#   docker build -t wanderbench-runtime:1.0 harbor/
#
# Run a single task (state lives under /workspace):
#   docker run --rm \
#     -v "$(pwd)/tasks/<task_id>:/task" \
#     -v "$(pwd)/world_graphs:/graphs" \
#     wanderbench-runtime:1.0 wb harbor-init /task
#
# Panos are fetched lazily over HTTPS from WANDERBENCH_PANOS_PUBLIC_URL (set
# below) — no credentials required.
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install the env package straight from the public repo. Pin to a tag/commit
# in production builds; using the default branch here so the image always
# tracks the latest CLI.
RUN pip install --no-cache-dir \
        "wanderbench-env @ git+https://github.com/typhamswann/wanderbench-env"

# Public anonymous pano bucket — set in the image so per-task containers
# don't have to know about it.
ENV WANDERBENCH_PANOS_PUBLIC_URL=https://pub-b410c3932f6242a08d9d3f2d6ed556a8.r2.dev
ENV WANDERBENCH_GRAPHS_DIR=/graphs
ENV WANDERBENCH_WORKSPACE=/workspace
ENV WANDERBENCH_LOGS_DIR=/logs

RUN mkdir -p /workspace /logs/agent /logs/verifier
WORKDIR /workspace
