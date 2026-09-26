"""Conservative vocabulary binding for source-quoted vehicle statements.

This is evidence interpretation, not a final fitment decision. Ambiguous
names, broad edition labels and unrecognized engines remain ``unknown``.
"""

import re


def unknown_alternative():
    return {field: {'state': 'unknown'} for field in ('make', 'model', 'year', 'engine')} | {
        'qualifiers': {}}


def _literal_pattern(value):
    words = re.split(r'\s+', value.strip())
    body = r'\s+'.join(re.escape(word) for word in words)
    return re.compile(r'(?<![\w])' + body + r'(?![\w])', re.I)


def _mentions(text, entities, aliases=(), year=None):
    matches = []
    for item in entities:
        for match in _literal_pattern(item['name']).finditer(text):
            matches.append((match.start(), match.end(), item['id'], len(match.group())))
    for alias in aliases:
        if ('year_start' in alias and
                (year is None or not alias['year_start'] <= year <= alias['year_end'])):
            continue
        for match in _literal_pattern(alias['literal']).finditer(text):
            matches.append((match.start(), match.end(), alias['target_id'],
                            len(match.group())))
    # A source naming Silverado 1500 does not separately assert Silverado.
    retained = []
    for start, end, identifier, length in sorted(matches, key=lambda x: -x[3]):
        if not any(start < other_end and end > other_start
                   for other_start, other_end, *_ in retained):
            retained.append((start, end, identifier, length))
    return {item[2] for item in retained}


def _year(text, bounded):
    if not bounded and not re.search(r'\bmodel\s+years?\b', text, re.I):
        return {'state': 'unknown'}
    range_match = re.search(r'\b((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2})\b', text)
    if range_match:
        start, end = map(int, range_match.groups())
        if 1886 <= start <= end <= 2100:
            return {'state': 'range', 'start': start, 'end': end}
    years = {int(value) for value in re.findall(r'\b(?:19|20)\d{2}\b', text)}
    return {'state': 'exact', 'value': years.pop()} if len(years) == 1 else {
        'state': 'unknown'}


def _engine(text, vocabulary, model_id, year):
    engines = vocabulary['engines']
    aliases = [alias for alias in vocabulary['aliases']
               if any(engine['id'] == alias['target_id'] for engine in engines)]
    year_value = year['value'] if year['state'] == 'exact' else None
    ids = _mentions(text, engines, aliases, year_value)
    if len(ids) == 1:
        return {'state': 'exact', 'value': next(iter(ids))}, True
    if len(ids) > 1:
        return {'state': 'unknown'}, False
    # A displacement alone is not an engine ID. It becomes one only when the
    # named model/year have exactly one known valid engine at that displacement.
    displacement = {float(number) for number in
                    re.findall(r'\b(\d{1,2}(?:\.\d)?)\s*(?:L\b|liter\b|litre\b)',
                               text, re.I)}
    if len(displacement) != 1 or not model_id or year['state'] != 'exact':
        return {'state': 'unknown'}, not bool(displacement)
    candidate = {config['engine_id'] for config in vocabulary['configurations']
                 if config['model_id'] == model_id and
                 config['model_year'] == year['value'] and
                 any(engine['id'] == config['engine_id'] and
                     engine['displacement_l'] in displacement for engine in engines)}
    if len(candidate) == 1:
        return {'state': 'exact', 'value': next(iter(candidate))}, True
    return {'state': 'unknown'}, False


def interpret_statement(statement, vocabulary, structured=None):
    """Return correlated alternatives and whether every named term was bound.

    ``structured`` is a Ford EPL vehicle dict with distinct year/name/engine
    fields. Unstructured text is never split into independent make/model/year
    arrays. Multiple model names become separate alternatives, and an engine
    is retained only if each complete tuple is valid in the vocabulary.
    """
    models = vocabulary['models']
    makes = vocabulary['makes']
    model_ids = {item['id'] for item in models}
    make_ids = {item['id'] for item in makes}
    aliases = vocabulary['aliases']
    model_text = structured.get('name', '') if structured else statement
    years_in_text = {int(value) for value in re.findall(r'\b(?:19|20)\d{2}\b',
                                                       structured.get('year', '')
                                                       if structured else statement)}
    alias_year = next(iter(years_in_text)) if len(years_in_text) == 1 else None
    model_mentions = _mentions(model_text, models,
                               [alias for alias in aliases
                                if alias['target_id'] in model_ids], alias_year)
    make_mentions = _mentions(model_text, makes,
                              [alias for alias in aliases
                               if alias['target_id'] in make_ids], alias_year)
    if structured:
        raw_year = structured.get('year', '')
        year = ({'state': 'exact', 'value': int(raw_year)}
                if re.fullmatch(r'(?:19|20)\d{2}', raw_year) else {'state': 'unknown'})
        engine_text = structured.get('engine', '')
    else:
        year = _year(statement, bool(model_mentions or make_mentions))
        engine_text = statement
    alternatives = []
    resolved = True
    if len(make_mentions) > 1 and not model_mentions:
        resolved = False
    candidates = sorted(model_mentions) if model_mentions else [None]
    for model_id in candidates:
        alt = unknown_alternative()
        alt['year'] = year.copy()
        if model_id:
            model = next(item for item in models if item['id'] == model_id)
            owner = model['make_id']
            if make_mentions and owner not in make_mentions:
                resolved = False
                continue
            alt['model'] = {'state': 'exact', 'value': model_id}
            alt['make'] = {'state': 'exact', 'value': owner}
        elif len(make_mentions) == 1:
            alt['make'] = {'state': 'exact', 'value': next(iter(make_mentions))}
        engine, unambiguous = _engine(engine_text, vocabulary, model_id, year)
        alt['engine'] = engine
        resolved &= unambiguous
        if (alt['make']['state'] == alt['model']['state'] == alt['year']['state'] ==
                alt['engine']['state'] == 'exact'):
            valid = any(config['make_id'] == alt['make']['value'] and
                        config['model_id'] == alt['model']['value'] and
                        config['model_year'] == alt['year']['value'] and
                        config['engine_id'] == alt['engine']['value']
                        for config in vocabulary['configurations'])
            if not valid:
                alt['engine'] = {'state': 'unknown'}
                resolved = False
        if alt not in alternatives:
            alternatives.append(alt)
    if not alternatives:
        alternatives = [unknown_alternative()]
        resolved = False
    if structured and structured.get('name') and not model_mentions:
        resolved = False
    if structured and structured.get('engine') and alternatives[0]['engine']['state'] == 'unknown':
        resolved = False
    if not structured and len(model_mentions) > 1:
        resolved = False
    return alternatives, resolved
