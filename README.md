# STIL Scan Pin Checker

A reusable Copilot skill and standalone Python CLI for checking STIL scan-data pins against tester pin groups. Includes a reference for explaining scan clocks without adding clock validation to the pin check.

## What it checks

- Reads `.stil` and `.stil.gz` without modifying or extracting inputs to disk.
- Extracts declared `ScanIn` and `ScanOut` from every `ScanStructures / ScanChain` block.
- Tests membership in the **union** of three pin groups (defaults: `stm_scan_in`, `stm_scan_out`, `stm_scan_nonclk_dpin`). Direction matching is intentionally not required.
- Converts names to uppercase and bus indices `[n]` to `_n`. Example: `"data_bus"[2]` becomes `DATA_BUS_2`.
- Reports chain names, decompressed line numbers, normalized/original pins and matching groups as JSON.
- Records clocks and absent ScanIn/ScanOut declarations as informational observations.

**It does not validate TCK, scan-clock period, frequency, duty cycle, pattern execution, electrical correctness or tester readiness.** Missing declarations alone do not fail membership. Empty/unreadable/unsupported inputs cannot pass.

## Installation

Requires Python **3.10+**. No pip packages or external services are required.

Clone this repository into your personal skills directory, naming the directory `stil-scan-pin-checker`:

```text
~/.copilot/skills/stil-scan-pin-checker/
```

On Windows this is `%USERPROFILE%\.copilot\skills\stil-scan-pin-checker`. Alternatively copy the repository into `.github/skills/stil-scan-pin-checker/` in a project. Reopen the editor/chat if the new skill is not immediately discovered.

Ask Copilot: "Check scan pins in this STIL directory against this pin file" or "Explain how this STIL scan clock toggles." The latter loads the clock reference; it does not add timing checks.

## Standalone usage

From the repository directory:

```shell
python scripts/check_scan_pins.py /path/to/patterns --pin-file /path/to/target.pin
python scripts/check_scan_pins.py /path/to/sample.stil.gz --pin-file /path/to/target.pin
python scripts/check_scan_pins.py /path/to/patterns --plt-dir /path/to/PLT --stage sort --die DRD
python scripts/check_scan_pins.py /path/to/patterns --pin-file /path/to/target.pin --groups scan_in scan_out scan_nonclk_dpin
```

Input directories are recursive. Only `.stil` / `.stil.gz` files are processed. Use your selected interpreter instead of `python` if needed.

### Optional pin-family selection

| Stage | Die | PLT filename family token |
|---|---|---|
| sort | DRD | ddr |
| sort | CCD | sort |
| sort | IOD | pcie |
| class | all three | class |

The token must be an underscore-separated part of the filename stem, e.g. `example_ddr_rev0.pin`. If several revisions match, select one explicitly with `--pin-file`. No vendor pin files are bundled. These family conventions are optional; explicit input paths and group overrides work with other installations.

## Results

JSON includes a top-level `summary` and per-file `pins`, `absent_fields`, `clocks_info_only` and `error` entries.

| Status | Meaning |
|---|---|
| PASS | At least one data pin was found and every declared data pin belongs to the allowed union |
| FAIL | At least one declared data pin is missing from the allowed union |
| UNDETERMINED | No declared data pins were found |
| ERROR | Configuration, parsing, decompression or file-read failure |

Exit codes: **0** = all PASS, **1** = membership failure, **2** = any ERROR/UNDETERMINED. If several statuses occur, inspect the JSON for every result. `line` refers to decompressed STIL, not a byte offset in gzip.

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
python -m unittest discover -s tests -v
```

Tests generate small synthetic STIL/pin fixtures in temporary directories. No proprietary pattern data is included.

## Sharing and privacy

The tool runs locally and makes no network requests. Do not commit actual STIL/pin files, generated reports, workstation paths, credentials or device data. Default ignore rules cover these common artifacts. Any test run can expose pin/chain names in its JSON; handle output under your organization's data policy.

This project is provided without a license grant at present. For redistribution or use beyond what the repository owner's permissions allow, obtain an appropriate license from the owner.