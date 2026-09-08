# merge — combine or expand maps

Stitch several maps into a larger grid, or grow one by N sectors. The guard
rails matter more than the copying: every one below encodes a real failure, most
of them lifted from MapForge's merge implementation, which is battle-tested
against real maps.

## Guards, in the order they must run

1. **`CellScale` and `HeightScale` must match** across every input. They are the
   world's unit system; merging maps that disagree produces terrain at two
   different scales in one file. Refuse, do not coerce.

2. **Textureset union and tile remap.** Each input indexes its own palette. Build
   the union, then **remap every `tile.raw` byte** to the new index. Skipping the
   remap is the classic merge bug: the map loads, and every texture is wrong.

3. **The 255 ceiling.** Slot 0 is the eraser, so the union may hold at most 255
   usable textures. Past that the merge is unrepresentable — say so and stop,
   rather than truncating.

4. **Water height table remap.** Each sector stores only the layers it uses, with
   `0xFF` meaning dry. Renumber per sector and preserve the sentinel; a sentinel
   treated as an index produces water at a garbage height.

5. **Coordinate shift.** `areadata` records are map-local, so every object in a
   map that moved must shift by the sector delta — **and Y is negated**, so the
   shift is subtracted there. Regen and Town coordinates are in units of 100,
   not centimetres; do not apply the same delta to both.

6. **Sector renaming.** Folder name is `x*1000 + y` formatted to six digits.
   Recompute it, never string-edit it.

7. **`server_attr` is dropped and regenerated.** It is derived, so a merged one
   is meaningless. MapForge drops it and says so in its status line — follow that.

## Expanding one map

Same machinery, one input. New sectors need the full ten-file set and an
`areaproperty.txt` each, `MapSize` must grow, and the new terrain must join the
old at the shared border vertices or there is a visible cliff at the seam.

Generate the new sectors through the pipeline using the existing map's archetype
statistics so the addition matches. Do not fill with flat default terrain.

## Afterwards

Audit the result, render previews, and look specifically at the **seams**: the
sector grid overlay exists for this. Height discontinuity at a join is the most
likely merge artefact, followed by a texture that changed identity because a
remap was missed.
