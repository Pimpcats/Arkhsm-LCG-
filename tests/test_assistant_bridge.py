import json
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from cardforge.assistant_bridge import context, register_art, sync_art, write


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.camp = self.root / 'campaigns/demo'
        write(self.camp / 'campaign.json', {'output_dir': 'out/demo', 'api_key': 'do-not-export'})
        write(self.camp / 'manifest.json', [{'id': 'demo-one', 'scene': 'A room', 'art_type': 'location'},
                                           {'id': 'demo-back', 'no_art': True}])
        write(self.root / 'pipeline/demo_cards_spec.json', [{'id': 'demo-one', 'name': 'Old'}])
        write(self.camp / 'card_overrides.json', {'demo-one': {'name': 'Current'}})

    def test_context(self):
        result = context('demo', self.root)
        self.assertEqual(result['cards'][0]['name'], 'Current')
        self.assertEqual(len(result['art_jobs']), 1)
        self.assertNotIn('do-not-export', json.dumps(result))

    def test_round_trip_preserves_other_selections_and_detects_tamper(self):
        image = self.root / 'input.jpg'
        Image.new('RGB', (20, 30), 'red').save(image)
        entry = register_art('demo', 'demo-one', image, self.root)
        write(self.root / 'out/demo/index.json', {'other': 'existing.png'})
        sync_art('demo', self.root)
        first = (self.root / 'out/demo/index.json').read_bytes()
        sync_art('demo', self.root)
        self.assertEqual(first, (self.root / 'out/demo/index.json').read_bytes())
        index = json.loads(first)
        self.assertEqual(index['other'], 'existing.png')
        self.assertTrue((self.root / index['demo-one']).is_file())
        self.assertEqual(context('demo', self.root)['art_jobs'][0]['status'], 'registered')
        (self.root / entry['path']).write_bytes(b'changed')
        with self.assertRaises(ValueError):
            sync_art('demo', self.root)
        self.assertEqual(first, (self.root / 'out/demo/index.json').read_bytes())

    def test_rejects_bad_identifiers_and_output_escape(self):
        with self.assertRaises(ValueError):
            context('../demo', self.root)
        write(self.camp / 'campaign.json', {'output_dir': '../escape'})
        with self.assertRaises(ValueError):
            sync_art('demo', self.root)

    def test_rejects_unknown_card_before_write(self):
        image = self.root / 'input.png'
        Image.new('RGB', (10, 10)).save(image)
        with self.assertRaises(ValueError):
            register_art('demo', 'unknown', image, self.root)
        self.assertFalse((self.camp / 'assistant').exists())


if __name__ == '__main__':
    unittest.main()
