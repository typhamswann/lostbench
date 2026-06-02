# [WanderBench](https://typhamswann.com/wanderbench)

WanderBench is a benchmark for measuring multimodal language models on
real-world spatial navigation. Drop a model into a Mapillary street-view
panorama somewhere in the United States, hand it a goal latitude and
longitude, and watch whether it can click its way down the road to within
25 meters of the goal. 60 tasks, 51 cities, 20 easy / 20 medium / 20 hard,
human-verified solvable, scored by the fraction of the optimal walkable
path closed.

## Task format

WanderBench tasks use the [Harbor](https://www.harborframework.com/docs/tasks)
task format:

```text
task.toml         Metadata: start pano, goal lat/lng, optimal path, resource limits
instruction.md    The prompt the agent sees
source.json       The underlying wanderbench task definition (read by the verifier)
environment/      Dockerfile that builds the agent sandbox
tests/            Verifier: test.sh writes path_progress in [0, 1] to /logs/verifier/reward.txt
```

Panos are fetched lazily over HTTPS from a public R2 bucket
(`WANDERBENCH_PANOS_PUBLIC_URL`, preset in every task's Dockerfile). World
graphs are mounted from `world_graphs/` at `/graphs`. No credentials
required to run anything in this repo.

## Quickstart

Run the benchmark under any [Harbor](https://www.harborframework.com/)-compatible
runtime:

```bash
git clone https://github.com/typhamswann/wanderbench-benchmark
harbor run -p wanderbench-benchmark/tasks --agent <agent> --model <model>
```

Harbor builds each task's sandbox from `environment/Dockerfile`, drives the
agent, runs `tests/test.sh`, and writes the per-task reward to
`/logs/verifier/reward.txt`. The verifier emits `path_progress ∈ [0, 1]`;
Harbor collates the per-task rewards into a leaderboard-style summary.

Any Harbor-compatible runner works (e.g.
[Pier](https://github.com/datacurve-ai/pier) for sandboxed CLI agents).
For local debugging or running outside Harbor entirely, the standalone
`wb` CLI from [wanderbench-env](https://github.com/typhamswann/wanderbench-env)
reads the same `tasks/` tree directly:

```bash
uv tool install git+https://github.com/typhamswann/wanderbench-env
wb run -p wanderbench-benchmark/tasks --model anthropic/claude-opus-4-7 --out eval_out/
```

### Modes

| mode | compass | self-pin on map | best for |
|---|---|---|---|
| **assisted** *(default)* | shown | shown | What a human gets in Street View; leaderboard standard. |
| **strict** | hidden | hidden | Pure visual navigation; stresses heading-from-imagery grounding. |

Pass `--strict` to `wb run` for the harder variant.

### Subsets and single tasks

```bash
harbor run -p wanderbench-benchmark/tasks --agent <agent> --n-tasks 10
harbor run -p wanderbench-benchmark/tasks/<task-id> --agent <agent>
```

## What the agent does

Every turn the model sees a 1024 × 768 viewport from the current
panorama plus a HUD line (pano id, last action, distance to goal). It
calls one of six tools:

| tool | effect |
| --- | --- |
| `move_cursor` | Move the cursor by a (direction, distance) vector. |
| `mouse_down` / `mouse_up` | Click (no cursor movement between) or drag. |
| `open_map` / `close_map` | Toggle between pano and overhead OSM map. |
| `scroll_wheel` | Zoom (FOV in pano; tile zoom in map). |
| `submit_guess` | Declare arrival. Ends the episode; final position is scored. |

Clicking the road ahead teleports the agent to that road point. Clicking
the sky or a building is a no-op — the model has to look at the image,
not just emit coordinates.

## Scoring

A single terminal reward in [0, 1]:

```
path_progress = clip(1 − final_path_dist_m / initial_path_dist_m, 0, 1)
```

Both distances are computed by **Dijkstra over the world graph** — edges
weighted by haversine between adjacent pano camera positions — plus a
last-mile haversine from the goal-nearest waypoint to the exact goal
coordinate. At the goal-nearest waypoint the reward is **1.0**; at the
start pano it is **0.0**; halfway along the optimal route it is **0.5**;
beyond start or unreachable, clipped to **0.0**.

This fixes the canonical pathology of straight-line rewards: an agent
across a freeway is 30 m haversine from the goal but 2 km away by any
walkable path. Path distance reflects the cost the agent has to actually
pay; the gradient points where you'd want it to point.

For each task the verifier emits:

```json
{
  "path_progress":      0.500,
  "reached_within_25m": false,
  "turns_taken":         87,
  "stop_condition":     "submit_guess"
}
```

The leaderboard ranks by **mean `path_progress`** across all 60 tasks.

## How the worlds were built

Each task lives inside a **world**: a navigable graph of real Mapillary
panoramas tied to a real city block, anchored to OpenStreetMap road
geometry.

- **Real photos, not renders.** Panoramas come from
  [Mapillary](https://www.mapillary.com)'s public spherical-image archive.
  Models contend with the long tail of the real world — weather, motion
  blur, occlusions, foreign-language signage, construction — that
  synthetic environments smooth over.
- **Road-aligned graph.** The walkable graph is derived from
  OpenStreetMap so navigation respects the topology a human walker would.
  Panos snap onto that graph, not the other way around.
- **Geographic diversity by construction.** 51 unique cities across the
  contiguous US (lat 25.6° → 47.6°, lng −122.2° → −72.3°), with hard caps
  on tasks-per-city and on tasks-per-region.
- **Difficulty stratification.** 20 easy + 20 medium + 20 hard, sampled
  to satisfy target distance bands and minimum hop counts. Difficulty is
  about how many decisions an agent has to get right, not just distance.

## Full RL environment

This repo is the **frozen 60-task benchmark slice** for public reporting.
The complete WanderBench RL environment extends the same env and reward
across the full **6,620-task corpus spanning 1,122 US cities** — the
training-scale environment behind the benchmark.

Available under separate terms; includes:

- **Harbor-compatible** packaging — drops into Harbor-managed RL workflows
  with no integration work required.
- The full task corpus, world graphs, and hosted panorama store.
- Per-rollout replay artifacts and a failure-triage UI.
- Hardened rollout infrastructure, validated across multimodal LLM stacks.

For access, contact **phamswannty@gmail.com**.
