"""Extend the A10 sample with distinct, source-reviewed Ford V10 fuel identities.

This is a bounded engineering fixture, not a catalog of all Ford configurations.
The gasoline pilot qualifiers are declared by the owner; the workshop VIN/VC
tables establish the corresponding codes, not the owner's actual VIN.
"""

import copy
import json
import sys

from sme.applicability_contracts import (
    configuration_id,
    digest,
    sidecar_id,
    validate_vocabulary,
)

FORD_SOURCE = 'src_7c2747f1e143b7a36697aae0f9f68f45'
V10_HEADING = '6.8L E/F-Series (A/T)'
V10_PATH = 'originals/content/useni4/v32/V326065.htm'
IDENTIFICATION_PATH = 'originals/content/useni4/s3o/S3O01001.htm'


def extend_vocabulary(accepted):
    validate_vocabulary(accepted)
    value = copy.deepcopy(accepted)
    ford = sidecar_id('make', 'ford')
    model = sidecar_id('model', ford, 'f-250')
    if not any(item['id'] == model for item in value['models']):
        raise ValueError('accepted vocabulary has no Ford F-250')
    for key, name, fuel, code, qualifiers in (
            ('6-8-sohc-efi-v10-gasoline', '6.8L V10', 'gasoline', 'VIN S',
             {'transmission': '4R100', 'drivetrain': '4WD'}),
            ('6-8-sohc-efi-v10-cng', '6.8L CNG V10', 'cng', 'VIN Z', {})):
        engine = sidecar_id('engine', 'ford', key)
        value['engines'].append({'id': engine, 'key': key, 'name': name,
                                'manufacturer': 'ford', 'fuel': fuel,
                                'displacement_l': 6.8, 'code': code})
        value['configurations'].append({
            'id': configuration_id(ford, model, 2003, engine, qualifiers),
            'make_id': ford, 'model_id': model, 'model_year': 2003,
            'engine_id': engine, 'qualifiers': qualifiers})
        literal = V10_HEADING if fuel == 'gasoline' else 'Natural Gas Fuel System'
        path = V10_PATH if fuel == 'gasoline' else 'originals/content/useni4/v32/V321025.htm'
        value['aliases'].append({'literal': literal, 'target_id': engine,
                                 'make_id': ford,
                                 'evidence': {'source_id': FORD_SOURCE,
                                              'citation': {'kind': 'path', 'path': path}}})
    value['revision'] = digest({key: item for key, item in value.items() if key != 'revision'})
    return validate_vocabulary(value)


def main():
    if len(sys.argv) != 3:
        raise SystemExit('usage: b1_pilot_vocabulary.py ACCEPTED.json OUTPUT.json')
    with open(sys.argv[1], encoding='utf-8') as stream:
        result = extend_vocabulary(json.load(stream))
    with open(sys.argv[2], 'x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
