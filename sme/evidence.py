"""Capture original applicability wording without inventing vehicle fitment."""

import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET

from .applicability_contracts import (
    EVIDENCE_CONTRACT,
    assertion_digest,
    digest,
    evidence_revision,
    sidecar_id,
    unit_id,
    validate_evidence,
    validate_vocabulary,
)
from .contract import load_manifest
from .normalize import CONTENT_NAME, _local_file, validate_content
from .source import INVENTORY_NAME, MANIFEST_NAME, SourceError, validate_inventory
from .vehicle_interpretation import interpret_statement

EVIDENCE_NAME = '.sme-applicability-evidence.json'
_ENGINE = re.compile(r'\b(\d{1,2}(?:\.\d)?)\s*(?:L\b|liter\b|litre\b)', re.I)
_EXCLUSION = re.compile(r'\b(?:except|excluding|not\s+for|does\s+not\s+apply\s+to)\b',
                        re.I)


def _file_sha(path):
    value = hashlib.sha256()
    with open(path, 'rb') as stream:
        while block := stream.read(1024 * 1024):
            value.update(block)
    return value.hexdigest()


def _mixed(text):
    return len(set(_ENGINE.findall(text))) > 1


def _ford_svg_statements(path):
    """Read Ford SVG <desc> fields as data, never the rendered derivative."""
    with open(path, 'rb') as stream:
        data = stream.read(16 * 1024 * 1024 + 1)
    if (len(data) > 16 * 1024 * 1024 or b'<!DOCTYPE' in data.upper()
            or b'<!ENTITY' in data.upper()):
        raise SourceError('Ford SVG metadata exceeds size/safety limits')
    try:
        root = ET.fromstring(data)
    except ET.ParseError as error:
        raise SourceError(f'invalid Ford SVG metadata: {error}') from error
    desc = next((child for child in root if child.tag.rsplit('}', 1)[-1] == 'desc'), None)
    if desc is None:
        return []
    fields = {node.tag.rsplit('}', 1)[-1]: (node.text or '').strip()
              for node in desc.iter() if node.text and node.text.strip()}
    year = fields.get('Modelyear', '')
    model = fields.get('Modelname', '')
    qualifiers = [(node.text or '').strip() for node in desc.iter()
                  if node.tag.rsplit('}', 1)[-1] == 'Qualifier' and node.text
                  and node.text.strip()]
    statements = []
    if year or model:
        statement = ' '.join(part for part in (year, model) if part)
        statements.append((statement, 'svg-desc:vehicle',
                           {'year': year, 'name': model, 'engine': ''}))
    for index, qualifier in enumerate(qualifiers):
        statement = ' '.join(part for part in (year, model, qualifier) if part)
        statements.append((statement, f'svg-desc:qualifier:{index}',
                           {'year': year, 'name': model, 'engine': qualifier}))
    return statements


def _new_unit(generation, document, content, kind, selector, parent=None):
    mixed = _mixed(content['text'])
    unit = {'id': unit_id(generation, document['id'], kind, selector),
            'document_id': document['id'], 'kind': kind, 'selector': selector,
            'original_sha256': document['content_sha256'],
            'citation': document['citations'][0], 'mixed_content': mixed,
            'search': {'state': 'whole' if content['text'] and not mixed
                       else 'metadata_only'}}
    if parent:
        unit['parent_unit_id'] = parent
        unit['search'] = {'state': 'metadata_only'}
    return unit


def _assertion(source_id, subject, statement, citation, selector, derivation,
               provenance, alternatives, support, intent='include',
               applies_to_descendants=False):
    value = {'subject_id': subject, 'statement': statement, 'citation': citation,
             'intent': intent, 'applies_to_descendants': applies_to_descendants,
             'derivation': derivation, 'provenance': provenance,
             'support': support, 'alternatives': alternatives}
    if selector:
        value['selector'] = selector
    value['digest'] = assertion_digest(value)
    value['id'] = sidecar_id('ev', source_id, subject, value['digest'])
    return value


def capture_evidence(package, vocabulary, verify_originals=True):
    """Produce A2 evidence records for one already normalized package.

    Automatic canonical vehicle mapping is intentionally absent here. Every
    statement is a proposal with unknown dimensions until A5 maps or reviews
    exact source assertions. This preserves title/OCR hints without letting a
    folder name or incidental date grant search eligibility.
    """
    root = os.path.abspath(package)
    if os.path.islink(package) or not os.path.isdir(root):
        raise SourceError('evidence input must be a regular normalized package')
    validate_vocabulary(vocabulary)
    manifest = load_manifest(_local_file(root, MANIFEST_NAME))
    content_path = _local_file(root, CONTENT_NAME)
    with open(content_path, 'rb') as stream:
        content_bytes = stream.read()
    content = validate_content(json.loads(content_bytes), manifest)
    with open(_local_file(root, INVENTORY_NAME), encoding='utf-8') as stream:
        inventory = validate_inventory(json.load(stream))
    if inventory['source_id'] != manifest['source']['id']:
        raise SourceError('source inventory does not match normalized package')
    if verify_originals:
        for member in inventory['members']:
            if _file_sha(_local_file(root, member['path'])) != member['sha256']:
                raise SourceError(f'original package member changed: {member["path"]}')
    content_sha = hashlib.sha256(content_bytes).hexdigest()
    manifest_sha = digest(manifest)
    generation = digest([manifest_sha, content_sha])
    value = {'contract': EVIDENCE_CONTRACT, 'source_id': manifest['source']['id'],
             'source_sha256': manifest['source']['sha256'],
             'manifest_sha256': manifest_sha, 'content_sha256': content_sha,
             'generation_sha256': generation,
             'vocabulary_revision': vocabulary['revision'],
             'units': [], 'assertions': []}
    records = {record['id']: record for record in content['documents']}
    assertion_ids = set()
    unit_ids = set()

    def add(subject, statement, citation, selector, derivation, provenance,
            structured=None, applies_to_descendants=False):
        if not statement or not statement.strip():
            return
        intent = 'exclude' if _EXCLUSION.search(statement) else 'include'
        alternatives, resolved = interpret_statement(statement, vocabulary, structured)
        bounded = any(alt[field]['state'] == 'exact' for alt in alternatives
                      for field in ('model', 'engine'))
        support = ('source_supported' if resolved and bounded and provenance == 'native'
                   and derivation in {'explicit_structured', 'explicit_text'}
                   else 'proposal')
        candidate = _assertion(value['source_id'], subject, statement.strip(), citation,
                               selector, derivation, provenance, alternatives, support,
                               intent, applies_to_descendants)
        if candidate['id'] not in assertion_ids:
            value['assertions'].append(candidate)
            assertion_ids.add(candidate['id'])

    for publication in manifest['publications']:
        if publication['documents']:
            first = publication['documents'][0]
            add(publication['id'], publication['title'], first['citations'][0],
                'publication-title', 'title_hint', 'catalog')
        if manifest['source']['format'].startswith('ford_tsp_disc_'):
            from fsd.disc import parse_epl

            structured = {}
            for item in publication['applicability']:
                with open(_local_file(root, item['source_path']), 'rb') as stream:
                    book = parse_epl(stream.read(), item['source_path'])
                if book:
                    for vehicle in book.vehicles:
                        wording = ' '.join(part for part in (
                            vehicle.get('year'), vehicle.get('name'),
                            vehicle.get('engine')) if part)
                        structured[wording] = vehicle
            for item in publication['applicability']:
                add(publication['id'], item['statement'],
                    {'kind': 'path', 'path': item['source_path']},
                    item.get('selector', 'ford-epl-vehicle'), 'explicit_structured',
                    'native', structured.get(item['statement']), True)
        # Other publication-level records may be inferred from a first HTML/PDF
        # page. Capture the page below; never promote it to whole-book scope.
        for document in publication['documents']:
            record = records[document['id']]
            kind = 'region' if record['role'] == 'pdf_page' else 'section'
            selector = f'page:{record["page"]}' if kind == 'region' else 'document'
            parent = _new_unit(generation, document, record, kind, selector)
            value['units'].append(parent)
            unit_ids.add(parent['id'])
            add(parent['id'], document['title'], document['citations'][0],
                'document-title', 'title_hint', 'catalog')
            for index, item in enumerate(document['applicability']):
                level = item['level']
                subject = parent['id']
                if level in {'table', 'figure'}:
                    child = _new_unit(generation, document, record, level,
                                      item.get('selector', f'{level}:{index}'), parent['id'])
                    if child['id'] not in unit_ids:
                        value['units'].append(child)
                        unit_ids.add(child['id'])
                    subject = child['id']
                derivation = ('title_hint' if item.get('selector') in
                              {'heading', 'publication-title'} else 'explicit_text')
                provenance = document['text']['provenance']
                if provenance == 'none':
                    provenance = 'native' if kind == 'section' else 'catalog'
                add(subject, item['statement'], document['citations'][0],
                    item.get('selector'), derivation, provenance)
            if manifest['source']['format'].startswith('ford_tsp_disc_'):
                citations = {citation['path'] for citation in document['citations']
                             if citation['kind'] == 'path'}
                for figure_index, figure in enumerate(record['figures']):
                    path = figure.get('path')
                    if not path or not path.casefold().endswith('.svg') or path not in citations:
                        continue
                    statements = _ford_svg_statements(_local_file(root, path))
                    if not statements:
                        continue
                    child = _new_unit(generation, document, record, 'figure',
                                      f'figure:{figure_index}:svg-desc', parent['id'])
                    if child['id'] not in unit_ids:
                        value['units'].append(child)
                        unit_ids.add(child['id'])
                    for statement, selector, structured in statements:
                        add(child['id'], statement, {'kind': 'path', 'path': path},
                            selector, 'explicit_structured', 'native', structured)
    value['revision'] = evidence_revision(value)
    return validate_evidence(value, manifest, vocabulary)


def write_evidence(package, vocabulary_path, destination):
    """Write or reuse a validated, hash-bound sidecar outside the package."""
    with open(vocabulary_path, encoding='utf-8') as stream:
        vocabulary = json.load(stream)
    validate_vocabulary(vocabulary)
    if os.path.islink(destination):
        raise SourceError('evidence destination may not be a symbolic link')
    if os.path.isfile(destination):
        root = os.path.abspath(package)
        manifest = load_manifest(_local_file(root, MANIFEST_NAME))
        content_path = _local_file(root, CONTENT_NAME)
        with open(content_path, 'rb') as stream:
            content_sha = hashlib.sha256(stream.read()).hexdigest()
        with open(_local_file(root, INVENTORY_NAME), encoding='utf-8') as stream:
            inventory = validate_inventory(json.load(stream))
        if inventory['source_id'] != manifest['source']['id']:
            raise SourceError('cached evidence source inventory does not match manifest')
        for member in inventory['members']:
            if _file_sha(_local_file(root, member['path'])) != member['sha256']:
                raise SourceError(f'original package member changed: {member["path"]}')
        with open(destination, encoding='utf-8') as stream:
            value = json.load(stream)
        if value.get('content_sha256') != content_sha:
            raise SourceError('cached evidence is stale for this content generation')
        validate_evidence(value, manifest, vocabulary)
        return {'output': os.path.abspath(destination), 'source_id': value['source_id'],
                'units': len(value['units']), 'assertions': len(value['assertions']),
                'revision': value['revision'], 'cached': True}
    if os.path.lexists(destination):
        raise SourceError(f'evidence destination is not a regular file: {destination}')
    value = capture_evidence(package, vocabulary)
    parent = os.path.dirname(os.path.abspath(destination))
    if not os.path.isdir(parent) or os.path.islink(parent):
        raise SourceError('evidence destination parent must be a regular directory')
    with open(destination, 'x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    return {'output': os.path.abspath(destination), 'source_id': value['source_id'],
            'units': len(value['units']), 'assertions': len(value['assertions']),
            'revision': value['revision'], 'cached': False}
