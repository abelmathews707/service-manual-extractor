"""Atomic offline library generations with pre-scoped text shards."""

import hashlib
import json
import math
import os
import re
import shutil
import tempfile
from collections import OrderedDict

from .applicability_contracts import digest, scope_fingerprint
from .contract import ContractError
from .library import make_library, resolve_scope, scope_selections, verified_package
from .matching import compile_evidence
from .normalize import _local_file

EXPORT_CONTRACT = 'service-manual-search-export/v1'
_WORD = re.compile(r'\w+', re.UNICODE)


def _transform_revision():
    root = os.path.dirname(os.path.dirname(__file__))
    sha = hashlib.sha256()
    for relative in ('sme/library.py', 'sme/library_export.py', 'sme/matching.py',
                     'sme/applicability_contracts.py'):
        sha.update(relative.encode() + b'\0')
        with open(os.path.join(root, relative), 'rb') as stream:
            while block := stream.read(1024 * 1024):
                sha.update(block)
    return sha.hexdigest()


class SearchCancelled(Exception):
    """A newer vehicle/query request superseded this search."""


def _json(path, value):
    with open(path, 'x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, separators=(',', ':'))
        stream.write('\n')


def _reject_symlinks(root):
    for directory, dirs, files in os.walk(root):
        for name in dirs + files:
            if os.path.islink(os.path.join(directory, name)):
                raise ContractError('library package contains a symbolic link')


def _unit_texts(records, projections):
    texts = {}
    for record in records:
        evidence = record['evidence']
        if evidence is None:
            continue
        content = {item['id']: item for item in record['content']['documents']}
        documents = {doc['id']: doc for pub in record['manifest']['publications']
                     for doc in pub['documents']}
        for unit in evidence['units']:
            if unit['search']['state'] == 'metadata_only':
                continue
            document = documents[unit['document_id']]
            content_record = content[unit['document_id']]
            if unit['search']['state'] == 'isolated':
                text = projections.get(unit['id'])
                if text is None or hashlib.sha256(text.encode()).hexdigest() != \
                        unit['search']['text_sha256']:
                    raise ContractError('isolated text projection is absent or changed')
            else:
                text = content_record['text']
            item = {'unit_id': unit['id'], 'text': text,
                    'document_id': unit['document_id'],
                    'publication_id': content_record['publication_id'],
                    'title': document['title'], 'citation': unit['citation'],
                    'provenance': document['text']['provenance']}
            previous = texts.get(unit['id'])
            if previous and previous != item:
                raise ContractError('same unit ID resolves to different text or citation')
            texts[unit['id']] = item
    return texts


def _scopes(library, records, vocabulary, review, history):
    results = {}
    compiled = {record['evidence']['source_id']:
                compile_evidence(record['evidence'], record['manifest'])
                for record in records if record['evidence'] is not None}
    for selection, browse_all in scope_selections(vocabulary):
        for mode in ('confirmed', 'include_possible'):
            for include_reference in (False, True):
                resolved = resolve_scope(library, records, vocabulary, review,
                                         selection, mode=mode,
                                         include_reference=include_reference,
                                         browse_all=browse_all,
                                         evidence_history=history,
                                         compiled_sources=compiled,
                                         _validated=True)
                scope = resolved['scope']
                results[scope['fingerprint']] = resolved
    return results


def _shards(scopes, texts, destination, max_shard_chars):
    membership = {unit_id: [] for unit_id in texts}
    for fingerprint, result in scopes.items():
        for item in result['scope']['eligible']:
            membership[item['unit_id']].append(fingerprint)
    grouped = {}
    for unit_id, fingerprints in membership.items():
        if fingerprints:
            grouped.setdefault(tuple(sorted(fingerprints)), []).append(unit_id)
    shards = {}
    unit_to_shard = {}
    folder = os.path.join(destination, 'shards')
    os.mkdir(folder)
    for signature, units in sorted(grouped.items()):
        batch, size = [], 0

        def flush(signature=signature):
            nonlocal batch, size
            if not batch:
                return
            payload = [texts[item] for item in batch]
            identifier = digest(payload)[:32]
            filename = f'shards/{identifier}.json'
            if identifier not in shards:
                _json(os.path.join(destination, filename), payload)
                shards[identifier] = {'path': filename, 'unit_ids': batch.copy(),
                                      'memberships': list(signature)}
            for item in batch:
                unit_to_shard[item] = identifier
            batch, size = [], 0

        for unit_id in sorted(units):
            text_size = len(texts[unit_id]['text'])
            if batch and size + text_size > max_shard_chars:
                flush()
            batch.append(unit_id)
            size += text_size
            if size >= max_shard_chars:
                flush()
        flush()
    return shards, unit_to_shard


def _index(scopes, shards, unit_to_shard, library, vocabulary, review,
           unsupported_inputs):
    scope_index = {}
    filter_counts = []
    for fingerprint, resolved in scopes.items():
        eligible = resolved['scope']['eligible']
        shard_ids = sorted({unit_to_shard[item['unit_id']] for item in eligible})
        scope_index[fingerprint] = {
            'scope': resolved['scope'], 'shard_ids': shard_ids,
            'counts': resolved['counts'], 'no_content': resolved['no_content'],
            'unit_occurrences': {item['unit_id']:
                                 resolved['unit_occurrences'][item['unit_id']]
                                 for item in eligible}}
        filter_counts.append({
            'selection': resolved['scope']['selection'],
            'mode': resolved['scope']['mode'],
            'include_reference': resolved['scope']['include_reference'],
            'browse_all': resolved['scope']['browse_all'],
            'eligible_units': len(eligible), 'state_counts': resolved['counts']})
    return {'contract': EXPORT_CONTRACT, 'library_revision': library['revision'],
            'vocabulary_revision': vocabulary['revision'],
            'review_revision': review['revision'],
            'policy_version': library['policy_version'],
            'scopes': scope_index, 'shards': shards,
            'filter_counts': filter_counts,
            'unsupported_inputs': unsupported_inputs,
            'transform_revision': _transform_revision()}


def publish_library(output_root, sources, vocabulary, review, *,
                    evidence_history=None, projections=None, max_shard_chars=96000,
                    before_activate=None, discovery_report=None):
    """Publish a new immutable generation, then atomically point to it.

    ``sources`` are dictionaries with ``package`` and optional ``evidence``
    (a validated sidecar value). The output root must not be inside a source.
    A failed build leaves the previous content generation in place. Consumers
    must still compare its review revision to the current review before search.
    """
    if type(max_shard_chars) is not int or not 1000 <= max_shard_chars <= 1000000:
        raise ContractError('shard character limit must be 1,000–1,000,000')
    unsupported = []
    if discovery_report is not None:
        for item in discovery_report['sources']:
            if item['status'] != 'recognized':
                unsupported.append({'name': item['name'], 'status': item['status'],
                                    'reason': item.get('reason') or item.get('failures')})
    root = os.path.abspath(output_root)
    if os.path.islink(output_root) or (os.path.lexists(root) and not os.path.isdir(root)):
        raise ContractError('library output root must be a regular directory')
    for source in sources:
        package = os.path.abspath(source['package'])
        if os.path.commonpath((package, root)) == package:
            raise ContractError('library output may not be inside a source package')
    os.makedirs(root, exist_ok=True)
    generations = os.path.join(root, 'generations')
    if os.path.islink(generations):
        raise ContractError('generation directory may not be a symbolic link')
    os.makedirs(generations, exist_ok=True)
    stage = tempfile.mkdtemp(prefix='.build-', dir=generations)
    try:
        package_folder = os.path.join(stage, 'packages')
        os.mkdir(package_folder)
        records = []
        for index, source in enumerate(sources):
            verified = verified_package(source['package'], source.get('evidence'),
                                        vocabulary if source.get('evidence') else None)
            _reject_symlinks(verified['root'])
            relative = f'packages/{index:04d}-{verified["manifest"]["source"]["id"]}'
            target = os.path.join(stage, relative)
            shutil.copytree(verified['root'], target, symlinks=False)
            copied = verified_package(target, source.get('evidence'),
                                      vocabulary if source.get('evidence') else None)
            copied['relative_root'] = relative
            copied['status'] = source.get('status', 'active')
            if 'superseded_by' in source:
                copied['superseded_by'] = source['superseded_by']
            records.append(copied)
        history = evidence_history or {}
        library = make_library(records, vocabulary, review, history)
        scopes = _scopes(library, records, vocabulary, review, history)
        texts = _unit_texts(records, projections or {})
        shards, unit_to_shard = _shards(scopes, texts, stage, max_shard_chars)
        exported = _index(scopes, shards, unit_to_shard, library, vocabulary,
                          review, unsupported)
        _json(os.path.join(stage, 'library.json'), library)
        _json(os.path.join(stage, 'vocabulary.json'), vocabulary)
        _json(os.path.join(stage, 'review.json'), review)
        _json(os.path.join(stage, 'search-index.json'), exported)
        evidence_dir = os.path.join(stage, 'evidence')
        os.mkdir(evidence_dir)
        for record in records:
            if record['evidence'] is not None:
                name = record['evidence']['source_id'] + '.json'
                path = os.path.join(evidence_dir, name)
                if not os.path.exists(path):
                    _json(path, record['evidence'])
        if before_activate:
            before_activate(stage)
        generation_key = digest([library['revision'], exported['transform_revision'],
                                 max_shard_chars, projections or {}, unsupported])
        published = os.path.join(generations, generation_key)
        if os.path.exists(published):
            with open(os.path.join(published, 'library.json'), encoding='utf-8') as stream:
                if json.load(stream) != library:
                    raise ContractError('existing generation has mismatched library content')
            with open(os.path.join(published, 'search-index.json'), encoding='utf-8') as stream:
                if json.load(stream) != exported:
                    raise ContractError('existing generation has mismatched search index')
            shutil.rmtree(stage)
        else:
            os.replace(stage, published)
        pointer = {'generation': generation_key, 'review_revision': review['revision'],
                   'library_revision': library['revision']}
        handle, temp = tempfile.mkstemp(prefix='.current-', suffix='.json', dir=root)
        try:
            with os.fdopen(handle, 'w', encoding='utf-8') as stream:
                json.dump(pointer, stream, sort_keys=True)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, os.path.join(root, 'current.json'))
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        return {'generation': published, 'library_revision': library['revision'],
                'review_revision': review['revision'],
                'scopes': len(scopes), 'shards': len(shards),
                'packages': len(records)}
    except Exception:
        if os.path.isdir(stage):
            shutil.rmtree(stage)
        raise


def open_current(output_root, *, current_review_revision):
    """Fail closed if content survived a failed build after review changed."""
    root = os.path.abspath(output_root)
    with open(_local_file(root, 'current.json'), encoding='utf-8') as stream:
        pointer = json.load(stream)
    if pointer['review_revision'] != current_review_revision:
        raise ContractError('published search eligibility is stale for current review')
    generation = os.path.join(root, 'generations', pointer['generation'])
    with open(_local_file(generation, 'search-index.json'), encoding='utf-8') as stream:
        index = json.load(stream)
    if index['review_revision'] != current_review_revision or \
            index['library_revision'] != pointer['library_revision']:
        raise ContractError('published search index has mismatched revision')
    return generation, index


def search_export(generation, index, selection, query, *, mode='confirmed',
                  include_reference=False, browse_all=False, limit=100,
                  load_shard=None, cancelled=None, current_review_revision):
    """Load only shards in the selected scope, then rank, excerpt and limit."""
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ContractError('search limit must be 1–1,000')
    if index['review_revision'] != current_review_revision:
        raise ContractError('search request has stale review eligibility')
    scope = {'library_revision': index['library_revision'],
             'vocabulary_revision': index['vocabulary_revision'],
             'review_revision': index['review_revision'],
             'policy_version': index['policy_version'], 'selection': selection,
             'mode': mode, 'include_reference': include_reference,
             'browse_all': browse_all}
    fingerprint = scope_fingerprint(scope)
    entry = index['scopes'].get(fingerprint)
    if entry is None:
        raise ContractError('scope was not exported; rebuild for this selection')
    if cancelled and cancelled():
        raise SearchCancelled()
    terms = [word.casefold() for word in _WORD.findall(query)]
    if not terms or entry['no_content']:
        return {'results': [], 'loaded_shard_ids': [],
                'fingerprint': fingerprint, 'counts': entry['counts']}
    loaded = []
    documents = []
    eligible = {item['unit_id'] for item in entry['scope']['eligible']}
    for shard_id in entry['shard_ids']:
        if cancelled and cancelled():
            raise SearchCancelled()
        shard = index['shards'][shard_id]
        if not set(shard['unit_ids']).issubset(eligible):
            raise ContractError('search shard contains excluded units')
        path = _local_file(generation, shard['path'])
        if load_shard:
            content = load_shard(path)
        else:
            with open(path, encoding='utf-8') as stream:
                content = json.load(stream)
        if {item['unit_id'] for item in content} != set(shard['unit_ids']):
            raise ContractError('search shard contents differ from index')
        if digest(content)[:32] != shard_id:
            raise ContractError('search shard text or metadata changed')
        loaded.append(shard_id)
        documents.extend(content)
    if cancelled and cancelled():
        raise SearchCancelled()
    tokens = {item['unit_id']: [word.casefold() for word in _WORD.findall(item['text'])]
              for item in documents}
    df = {term: sum(term in set(words) for words in tokens.values()) for term in set(terms)}
    results = []
    for item in documents:
        words = tokens[item['unit_id']]
        if not all(term in words for term in terms):
            continue
        score = sum(words.count(term) * math.log((len(documents) + 1) /
                                                  (df[term] + 1)) for term in terms)
        lower = item['text'].casefold()
        first = min((lower.find(term) for term in terms if term in lower), default=0)
        snippet = item['text'][max(0, first - 60):first + 160]
        results.append({'unit_id': item['unit_id'], 'score': score,
                        'title': item['title'], 'snippet': snippet,
                        'citation': item['citation'],
                        'occurrence_ids': entry['unit_occurrences'][item['unit_id']]})
    results.sort(key=lambda item: (-item['score'], item['unit_id']))
    return {'results': results[:limit], 'loaded_shard_ids': loaded,
            'fingerprint': fingerprint, 'counts': entry['counts']}


class ScopeCache:
    """Small LRU for on-demand scope resolution; revisions are in the key."""

    def __init__(self, max_entries=16):
        if type(max_entries) is not int or not 1 <= max_entries <= 128:
            raise ValueError('scope cache size must be 1–128')
        self.max_entries = max_entries
        self._entries = OrderedDict()

    def get(self, library, vocabulary, review, selection, *, mode='confirmed',
            include_reference=False, browse_all=False, resolver):
        key = digest([library['revision'], vocabulary['revision'], review['revision'],
                      selection, mode, include_reference, browse_all])
        if key not in self._entries:
            self._entries[key] = resolver()
            if len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)
        self._entries.move_to_end(key)
        return self._entries[key]
