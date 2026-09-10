---
name: meshy-character-wardrobe
description: Build or operate the Meshy character wardrobe pipeline, including backend/UI control, resumable rigging jobs, and Blender part separation.
---

# Meshy Character Wardrobe

Preserve the user's character sources, paid task state, and separate technical evidence from visual approval. Accept an existing rigged Meshy model or a generation image; do not regenerate an imported character just to fit an image-only workflow.

When operating an existing batch, start with the read-only audit from the repository root:

```powershell
uv run python .codex/skills/meshy-character-wardrobe/scripts/audit_batch.py data/characters/batch.json
```

Use the report as a navigation hint and verify the actual run before mutation. It does not prove asset quality or authorize execution. Harness/API design and ordinary UI edits do not require a batch audit.

## Route the work

- Before creating, polling, downloading, or recovering Meshy tasks, read [references/meshy-jobs.md](references/meshy-jobs.md).
- Before separating clothing or semantic parts in Blender, read [references/blender-parts.md](references/blender-parts.md).
- Before exposing pipeline state or actions through backend APIs or a browser UI, read the [shared control contract](../../../docs/character-control-plane.md). Do not apply provider submission procedures to ordinary UI edits.
- Before calling a character complete or comparing the five-character batch, read [references/acceptance.md](references/acceptance.md).

Do not load all references when only a status audit or one stage is requested.

## Shared invariants

- Preserve the selected source and its SHA-256. For generated characters keep image and provider task lineage; for imported rigged GLBs record file provenance and leave unavailable provider history unknown.
- A height reference may supply scale only. Never substitute its mesh, body, clothing, materials, or rig.
- Prefer a successful Meshy rig. If Meshy rejects rigging, keep that provider result and label any Blender-authored skeleton as `local_fallback`.
- Separate parts after the canonical rig exists so detached meshes retain skin weights and the same armature contract.
- Keep the untouched generated and rigged GLBs. Write Blender work and exports to new versioned directories.
- Never reuse another character's landmarks or part selectors by changing only a hash.
- Keep technical and visual review separate and bound to the output version/hash. An audit report or an `approved` string alone is insufficient evidence.

Follow the session's authorized targets, stages and spending/retry limits. Continue already authorized steps without repeated approval. A missing POST response requires task recovery, not another paid submission. Harness design does not require live Meshy or Blender mutation.
