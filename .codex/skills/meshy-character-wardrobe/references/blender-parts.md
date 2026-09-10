# Blender part separation

Part separation is an authored Blender stage, because image-to-3D output often fuses semantic regions or omits the body beneath clothing. Material slots and connected components are useful candidates, not proof of part identity.

## Canonical package

Keep one armature and one coordinate system. Use stable semantic roles rather than provider object names:

```text
character_<id>/
  source/rigged-original.glb
  work/v001/source.blend
  export/v001/character.glb
  export/v001/parts.json
  review/v001/rest.png
  review/v001/pose-*.png
```

`parts.json` records the source SHA-256, armature, output object names, semantic role, detachable flag, coverage limitation, and review status. Required roles are `body` and `outfit_base`. Add `hair`, `accessory`, `eyes`, or other roles only when the source contains a real separable part.

## Authoring order

1. Import the untouched rigged GLB and verify armature, bind pose, scale, axes, and animation playback.
2. Duplicate into a new work version. Identify candidate regions using material boundaries, connected components, texture islands, and visual inspection.
3. Separate the original outfit as `outfit_base`; separate optional parts only when their boundary is defensible. Retain the same armature modifier and vertex groups.
4. Inspect seams, duplicate vertices, normals, weights, and deformation at shoulders, elbows, hips, knees, neck, and part attachment points.
5. Export a combined character GLB and retain `source.blend`. Export detachable part GLBs only when the consumer needs them and their armature contract is preserved.

If the source has no hidden torso or limbs beneath the original outfit, set `body_coverage` to `partial`. That character supports only replacement garments with equal or greater coverage until body reconstruction is completed and reviewed. Do not hide this limitation with geometry fills that have not been visually checked.

The current repository's `local-rig` recipe supports region-authored `outfit_base` extraction for Meshy rigging failures. It is a fallback for one generated model, not a generic semantic segmenter.

