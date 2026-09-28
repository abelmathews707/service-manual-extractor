"""Exercise the viewer's pure request scheduler without a browser or manuals."""

import shutil
import subprocess
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which('node'), 'optional JavaScript scheduler gate requires Node')
class ViewerShardPoolTests(unittest.TestCase):
    def test_bounded_ordered_cancelled_and_failed_requests(self):
        source = Path(__file__).resolve().parents[1] / 'viewer/assets/app.js'
        scheduler = source.read_text(encoding='utf-8').split(
            'async function libraryShards(', 1)[1]
        scheduler = 'async function libraryShards(' + scheduler.split(
            'async function libraryShard(', 1)[0]
        script = scheduler + r"""
const assert = require('node:assert/strict');
(async () => {
  let active = 0, maximum = 0;
  const ids = Array.from({length: 80}, (_, index) => index);
  const controller = new AbortController();
  const output = await libraryShards(ids, async id => {
    active++; maximum = Math.max(maximum, active);
    await new Promise(resolve => setTimeout(resolve, (id % 3) + 1));
    active--; return id;
  }, controller.signal);
  assert.deepEqual(output, ids);
  assert.equal(maximum, 6);
  assert.deepEqual(await libraryShards([], async () => assert.fail(), controller.signal), []);
  const cancel = new AbortController(); let calls = 0;
  await assert.rejects(libraryShards(ids, async id => {
    calls++; if (id === 0) cancel.abort(); return id;
  }, cancel.signal), {name: 'AbortError'});
  assert.equal(calls, 1);
  let failedCalls = 0;
  await assert.rejects(libraryShards(ids, async () => {
    failedCalls++; throw new Error('unavailable');
  }, controller.signal), /unavailable/);
  assert.ok(failedCalls <= 6);
})().catch(error => { console.error(error); process.exitCode = 1; });
"""
        result = subprocess.run([shutil.which('node'), '-e', script],
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
