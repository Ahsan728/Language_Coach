import json
import tempfile
import unittest
from pathlib import Path

from backend import create_app
from backend.services import get_lessons, get_vocab


class ConfigIsolationTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.base_dir = root / 'isolated_app'
        self.data_dir = root / 'isolated_data'

        (self.base_dir / 'templates').mkdir(parents=True, exist_ok=True)
        (self.base_dir / 'static' / 'css').mkdir(parents=True, exist_ok=True)
        (self.base_dir / 'static' / 'js').mkdir(parents=True, exist_ok=True)
        (self.base_dir / 'logo').mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        (self.base_dir / 'templates' / 'dashboard.html').write_text(
            "isolated-dashboard french-total={{ stats['french']['total'] }}",
            encoding='utf-8',
        )
        (self.base_dir / 'templates' / 'resources.html').write_text('isolated resources', encoding='utf-8')
        (self.base_dir / 'static' / 'css' / 'style.css').write_bytes(b'isolated css')
        (self.base_dir / 'static' / 'js' / 'app.js').write_bytes(b'isolated js')
        (self.base_dir / 'logo' / 'Language_Coach_logo.png').write_bytes(b'isolated-logo')

        lessons = {
            'french': [
                {
                    'id': 1,
                    'title_en': 'Isolated French',
                    'title_bn': '',
                    'title_lang': '',
                    'cefr_level': 'A1',
                    'vocabulary_categories': [],
                }
            ],
            'spanish': [],
        }
        vocab = {
            'french': {
                'greetings': [
                    {
                        'word': 'bonjour-temp',
                        'english': 'hello-temp',
                        'bengali': 'হ্যালো-temp',
                    }
                ]
            },
            'spanish': {},
        }
        resources = {'french': [], 'spanish': []}

        (self.data_dir / 'lessons.json').write_text(json.dumps(lessons), encoding='utf-8')
        (self.data_dir / 'vocabulary.json').write_text(json.dumps(vocab), encoding='utf-8')
        (self.data_dir / 'resource_sentences.json').write_text(json.dumps(resources), encoding='utf-8')

        default_lessons = get_lessons()
        self.assertNotEqual(
            default_lessons.get('french', [{}])[0].get('title_en'),
            'Isolated French',
            'default repo cache unexpectedly matched isolation fixture',
        )

        self.app = create_app(
            {
                'TESTING': True,
                'SECRET_KEY': 'test-secret',
                'BASE_DIR': str(self.base_dir),
                'DATA_DIR': str(self.data_dir),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_instance_paths_use_isolated_base_and_data_dirs(self):
        with self.app.app_context():
            lessons = get_lessons()
            vocab = get_vocab()

            self.assertEqual(lessons['french'][0]['title_en'], 'Isolated French')
            self.assertEqual(vocab['french']['greetings'][0]['word'], 'bonjour-temp')
            self.assertTrue(Path(self.app.config['BASE_DIR']).samefile(self.base_dir))
            self.assertTrue(Path(self.app.config['DATA_DIR']).samefile(self.data_dir))
            self.assertTrue(Path(self.app.config['DB_PATH']).samefile(self.data_dir / 'progress.db'))
            self.assertEqual(Path(self.app.config['TTS_CACHE_DIR']).name, 'tts_cache')
            self.assertTrue(Path(self.app.config['TTS_CACHE_DIR']).parent.samefile(self.data_dir))
            self.assertTrue(Path(self.app.config['TEMPLATE_DIR']).samefile(self.base_dir / 'templates'))
            self.assertTrue(Path(self.app.config['STATIC_DIR']).samefile(self.base_dir / 'static'))

        dashboard = self.client.get('/')
        resources = self.client.get('/resources')
        static_css = self.client.get('/static/css/style.css')
        logo = self.client.get('/logo.png')

        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b'isolated-dashboard french-total=1', dashboard.data)
        self.assertEqual(resources.status_code, 200)
        self.assertEqual(resources.data, b'isolated resources')
        self.assertEqual(static_css.status_code, 200)
        self.assertEqual(static_css.data, b'isolated css')
        self.assertEqual(logo.status_code, 200)
        self.assertEqual(logo.data, b'isolated-logo')

        dashboard.close()
        resources.close()
        static_css.close()
        logo.close()


if __name__ == '__main__':
    unittest.main()
