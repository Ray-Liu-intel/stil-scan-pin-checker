---
name: stil-scan-pin-checker
description: 'Check STIL or STIL.GZ ScanIn/ScanOut pins against pin-file scan groups. Classify body patterns and copy scan-in/out-only bodies to versioned Channellink folders with _CHL names. Use for scan pin checks, Channellink, scan_in/scan_out/scan_nonclk_dpin membership, sort/class DRD CCD IOD pattern validation, 检查scan pin or 检查STIL. Also explain scanclk, ScanMasterClock, MacroDefs, Shift, waveform characters, vector inheritance and toggling. Automated checks cover data-pin membership only, NOT clock or period compliance.'
---

# STIL scan pin checker

## Scope and invariants

- Read-only inspection of `.stil`, `.stil.gz` and `.pin` inputs. Never rewrite or move originals. Optional body classification creates byte-identical copies only.
- Extract data pins from **every `ScanStructures → ScanChain → ScanIn/ScanOut`**, not from the global Signals list or names of macro arguments.
- **Direction matching is required for all input files, including body and setup**: `ScanIn` must belong to `stm_scan_in` OR `stm_scan_nonclk_dpin`; `ScanOut` must belong to `stm_scan_out` OR `stm_scan_nonclk_dpin`. Only dpin membership exempts direction. A pin found only in the opposite scan group is FAIL (DIRECTION_MISMATCH), not PASS. A pin in neither allowed group nor any other scan group is PIN_NOT_FOUND. These rules supersede earlier direction-free union checks.
- Normalize pin references to uppercase and convert `[n]` to `_n`, preserving the index value. Example: `"data_bus"[2]` → `DATA_BUS_2`. Always disclose this comparison convention. Never silently add aliases or change physical pin identities.
- `ScanMasterClock` identifies scanclk and is informational only. **No automated clock, TCK, waveform, duty-cycle, frequency or period checks.** PASS is not a claim of tester readiness.
- Missing ScanIn/ScanOut declarations are reported as observations, not membership failures. A file with no data pins is UNDETERMINED, not PASS.
- Missing groups, unsupported syntax, corrupted gzip or read failures must be surfaced, never treated as PASS.

## Select the pin file

| Stage | Die | Pin file family in PLT |
|---|---|---|
| sort | DRD | ddr |
| sort | CCD | sort |
| sort | IOD | pcie |
| class | DRD / CCD / IOD | class |

Determine stage/die from the user's request or directory context. Do not infer from individual pin names. Locate the actual file; filenames and revisions vary by installation. Prefer an explicit `--pin-file` when multiple revisions exist. Auto-selection accepts one `.pin` whose underscore-separated basename contains the family token; zero/multiple matches are errors. Custom installations can override all three group names with `--groups`.

If an installation-local `local-profile.md` exists beside this skill, read it for local paths and taught examples. It is optional, ignored by Git, and must not be published. Do not reuse historical results as current validation.

## Execution

1. Confirm the input file/directory, pin file and comparison convention. A directory is scanned recursively, excluding generated `_Channellink` folders and `_CHL` files.
2. Configure/select an available Python environment. Python 3.10+; standard library only. Do not install packages.
3. Run [scripts/check_scan_pins.py](./scripts/check_scan_pins.py) with an explicit interpreter and either:
   - `<input> --pin-file <pin-file>`
   - `<input> --plt-dir <PLT-directory> --stage sort --die DRD`
4. Capture stdout JSON. Prefer consuming it in memory and displaying summary/per-file counts rather than dumping large pin arrays. Do not publish generated reports or proprietary input files.
5. Report total PASS/FAIL/ERROR/UNDETERMINED, pin-file path, allowed groups, unique ScanIn/ScanOut counts, and every pin with `passed=false`: show failure type (DIRECTION_MISMATCH or PIN_NOT_FOUND), expected group, actual groups, chain and decompressed line number. Do not detect failure merely by empty `groups`; wrong-direction pins have a nonempty group list. Report absent declarations separately. State that clocks/periods were not checked.
6. Exit codes: `0` all PASS; `1` membership FAIL; `2` configuration/parse/read error or UNDETERMINED. Exit 2 can coexist with other membership failures: inspect all results.

## Body pattern Channellink workflow

When asked to check **and organize/classify body patterns**, add `--channel-link` to the invocation above. For an explicit check-only request, keep read-only behavior; use `--channel-link --dry-run` to preview without writing. Do not organize real data merely because the user asks to develop this skill.

1. Always perform the direction-aware base check (with dpin exemption) first. FAIL/ERROR/UNDETERMINED files cannot be copied.
2. Body filenames must have an underscore-delimited `body` token (case-insensitive), not `setup`. Setup files may still be checked but are never copied.
3. A passing body is eligible iff **every ScanIn belongs to scan_in AND every ScanOut belongs to scan_out** (first two `--groups` names, in that order). CHL has no dpin exemption: if any pin only passes the base check through dpin, do not copy. A pin also present in nonclk is allowed if it belongs to its correct directional scan group. Opposite-group membership alone never qualifies. Do not swap group meanings or rewrite pins to force a pass.
4. Extract the single `v<number>` token from the body filename. Do not use the full input folder name. Each source's own parent gets `<version>_Channellink`. Example: `v1_TC100_G134/example_body_v1_TC100.stil.gz` → `v1_TC100_G134/v1_Channellink/example_body_v1_TC100_CHL.stil.gz`. Missing/ambiguous versions produce a classification ERROR, not a guessed path. Mixed versions create their corresponding folders.
5. Copy, never move; append `_CHL` immediately before `.stil`/`.stil.gz`. Contents (including compressed bytes) stay identical; verify SHA256. No folder is created unless at least one eligible file is actually copied.
6. Existing identical destinations are ALREADY_EXISTS; differing files are ERROR and never overwritten. Generated paths are excluded on repeat scans; no `_CHL_CHL` or nested output folders.
7. Report membership status separately from `channel_link` actions: ELIGIBLE (check-only), WOULD_COPY (preview), COPIED, ALREADY_EXISTS, SKIPPED or ERROR. Any export ERROR sets exit 2; other eligible files may have been copied successfully. This is not an all-or-nothing transaction. Absent declarations remain informational under the existing rule.

## Clock explanation mode

When asked how a clock is identified or toggles, **read [references/clock-reading.md](./references/clock-reading.md)**, then inspect the requested STIL read-only. Use actual evidence and applicable table/category selection. This is a knowledge reference, not an automatic validation feature. Do not impose the example's numerical values on other patterns. TCK-specific compliance criteria have not been supplied.

## Limitations

The bundled script is a targeted parser, not a full IEEE STIL validator. See [README.md](./README.md) for supported syntax and installation. Files referenced only through `Include` are not automatically resolved. Do not claim full coverage when scan declarations are external. Package tests use synthetic data only.