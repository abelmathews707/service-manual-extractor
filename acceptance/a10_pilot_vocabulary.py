"""Small, source-reviewed A10 vehicle sample; not a production vehicle catalog.

Usage: python3 acceptance/a10_pilot_vocabulary.py OUTPUT.json

The Ford tuple is from the 2003 V3D PC/ED source and the Chevrolet tuples
are from the 2006 Silverado 1500 wiring PDF. This intentionally omits other
engines, model years and makes until their original citations are reviewed.
"""

import json
import sys

from sme.applicability_contracts import (
    VOCABULARY_CONTRACT,
    configuration_id,
    digest,
    sidecar_id,
    validate_vocabulary,
)


def make_pilot_vocabulary():
    ford = sidecar_id('make', 'ford')
    chevrolet = sidecar_id('make', 'chevrolet')
    f250 = sidecar_id('model', ford, 'f-250')
    silverado = sidecar_id('model', chevrolet, 'silverado-1500')
    diesel = sidecar_id('engine', 'ford', '6-0-power-stroke-diesel')
    vin_x = sidecar_id('engine', 'gm', '4-3-vin-x-gasoline')
    vin_v = sidecar_id('engine', 'gm', '4-8-vin-v-gasoline')
    tuples = [(ford, f250, 2003, diesel),
              (chevrolet, silverado, 2006, vin_x),
              (chevrolet, silverado, 2006, vin_v)]
    value = {
        'contract': VOCABULARY_CONTRACT,
        'makes': [
            {'id': ford, 'key': 'ford', 'name': 'Ford'},
            {'id': chevrolet, 'key': 'chevrolet', 'name': 'Chevrolet'},
        ],
        'models': [
            {'id': f250, 'key': 'f-250', 'name': 'F-250', 'make_id': ford,
             'family': 'Super Duty'},
            {'id': silverado, 'key': 'silverado-1500', 'name': 'Silverado 1500',
             'make_id': chevrolet},
        ],
        'engines': [
            {'id': diesel, 'key': '6-0-power-stroke-diesel',
             'name': '6.0L Power Stroke diesel', 'manufacturer': 'ford',
             'fuel': 'diesel', 'displacement_l': 6.0},
            {'id': vin_x, 'key': '4-3-vin-x-gasoline', 'name': '4.3L VIN X',
             'manufacturer': 'gm', 'fuel': 'gasoline', 'displacement_l': 4.3,
             'code': 'VIN X'},
            {'id': vin_v, 'key': '4-8-vin-v-gasoline', 'name': '4.8L VIN V',
             'manufacturer': 'gm', 'fuel': 'gasoline', 'displacement_l': 4.8,
             'code': 'VIN V'},
        ],
        'configurations': [
            {'id': configuration_id(make, model, year, engine),
             'make_id': make, 'model_id': model, 'model_year': year,
             'engine_id': engine, 'qualifiers': {}}
            for make, model, year, engine in tuples
        ],
        'aliases': [],
    }
    value['revision'] = digest(value)
    return validate_vocabulary(value)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('usage: a10_pilot_vocabulary.py OUTPUT.json')
    with open(sys.argv[1], 'x', encoding='utf-8') as stream:
        json.dump(make_pilot_vocabulary(), stream, indent=2, ensure_ascii=False)
        stream.write('\n')
