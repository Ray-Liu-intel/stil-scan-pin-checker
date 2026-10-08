---
name: stil-scan-pin-checker
description: 'Check STIL or STIL.GZ ScanIn/ScanOut against pin-file scan groups. DRD: basic only. IOD/CCD: basic plus Channellink eligibility; copy only on explicit request, inserting _sc_ before the version token. Use for scan pin checks, Channellink, scan_in/scan_out/scan_nonclk_dpin membership, sort/class DRD CCD IOD pattern validation, 检查scan pin, 检查STIL, 修改规则 or 抽检验证不创建. Also explain scanclk, ScanMasterClock, MacroDefs, Shift, waveform characters, vector inheritance and toggling. Automated checks cover data-pin membership only, NOT clock or period compliance.'
---

# STIL scan pin checker

## Scope and invariants

- Read-only inspection of `.stil`, `.stil.gz` and `.pin` inputs. Never rewrite, rename or move originals. Eligibility assessment never writes; explicitly requested IOD/CCD exports create byte-identical copies only.
- **Die policy applies to both SORT and CLASS:** DRD gets basic pin checks only, with no Channellink assessment/export. IOD and CCD get basic checks plus read-only Channellink eligibility by default. Development, sampling and check-only requests do not authorize real output creation.
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

Always pass `--die DRD|IOD|CCD`, **including with an explicit pin file**. The CLI requires it rather than guessing the policy from a pin filename. Use one die per invocation; split mixed-die directories into separate scopes.

If an installation-local `local-profile.md` exists beside this skill, read it for local paths and taught examples. It is optional, ignored by Git, and must not be published. Do not reuse historical results as current validation.

## Execution

1. Confirm the input file/directory, die, pin file and comparison convention. A directory is scanned recursively, excluding generated `_Channellink` folders, `_sc_v<number>` names and legacy `_CHL` files. For a sampling request, pass only selected files, not the full directory. Include an actual body from each IOD/CCD scope when validating CHL eligibility; setup-only sampling cannot establish body eligibility.
2. Reuse an existing local Python 3.10+ interpreter; standard library only. Select/configure it against a local script resource with an explicit interpreter. Do not install packages or create `.venv`, `.vscode` or bytecode caches in shared pattern directories. Use `-B`; any necessary isolated environment belongs outside the shared workspace.
3. Run [scripts/check_scan_pins.py](./scripts/check_scan_pins.py) with an explicit interpreter and either:
   - `<input> --pin-file <pin-file> --die IOD` (or CCD/DRD as applicable)
   - `<input> --plt-dir <PLT-directory> --stage sort --die DRD`
   Omit `--channel-link` for checks/samples. DRD reports CHL NOT_CHECKED; IOD/CCD report eligibility without copying.
4. Capture stdout JSON. Prefer consuming it in memory and displaying summary/per-file counts rather than dumping large pin arrays. Do not publish generated reports or proprietary input files.
5. Report total PASS/FAIL/ERROR/UNDETERMINED, pin-file path, allowed groups, unique ScanIn/ScanOut counts, and every pin with `passed=false`: show failure type (DIRECTION_MISMATCH or PIN_NOT_FOUND), expected group, actual groups, chain and decompressed line number. Do not detect failure merely by empty `groups`; wrong-direction pins have a nonempty group list. Report absent declarations separately. State that clocks/periods were not checked.
6. Check-only exit codes cover basic checks: `0` all PASS; `1` membership FAIL; `2` configuration/parse/read error or UNDETERMINED. Inspect CHL actions separately, including any filename-version ERROR. Export/preview CHL errors also cause exit 2. Exit 2 can coexist with other membership failures: inspect all results.

## Body pattern Channellink workflow

| Die | Basic check | CHL assessment | Actual copies |
|---|---|---|---|
| DRD | Required | NOT_CHECKED | Disabled |
| IOD / CCD | Required | Automatic, read-only | Explicit generation request only |

Classifying or asking whether a pattern can use Channellink is **not** permission to copy. Only for an explicit IOD/CCD generation/copy request, add `--channel-link`. `--channel-link --dry-run` previews without writing; normal check-only already reports planned destinations. DRD rejects `--channel-link`, including dry-run, so never use that flag for DRD. Do not create real output folders/files for rule changes, sampling or requests such as “抽检验证不创建”. Synthetic regression-copy tests may use local temporary directories.

1. Always perform the direction-aware base check (with dpin exemption) first. FAIL/ERROR/UNDETERMINED files cannot be copied.
2. IOD/CCD body filenames must have an underscore-delimited `body` token (case-insensitive), not `setup`. Setup and chain files without a `body` token may still be checked but are never copied.
3. A passing body is eligible iff **every ScanIn belongs to scan_in AND every ScanOut belongs to scan_out** (first two `--groups` names, in that order). CHL has no dpin exemption: if any pin only passes the base check through dpin, do not copy. A pin also present in nonclk is allowed if it belongs to its correct directional scan group. Opposite-group membership alone never qualifies. Do not swap group meanings or rewrite pins to force a pass.
4. Extract the single `v<number>` filename token. Each source's own parent gets `<version>_Channellink`, using the lowercased filename version, not the full source folder name. For a source in `sort_IOD/batch/v1/`, the output is **inside that v1 directory**, not beside it under `batch/`. Missing/ambiguous versions produce a classification ERROR, not a guessed path. DRD never runs this naming check.
5. Insert `sc_` immediately before that original version token: `_body_p1_v1` → `_body_p1_sc_v1`; `_body_v1_TC100` → `_body_sc_v1_TC100`. Preserve every other token, version case and `.stil`/`.stil.gz` suffix. Never append a second version, legacy `_CHL`, extra underscores or another `_sc_` marker. Example: `sort_IOD/batch/v1/example_body_p1_v1.stil.gz` → `sort_IOD/batch/v1/v1_Channellink/example_body_p1_sc_v1.stil.gz`.
6. Copy, never move; contents (including compressed bytes) stay identical and SHA256 is verified. Check-only/dry-run creates no folders or files. Existing identical destinations are ALREADY_EXISTS; differing files are ERROR and never overwritten. Generated `_sc_v<number>` names, legacy `_CHL` names and `_Channellink` folders are excluded on repeat scans to prevent repeated markers or nested output folders.
7. Report membership status separately from `channel_link` actions: NOT_CHECKED (`eligible=null`, DRD policy), ELIGIBLE (IOD/CCD check-only), WOULD_COPY (preview), COPIED, ALREADY_EXISTS, SKIPPED or ERROR. Top-level `die` and `channel_link_checks` make the policy explicit. Any export/preview ERROR sets exit 2; other eligible files may already have been copied successfully in export mode. This is not an all-or-nothing transaction. Absent declarations remain informational under the existing rule.

## Clock explanation mode

When asked how a clock is identified or toggles, **read [references/clock-reading.md](./references/clock-reading.md)**, then inspect the requested STIL read-only. Use actual evidence and applicable table/category selection. This is a knowledge reference, not an automatic validation feature. Do not impose the example's numerical values on other patterns. TCK-specific compliance criteria have not been supplied.

## Limitations

The bundled script is a targeted parser, not a full IEEE STIL validator. See [README.md](./README.md) for supported syntax and installation. Files referenced only through `Include` are not automatically resolved. Do not claim full coverage when scan declarations are external. Package tests use synthetic data only.