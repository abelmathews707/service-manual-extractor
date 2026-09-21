"""Contract-only neutral command line introduced in implementation Step 2."""
import argparse
import json
import sys

from . import __version__
from .contract import ContractError, contract_summary, load_manifest


def cmd_contract(args):
    value = contract_summary()
    if args.json:
        print(json.dumps(value, indent=2))
    else:
        print(f'Manifest contract: {value["manifest_contract"]}')
        print(f'Operation contract: {value["operation_contract"]}')
        print('Declared formats: ' + ', '.join(value['formats']))
        print('Neutral readers: none (Step 2 defines contracts only)')
    return 0


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


def make_parser():
    parser = argparse.ArgumentParser(
        prog='sme',
        description='Inspect the versioned, manufacturer-neutral extraction contract.',
        epilog=('Step 2 defines contracts only. Source probe and extraction readers '
                'arrive in Step 3.'),
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
    return parser


def main(argv=None):
    args = make_parser().parse_args(argv)
    return args.function(args)
