"""Ford POD archives to the neutral, cited manual package.

This is an adapter over ``fsd``. Other ``sme`` readers never inspect EPL files.
An import selects exact source-relative archives, not a display code or role.
"""

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter

from fsd.build import parse_pced, parse_wiring, parse_wsm_section, parse_wsm_toc
from fsd.disc import book_of, books_in_dir, open_source
from fsd.extract import extract, safe_name

from . import __version__
from .contract import (
    MANIFEST_CONTRACT,
    asset_id,
    canonical_path,
    publication_id,
    source_id,
    validate_manifest,
)
from .html_content import parse_html, safe_svg
from .normalize import (
    CONTENT_CONTRACT,
    CONTENT_NAME,
    DERIVED,
    _aliases,
    _base_document,
    _content_record,
    _prepare_figures,
    _resolve_links,
    digest,
    validate_content,
)
from .pdf_content import pdf_text_pages
from .source import (
    INVENTORY_CONTRACT,
    INVENTORY_NAME,
    MANIFEST_NAME,
    Member,
    SourceError,
    _content_digest,
    _media_type,
    _pdf_page_count,
    validate_inventory,
)

BRIDGE_NAME = ".sme-ford-identity.json"
CAPABILITIES_NAME = ".sme-ford-capabilities.json"
_KIND = {"SERVICE": "workshop", "EVTM": "wiring", "PCED": "diagnostics"}


def _hash_stream(stream):
    sha = hashlib.sha256()
    while block := stream.read(1024 * 1024):
        sha.update(block)
    return sha.hexdigest()


def _json(path, value):
    with open(path, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def _archive_info(ref):
    if os.path.islink(ref.path):
        raise SourceError(f"{ref.identity}: symbolic-link archive is unsupported")
    with ref.open() as archive:
        names = [safe_name(entry.name) for entry in archive]
        folded = [name.casefold() for name in names]
        if len(folded) != len(set(folded)):
            raise SourceError(
                f"{ref.identity}: archive entries collide after safe filename mapping"
            )
        if any(not name or name in {".", ".."} for name in names):
            raise SourceError(f"{ref.identity}: archive has an unusable filename")
        book = book_of(archive)
        version = archive.version
    with ref._open() as stream:
        sha = _hash_stream(stream)
    return {
        "identity": ref.identity,
        "code": ref.code,
        "output_dir": ref.output_dir,
        "sha256": sha,
        "size": ref.size,
        "version": version,
        "entries": len(names),
        "book": book,
    }


def probe_ford(path):
    """List exact archive identities and declared books without extracting."""
    with open_source(path) as source:
        archives = []
        for ref in source.archives():
            with ref.open() as archive:
                book = book_of(archive)
                archives.append(
                    {
                        "identity": ref.identity,
                        "code": ref.code,
                        "output_dir": ref.output_dir,
                        "version": archive.version,
                        "entries": len(archive),
                        "type": book.type if book else "",
                        "title": book.title if book else "",
                    }
                )
        return {"label": source.label, "container": source.kind, "archives": archives}


def _selected(source, identities):
    refs = source.archives()
    requested = [canonical_path(item).casefold() for item in identities]
    if not requested or len(requested) != len(set(requested)):
        raise SourceError("select one or more distinct exact archive identities")
    available = {ref.identity: ref for ref in refs}
    unknown = set(requested) - set(available)
    if unknown:
        raise SourceError("unknown Ford archive identity: " + ", ".join(sorted(unknown)))
    selected = [available[item] for item in requested]
    counts = Counter(ref.code.casefold() for ref in refs)
    return selected, counts


def _member(path, local):
    if os.path.islink(local) or not stat.S_ISREG(os.stat(local, follow_symlinks=False).st_mode):
        raise SourceError(f"not a regular extracted Ford file: {path}")
    with open(local, "rb") as stream:
        sha = _hash_stream(stream)
    value = {
        "path": path,
        "size": os.path.getsize(local),
        "sha256": sha,
        "media_type": _media_type(path),
    }
    if path.casefold().endswith(".pdf"):
        try:
            count, method = _pdf_page_count(local)
            value.update(page_count=count, page_count_method=method)
        except (OSError, SourceError, TimeoutError) as error:
            value["pdf_error"] = str(error)
    return value


def _prefix(ref):
    return "originals/" + ref.identity.rsplit(".", 1)[0]


def _publication_applicability(book, epl_path):
    if not epl_path:
        return []
    result = []
    for vehicle in book.vehicles:
        statement = " ".join(
            part
            for part in (vehicle.get("year"), vehicle.get("name"), vehicle.get("engine"))
            if part
        )
        if statement and statement not in {item["statement"] for item in result}:
            result.append({"level": "publication", "statement": statement, "source_path": epl_path})
    return result


def _route_labels(book, directory):
    """Use Ford's own TOC/section parsers, preserving all nested routes."""
    routes = {}
    prefix = book.prefix

    def add(slug, labels):
        routes.setdefault(slug.casefold(), []).append(labels)

    if book.type.upper() == "SERVICE":
        tree, extras = parse_wsm_toc(directory, prefix)
        for group in tree:
            for section_group in group["groups"]:
                for section in section_group["sections"]:
                    base = [group["title"], section_group["title"], section["title"]]
                    add(section["id"], base)
                    for page in parse_wsm_section(directory, prefix, section["id"]):
                        add(page["id"], base + [page["title"]])
        for extra in extras:
            add(extra["id"], [extra["title"]])
    elif book.type.upper() == "PCED":
        for section in parse_pced(directory, prefix):
            for page in section["pages"]:
                add(page["id"], [section["title"], page["title"]])
    return routes


def _html_files(pub, directory, base, staging, members, records, failures):
    paths = sorted(
        path
        for path in members
        if path.startswith(base + "/") and path.casefold().endswith((".htm", ".html"))
    )
    folded = {path.casefold(): path for path in members if path.startswith(base + "/")}
    for path in paths:
        local = os.path.join(directory, path.rsplit("/", 1)[-1])
        try:
            with open(local, "rb") as stream:
                parsed = parse_html(stream.read(32 * 1024 * 1024 + 1), path, ford_legacy=True)
            text = parsed.pop("text")
            role = parsed.pop("role")
            name = path.rsplit("/", 1)[-1].casefold()
            if re.search(r"(left|right|main|s\d+[lr]|g\d+l|s[\w]+l)\.htm$", name):
                role, text = "navigation", ""
            info = (
                {"provenance": "native", "sha256": digest(text.encode())}
                if text
                else {"provenance": "none"}
            )
            document = _base_document(
                pub,
                path,
                members[path],
                parsed.pop("title"),
                [{"kind": "path", "path": path}],
                info,
            )
            document["applicability"] = parsed.pop("applicability")
            document["breadcrumbs"] = parsed.pop("breadcrumbs")
            content = _content_record(document, pub, path, text, role)
            content.update(parsed)
            content["search_eligible"] = bool(text) and role == "procedure"
            for figure in content["figures"]:
                target = figure.get("path")
                if target:
                    figure["path"] = folded.get(target.casefold(), target)
            _prepare_ford_figures(document, content, members, staging)
            pub["documents"].append(document)
            records.append(content)
        except (OSError, SourceError, ValueError, RecursionError) as error:
            failures.append({"code": "ford_html_failed", "path": path, "message": str(error)})


def _fix_local_targets(records, members):
    """Ford filenames are case-insensitive; retain actual cited file spelling."""
    folded = {path.casefold(): path for path in members}
    for record in records:
        for item in record["references"] + record["figures"]:
            path = item.get("path")
            if path and path.casefold() in folded:
                item["path"] = folded[path.casefold()]


def _prepare_ford_figures(document, content, members, staging):
    _prepare_figures(document, content, members, staging)
    for figure in content["figures"]:
        path = figure.get("path")
        if not path or figure["status"] != "unsupported" or not path.casefold().endswith(".svg"):
            continue
        try:
            with open(os.path.join(staging, path), "rb") as stream:
                original = stream.read(16 * 1024 * 1024 + 1)
            if not re.search(rb"<svg\b[^>]*\bxmlns\s*=", original, re.I):
                original = re.sub(
                    rb"<svg\b",
                    b'<svg xmlns="http://www.w3.org/2000/svg"',
                    original,
                    count=1,
                    flags=re.I,
                )
            if b"<!DOCTYPE" in original.upper() or b"<!ENTITY" in original.upper():
                raise SourceError("SVG DTD/entities are unsupported")
            tree = ET.fromstring(original)
            # Ford places non-rendering vehicle XML inside <desc>; retain the
            # original file, but omit that metadata from the display derivative.
            for child in list(tree):
                if child.tag == "{http://www.w3.org/2000/svg}desc":
                    tree.remove(child)
            for node in tree.iter():
                node.attrib.pop("enable-background", None)
                if node.tag == "{http://www.w3.org/2000/svg}image":
                    embedded = node.attrib.pop("{http://www.w3.org/1999/xlink}href", None)
                    if embedded and embedded.startswith("data:;base64,"):
                        node.set("href", "data:image/png;base64," + embedded[13:])
                    elif embedded:
                        node.set("href", embedded)
            used_ids = set()
            for node in tree.iter():
                for value in node.attrib.values():
                    used_ids.update(re.findall(r"url\(#([A-Za-z_][\w.-]*)\)", value))
            seen_ids = set()
            for node in tree.iter():
                identifier = node.attrib.get("id")
                if identifier and identifier not in used_ids:
                    del node.attrib["id"]
                elif identifier in seen_ids:
                    raise SourceError("duplicate referenced SVG ID")
                elif identifier:
                    seen_ids.add(identifier)
            sanitized = safe_svg(ET.tostring(tree, encoding="utf-8"))
            safe_path = f"{DERIVED}/{digest(sanitized)}.svg"
            os.makedirs(os.path.join(staging, DERIVED), exist_ok=True)
            with open(os.path.join(staging, safe_path), "wb") as stream:
                stream.write(sanitized)
            figure.update(
                status="safe_svg",
                reason=None,
                render_path=safe_path,
                render_sha256=digest(sanitized),
            )
        except (OSError, SourceError, ET.ParseError) as error:
            figure.update(status="unsupported", reason=str(error))


def _navigation(records, pub, book, directory):
    routes = _route_labels(book, directory)
    for content in records:
        if content["publication_id"] != pub["id"]:
            continue
        slug = content["original_path"].rsplit("/", 1)[-1].rsplit(".", 1)[0].casefold()
        if slug in routes:
            content["navigation_routes"] = [
                {"source_path": pub["source_path"], "labels": labels, "fragment": ""}
                for labels in routes[slug]
            ]


def _wiring_files(pub, directory, base, staging, members, records, failures):
    try:
        cells, _indexes = parse_wiring(directory, pub["_prefix"], warn=lambda *_: None)
    except (OSError, ValueError) as error:
        failures.append(
            {"code": "ford_wiring_xml_failed", "path": pub["source_path"], "message": str(error)}
        )
        return 0
    folded = {
        path.rsplit("/", 1)[-1].casefold(): path for path in members if path.startswith(base + "/")
    }
    created = 0
    for cell in cells:
        for page in cell["pages"]:
            meta = folded.get((page["id"] + ".xml").casefold())
            index = folded.get((pub["_prefix"] + "CEL_" + cell["cell"] + ".XML").casefold())
            origin = meta or index
            if not origin:
                continue
            title = page["title"] or page["id"]
            text = "\n".join(
                item
                for item in (
                    cell["title"],
                    title,
                    page["type"],
                    *(entry.get("name", "") for entry in page["conns"]),
                    *(entry.get("name", "") for entry in page["grounds"]),
                    *(entry.get("name", "") for entry in page["splices"]),
                )
                if item
            )
            logical = f"{DERIVED}/ford-pages/{pub['id']}/{page['id']}"
            info = (
                {"provenance": "native", "sha256": digest(text.encode())}
                if text
                else {"provenance": "none"}
            )
            document = _base_document(
                pub,
                logical,
                members[origin],
                title,
                [{"kind": "path", "path": origin, "fragment": "page:" + page["id"]}],
                info,
            )
            document["breadcrumbs"] = [cell["title"] or "Cell " + cell["cell"]]
            content = _content_record(document, pub, origin, text, "procedure")
            content["structure"] = [{"tag": "h2", "attrs": {}, "children": [title]}]
            if text:
                content["structure"].append({"tag": "p", "attrs": {}, "children": [text]})
            svg = folded.get((page["svg"] or "").casefold()) if page["svg"] else None
            if svg:
                document['citations'].append({'kind': 'path', 'path': svg})
                content["figures"].append(
                    {"path": svg, "caption": title, "status": "pending", "reason": None}
                )
                content["structure"].append({"tag": "img", "attrs": {"figure": 0}, "children": []})
            _prepare_ford_figures(document, content, members, staging)
            pub["documents"].append(document)
            records.append(content)
            created += 1
    return created


def _pdf_files(pub, base, members, staging, records, failures):
    count = 0
    for path in sorted(members):
        if not path.startswith(base + "/") or not path.casefold().endswith(".pdf"):
            continue
        member = members[path]
        if "page_count" not in member:
            failures.append(
                {
                    "code": "ford_pdf_unsupported",
                    "path": path,
                    "message": member.get("pdf_error", "PDF page count unavailable"),
                }
            )
            continue
        try:
            texts, warnings = pdf_text_pages(os.path.join(staging, path), member["page_count"])
        except (OSError, SourceError) as error:
            failures.append({"code": "ford_pdf_failed", "path": path, "message": str(error)})
            continue
        for number, text in enumerate(texts, 1):
            logical = f"{DERIVED}/pdf-pages/{pub['id']}/{path.rsplit('/', 1)[-1]}/{number:06d}"
            info = (
                {"provenance": "native", "sha256": digest(text.encode())}
                if text
                else {"provenance": "none"}
            )
            doc = _base_document(
                pub,
                logical,
                member,
                f"{path.rsplit('/', 1)[-1]} — page {number}",
                [{"kind": "page", "path": path, "page": number}],
                info,
            )
            doc["assets"] = [
                {
                    "id": asset_id(doc["id"], path),
                    "path": path,
                    "sha256": member["sha256"],
                    "media_type": "application/pdf",
                    "caption": f"Original PDF page {number}",
                }
            ]
            content = _content_record(doc, pub, path, text, "pdf_page", page=number)
            content["figures"] = [
                {
                    "path": path,
                    "page": number,
                    "status": "original_pdf_page",
                    "caption": f"Original PDF page {number}",
                    "sha256": member["sha256"],
                }
            ]
            content["warnings"] = warnings if number == 1 else []
            if not text:
                content["warnings"].append("no_searchable_text: original PDF remains available")
            pub["documents"].append(doc)
            records.append(content)
            count += 1
    return count


def _bridge(manifest, infos, counts, records):
    refs = []
    routes = {}
    by_id = {record['id']: record for record in records}
    for pub, info in zip(manifest["publications"], infos):
        book = info["book"]
        key = (
            f"{book.code}::{info['identity']}" if counts[info["code"].casefold()] > 1 else book.code
        )
        for doc in pub["documents"]:
            path = doc["citations"][0]["path"]
            name = path.rsplit("/", 1)[-1]
            role = book.role or "unknown"
            old_route = (
                f"#/{role}/{name.rsplit('.', 1)[0].lower()}"
                if doc["citations"][0]["kind"] == "path"
                else None
            )
            refs.append(
                {
                    "archive_identity": info["identity"],
                    "legacy_book_key": key,
                    "legacy_relative_path": name,
                    "legacy_route": old_route,
                    "legacy_page": doc["citations"][0].get("page"),
                    "legacy_fragment": doc["citations"][0].get("fragment"),
                    "anchors": by_id[doc["id"]]["anchors"],
                    "publication_id": pub["id"],
                    "document_id": doc["id"],
                }
            )
            if old_route:
                routes.setdefault(old_route, set()).add(doc["id"])
    return {
        "contract": "service-manual-ford-identity/v1",
        "source_id": manifest["source"]["id"],
        "references": refs,
        "ambiguous_unscoped_routes": sorted(route for route, ids in routes.items() if len(ids) > 1),
    }


def resolve_legacy_citation(bridge, legacy_book_key, locator, page=None):
    """Resolve one old Ford book/file or book/hash-route citation exactly.

    A bare route shared by two books is never assigned arbitrarily. PDF page
    citations must include their page number when a PDF has multiple pages.
    """
    if bridge.get("contract") != "service-manual-ford-identity/v1":
        raise SourceError("unsupported Ford identity bridge")
    fragment = None
    if not locator.startswith('#/') and '#' in locator:
        locator, fragment = locator.split('#', 1)
    matches = [
        item
        for item in bridge["references"]
        if item["legacy_book_key"].casefold() == legacy_book_key.casefold()
        and (
            item["legacy_relative_path"].casefold() == locator.casefold()
            or item["legacy_route"] == locator
        )
        and (page is None or item["legacy_page"] == page)
        and (fragment is None or fragment in item['anchors']
             or fragment == item['legacy_fragment'])
    ]
    ids = {item["document_id"] for item in matches}
    if len(ids) != 1:
        raise SourceError(
            "legacy Ford citation is absent or ambiguous; "
            "supply the exact archive-scoped book key and PDF page"
        )
    item = matches[0]
    return {"publication_id": item["publication_id"],
            "document_id": item["document_id"], "fragment": fragment}


def _resolve_ford_pdf_links(manifest, records):
    """Ford HTML points at printable PDFs; open their first cited page."""
    first_pages = {
        record["original_path"]: record["id"]
        for record in records
        if record["role"] == "pdf_page" and record["page"] == 1
    }
    documents = {doc["id"]: doc for pub in manifest["publications"] for doc in pub["documents"]}
    for content in records:
        if content["role"] == "pdf_page":
            continue
        document = documents[content["id"]]
        for link in content["references"]:
            target = first_pages.get(link.get("path"))
            if link["status"] != "unsupported" or not target:
                continue
            link.update(status="resolved", reason=None, target_id=target)
            for reference in document["references"]:
                if reference["path"] == link["path"] and reference["status"] == "missing":
                    reference.update(status="resolved", target_id=target)
                    reference.pop("reason", None)


def import_ford(path, destination, archive_identities):
    """Build a verified neutral package from exact Ford archive occurrences.

    Selected archives must be one POD generation per package; mixed-generation
    discs can be imported in two calls and combined at the library layer.
    """
    destination = os.path.abspath(destination)
    if os.path.lexists(destination):
        raise SourceError(f"destination already exists: {destination}")
    parent = os.path.dirname(destination)
    if not os.path.isdir(parent) or os.path.islink(parent):
        raise SourceError(f"destination parent must be a regular directory: {parent}")
    source_abs = os.path.abspath(path)
    if os.path.islink(path):
        raise SourceError("Ford source may not be a symbolic link")
    if os.path.isdir(source_abs) and os.path.commonpath((source_abs, destination)) == source_abs:
        raise SourceError("destination may not be inside the Ford source")
    with open_source(path) as source:
        refs, counts = _selected(source, archive_identities)
        infos = [_archive_info(ref) for ref in refs]
        versions = {info["version"] for info in infos}
        if len(versions) != 1:
            raise SourceError(
                "selected archives mix Ford POD v1/v2; import each generation separately"
            )
        source_hash = digest(
            json.dumps([(i["identity"], i["sha256"]) for i in infos], sort_keys=True).encode()
        )
        format_ = f"ford_tsp_disc_v{versions.pop()}"
        container = "directory" if source.kind == "directory" else "disc_image"
        identity = source.label + ":" + ",".join(i["identity"] for i in infos)
        src_id = source_id(format_, container, identity, source_hash)
        staging = tempfile.mkdtemp(prefix=".sme-ford-", dir=parent)
        try:
            raw_root = os.path.join(staging, ".raw-ford")
            result = extract(
                source,
                raw_root,
                archives=[i["identity"] for i in infos],
                validate=True,
                log=lambda *_: None,
            )
            if result.failed:
                raise SourceError(
                    f"Ford extraction failed for {len(result.failed)} entries: {result.failed[:3]}"
                )
            for ref, info in zip(refs, infos):
                with ref._open() as stream:
                    if _hash_stream(stream) != info["sha256"]:
                        raise SourceError(f"{ref.identity}: archive changed during extraction")
            books = {book.dir.rsplit(os.sep, 1)[-1]: book for book in books_in_dir(raw_root)}
            source_record = {
                "id": src_id,
                "format": format_,
                "container": container,
                "identity": identity,
                "sha256": source_hash,
                "status": "complete",
                "failures": [],
                "extractor": {
                    "name": "service-manual-extractor",
                    "version": __version__,
                    "revision": "ford-adapter-v1",
                },
            }
            manifest = {"contract": MANIFEST_CONTRACT, "source": source_record, "publications": []}
            members = {}
            selections = []
            records = []
            failures = []
            capabilities = []
            for ref, info in zip(refs, infos):
                directory = os.path.join(raw_root, ref.output_dir)
                book = books[ref.output_dir]
                info["book"] = book
                base = _prefix(ref)
                selected_paths = []
                for name in sorted(os.listdir(directory)):
                    local = os.path.join(directory, name)
                    path_in_package = canonical_path(base + "/" + name)
                    member = _member(path_in_package, local)
                    members[path_in_package] = member
                    selected_paths.append(path_in_package)
                    target = os.path.join(staging, path_in_package)
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    os.replace(local, target)
                if len(selected_paths) != info["entries"]:
                    raise SourceError(f"{ref.identity}: extracted entry count differs from archive")
                epl = next((p for p in selected_paths if p.casefold().endswith(".epl")), None)
                pub_id = publication_id(src_id, ref.identity)
                pub = {
                    "id": pub_id,
                    "source_path": ref.identity,
                    "title": book.title or book.describe(),
                    "kind": _KIND.get(book.type.upper(), "unknown"),
                    "applicability": _publication_applicability(book, epl),
                    "documents": [],
                }
                manifest["publications"].append(pub)
                selections.append(
                    {"id": pub_id, "source_path": ref.identity, "member_paths": selected_paths}
                )
                local_dir = os.path.join(staging, base)
                previous = len(records)
                _html_files(pub, local_dir, base, staging, members, records, failures)
                html_count = len(records) - previous
                _navigation(records, pub, book, local_dir)
                pub["_prefix"] = book.prefix
                wiring_pages = (
                    _wiring_files(pub, local_dir, base, staging, members, records, failures)
                    if book.type.upper() == "EVTM"
                    else 0
                )
                del pub["_prefix"]
                pdf_pages = _pdf_files(pub, base, members, staging, records, failures)
                extensions = Counter(
                    os.path.splitext(p)[1].casefold() or "(none)" for p in selected_paths
                )
                capabilities.append(
                    {
                        "archive_identity": ref.identity,
                        "publication_id": pub_id,
                        "archive_version": info["version"],
                        "book_type": book.type,
                        "extracted_files": len(selected_paths),
                        "normalized_html_documents": html_count,
                        "normalized_wiring_pages": wiring_pages,
                        "normalized_pdf_pages": pdf_pages,
                        "raw_extensions": dict(sorted(extensions.items())),
                        "unsupported": [
                            x
                            for x in (
                                "MDB database not interpreted" if extensions[".mdb"] else "",
                                "XML without Ford wiring page mapping not interpreted"
                                if extensions[".xml"] and not wiring_pages
                                else "",
                                "unknown Ford book type" if pub["kind"] == "unknown" else "",
                            )
                            if x
                        ],
                    }
                )
            _fix_local_targets(records, members)
            _resolve_links(manifest, records, members, set(members))
            _resolve_ford_pdf_links(manifest, records)
            _aliases(manifest, records)
            for capability in capabilities:
                selected_records = [
                    record
                    for record in records
                    if record["publication_id"] == capability["publication_id"]
                ]
                statuses = Counter(
                    figure["status"] for record in selected_records for figure in record["figures"]
                )
                capability["diagram_statuses"] = dict(sorted(statuses.items()))
                if statuses["unsupported"] or statuses["missing"]:
                    capability["unsupported"].append(
                        f"{statuses['unsupported']} unsupported and "
                        f"{statuses['missing']} missing displayed diagrams; "
                        "original assets retained"
                    )
            # Keep the v1 manifest strictly unchanged; capability detail lives beside it.
            for pub in manifest["publications"]:
                for doc in pub["documents"]:
                    if (
                        doc["path"].startswith(DERIVED + "/")
                        and doc["citations"][0]["kind"] == "path"
                    ):
                        doc["content_sha256"] = members[doc["citations"][0]["path"]]["sha256"]
            validate_manifest(manifest)
            content = {
                "contract": CONTENT_CONTRACT,
                "source_id": src_id,
                "status": "partial" if failures else "complete",
                "failures": failures,
                "documents": records,
            }
            validate_content(content, manifest)
            raw_members = [
                {key: value for key, value in member.items() if key != "pdf_error"}
                for member in members.values()
            ]
            content_hash = _content_digest(
                [
                    Member(
                        m["path"],
                        m["size"],
                        m["sha256"],
                        m["media_type"],
                        m.get("page_count"),
                        m.get("page_count_method"),
                    )
                    for m in raw_members
                ],
                [],
            )
            inventory = {
                "contract": INVENTORY_CONTRACT,
                "source_id": src_id,
                "source_content_sha256": content_hash,
                "selected_content_sha256": content_hash,
                "members": sorted(raw_members, key=lambda m: m["path"]),
                "empty_directories": [],
                "ignored": [],
                "publications": selections,
            }
            validate_inventory(inventory)
            _json(os.path.join(staging, MANIFEST_NAME), manifest)
            _json(os.path.join(staging, INVENTORY_NAME), inventory)
            _json(os.path.join(staging, CONTENT_NAME), content)
            _json(os.path.join(staging, BRIDGE_NAME),
                  _bridge(manifest, infos, counts, records))
            _json(
                os.path.join(staging, CAPABILITIES_NAME),
                {
                    "contract": "service-manual-ford-capabilities/v1",
                    "source_id": src_id,
                    "publications": capabilities,
                    "failures": failures,
                },
            )
            shutil.rmtree(raw_root)
            os.replace(staging, destination)
            return {
                "output": destination,
                "source_id": src_id,
                "publications": len(manifest["publications"]),
                "documents": len(records),
                "failures": failures,
                "capabilities": capabilities,
            }
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
