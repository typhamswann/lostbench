# Per-task layer for wanderbench/cell_new_00236_easy_02.
#
# Inherits the shared runtime built from harbor/Dockerfile at the repo root.
# All deps and the `wb` CLI are already installed there; this layer just
# carries the task definition and sets the entrypoint.
FROM wanderbench-runtime:1.0

COPY task.toml /task/task.toml
COPY source.json /task/source.json
COPY instruction.md /task/instruction.md

WORKDIR /workspace
# Boot the sim on container start; Harbor expects /workspace to be populated
# (view.jpg, state.json) before the agent's first action.
CMD ["wb", "harbor-init", "/task"]
