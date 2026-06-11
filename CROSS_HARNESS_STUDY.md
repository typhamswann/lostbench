# Cross-harness, cross-reasoning, and contamination study

> Companion to [METHODOLOGY.md](METHODOLOGY.md). Three questions on a fixed
> 3-task slice (1 easy / 1 medium / 1 hard) of the public benchmark:
> **(A)** how much does the *harness* (not the model) move the score?
> **(B)** does *reasoning effort* move it? **(C)** can a model shortcut the task
> by *recognizing where it is* (contamination)? Every rollout is
> deterministic-verifier scored (`path_progress` ∈ [0,1]), goal-leak stripped,
> and isolated in its own workspace.

## Setup

- **Tasks (held constant):** `cell_new_00236_easy_02`, `cand_0030_national2_medium_02`, `cand_0196_national_hard_02`; turn budgets 40 / 80 / 120.
- **Harnesses:**
  - *Native production CLIs* — Claude Code (`claude -p`), Codex (`codex exec`), Antigravity (`agy -p`), Qwen Code (`qwen`). Driven headlessly, one isolated workspace per rollout (`scripts/run_native_harness.py`).
  - *My harness* — a plain multi-turn chat loop (read `view.jpg`, emit a JSON tool call, sliding 4-image window), calling each model's API directly (`scripts/run_api_harness.py`): GPT→OpenAI, Claude→Bedrock, Gemini→Gemini API. No OpenRouter, no proxy.
- **Reasoning sweep:** `low` vs `high` (Claude `--effort`, Codex `model_reasoning_effort`, Antigravity model tier, my harness `reasoning_effort` / Anthropic thinking).
- **Fairness:** the goal coordinate is stripped from `state.json`; observation is free, only `wb harbor-step` actions burn the budget.
- **Sampling:** the frontier results below are **n=2 seeds** per cell. (An earlier single-seed pilot produced two spurious "findings" — see *Methodology incidents*; those numbers are discarded.)

---

## Master table — frontier models (n=2, mean path_progress over 3 tasks)

Every frontier finding reads off this one table. Columns are the two axes:
**harness** (native ↔ mine) and **reasoning** (low ↔ high).

| Model | native·low | native·high | mine·low | mine·high |
|---|---|---|---|---|
| GPT-5.5 | 0.871 | 0.877 | 0.911 | 0.888 |
| Opus 4.8 | 0.910 | 0.917 | 0.911 | 0.915 |
| Opus 4.7 | 0.877 | 0.879 | 0.941 | 0.857 |
| Sonnet 4.6 | 0.882 | 0.898 | 0.905 | 0.856 |
| Gemini 3.1 Pro | 0.899 | 0.916 | 0.883 | 0.872 |
| Gemini 3.5 Flash | 0.874 | 0.884 | 0.885 | 0.927 |

---

## A. The harness effect — the headline

**Hold the model fixed, swap only the harness.** Δ = mean(mine) − mean(native), averaged over low/high.

| | Model | native | mine | **Δ harness** |
|---|---|---|---|---|
| **Frontier** | GPT-5.5 | 0.874 | 0.900 | +0.026 |
| | Opus 4.8 | 0.914 | 0.913 | −0.001 |
| | Opus 4.7 | 0.878 | 0.899 | +0.021 |
| | Sonnet 4.6 | 0.890 | 0.881 | −0.010 |
| | Gemini 3.1 Pro | 0.908 | 0.878 | −0.030 |
| | Gemini 3.5 Flash | 0.879 | 0.906 | +0.027 |
| **Open** | Qwen3.7-Plus | 0.394 | 0.111 | **−0.283** |
| | GLM-5V-Turbo | 0.478 | 0.241 | **−0.237** |

*(Open-model row: the native Qwen Code CLI vs my harness, same model + OpenRouter route — only the harness differs. native = `eval_out_qwencode/`; mine = `eval_out/*_assisted-imghist4*.json`, harness `verifiers-chat`, over the same 3 tasks. A **negative** Δ means the native CLI scored higher — the opposite of the frontier rows.)*

**Finding: scaffolding is load-bearing for weak models, cosmetic for strong ones.**
- **Frontier models are harness-robust** — every Δ is within **±0.03**. A strong model drives a generic chat loop about as well as its bespoke production CLI.
- **Open models are not** — the native agentic CLI scored **~2–4× higher** (native 0.39–0.48 vs my harness 0.11–0.24; |Δ| = 0.24–0.28) with the model untouched. A large fraction of what an open-model leaderboard reads as "capability" is actually harness limitation. This is the concrete "the harness IS the product" result.
- **Implication:** a *frontier* leaderboard is far less harness-sensitive than an *open-model* one — but you only know that by measuring both, and you must never compare a my-harness number to a native one (only native↔native or mine↔mine).

Caveat: the native CLIs are *coding* tools, so the open-model gap reflects how well they run the image/tool loop, not pure capability.

---

## B. The reasoning effect — a non-finding

**Hold model + harness fixed, swap low ↔ high.** δ = high − low.

| Model | δ native | δ mine |
|---|---|---|
| GPT-5.5 | +0.006 | −0.023 |
| Opus 4.8 | +0.007 | +0.004 |
| Opus 4.7 | +0.002 | −0.084 |
| Sonnet 4.6 | +0.016 | −0.049 |
| Gemini 3.1 Pro | +0.017 | −0.011 |
| Gemini 3.5 Flash | +0.010 | +0.042 |

**On native harnesses high effort is marginally ≥ low (all +, ≤0.017); on my harness it's mostly slightly worse.** Either way the magnitude is **within seed-noise (≤~0.05)** and the *direction flips with the harness* — so there is no reliable reasoning signal on these tasks. High effort neither clearly helps nor hurts.

Context: this ≤0.05 reasoning knob is dwarfed by the **+0.24–0.28 harness effect (A)** and by the **0.32** observation-window effect in the open-model study — *what you show the model and how you wrap it dominate how hard it thinks.*

---

## C. The leaderboard — near-saturation

On native harnesses the frontier field is **tightly bunched (0.87–0.92)** and nearly every rollout is `solved` (within 25 m). These 3 tasks don't separate the frontier — to do that you need harder / longer-horizon / strict-mode tasks. Two compressors to note:
- The **easy task is pp-capped at 0.743** (it starts 92.6 m out, so reaching the 25 m radius caps the score), squashing the range.
- Differences are small enough that the **second seed reshuffled the order** — GPT-5.5 led at n=1 (0.911) but sits last at n=2 (0.874). A single-seed leaderboard here is meaningless.

---

## D. Contamination — vision-native geolocation probe

The task is to **navigate** (move pano-to-pano) to a **randomized, map-pin-revealed goal**, not to name a place. The goal never appears as text (static n-gram scan: **57/57 tasks clean**). The only recall-based shortcut left is a model **recognizing where its imagery was taken** and navigating by geographic memory. The probe tests whether that substrate exists: given a clean 360° pano (no map, no coords — the model's *best* shot), how precisely can it self-localize? (`scripts/geo_contamination_probe.py`, 12 start panos.)

| Model | median err | best single | within 1 km | within 50 km |
|---|---|---|---|---|
| Gemini 3.1 Pro | 13.9 km | 3.35 km | 0% | **90%** |
| Gemini 3.5 Flash | 19.9 km | **0.11 km** | 8% | 75% |
| Opus 4.8 | 19 km | 1.16 km | 0% | 67% |
| GLM-5V-Turbo | 16–26 km | 2.09 km | 0% | 58% |
| GPT-5.5 | 169 km | 0.94 km | 9% | 45% |
| Qwen3.7-Plus | 219–386 km | 1.26 km | 0% | 42% |

The probe is *sensitive* — Gemini 3.1 Pro names the **metro 90%** of the time (Miami, Houston, Detroit… from visual cues). But **no model self-localizes at task scale**: the task operates at **25 m**, the best single guess across ~70 attempts was **110 m**, and medians are **14–386 km**. Models have a **city-level prior, not street-level recall**, so:
- **Necessary condition fails** — they can't recover position from pixels at meter precision (0–9% within 1 km).
- **Sufficient condition fails by design** — the goal is randomized and map-revealed; knowing your start city says nothing about the route to the pin.

Because the best geolocator *can* place panos to metro level, the null on street-level recall is a real measurement, not a blind probe — the vision-native analog of n-gram testing, and a stronger guarantee than n-gram is for text.

---

## Methodology incidents (worth recording)

- **Seeds matter — two single-seed "findings" were noise.** The n=1 pilot showed Gemini 3.5 Flash *collapsing* at high effort (medium 0.435) and Gemini 3.1 Pro *cratering* −0.47 on my harness. At n=2 both vanish (Flash-high medium = **0.947**; Gemini-Pro Δ = **−0.02/−0.04**). We discarded the single-seed numbers. This is the in-house proof of the core thesis: a single cross-harness/reasoning rollout sits inside the noise band.
- **Caching fights a sliding-window vision harness.** A moving `cache_control` breakpoint *thrashed* — Sonnet cache-writes hit 1.2M tokens and cost *more* than no cache, because the image window changes the prefix every turn. Fix: cache only the stable system prompt. You can't have observation-truncation and cheap caching at once.
- **Provider thinking-APIs diverge.** Sonnet 4.6 uses `thinking.type=enabled` + `budget_tokens`; Opus 4.7/4.8 require `thinking.type=adaptive` + `output_config.effort`. A single "enable thinking" path silently failed on half the models.
- **Agent-vs-scorer isolation.** A Codex agent (bypassed sandbox) `pip install`ed an x86_64 Pillow into user-site mid-run, clobbering the scorer's `PIL`. Fix: the `wb` shim runs in a dedicated arm64 venv that ignores user-site — the harness must isolate its runtime from agent-writable paths (Cai's `tool_approval_policy` / `isolation_granularity`).

## Caveats & cost

- **n:** A/B/C frontier = **n=2 × low/high**; open-model harness (A) = n=2, no reasoning knob; contamination (D) = 1 × 12 panos. A small 3-task slice — directional, not a full-power leaderboard; even at n=2, ±0.05 swings aren't robust.
- **Cost:** the my-harness frontier run was **~$64** (72 rollouts, real tokens × verified prices: Bedrock Opus $5/$25, etc.) on direct provider accounts; native side was subscription-covered. My harness has no usable caching here, so it is far pricier per rollout than the native harnesses — itself a measure of harness *efficiency*, not capability.
