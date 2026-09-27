"""A malformed Ford page-metadata XML must not erase healthy wiring sheets."""

import os
import tempfile
import unittest

from fsd.build import parse_wiring


class WiringPartialTests(unittest.TestCase):
    def test_bad_metadata_retains_good_page_and_figure(self):
        with tempfile.TemporaryDirectory() as directory:
            files = {
                'EDOCEL_001.XML': (
                    '<root><page><num>1</num><file>EDO0001</file></page>'
                    '<page><num>2</num><file>EDO0002</file></page></root>'),
                'EDO0001.XML': '<root><page><title>Good circuit</title></page></root>',
                'EDO0002.XML': '<root><page><title>Bad & circuit</title></page></root>',
                'EDO0002.SVG': '<svg xmlns="http://www.w3.org/2000/svg"/>',
            }
            for name, content in files.items():
                with open(os.path.join(directory, name), 'w', encoding='utf-8') as stream:
                    stream.write(content)
            warnings = []
            cells, _ = parse_wiring(directory, 'EDO', warn=warnings.append)
            self.assertEqual(len(cells), 1)
            self.assertEqual([page['id'] for page in cells[0]['pages']],
                             ['edo0001', 'edo0002'])
            self.assertEqual(cells[0]['pages'][0]['title'], 'Good circuit')
            self.assertEqual(cells[0]['pages'][1]['title'], '')
            self.assertEqual(cells[0]['pages'][1]['svg'], 'edo0002.svg')
            self.assertEqual(len(warnings), 1)
            self.assertIn('EDO0002.XML', warnings[0])


if __name__ == '__main__':
    unittest.main()
