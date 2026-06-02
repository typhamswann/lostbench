"""Generate Harbor / Pier-compatible per-task directories.

Reads the flat `tasks/{easy,medium,hard}/NN_<city>.json` shape and emits one
directory per task under `tasks/<task_id>/`:

    tasks/<task_id>/
    ├── task.toml          # Harbor schema v1.1
    ├── instruction.md     # what the agent reads
    ├── source.json        # original wanderbench-bench task JSON
    ├── environment/
    │   └── Dockerfile     # `FROM wanderbench-runtime:1.0`
    └── tests/
        └── test.sh        # writes path_progress to /logs/verifier/reward.txt

Run from the bench repo root:

    python scripts/gen_harbor_tasks.py [--delete-old]

Pass --delete-old to remove the old flat NN_<city>.json files after writing
the new per-task directories. The new directories live alongside the old
{easy,medium,hard}/ subdirs under tasks/.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import textwrap
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_ROOT = REPO_ROOT / "tasks"
SPLITS = ("easy", "medium", "hard")


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

TASK_TOML_TPL = """\
schema_version = "1.1"
artifacts = []

[task]
name = "wanderbench/{task_id}"
description = "{display_description}"
authors = ["Ty Pham-Swann"]
keywords = ["navigation", "multimodal", "vlm", "wanderbench"]

[metadata]
ext_id = "wanderbench-{task_id}"
task_id = "{task_id}"
display_title = "{display_title}"
display_description = "{display_description}"
category = "navigation"
language = "english"
repository_url = "https://github.com/typhamswann/wanderbench-benchmark"
base_commit_hash = ""
# Path is relative to the task directory; harbor-init reads it.
wanderbench_task_path = "source.json"
difficulty = "{difficulty}"
city = "{city}"

[verifier]
timeout_sec = 600.0

[verifier.env]

[agent]
timeout_sec = 1800.0

[environment]
build_timeout_sec = 1800.0
docker_image = "wanderbench-runtime:1.0"
os = "linux"
cpus = 2
memory_mb = 4096
storage_mb = 4096
gpus = 0
allow_internet = true
mcp_servers = []

[environment.env]

[solution]

[solution.env]
"""


INSTRUCTION_TPL = """\
# WanderBench task — {task_id}

You are navigating a real city using mouse controls. The view at
`/workspace/view.jpg` shows your current pose: a 1024x768 viewport rendered
from a real Mapillary 360 panorama, with a small HUD overlay (current pano
id, last action, distance to goal) and a red crosshair cursor.

## Goal
Travel from the start pano to the goal coordinate, then declare arrival
with `submit_guess`. You get ONE `submit_guess` attempt and are scored on
how close you are to the true goal when you submit.

- **City:** {city_label}
- **Start pano:** `{start_pano_id}` at ({start_lat:.6f}, {start_lng:.6f})
- **Goal:** ({goal_lat:.6f}, {goal_lng:.6f}), within {goal_radius_m:.0f} m
- **Optimal walkable distance:** {optimal_distance_m:.0f} m ({optimal_steps} steps)

## Tools (one per turn)

| tool | args | effect |
| --- | --- | --- |
| `open_map`    | —                                  | Switch to top-down OSM view. |
| `close_map`   | —                                  | Back to pano view. |
| `mouse_down`  | —                                  | Press the mouse button. |
| `mouse_up`    | —                                  | Release; if cursor didn't move it's a CLICK. |
| `move_cursor` | `direction_deg`, `distance_px`     | Move cursor by a vector. 0=right, 90=up, 180=left, 270=down. With mouse held: pan/drag. |
| `scroll_wheel`| `delta_y`                          | Positive = zoom in, negative = zoom out. |
| `submit_guess`| —                                  | Declare arrival; ends the episode. |

In pano view, clicking on the visible road ahead teleports you down it.
Clicks on the sky or buildings are no-ops. The blue rectangle on the map
marks the traversable region — you can only walk on roads inside that box.

## Driving the environment

Issue tool calls via the `wb harbor-step` shell command:

```bash
wb harbor-step --tool move_cursor --args '{{"direction_deg":270,"distance_px":140}}'
wb harbor-step --tool mouse_down
wb harbor-step --tool mouse_up                       # click at current cursor
wb harbor-step --tool open_map
wb harbor-step --tool scroll_wheel --args '{{"delta_y":2}}'
wb harbor-step --tool submit_guess
```

After every `wb harbor-step`, the new viewport is written to
`/workspace/view.jpg` and a JSON state snapshot to `/workspace/state.json`.
Read them to plan your next move.

When you believe you've arrived, call `wb harbor-step --tool submit_guess`
to end the episode. The verifier (`tests/test.sh`) will then run
`wb harbor-score`, which writes the final `path_progress` reward to
`/logs/verifier/reward.txt`.
"""


PER_TASK_DOCKERFILE_TPL = """\
# Per-task layer for wanderbench/{task_id}.
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
"""


TEST_SH_TPL = """\
#!/usr/bin/env bash
# Harbor verifier — invoked once the agent has finished its rollout.
# Mirrors the deep-swe pattern: writes a single reward (0..1) to
# /logs/verifier/reward.txt, exits 0 on success.
set -euo pipefail

LOG_PFX="[verifier]"

mkdir -p /logs/verifier /logs/agent

echo "${{LOG_PFX}} scoring wanderbench task {task_id}"
wb harbor-score

if [[ ! -f /logs/verifier/reward.txt ]]; then
    echo "${{LOG_PFX}} ERROR: reward.txt was not written" >&2
    exit 1
fi

REWARD=$(cat /logs/verifier/reward.txt)
echo "${{LOG_PFX}} path_progress=${{REWARD}}"

# Always exit 0 — the reward is the signal, not the exit code.
exit 0
"""


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def _read_task_json(p: Path) -> dict:
    return json.loads(p.read_text())


def _display_title(task: dict) -> str:
    return (
        f"Navigate to ({task['goal']['lat']:.5f}, {task['goal']['lng']:.5f}) "
        f"in {task.get('city_label', task['city'])}"
    )


def _display_description(task: dict) -> str:
    return (
        f"Walk from pano {task['start']['pano_id']} to the goal coordinate "
        f"within {task['goal']['radius_m']:.0f} m. "
        f"Difficulty: {task['difficulty']}. "
        f"Optimal walkable distance: {task['optimal']['distance_m']:.0f} m."
    )


def _toml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _emit_task_dir(task: dict, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # task.toml
    toml = TASK_TOML_TPL.format(
        task_id=task["task_id"],
        display_title=_toml_escape(_display_title(task)),
        display_description=_toml_escape(_display_description(task)),
        difficulty=task["difficulty"],
        city=_toml_escape(task["city"]),
    )
    (out_dir / "task.toml").write_text(toml)

    # instruction.md
    instr = INSTRUCTION_TPL.format(
        task_id=task["task_id"],
        city_label=task.get("city_label", task["city"]),
        start_pano_id=task["start"]["pano_id"],
        start_lat=task["start"]["lat"],
        start_lng=task["start"]["lng"],
        goal_lat=task["goal"]["lat"],
        goal_lng=task["goal"]["lng"],
        goal_radius_m=task["goal"]["radius_m"],
        optimal_distance_m=task["optimal"]["distance_m"],
        optimal_steps=task["optimal"]["steps"],
    )
    (out_dir / "instruction.md").write_text(instr)

    # source.json — the canonical wanderbench-bench task definition.
    (out_dir / "source.json").write_text(json.dumps(task, indent=2))

    # environment/Dockerfile
    env_dir = out_dir / "environment"
    env_dir.mkdir(exist_ok=True)
    (env_dir / "Dockerfile").write_text(
        PER_TASK_DOCKERFILE_TPL.format(task_id=task["task_id"])
    )

    # tests/test.sh
    tests_dir = out_dir / "tests"
    tests_dir.mkdir(exist_ok=True)
    test_sh = TEST_SH_TPL.format(task_id=task["task_id"])
    test_path = tests_dir / "test.sh"
    test_path.write_text(test_sh)
    test_path.chmod(0o755)


def _gather_source_tasks() -> list[tuple[Path, dict]]:
    out: list[tuple[Path, dict]] = []
    for split in SPLITS:
        split_dir = TASKS_ROOT / split
        if not split_dir.exists():
            continue
        for p in sorted(split_dir.glob("*.json")):
            out.append((p, _read_task_json(p)))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--delete-old", action="store_true",
                    help="rm -rf tasks/{easy,medium,hard}/ after writing the "
                         "new per-task directories.")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan, don't write anything")
    args = ap.parse_args(argv)

    tasks = _gather_source_tasks()
    if not tasks:
        print(f"no tasks under {TASKS_ROOT}/{{{','.join(SPLITS)}}}", file=sys.stderr)
        return 1

    print(f"found {len(tasks)} tasks under {TASKS_ROOT}")

    # Collision check: every task_id must be unique.
    seen: dict[str, Path] = {}
    for src, t in tasks:
        tid = t["task_id"]
        if tid in seen:
            print(f"DUP task_id {tid!r}: {src} and {seen[tid]}", file=sys.stderr)
            return 1
        seen[tid] = src

    for src, t in tasks:
        out_dir = TASKS_ROOT / t["task_id"]
        if args.dry_run:
            print(f"  would write {out_dir}/")
            continue
        _emit_task_dir(t, out_dir)
    if args.dry_run:
        return 0

    print(f"wrote {len(tasks)} task directories under {TASKS_ROOT}/")

    if args.delete_old:
        for split in SPLITS:
            d = TASKS_ROOT / split
            if d.exists():
                shutil.rmtree(d)
                print(f"  removed {d}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
