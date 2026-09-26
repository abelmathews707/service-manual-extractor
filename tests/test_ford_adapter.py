"""Ford-to-neutral bridge regression tests; no owned manual bytes required."""

import json
import os
import tempfile
import unittest

from test_formats import make_arc, make_v1_arc, payload
from test_sources import pdf_bytes

from sme.ford_adapter import (
    BRIDGE_NAME,
    CAPABILITIES_NAME,
    import_ford,
    probe_ford,
    resolve_legacy_citation,
)
from sme.normalize import CONTENT_NAME, validate_content
from sme.source import MANIFEST_NAME, SourceError
from sme.viewer import build_viewer


def _epl(code="SAA"):
    return (
        f"<workunit><code>{code}</code><type>SERVICE</type>"
        f"<title>{code} Workshop</title><vehicle><year>2003</year>"
        "<name>F-250</name><engine>6.0L</engine></vehicle></workunit>"
    ).encode()


def _files(code="SAA"):
    return [
        (f"{code}.EPL", payload(stored=[_epl(code)])),
        (
            "PAGE.HTM",
            payload(
                stored=[
                    b'<html><body><h1 id="repair">Repair</h1><p>Remove the pump.</p>'
                    b'<a href="NEXT.HTM">Next step</a></body></html>'
                ]
            ),
        ),
        (
            "NEXT.HTM",
            payload(
                stored=[
                    b"<html><body><h1>Next</h1><p>Install the pump.</p>"
                    b'<a href="PAGE.HTM">Return</a></body></html>'
                ]
            ),
        ),
    ]


class FordAdapterTest(unittest.TestCase):
    def _disc(self, root, version, locales=("useni4",)):
        selected = []
        for locale in locales:
            directory = os.path.join(root, "content", locale)
            os.makedirs(directory)
            data = _files() if locale == "useni4" else _files()
            archive = make_v1_arc(data) if version == 1 else make_arc(dict(data))
            with open(os.path.join(directory, "SAA.arc"), "wb") as stream:
                stream.write(archive)
            selected.append(f"content/{locale}/saa.arc")
        return selected

    def _load(self, package, filename):
        with open(os.path.join(package, filename), encoding="utf-8") as stream:
            return json.load(stream)

    def test_both_pod_generations_and_return_links(self):
        for version in (1, 2):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as root:
                disc = os.path.join(root, "disc")
                selected = self._disc(disc, version)
                package = os.path.join(root, "package")
                result = import_ford(disc, package, selected)
                self.assertEqual(result["publications"], 1)
                self.assertEqual(result["documents"], 2)
                manifest = self._load(package, MANIFEST_NAME)
                content = self._load(package, CONTENT_NAME)
                validate_content(content, manifest)
                self.assertEqual(manifest["source"]["format"], f"ford_tsp_disc_v{version}")
                self.assertTrue(
                    all(
                        doc["references"][0]["status"] == "resolved"
                        for doc in manifest["publications"][0]["documents"]
                    )
                )
                viewer = os.path.join(root, "viewer")
                built = build_viewer(package, viewer)
                self.assertEqual(built["documents"], 2)

    def test_two_workshop_occurrences_remain_distinct(self):
        with tempfile.TemporaryDirectory() as root:
            disc = os.path.join(root, "disc")
            selected = self._disc(disc, 2, ("useni4", "cnfri4"))
            self.assertEqual(len(probe_ford(disc)["archives"]), 2)
            package = os.path.join(root, "package")
            import_ford(disc, package, selected)
            manifest = self._load(package, MANIFEST_NAME)
            bridge = self._load(package, BRIDGE_NAME)
            self.assertEqual(len(manifest["publications"]), 2)
            self.assertEqual(len({pub["id"] for pub in manifest["publications"]}), 2)
            self.assertEqual(len({entry["legacy_book_key"] for entry in bridge["references"]}), 2)
            self.assertIn("#/wsm/page", bridge["ambiguous_unscoped_routes"])
            for publication in manifest["publications"]:
                key = next(
                    item["legacy_book_key"]
                    for item in bridge["references"]
                    if item["publication_id"] == publication["id"]
                )
                resolved = resolve_legacy_citation(bridge, key, "PAGE.HTM")
                self.assertEqual(resolved["publication_id"], publication["id"])
                anchored = resolve_legacy_citation(bridge, key, 'PAGE.HTM#repair')
                self.assertEqual(anchored['fragment'], 'repair')
            capabilities = self._load(package, CAPABILITIES_NAME)
            self.assertEqual(len(capabilities["publications"]), 2)

    def test_html_link_to_original_pdf_resolves_to_first_page(self):
        with tempfile.TemporaryDirectory() as root:
            disc = os.path.join(root, "disc")
            folder = os.path.join(disc, "content", "useni4")
            os.makedirs(folder)
            files = dict(_files())
            files["PAGE.HTM"] = payload(
                stored=[b'<html><body><h1>Repair</h1><a href="PRINT.PDF">Print</a></body></html>']
            )
            files["PRINT.PDF"] = payload(stored=[pdf_bytes(("first", "second"))])
            with open(os.path.join(folder, "SAA.arc"), "wb") as stream:
                stream.write(make_arc(files))
            package = os.path.join(root, "package")
            import_ford(disc, package, ["content/useni4/saa.arc"])
            content = self._load(package, CONTENT_NAME)
            pages = [record for record in content["documents"] if record["role"] == "pdf_page"]
            self.assertEqual([record["page"] for record in pages], [1, 2])
            html = next(
                record
                for record in content["documents"]
                if record["original_path"].endswith("PAGE.HTM")
            )
            self.assertEqual(html["references"][0]["target_id"], pages[0]["id"])
            bridge = self._load(package, BRIDGE_NAME)
            with self.assertRaisesRegex(SourceError, "ambiguous"):
                resolve_legacy_citation(bridge, "SAA", "PRINT.PDF")
            self.assertEqual(
                resolve_legacy_citation(bridge, "SAA", "PRINT.PDF", page=2)["document_id"],
                pages[1]["id"],
            )
            viewer = os.path.join(root, "viewer")
            build_viewer(package, viewer)
            library = self._load(os.path.join(viewer, "data"), "manifest.json")
            self.assertTrue(library["books"][0]["navigation"])

    def test_mixed_generations_are_explicitly_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            disc = os.path.join(root, "disc")
            first = self._disc(disc, 1)[0]
            other = os.path.join(disc, "content", "cnfri4")
            os.makedirs(other)
            with open(os.path.join(other, "SAA.arc"), "wb") as stream:
                stream.write(make_arc(dict(_files())))
            destination = os.path.join(root, "package")
            with self.assertRaisesRegex(SourceError, "mix Ford POD v1/v2"):
                import_ford(disc, destination, [first, "content/cnfri4/saa.arc"])
            self.assertFalse(os.path.exists(destination))


if __name__ == "__main__":
    unittest.main()
