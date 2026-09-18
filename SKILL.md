---
name: stil-scan-pin-checker
description: 'Check STIL or STIL.GZ ScanIn/ScanOut pins against pin-file scan groups. Use for scan pin checks, scan_in/scan_out/scan_nonclk_dpin membership, sort/class DRD CCD IOD pattern validation, 检查scan pin or 检查STIL. Also use to explain scanclk, ScanMasterClock, MacroDefs, Shift, waveform characters, vector inheritance and clock toggling. Automated checks cover data-pin membership only, NOT clock or period compliance.'
---

# STIL scan pin checker

## Scope and invariants

- Read-only inspection of `.stil`, `.stil.gz` and `.pin` inputs. Never rewrite them.
- Extract data pins from **every `ScanStructures → ScanChain → ScanIn/ScanOut`**, not from the global Signals list or names of macro arguments.
- Membership is in the **union** of `stm_scan_in`, `stm_scan_out`, `stm_scan_nonclk_dpin`. A ScanIn can pass by being in any of these; do not enforce direction matching.
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

1. Confirm the input file/directory, pin file and comparison convention. A directory is scanned recursively.
2. Configure/select an available Python environment. Python 3.10+; standard library only. Do not install packages.
3. Run [scripts/check_scan_pins.py](./scripts/check_scan_pins.py) with an explicit interpreter and either:
   - `<input> --pin-file <pin-file>`
   - `<input> --plt-dir <PLT-directory> --stage sort --die DRD`
4. Capture stdout JSON. Prefer consuming it in memory and displaying summary/per-file counts rather than dumping large pin arrays. Do not publish generated reports or proprietary input files.
5. Report total PASS/FAIL/ERROR/UNDETERMINED, pin-file path, allowed groups, unique ScanIn/ScanOut counts, missing pins with chain and decompressed line number, and absent declarations. State that clocks/periods were not checked.
6. Exit codes: `0` all PASS; `1` membership FAIL; `2` configuration/parse/read error or UNDETERMINED. Exit 2 can coexist with other membership failures: inspect all results.

## Clock explanation mode

When asked how a clock is identified or toggles, **read [references/clock-reading.md](./references/clock-reading.md)**, then inspect the requested STIL read-only. Use actual evidence and applicable table/category selection. This is a knowledge reference, not an automatic validation feature. Do not impose the example's numerical values on other patterns. TCK-specific compliance criteria have not been supplied.

## Limitations

The bundled script is a targeted parser, not a full IEEE STIL validator. See [README.md](./README.md) for supported syntax and installation. Files referenced only through `Include` are not automatically resolved. Do not claim full coverage when scan declarations are external. Package tests use synthetic data only.