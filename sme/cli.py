"""Manufacturer-neutral command line for source inspection and extraction."""
import argparse
import json
import sys

from . import __version__
from .contract import ContractError, contract_summary, load_manifest
from .normalize import normalize_source
from .source import SourceError, extract_source, inspect_source


def cmd_contract(args):
    value = contract_summary()
    if args.json:
        print(json.dumps(value, indent=2))
    else:
        print(f'Manifest contract: {value["manifest_contract"]}')
        print(f'Operation contract: {value["operation_contract"]}')
        print('Declared formats: ' + ', '.join(value['formats']))
        print('Neutral readers: ' + ', '.join(value['neutral_readers']))
    return 0


def _print_operation(value):
    source = value['source']
    print(f'Format: {source["format"]}')
    print(f'Container: {source["container"]}')
    print(f'Status: {source["status"]}')
    print(f'Source ID: {source["id"]}')
    print(f'Publications: {len(value["publications"])}')
    for publication in value['publications']:
        print(f'  {publication["id"]}  {publication["source_path"]}')
    for diagnostic in value['diagnostics']:
        print(f'{diagnostic["level"]}: {diagnostic["message"]}', file=sys.stderr)
    if value['operation'] == 'extract' and value['output']:
        output = value['output']
        print(f'Files written: {output["files_written"]}')
        print(f'Bytes written: {output["bytes_written"]}')


def _source_error(args, error):
    if args.json:
        print(json.dumps({'ok': False, 'error': str(error)}, indent=2))
    else:
        print(f'error: {error}', file=sys.stderr)
    return 2


def cmd_probe(args):
    try:
        value = inspect_source(args.source).operation()
    except (OSError, SourceError) as ex:
        return _source_error(args, ex)
    if args.json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        _print_operation(value)
    return 0 if value['ok'] else 1


def cmd_extract(args):
    try:
        value = extract_source(
            args.source, args.out, publication_ids=args.publication,
        )
    except (OSError, SourceError) as ex:
        return _source_error(args, ex)
    if args.json:
        print(json.dumps(value, indent=2, ensure_ascii=False))
    else:
        _print_operation(value)
    return 0 if value['ok'] else 1


def cmd_validate(args):
    try:
        value = load_manifest(args.manifest)
    except (OSError, json.JSONDecodeError, ContractError) as ex:
        if args.json:
            print(json.dumps({'ok': False, 'error': str(ex)}, indent=2))
        else:
            print(f'error: {ex}', file=sys.stderr)
        return 1
    result = {
        'ok': True,
        'contract': value['contract'],
        'source_id': value['source']['id'],
        'publications': len(value['publications']),
        'documents': sum(len(item['documents']) for item in value['publications']),
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f'{args.manifest}: valid {value["contract"]}')
    return 0


def cmd_normalize(args):
    try:
        result = normalize_source(args.source, args.out, args.ocr_manifest, args.source_inventory)
    except (OSError, SourceError, ContractError, json.JSONDecodeError) as ex:
        return _source_error(args, ex)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f'Normalization: {result["status"]}')
        print(f'Documents: {result["documents"]}; searchable: {result["searchable_documents"]}')
        print(f'Output: {result["output"]}')
        for failure in result['failures']:
            print(f'{failure["path"]}: {failure["message"]}', file=sys.stderr)
    return 0 if result['ok'] else 1


def make_parser():
    parser = argparse.ArgumentParser(
        prog='sme',
        description='Safely inspect and extract supported service-manual sources.',
        epilog='Normalize a verified extraction to preserve HTML structure and cited PDF pages.',
    )
    parser.add_argument('--version', action='version', version=f'sme {__version__}')
    commands = parser.add_subparsers(dest='command', required=True, metavar='COMMAND')

    command = commands.add_parser('contract', help='show the supported contract vocabulary')
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_contract)

    command = commands.add_parser('validate-manifest', help='validate a v1 manifest JSON file')
    command.add_argument('manifest')
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_validate)

    command = commands.add_parser(
        'probe', help='inspect a ZIP, folder or PDF without writing output',
    )
    command.add_argument('source')
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_probe)

    command = commands.add_parser(
        'extract', help='verify and atomically copy selected original files',
    )
    command.add_argument('source')
    command.add_argument('-o', '--out', required=True)
    command.add_argument(
        '--publication', action='append',
        help='exact publication ID to extract (repeatable; default: all)',
    )
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_extract)

    command = commands.add_parser('normalize', help='normalize a verified Step 3 extraction')
    command.add_argument('source')
    command.add_argument('-o', '--out', required=True)
    command.add_argument('--ocr-manifest', help='hash-bound service-manual-ocr-map/v1 JSON')
    command.add_argument('--source-inventory', help='full same-source inventory for excluded links')
    command.add_argument('--json', action='store_true', help='machine-readable output')
    command.set_defaults(function=cmd_normalize)
    return parser


def main(argv=None):
    args = make_parser().parse_args(argv)
    return args.function(args)
