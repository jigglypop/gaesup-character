# Meshy job stages

Use `data/characters/batch.json` as the batch inventory and each run's `character.json` as provider state. The inventory expresses intent; persisted task state is authoritative for whether a POST already happened.

## State transitions

```text
source_ready
  -> generation submitted -> generation complete -> generated.glb
  -> rigging submitted    -> rigging complete    -> rigged.glb
                                              \-> provider rejected -> local fallback candidate
```

Generation and rigging are separate paid mutations. Submit a single character at a time, persist `submission_uncertain` before each POST, and record the returned task ID before moving to the next character. Polling, result download, and local auditing are read-only with respect to Meshy jobs.

Use the existing commands; do not build a second provider client in the harness:

```powershell
uv run python -m src.character_cli --run <run> generate --image <image> --height <meters>
uv run python -m src.character_cli --run <run> status
uv run python -m src.character_cli --run <run> download --stage generation
uv run python -m src.character_cli --run <run> rig
uv run python -m src.character_cli --run <run> download --stage rigging
```

When status is `submission_uncertain`, inspect Meshy's task list or dashboard and recover with `status --task-id <id>`. Do not infer that no task exists from the absence of a local task ID or from My Assets alone.

When rigging is rejected, preserve the HTTP status and generated GLB. Decide per character whether to improve the source/model and create a new explicitly named run, or author a local rig recipe. Do not overwrite the rejected run or describe a local fallback as Meshy-rigged.
# Current preparation profiles

For Meshy 7 / Smart Topology generation and the resumable rig + idle/walk/run/jump/fall operation, use the [preparation contract](../../../../docs/character-preparation.md). Rigging and additional animation clips are separate provider tasks even when the UI offers one execution. Resolve current action IDs from the free library endpoint and retain the authorized task-count limit across resumes.
