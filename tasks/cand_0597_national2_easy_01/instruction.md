# WanderBench task — cand_0597_national2_easy_01

You are navigating a real city using mouse controls. The view at
`/workspace/view.jpg` shows your current pose: a 1024x768 viewport rendered
from a real Mapillary 360 panorama, with a small HUD overlay (current pano
id, last action, distance to goal) and a red crosshair cursor.

## Goal
Travel from the start pano to the goal coordinate, then declare arrival
with `submit_guess`. You get ONE `submit_guess` attempt and are scored on
how close you are to the true goal when you submit.

- **City:** cand_0597_national2
- **Start pano:** `w190525089_i5` at (25.789541, -80.189456)
- **Goal:** (25.788270, -80.189584), within 25 m
- **Optimal walkable distance:** 142 m (32 steps)

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
wb harbor-step --tool move_cursor --args '{"direction_deg":270,"distance_px":140}'
wb harbor-step --tool mouse_down
wb harbor-step --tool mouse_up                       # click at current cursor
wb harbor-step --tool open_map
wb harbor-step --tool scroll_wheel --args '{"delta_y":2}'
wb harbor-step --tool submit_guess
```

After every `wb harbor-step`, the new viewport is written to
`/workspace/view.jpg` and a JSON state snapshot to `/workspace/state.json`.
Read them to plan your next move.

When you believe you've arrived, call `wb harbor-step --tool submit_guess`
to end the episode. The verifier (`tests/test.sh`) will then run
`wb harbor-score`, which writes the final `path_progress` reward to
`/logs/verifier/reward.txt`.
