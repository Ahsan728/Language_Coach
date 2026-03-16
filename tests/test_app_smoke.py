import tempfile
import unittest
from pathlib import Path

from backend import create_app
from backend.services import get_lessons


class AppSmokeTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        temp_path = Path(self.temp_dir.name)
        self.app = create_app(
            {
                'TESTING': True,
                'DB_PATH': str(temp_path / 'progress.db'),
                'TTS_CACHE_DIR': str(temp_path / 'tts_cache'),
                'SECRET_KEY': 'test-secret',
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dashboard_and_resources_render(self):
        dashboard = self.client.get('/')
        resources = self.client.get('/resources')

        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(resources.status_code, 200)

    def test_protected_lesson_redirects_to_login(self):
        french_lessons = get_lessons().get('french', [])
        self.assertTrue(french_lessons, 'expected french lessons fixture data')

        lesson_id = int(french_lessons[0]['id'])
        response = self.client.get(f'/lesson/french/{lesson_id}')

        self.assertEqual(response.status_code, 302)
        self.assertIn('/login', response.headers['Location'])

    def test_api_translate_validates_missing_text(self):
        response = self.client.post('/api/translate', json={})

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload['ok'], False)


if __name__ == '__main__':
    unittest.main()
