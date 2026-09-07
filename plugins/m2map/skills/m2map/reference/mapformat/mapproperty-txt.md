# `mapproperty.txt` — Map Type Property

Tiny client-side descriptor of the map kind. The server never reads it.

- **Path:** `<map>/mapproperty.txt`
- **Source:** read `CMapBase::LoadProperty` (`GameLib/MapBase.cpp:52-98`), write `CMapOutdoorAccessor::SaveProperty` (`WorldEditor/DataCtrl/MapAccessorOutdoor.cpp:81-103`)

## Keys

| Key | Tokens | Required | Meaning |
|---|---|---|---|
| `ScriptType` | `MapProperty` | **yes** | File type tag |
| `MapType` | `"Indoor"` \| `"Outdoor"` \| `"Invalid"` | **yes** | Quoted. `Indoor` → indoor map type; `Outdoor` and `Invalid` both load as outdoor |
| `ParentMapName` | string | no | Read but never written by the WorldEditor |

## Canonical file (map_a2, verbatim, 47 bytes)

```
ScriptType MapProperty

MapType "Outdoor"

```

Space-separated (unlike `setting.txt`'s tabs — the tokenizer accepts both).

## Pitfalls

- `MapType` value is conventionally quoted (the tokenizer accepts it bare too — quoting only matters for values with spaces). Write it quoted for byte-compat.
- Practically every playable map is `"Outdoor"`; the indoor pipeline is vestigial.
