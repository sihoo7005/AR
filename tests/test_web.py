import http.client
import json
import threading
import unittest
from unittest.mock import patch

from free_ai_router.web import make_server
from free_ai_router.chat import ChatError


class WebTests(unittest.TestCase):
    def setUp(self):
        self.server = make_server('secret', groq_key='groq-secret')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = f'127.0.0.1:{self.server.server_port}'
        self.conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)

    def tearDown(self):
        self.conn.close()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, method, path, body=None, headers=None):
        self.conn.request(method, path, body, headers or {})
        response = self.conn.getresponse()
        return response.status, response.read().decode()

    def test_origin_host_and_stream(self):
        status, page = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertNotIn('secret', page)
        token = page.split('name="chat-token" content="')[1].split('"')[0]
        self.assertEqual(self.request('GET', '/', headers={'Host': 'evil.example'})[0], 403)
        body = json.dumps({'model': 'auto', 'messages': [{'role': 'user', 'content': 'hi'}]})
        headers = {'Content-Type': 'application/json', 'Origin': 'https://evil.example', 'X-Chat-Token': token}
        self.assertEqual(self.request('POST', '/chat', body, headers)[0], 403)
        headers['Origin'] = 'http://' + self.host
        with patch('free_ai_router.web.stream_chat', return_value=iter(['hello'])) as chat:
            status, data = self.request('POST', '/chat', body, headers)
        self.assertEqual(status, 200)
        self.assertIn('"value": "hello"', data)
        self.assertIn('"type": "done"', data)
        self.assertEqual(chat.call_args.args[2], 'openrouter/free')

    def test_auto_fallback_and_partial_response(self):
        _, page = self.request('GET', '/')
        token = page.split('name="chat-token" content="')[1].split('"')[0]
        headers = {'Content-Type': 'application/json', 'Origin': 'http://' + self.host, 'X-Chat-Token': token}
        body = json.dumps({'provider': 'auto', 'model': 'auto', 'messages': [{'role': 'user', 'content': 'hi'}]})
        def fallback(key, messages, model, provider='openrouter'):
            if provider == 'groq':
                raise ChatError('제한', retryable=True)
            yield 'ok'
        with patch('free_ai_router.web.stream_chat', side_effect=fallback):
            _, result = self.request('POST', '/chat', body, headers)
        self.assertIn('"type": "notice"', result)
        self.assertIn('"value": "ok"', result)
        def partial(key, messages, model, provider='openrouter'):
            yield 'partial'
            raise ChatError('장애', retryable=True)
        with patch('free_ai_router.web.stream_chat', side_effect=partial) as chat:
            _, result = self.request('POST', '/chat', body, headers)
        self.assertEqual(chat.call_count, 1)
        self.assertIn('"type": "error"', result)
        self.assertNotIn('"type": "notice"', result)

    def test_free_model_rejected(self):
        _, page = self.request('GET', '/')
        token = page.split('name="chat-token" content="')[1].split('"')[0]
        headers = {'Content-Type': 'application/json', 'Origin': 'http://' + self.host, 'X-Chat-Token': token}
        body = json.dumps({'model': 'vendor/paid', 'messages': [{'role': 'user', 'content': 'hi'}]})
        with patch('free_ai_router.chat.urllib.request.urlopen') as urlopen:
            _, result = self.request('POST', '/chat', body, headers)
        self.assertIn('"type": "error"', result)
        urlopen.assert_not_called()


if __name__ == '__main__':
    unittest.main()
