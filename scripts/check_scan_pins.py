"""Read-only STIL scan-data pin membership checker (Python 3.10+, stdlib only)."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import re
import sys

DEFAULT_GROUPS = ('stm_scan_in', 'stm_scan_out', 'stm_scan_nonclk_dpin')
# Quoted strings are consumed whole so comment markers inside names remain literal.
LEX = re.compile(r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*|\{\*|\*/|\*\}')
QUOTED = re.compile(r'"(?:\\.|[^"\\])*"')
REF = re.compile(r'\s*(?:"([^"\n]+)"|([A-Za-z_][\w.$]*))\s*(?:\[\s*(\d+)\s*\])?\s*')


class ParseError(ValueError):
    pass


def uncomment(lines, pin_file=False):
    """Strip multiline comments, annotations and line comments; retain line numbers."""
    end_marker = None
    for number, line in enumerate(lines, 1):
        if pin_file:
            line = line.split('#', 1)[0] + ('\n' if '#' in line else '')
        pos = 0
        pieces = []
        while pos < len(line):
            if end_marker:
                end = line.find(end_marker, pos)
                if end < 0:
                    break
                pos = end + len(end_marker)
                end_marker = None
                pieces.append(' ')
                continue
            match = LEX.search(line, pos)
            if match is None:
                pieces.append(line[pos:])
                break
            pieces.append(line[pos:match.start()])
            token = match[0]
            pos = match.end()
            if token.startswith('"'):
                pieces.append(token)
            elif token.startswith('//'):
                break
            elif token in ('/*', '{*'):
                end_marker = '*/' if token == '/*' else '*}'
                pieces.append(' ')
            else:
                raise ParseError(f'Unexpected comment terminator at line {number}')
        yield number, ''.join(pieces).rstrip('\r\n') + '\n'
    if end_marker:
        raise ParseError('Unterminated comment or annotation')


def normalize(ref):
    match = REF.fullmatch(ref)
    if match is None:
        raise ParseError(f'Unsupported pin reference: {ref!r}')
    base = match[1] or match[2]
    # Support both "bus"[2] and "bus[2]".
    embedded = re.fullmatch(r'(.+)\[(\d+)\]', base)
    if embedded:
        if match[3] is not None:
            raise ParseError(f'Double pin index: {ref}')
        base, index = embedded.groups()
    else:
        index = match[3]
    return (base + ('_' + index if index is not None else '')).upper()


def load_groups(path, names):
    with Path(path).open(encoding='utf-8-sig') as stream:
        text = ''.join(line for _, line in uncomment(stream, pin_file=True))
    definitions = {}
    for match in re.finditer(r'\bGroup\s+(\w+)\s*\{([^{}]*)\}', text):
        if match[1] in definitions:
            raise ParseError(f'Duplicate group: {match[1]}')
        definitions[match[1]] = match[2]
    # Resource-level pin declarations are the terminals of nested groups.
    declared = set(re.findall(r'^\s*([A-Za-z_]\w*)\s*;', text, re.M))

    def expand(name, stack=()):
        if name in stack:
            raise ParseError(f'Group cycle: {stack + (name,)}')
        if name not in definitions:
            raise ParseError(f'Missing group: {name}')
        pins = set()
        for item in definitions[name].split(','):
            item = item.strip()
            if not item:
                continue
            if item in definitions:
                pins.update(expand(item, stack + (name,)))
            elif item in declared:
                pins.add(normalize(item))
            else:
                raise ParseError(f'Unknown or unsupported member {item!r} in {name}')
        if not pins:
            raise ParseError(f'Empty group: {name}')
        return pins

    return {name: expand(name) for name in names}


def scan_blocks(path):
    """Read every line, retain only ScanStructures blocks; validates gzip on EOF."""
    opener = gzip.open if str(path).lower().endswith('.gz') else open
    active = None
    buffer = []
    depth = 0
    opened = False
    with opener(path, 'rt', encoding='utf-8-sig') as stream:
        for number, line in uncomment(stream):
            mask = QUOTED.sub(lambda m: ' ' * len(m[0]), line)
            if active is None:
                if not re.match(r'^\s*ScanStructures\b', mask):
                    if re.search(r'\bScanStructures\b', mask):
                        raise ParseError(f'ScanStructures must start a line ({number})')
                    continue
                active = number
                depth = 0
                opened = False
            buffer.append(line)
            for char in mask:
                if char == '{':
                    depth += 1
                    opened = True
                elif char == '}':
                    depth -= 1
                    if depth < 0:
                        raise ParseError(f'Unbalanced braces at {number}')
            if opened and depth == 0:
                yield active, ''.join(buffer)
                active = None
                buffer = []
            if sum(map(len, buffer[-1:])) > 16 * 1024 * 1024 or len(buffer) > 200000:
                raise ParseError('ScanStructures exceeds supported size')
    if active is not None:
        raise ParseError('Unterminated ScanStructures')


def check_file(path, groups):
    rows = []
    absent = []
    clocks = set()
    chains_count = 0
    blocks_count = 0
    try:
        for first, text in scan_blocks(path):
            blocks_count += 1
            header = re.match(r'\s*ScanStructures\s*(?:"[^"]*"|\w+)?\s*\{', text)
            if header is None:
                raise ParseError('Unsupported ScanStructures header')
            body = text[header.end():text.rfind('}')]
            chain_re = re.compile(r'\bScanChain\s+("[^"]+"|[^\s{]+)\s*\{([^{}]*)\}')
            matches = list(chain_re.finditer(body))
            if chain_re.sub('', body).strip():
                raise ParseError('Unsupported content inside ScanStructures')
            if not matches:
                raise ParseError('Empty ScanStructures')
            for chain in matches:
                chains_count += 1
                name = chain[1].strip('"')
                body_start = header.end() + chain.start(2)
                for role in ('ScanIn', 'ScanOut', 'ScanMasterClock'):
                    fields = list(re.finditer(r'\b' + role + r'\b\s*([^;{}]+);', chain[2]))
                    if len(fields) != len(re.findall(r'\b' + role + r'\b', chain[2])):
                        raise ParseError(f'Malformed {role} in {name}')
                    if len(fields) > 1:
                        raise ParseError(f'Duplicate {role} in {name}')
                    if not fields and role != 'ScanMasterClock':
                        absent.append({'chain': name, 'field': role})
                    for field in fields:
                        raw = field[1].strip()
                        pin = normalize(raw)
                        if role == 'ScanMasterClock':
                            clocks.add(pin)
                            continue
                        hits = [g for g, pins in groups.items() if pin in pins]
                        rows.append({'chain': name, 'role': role, 'original': raw,
                                     'pin': pin, 'groups': hits,
                                     'line': first + text[:body_start + field.start()].count('\n')})
        status = 'FAIL' if any(not row['groups'] for row in rows) else ('PASS' if rows else 'UNDETERMINED')
        error = None if rows else 'No declared scan data pins found'
    except (OSError, EOFError, UnicodeError, ValueError) as exc:
        status = 'ERROR'
        error = str(exc)
    return {'file': str(path), 'status': status, 'error': error,
            'blocks': blocks_count, 'chains': chains_count, 'pins': rows,
            'absent_fields': absent, 'clocks_info_only': sorted(clocks)}


def resolve_pin(args):
    if args.pin_file:
        return args.pin_file
    if not (args.plt_dir and args.stage and args.die):
        raise ParseError('Use --pin-file or all of --plt-dir, --stage, --die')
    kind = 'class' if args.stage == 'class' else {'DRD': 'ddr', 'CCD': 'sort', 'IOD': 'pcie'}[args.die]
    candidates = [p for p in args.plt_dir.iterdir()
                  if p.suffix.lower() == '.pin' and kind in p.stem.lower().split('_')]
    if len(candidates) != 1:
        raise ParseError(f'Expected one {kind} pin file; found {len(candidates)}. Use --pin-file.')
    return candidates[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path, help='STIL file or directory (recursive)')
    parser.add_argument('--pin-file', type=Path)
    parser.add_argument('--plt-dir', type=Path)
    parser.add_argument('--stage', choices=('sort', 'class'))
    parser.add_argument('--die', type=str.upper, choices=('DRD', 'CCD', 'IOD'))
    parser.add_argument('--groups', nargs=3, default=DEFAULT_GROUPS)
    args = parser.parse_args(argv)
    try:
        pin_file = resolve_pin(args)
        groups = load_groups(pin_file, args.groups)
        paths = [args.input] if args.input.is_file() else sorted(args.input.rglob('*'))
        paths = [p for p in paths if p.is_file() and p.name.lower().endswith(('.stil', '.stil.gz'))]
        if not paths:
            raise ParseError('No .stil or .stil.gz files found')
        results = [check_file(path, groups) for path in paths]
        counts = dict(Counter(row['status'] for row in results))
        print(json.dumps({'pin_file': str(pin_file), 'group_sizes': {g: len(p) for g, p in groups.items()},
                          'normalization': 'uppercase; [n] -> _n', 'clock_checks': False,
                          'summary': counts, 'files': results}, indent=2))
        if any(r['status'] in ('ERROR', 'UNDETERMINED') for r in results):
            return 2
        return 1 if counts.get('FAIL') else 0
    except (OSError, ValueError) as exc:
        print(json.dumps({'status': 'ERROR', 'error': str(exc)}))
        return 2


if __name__ == '__main__':
    sys.exit(main())