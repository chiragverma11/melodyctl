# Prior art — index

Status: Phase 1 notes written — one file per project, each pinned to an
inspected commit with `path:line` citations and a licence section.

| project | form | licence | what to take |
|---|---|---|---|
| GazzasaurusRex/oneplus-buds-omarchy | Python backend + Omarchy QML | MIT | evidence discipline, per-device records, measurement logs |
| Leaf-lsgtky/OppoPods | Android Xposed (Kotlin) | **none — facts only, never code** | whitelist-driven capability profiles, `protocolIndex` ANC bitmaps |
| osp54/oppo-pods | Noctalia (Luau) + Python CLI | MIT | broad-model detection, ANC cycling UX |
| buildscript-dev/omarchy-oneplus-experience | Python daemon + QML | MIT | honest "untested" labels, resource-usage discipline |

Gazz's `docs/research/open-source.md` lists six further projects worth sweeping in
Phase 1 (OppoPodsManager, 1812z/OppoPods, cracked-oneplus-buds,
oneplus_buds3_pro_python, OpenPeats, …).

Deep notes: `prior-art/gazzasaurusrex.md`, `prior-art/leaf-lsgtky-oppopods.md`,
`prior-art/osp54-oppo-pods.md`, `prior-art/buildscript-dev-omarchy-oneplus-experience.md`.

Known corroborations / conflicts are tracked in `../claims-matrix.md`.
Notable: `0x0105` shape corroborated (Gazz); ANC bitmap + modeType map (Leaf);
channel 12-vs-15 (OQ-3); `0x0205`-vs-`0x0201` (OQ-2); Buds 3 id
`063C14` vs `045010` (claim 18).
