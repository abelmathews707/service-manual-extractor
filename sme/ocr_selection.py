"""Hash-bound PDF page triage before any toolkit OCR is requested."""

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile

from .contract import load_manifest
from .normalize import CONTENT_NAME, _local_file, validate_content
from .source import INVENTORY_NAME, MANIFEST_NAME, SourceError, _sha_file, validate_inventory

OCR_PLAN_CONTRACT = 'service-manual-ocr-selection/v1'


def _image_pages(path):
    tool = shutil.which('pdfimages')
    if not tool:
        raise SourceError('PDF page triage requires Poppler pdfimages')
    result = subprocess.run([tool, '-list', path], capture_output=True, text=True,
                            timeout=120, check=False)
    if result.returncode:
        raise SourceError('pdfimages could not inspect original PDF: ' +
                          result.stderr.strip()[:300])
    pages = set()
    for line in result.stdout.splitlines()[2:]:
        fields = line.split()
        if fields and fields[0].isdigit():
            pages.add(int(fields[0]))
    return pages


def plan_ocr(package, low_text_chars=80):
    """Suggest only image-only pages for automatic OCR; flag mixed pages.

    A short native footer is not evidence that the diagram is searchable.
    Low-text pages with images require human selection before OCR; this plan
    does not invoke OCR or replace any original PDF.
    """
    if type(low_text_chars) is not int or not 1 <= low_text_chars <= 1000:
        raise SourceError('low-text threshold must be 1–1000 characters')
    root = os.path.abspath(package)
    if os.path.islink(package) or not os.path.isdir(root):
        raise SourceError('OCR input must be a normalized regular package')
    manifest = load_manifest(_local_file(root, MANIFEST_NAME))
    with open(_local_file(root, CONTENT_NAME), encoding='utf-8') as stream:
        content = validate_content(json.load(stream), manifest)
    with open(_local_file(root, INVENTORY_NAME), encoding='utf-8') as stream:
        inventory = validate_inventory(json.load(stream))
    if inventory['source_id'] != manifest['source']['id']:
        raise SourceError('OCR source inventory does not match manifest')
    members = {member['path']: member for member in inventory['members']}
    grouped = {}
    for record in content['documents']:
        if record['role'] == 'pdf_page':
            grouped.setdefault(record['original_path'], []).append(record)
    publications = []
    for path, pages in sorted(grouped.items()):
        member = members.get(path)
        if not member or member.get('page_count') != len(pages):
            raise SourceError(f'PDF pages do not match the verified inventory: {path}')
        local = _local_file(root, path)
        if _sha_file(local) != member['sha256']:
            raise SourceError(f'original PDF changed after verification: {path}')
        image_pages = _image_pages(local)
        entries = []
        for record in sorted(pages, key=lambda item: item['page']):
            number = record['page']
            text = record['text'].strip()
            chars = len(re.sub(r'\s+', '', text))
            image = number in image_pages
            if record.get('ocr'):
                state = 'already_ocr'
            elif not text and image:
                state = 'auto_image_only'
            elif not text:
                state = 'review_empty_without_image'
            elif chars < low_text_chars and image:
                state = 'review_low_text_with_image'
            elif chars < low_text_chars:
                state = 'review_low_text'
            else:
                state = 'native_readable'
            entries.append({'page': number, 'state': state, 'nonspace_chars': chars,
                            'has_raster_image': image})
        publications.append({'source_path': path, 'source_sha256': member['sha256'],
                             'page_count': member['page_count'], 'pages': entries,
                             'auto_pages': [item['page'] for item in entries
                                            if item['state'] == 'auto_image_only'],
                             'review_pages': [item['page'] for item in entries
                                              if item['state'].startswith('review_')]})
    return {'contract': OCR_PLAN_CONTRACT, 'source_id': manifest['source']['id'],
            'low_text_chars': low_text_chars, 'publications': publications}


def run_toolkit_ocr(package, source_path, toolkit_root, cache_root, approved_pages=()):
    """OCR only image-only pages plus explicitly approved low-text pages.

    Uses the independently versioned toolkit's page extraction/merge helpers.
    Cache keys include original bytes, exact page selection, toolkit script
    bytes and OCR runtime version. No existing cache or source is overwritten.
    """
    plan = plan_ocr(package)
    item = next((entry for entry in plan['publications']
                 if entry['source_path'] == source_path), None)
    if item is None:
        raise SourceError('PDF is not a cited page source in this package')
    approved = set(approved_pages)
    if any(type(page) is not int for page in approved) or not approved.issubset(
            item['review_pages']):
        raise SourceError('approved OCR pages must come from the review-page list')
    pages = sorted(set(item['auto_pages']) | approved)
    if not pages:
        raise SourceError('no pages selected for OCR')
    original = _local_file(os.path.abspath(package), source_path)
    toolkit = os.path.abspath(toolkit_root)
    script = os.path.join(toolkit, 'scripts', 'ocr.py')
    if (os.path.islink(toolkit_root) or
            os.path.islink(os.path.join(toolkit, 'scripts')) or
            os.path.islink(script) or not os.path.isfile(script)):
        raise SourceError('toolkit must have a regular scripts/ocr.py')
    ocrmypdf = shutil.which('ocrmypdf')
    if not ocrmypdf:
        raise SourceError('ocrmypdf is not installed')
    try:
        version = subprocess.run([ocrmypdf, '--version'], capture_output=True,
                                 text=True, timeout=30, check=True).stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        raise SourceError(f'cannot identify ocrmypdf runtime: {error}') from error
    script_sha = _sha_file(script)
    key = hashlib.sha256(json.dumps([item['source_sha256'], pages, script_sha, version],
                                    separators=(',', ':')).encode()).hexdigest()
    cache = os.path.abspath(cache_root)
    if not os.path.isdir(cache) or os.path.islink(cache):
        raise SourceError('OCR cache root must be an existing regular directory')
    destination = os.path.join(cache, key)
    if os.path.isdir(destination):
        with open(os.path.join(destination, 'ocr-map.json'), encoding='utf-8') as stream:
            mapping = json.load(stream)
        entry = mapping['entries'][0]
        if (entry['source_path'] != source_path or
                entry['source_sha256'] != item['source_sha256'] or
                entry['page_count'] != item['page_count'] or
                _sha_file(os.path.join(destination, entry['derived_path'])) !=
                entry['derived_sha256']):
            raise SourceError('cached OCR result does not match source and derived hashes')
        return {'output': destination, 'cached': True, 'pages': pages,
                'ocr_map': os.path.join(destination, 'ocr-map.json')}
    stage = tempfile.mkdtemp(prefix='.sme-ocr-', dir=cache)
    try:
        spec = importlib.util.spec_from_file_location('sme_external_toolkit_ocr', script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        sub_pdf = os.path.join(stage, 'selected-pages.pdf')
        ocr_pdf = os.path.join(stage, 'selected-pages.ocr.pdf')
        derived = os.path.join(stage, 'manual-searchable.pdf')
        module.extract_sub_pdf(module.Path(original), [page - 1 for page in pages],
                               module.Path(sub_pdf))
        # The seller's scanned PDFs need PDF/A output for qpdf-clean results;
        # the toolkit still owns page extraction and exact merge-back mapping.
        try:
            subprocess.run([ocrmypdf, '--output-type', 'pdfa', sub_pdf, ocr_pdf],
                           check=True, timeout=3600, capture_output=True)
        except subprocess.CalledProcessError as error:
            detail = error.stderr.decode('utf-8', errors='replace')[-500:]
            raise SourceError(f'toolkit OCR failed: {detail}') from error
        except subprocess.TimeoutExpired as error:
            raise SourceError('toolkit OCR timed out') from error
        module.merge_back(module.Path(original), module.Path(ocr_pdf),
                          [page - 1 for page in pages], module.Path(derived))
        from .pdf_content import pdf_text_pages
        texts, warnings = pdf_text_pages(derived, item['page_count'])
        mapping = {'contract': 'service-manual-ocr-map/v1', 'entries': [{
            'source_path': source_path, 'source_sha256': item['source_sha256'],
            'derived_path': 'manual-searchable.pdf', 'derived_sha256': _sha_file(derived),
            'page_count': item['page_count'], 'tool': {
                'name': 'workshop-manual-toolkit/ocrmypdf',
                'version': f'{version}; script-sha256:{script_sha}'}}]}
        with open(os.path.join(stage, 'ocr-map.json'), 'w', encoding='utf-8') as stream:
            json.dump(mapping, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        report = {'source_path': source_path, 'selected_pages': pages,
                  'pages_without_ocr_text': [page for page in pages if not texts[page - 1]],
                  'warnings': warnings}
        with open(os.path.join(stage, 'ocr-report.json'), 'w', encoding='utf-8') as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        if _sha_file(original) != item['source_sha256']:
            raise SourceError('original PDF changed during toolkit OCR')
        os.replace(stage, destination)
        return {'output': destination, 'cached': False, 'pages': pages,
                'ocr_map': os.path.join(destination, 'ocr-map.json'),
                'pages_without_ocr_text': report['pages_without_ocr_text']}
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
