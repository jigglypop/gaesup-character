# Acceptance gates

Track each gate independently so a valid GLB is never presented as a finished wardrobe asset.

## Per-character gates

| Gate | Evidence | Pass condition |
|---|---|---|
| Provenance | manifest, source hashes, available task lineage | Selected image or imported rigged GLB is traceable; unavailable external task history is explicitly unknown |
| Rig | GLB inspection and animation playback | One armature, expected joints, no unweighted deforming vertices, usable rest pose |
| Parts | `parts.json` and `source.blend` | Required semantic roles exist, boundaries are reviewed, rig contract is preserved |
| Technical | quality report and re-import | No parser/export errors; budgets and required clips pass |
| Motion | pose renders or target clips | No material weight collapse or unacceptable separation at major joints |
| Visual | rest, front/back/side, and motion review | Character identity is preserved; clothing and optional parts look intentional |

Use these statuses:

- `blocked`: missing input, provenance conflict, or uncertain task needing recovery.
- `in_progress`: an external or Blender stage is active.
- `review_required`: technical evidence exists but visual review is incomplete.
- `approved`: all required technical, motion, and visual checks passed for the declared use case.

## Batch completion

The requested batch is complete only when every entry has an approved canonical package or the user explicitly excluded it with a recorded reason. Report approved and excluded counts separately; exclusion does not create an approved fifth character. Report each blocked or review-required character.

Bind every review to the actual output version/hash and evidence. The current audit script reads status declarations and performs partial checks; it does not establish complete provenance, rig integrity, or visual approval by itself.

For broad-motion validation, sample at least the intended idle plus motions that exercise shoulders, elbows, hips, and knees. The exact clips may differ by character and product; document the chosen set in `parts.json` or the review report.
