#!/usr/bin/env bash
# Smoke-test one wanderbench Harbor task end-to-end inside the runtime image.
#
# Builds the shared image, boots a single task, takes one step, submits the
# guess, then runs the verifier and prints the resulting reward.
#
# Usage:
#   bash scripts/test_harbor_task.sh                # default: first task
#   bash scripts/test_harbor_task.sh <task_id>      # specific task
#
# Requires Docker. The container fetches panos lazily over HTTPS from the
# public R2 bucket (no credentials needed); world graphs are mounted from
# the repo's `world_graphs/` directory.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

TASK_ID="${1:-}"
if [[ -z "${TASK_ID}" ]]; then
    TASK_ID="$(ls -1 tasks/ | grep -v '\.' | head -n1)"
fi
TASK_DIR="tasks/${TASK_ID}"

if [[ ! -d "${TASK_DIR}" ]]; then
    echo "no task directory at ${TASK_DIR}" >&2
    exit 1
fi

IMAGE_TAG="wanderbench-runtime:1.0"

if ! command -v docker >/dev/null 2>&1; then
    echo "[smoke] docker not installed; skipping container steps." >&2
    echo "[smoke] would build ${IMAGE_TAG} from harbor/Dockerfile,"
    echo "[smoke] then run the task at ${TASK_DIR}."
    exit 0
fi

echo "[smoke] building ${IMAGE_TAG} from harbor/Dockerfile..."
docker build -t "${IMAGE_TAG}" harbor/

echo "[smoke] running task ${TASK_ID}..."

# Single container with shared /workspace + /logs. Inside, we exercise the
# full harbor-init -> harbor-step -> harbor-score lifecycle, then the
# verifier script.
docker run --rm \
    -v "${REPO_ROOT}/${TASK_DIR}:/task:ro" \
    -v "${REPO_ROOT}/world_graphs:/graphs:ro" \
    "${IMAGE_TAG}" bash -lc "
        set -euo pipefail
        wb harbor-init /task
        wb harbor-step --tool move_cursor --args '{\"direction_deg\":270,\"distance_px\":140}'
        wb harbor-step --tool submit_guess
        bash /task/tests/test.sh
        echo '--- /logs/verifier/reward.txt ---'
        cat /logs/verifier/reward.txt
        echo '--- /logs/agent/final.json ---'
        cat /logs/agent/final.json
    "

echo "[smoke] done."
