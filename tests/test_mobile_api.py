import tempfile
import unittest
from pathlib import Path

from backend import create_app
from backend.services import get_lessons


class MobileApiTest(unittest.TestCase):
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

    def _create_mobile_session(self, email='mobile.user@example.com', name=''):
        response = self.client.post(
            '/api/v1/auth/session',
            json={
                'email': email,
                'name': name,
                'remember_me': True,
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload['ok'])
        return payload

    def _login_via_web(self, email='web.user@example.com', name='Web User'):
        response = self.client.post(
            '/login',
            data={
                'name': name,
                'email': email,
                'remember': 'on',
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        return response

    def test_auth_session_lifecycle(self):
        session_payload = self._create_mobile_session()
        token = session_payload['access_token']
        headers = {'Authorization': f'Bearer {token}'}

        self.assertEqual(session_payload['auth_mode'], 'email_only_unverified')
        self.assertEqual(session_payload['token_type'], 'Bearer')
        self.assertEqual(session_payload['user']['name'], 'Mobile User')
        self.assertIsNotNone(session_payload['expires_at'])
        self.assertIsNotNone(session_payload['user']['created_at'])
        self.assertIsNotNone(session_payload['user']['last_login'])

        me = self.client.get('/api/v1/me', headers=headers)
        self.assertEqual(me.status_code, 200)
        me_payload = me.get_json()
        self.assertTrue(me_payload['ok'])
        self.assertEqual(me_payload['user']['email'], 'mobile.user@example.com')

        logout = self.client.delete('/api/v1/auth/session', headers=headers)
        self.assertEqual(logout.status_code, 200)
        self.assertEqual(logout.get_json(), {'ok': True})

        me_after_logout = self.client.get('/api/v1/me', headers=headers)
        self.assertEqual(me_after_logout.status_code, 401)
        self.assertEqual(me_after_logout.get_json()['error']['code'], 'unauthorized')

    def test_protected_endpoints_require_auth(self):
        lesson_id = int(get_lessons()['french'][0]['id'])
        checks = [
            ('get', '/api/v1/me'),
            ('delete', '/api/v1/auth/session'),
            ('post', f'/api/v1/languages/french/lessons/{lesson_id}/touch'),
            ('get', '/api/v1/progress'),
        ]

        for method, path in checks:
            response = getattr(self.client, method)(path)
            self.assertEqual(response.status_code, 401, path)
            payload = response.get_json()
            self.assertFalse(payload['ok'])
            self.assertEqual(payload['error']['code'], 'unauthorized')
            self.assertIn('request_id', payload['error'])

    def test_languages_lessons_vocabulary_and_progress(self):
        session_payload = self._create_mobile_session(email='progress.user@example.com', name='Progress User')
        headers = {'Authorization': f'Bearer {session_payload["access_token"]}'}
        lesson_id = int(get_lessons()['french'][0]['id'])

        languages = self.client.get('/api/v1/languages')
        self.assertEqual(languages.status_code, 200)
        languages_payload = languages.get_json()
        self.assertTrue(languages_payload['ok'])
        self.assertEqual({item['id'] for item in languages_payload['languages']}, {'french', 'spanish'})

        public_lessons = self.client.get('/api/v1/languages/french/lessons')
        self.assertEqual(public_lessons.status_code, 200)
        public_payload = public_lessons.get_json()
        self.assertTrue(public_payload['ok'])
        self.assertIsInstance(public_payload['recommended_lesson_id'], int)
        self.assertNotIn('progress', public_payload['lessons'][0])

        authed_lessons = self.client.get('/api/v1/languages/french/lessons', headers=headers)
        self.assertEqual(authed_lessons.status_code, 200)
        authed_payload = authed_lessons.get_json()
        self.assertIn('progress', authed_payload['lessons'][0])
        self.assertEqual(authed_payload['lessons'][0]['progress']['attempts'], 0)

        touch = self.client.post(f'/api/v1/languages/french/lessons/{lesson_id}/touch', headers=headers)
        self.assertEqual(touch.status_code, 200)
        touch_payload = touch.get_json()
        self.assertTrue(touch_payload['ok'])
        self.assertTrue(touch_payload['last_seen'].endswith('Z'))

        vocabulary = self.client.get('/api/v1/languages/french/vocabulary?category=greetings&limit=5&offset=0')
        self.assertEqual(vocabulary.status_code, 200)
        vocabulary_payload = vocabulary.get_json()
        self.assertTrue(vocabulary_payload['ok'])
        self.assertEqual(vocabulary_payload['language'], 'french')
        self.assertEqual(vocabulary_payload['category'], 'greetings')
        self.assertEqual(vocabulary_payload['limit'], 5)
        self.assertEqual(vocabulary_payload['offset'], 0)
        self.assertGreater(vocabulary_payload['total'], 0)
        self.assertEqual(vocabulary_payload['categories'][0]['id'], 'greetings')
        self.assertLessEqual(len(vocabulary_payload['items']), 5)
        self.assertEqual(vocabulary_payload['items'][0]['category'], 'greetings')

        progress = self.client.get('/api/v1/progress?include=summary,lessons', headers=headers)
        self.assertEqual(progress.status_code, 200)
        progress_payload = progress.get_json()
        self.assertTrue(progress_payload['ok'])
        self.assertIn('today', progress_payload)
        self.assertIn('languages', progress_payload)
        self.assertIn('lessons', progress_payload)
        self.assertEqual(progress_payload['languages']['french']['last_seen_lesson_id'], lesson_id)
        lesson_progress = next(item for item in progress_payload['lessons']['french'] if item['lesson_id'] == lesson_id)
        self.assertFalse(lesson_progress['completed'])
        self.assertEqual(lesson_progress['attempts'], 0)
        self.assertIsNotNone(lesson_progress['last_seen'])

    def test_auth_session_validates_email(self):
        response = self.client.post(
            '/api/v1/auth/session',
            json={'email': 'not-an-email', 'name': 'Bad', 'remember_me': True},
        )

        self.assertEqual(response.status_code, 422)
        payload = response.get_json()
        self.assertFalse(payload['ok'])
        self.assertEqual(payload['error']['code'], 'validation_error')
        self.assertEqual(payload['error']['fields']['email'], 'invalid')

    def test_web_login_cookie_is_not_accepted_for_required_mobile_auth(self):
        lesson_id = int(get_lessons()['french'][0]['id'])
        self._login_via_web()

        me = self.client.get('/api/v1/me')
        self.assertEqual(me.status_code, 401)
        self.assertEqual(me.get_json()['error']['code'], 'unauthorized')

        touch = self.client.post(f'/api/v1/languages/french/lessons/{lesson_id}/touch')
        self.assertEqual(touch.status_code, 401)
        self.assertEqual(touch.get_json()['error']['code'], 'unauthorized')

        progress = self.client.get('/api/v1/progress')
        self.assertEqual(progress.status_code, 401)
        self.assertEqual(progress.get_json()['error']['code'], 'unauthorized')


if __name__ == '__main__':
    unittest.main()
