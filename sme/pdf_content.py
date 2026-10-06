"""Page-preserving Poppler extraction with explicit, hash-bound OCR input."""
import hashlib
import os
import re
import shutil
import subprocess

from .html_content import EVIDENCE, evidence
from .source import SourceError, _sha_file


def pdf_text_pages(path, expected_pages):
    executable = shutil.which('pdftotext')
    info = shutil.which('pdfinfo')
    if not executable or not info:
        raise SourceError('PDF normalization requires Poppler pdfinfo and pdftotext')
    env = dict(os.environ, LC_ALL='C')
    metadata = subprocess.run(
        [info, path], capture_output=True, text=True, errors='replace',
        timeout=120, check=False, env=env,
    )
    count = re.search(r'^Pages:\s+(\d+)\s*$', metadata.stdout, re.M)
    if metadata.returncode or not count or int(count[1]) != expected_pages:
        raise SourceError('PDF reader page count does not match the verified inventory')
    if re.search(r'^Encrypted:\s+yes', metadata.stdout, re.M):
        raise SourceError('encrypted PDF is unsupported')
    result = subprocess.run(
        [executable, '-layout', '-enc', 'UTF-8', path, '-'],
        capture_output=True, timeout=300, check=False, env=env,
    )
    if result.returncode:
        raise SourceError('PDF text extraction failed: ' +
                          result.stderr.decode('utf-8', errors='replace')[:500])
    try:
        pages = result.stdout.decode('utf-8').split('\f')
    except UnicodeError as ex:
        raise SourceError(f'PDF text encoding error: {ex}') from None
    if pages and not pages[-1].strip():
        pages.pop()
    if len(pages) != expected_pages:
        raise SourceError('PDF extracted page boundaries do not match the inventory')
    warnings = result.stderr.decode('utf-8', errors='replace').strip()
    return [page.strip() for page in pages], ([warnings[:2000]] if warnings else [])


def load_ocr_entry(entry, original, base_directory):
    required = {'source_path', 'source_sha256', 'derived_path', 'derived_sha256',
                'page_count', 'tool'}
    if not isinstance(entry, dict) or set(entry) != required:
        raise SourceError('OCR mapping has missing or unknown fields')
    if entry['source_path'] != original['path'] or entry['source_sha256'] != original['sha256']:
        raise SourceError('OCR mapping does not identify the verified original PDF')
    if type(entry['page_count']) is not int or entry['page_count'] != original['page_count']:
        raise SourceError('OCR mapping page count does not match the original PDF')
    tool = entry['tool']
    if not isinstance(tool, dict) or set(tool) != {'name', 'version'} or any(
            not isinstance(value, str) or not value.strip() for value in tool.values()):
        raise SourceError('OCR mapping must name the actual tool and version')
    if not isinstance(entry['derived_path'], str) or not entry['derived_path']:
        raise SourceError('OCR mapping derived_path must be a non-empty string')
    path = os.path.abspath(os.path.join(base_directory, entry['derived_path']))
    if os.path.islink(path) or not os.path.isfile(path):
        raise SourceError('OCR derived PDF must be a regular local file')
    if _sha_file(path) != entry['derived_sha256']:
        raise SourceError('OCR derived PDF hash does not match its mapping')
    pages, warnings = pdf_text_pages(path, original['page_count'])
    if _sha_file(path) != entry['derived_sha256']:
        raise SourceError('OCR derived PDF changed during extraction')
    return pages, warnings


def title_and_kind(first_page):
    lines = [line.strip() for line in first_page.splitlines() if line.strip()]
    title = ' / '.join(lines[:4])[:500] or 'Untitled PDF publication'
    sample = '\n'.join(lines[:30]).casefold()
    if re.search(r"\bowner(?:'s|s)?\s+(?:manual|guide)\b", sample):
        kind = 'owner'
    elif 'generic' in sample and ('code' in sample or 'obd' in sample):
        kind = 'reference'
    elif 'wiring diagram' in sample:
        kind = 'wiring'
    elif 'trouble code' in sample or 'diagnostic' in sample:
        kind = 'diagnostics'
    else:
        kind = 'unknown'
    return title, kind


def page_content(text, original, page_number, provenance='native', tool=None):
    path = original['path']
    metadata = {'provenance': 'none'}
    if text:
        metadata = {'provenance': provenance,
                    'sha256': hashlib.sha256(text.encode('utf-8')).hexdigest()}
        if provenance == 'ocr':
            metadata.update(derived_from_sha256=original['sha256'], tool=tool)
    # Raw page wording is evidence, never a parsed claim that a vehicle fits.
    applicability = [evidence(line.strip(), path, selector=f'page:{page_number}:line:{index}')
                     for index, line in enumerate(text.splitlines(), 1)
                     if EVIDENCE.search(line) and line.strip()]
    return metadata, applicability
