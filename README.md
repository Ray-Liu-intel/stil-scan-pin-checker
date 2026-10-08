# STIL Scan Pin Checker

A reusable Copilot skill and standalone Python CLI for checking STIL scan-data pins against tester pin groups. Includes a reference for explaining scan clocks without adding clock validation to the pin check.

## What it checks

- Reads `.stil` and `.stil.gz` without modifying or extracting inputs to disk.
- Extracts declared `ScanIn` and `ScanOut` from every `ScanStructures / ScanChain` block.
- Requires **direction matching** in the base check for both body and setup: ScanIn must be in `stm_scan_in` or `stm_scan_nonclk_dpin`; ScanOut must be in `stm_scan_out` or `stm_scan_nonclk_dpin`. The dpin group is direction-free. Pins only in the opposite scan group fail with DIRECTION_MISMATCH; pins in none of these groups fail with PIN_NOT_FOUND.
- Converts names to uppercase and bus indices `[n]` to `_n`. Example: `"data_bus"[2]` becomes `DATA_BUS_2`.
- Reports chain names, decompressed line numbers, normalized/original pins and matching groups as JSON.
- Records clocks and absent ScanIn/ScanOut declarations as informational observations.
- DRD performs basic checks only. IOD/CCD additionally assess body Channellink eligibility using strictly direction-matched scan-in/out membership; no copies are made by default.
- On an explicit IOD/CCD export request, copies eligible files into a versioned Channellink folder inside each source directory, inserting `_sc_` before the filename version and keeping originals unchanged.

**It does not validate TCK, scan-clock period, frequency, duty cycle, pattern execution, electrical correctness or tester readiness.** Missing declarations alone do not fail membership. Empty/unreadable/unsupported inputs cannot pass.

## Installation

Requires Python **3.10+**. No pip packages or external services are required.

Reuse an existing local interpreter and use `-B` to avoid bytecode caches. Do not create an environment or editor-setup folders in shared pattern directories; if an isolated environment is needed, keep it outside that workspace.

Clone this repository into your personal skills directory, naming the directory `stil-scan-pin-checker`:

```text
~/.copilot/skills/stil-scan-pin-checker/
```

On Windows this is `%USERPROFILE%\.copilot\skills\stil-scan-pin-checker`. Alternatively copy the repository into `.github/skills/stil-scan-pin-checker/` in a project. Reopen the editor/chat if the new skill is not immediately discovered.

Ask Copilot: "Check scan pins in this STIL directory against this pin file" or "Explain how this STIL scan clock toggles." The latter loads the clock reference; it does not add timing checks.

## Standalone usage

From the repository directory:

```shell
python -B scripts/check_scan_pins.py /path/to/patterns --pin-file /path/to/target.pin --die DRD
python -B scripts/check_scan_pins.py /path/to/sample.stil.gz --pin-file /path/to/target.pin --die IOD
python -B scripts/check_scan_pins.py /path/to/patterns --plt-dir /path/to/PLT --stage sort --die DRD
python -B scripts/check_scan_pins.py /path/to/patterns --pin-file /path/to/target.pin --die CCD --groups scan_in scan_out scan_nonclk_dpin
```

`--die` is required even with `--pin-file`; missing/unknown dies are rejected instead of guessing a CHL policy. Each invocation covers one die, so split mixed-die scopes. These rules apply to both SORT and CLASS:

| Die | Default behavior | Copy policy |
|---|---|---|
| DRD | Basic only; CHL NOT_CHECKED | Disabled; `--channel-link` is rejected, even with `--dry-run` |
| IOD / CCD | Basic plus read-only CHL eligibility | Only with explicit `--channel-link` |

Input directories are recursive. Only `.stil` / `.stil.gz` files are processed. Generated `_Channellink` directories, `_sc_v<number>` names and legacy `_CHL` files are excluded to avoid processing outputs on repeat runs. Use your selected interpreter instead of `python` if needed. For sampling, pass selected files instead of a whole directory; include an actual IOD/CCD body to test positive eligibility. Rule development or sample checks do not authorize real copies.

### Body classification and Channellink copies

```shell
# Preview only (no file creation)
python -B scripts/check_scan_pins.py /path/to/patterns --pin-file /path/to/target.pin --die IOD --channel-link --dry-run
# Explicitly requested IOD/CCD generation only; preserve originals
python -B scripts/check_scan_pins.py /path/to/patterns --pin-file /path/to/target.pin --die CCD --channel-link
```

All files first undergo the direction-aware base check with its dpin exemption. DRD stops there and is not assessed for CHL. For IOD/CCD, only PASS files with an underscore-delimited `body` filename token and **every ScanIn in scan_in, every ScanOut in scan_out** qualify. CHL has no dpin exemption: a pin requiring dpin to pass prevents eligibility, although the file can still PASS the base check. Overlap with dpin is allowed when the correct directional scan group also contains the pin. Setup files, chain filenames without `body`, failed checks and files without data pins are never copied. With custom `--groups`, the order is scan-in, scan-out, nonclk dpin; three distinct names are required.

The version is extracted from a single `v<number>` filename token. Insert `sc_` immediately before that existing token, preserving all other tokens, version case and the full extension. Do not append a second version or the legacy `_CHL` suffix. For example:

```text
sort_IOD/batch/v1/example_body_p1_v1.stil.gz
	-> sort_IOD/batch/v1/v1_Channellink/example_body_p1_sc_v1.stil.gz
v1_TC100_G134/example_body_v1_TC100.stil.gz
	-> v1_TC100_G134/v1_Channellink/example_body_sc_v1_TC100.stil.gz
```

For recursive inputs, each file's own parent receives its output folder. A source under `batch/v1/` therefore gets `batch/v1/v1_Channellink/`, **not** `batch/v1_Channellink/`. The folder uses the lowercased filename version, not the full source directory name. Missing/ambiguous versions are reported instead of guessed; DRD skips this CHL naming check. `.stil` and `.stil.gz` retain their format, bytes and contents. Only the copied filename changes; SHA256 is verified. Existing identical files are skipped as ALREADY_EXISTS; differing files are errors and never overwritten. No rename, move or deletion of originals occurs.

Check-only IOD/CCD invocations report ELIGIBLE/SKIPPED (or a classification ERROR) with planned destinations and no writes. DRD reports NOT_CHECKED with `eligible: null` and no destination; this does not mean the pattern failed CHL requirements, since they were not evaluated. IOD/CCD export reports COPIED/ALREADY_EXISTS/SKIPPED/ERROR; preview uses WOULD_COPY and does not validate existing destination contents. Both check-only and preview create no output folders or files. Membership and CHL results are separate in JSON. Export/preview errors cause exit 2 even when membership passes; successful copies in other files are retained in export mode. Missing ScanIn/ScanOut declarations remain informational, as in basic mode.

### Optional pin-family selection

| Stage | Die | PLT filename family token |
|---|---|---|
| sort | DRD | ddr |
| sort | CCD | sort |
| sort | IOD | pcie |
| class | all three | class |

The token must be an underscore-separated part of the filename stem, e.g. `example_ddr_rev0.pin`. If several revisions match, select one explicitly with `--pin-file`. No vendor pin files are bundled. These family conventions are optional; explicit input paths and group overrides work with other installations.

## Results

JSON includes top-level `die`, `channel_link_checks` (false for DRD), `summary`, `channel_link_summary`, `channel_link_requested` and `dry_run`, plus per-file `pins`, `absent_fields`, `clocks_info_only`, `error` and `channel_link` entries.

Each pin has `passed`, `failure`, `expected_group`, `allowed_groups`, `direction_matches` and actual `groups`. `passed=false` identifies a failure; a nonempty `groups` list does not imply success when direction is wrong. These direction-aware rules supersede the older union-only behavior; rerun previously passing inputs under the current rules.

| Status | Meaning |
|---|---|
| PASS | At least one data pin was found and every declared data pin matches its direction or belongs to direction-free dpin |
| FAIL | At least one declared data pin is missing or only belongs to the opposite directional group without dpin exemption |
| UNDETERMINED | No declared data pins were found |
| ERROR | Configuration, parsing, decompression or file-read failure |

Check-only exit codes cover basic checks: **0** = all PASS, **1** = membership failure, **2** = configuration/basic ERROR or UNDETERMINED. A check-only CHL filename error is reported separately in JSON; inspect it even if basic passes. Export/preview CHL errors also cause exit 2. If several statuses occur, inspect every result. `line` refers to decompressed STIL, not a byte offset in gzip.

### Supported syntax and limits

- Quoted or simple unquoted pin references, scalar pins and single numeric bus indices (also `"bus[2]"`).
- ScanStructures starts a line; opening brace can be on a later line. Optional structure names are accepted. Multiple blocks supported; flat ScanChain bodies required.
- STIL `//`, `/* ... */` and `{* ... *}` annotations are ignored while preserving line positions. Quoted names containing comment delimiters remain intact.
- Pin files: `Resource` pin declarations; comma-separated `Group` members, including nested group references. Unknown members, cycles, duplicate/missing/empty requested groups cause an error. `#` comments are supported in pin files.
- UTF-8/ASCII inputs. Arbitrary pin expressions, ranges, escaped pin names and full IEEE STIL semantics are not implemented. Source files referenced by `Include` are not auto-resolved; declarations outside the inspected files are not covered.
- This is a targeted checker, not a complete language parser. Always review ERROR/UNDETERMINED and informational absent-field entries.

## Clock knowledge

See [references/clock-reading.md](references/clock-reading.md) for the evidence path from ScanMasterClock through SignalGroups, active waveform table, Spec parameters, vectors and Macro/Shift expansion. Example names and values are synthetic/illustrative, not product timing requirements.

## Development and tests

```shell
python -B -m unittest discover -s tests -v
```

Tests generate small synthetic STIL/pin fixtures in temporary directories, including isolated copy tests. They cover basic direction rules, die policy, `_sc_v<number>` insertion, source-parent placement, repeat-run exclusion and no-write check/preview behavior. No proprietary pattern data is included.

## Sharing and privacy

The tool runs locally and makes no network requests. Do not commit actual STIL/pin files, generated reports, workstation paths, credentials or device data. Default ignore rules cover these common artifacts. Any test run can expose pin/chain names in its JSON; handle output under your organization's data policy.

This project is provided without a license grant at present. For redistribution or use beyond what the repository owner's permissions allow, obtain an appropriate license from the owner.