import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from free_ai_router.chat import ChatError, stream_chat


class ChatTests(unittest.TestCase):
    @patch("free_ai_router.chat.urllib.request.urlopen")
    def test_stream_and_free_model(self, urlopen):
        urlopen.return_value = io.BytesIO(b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\ndata: [DONE]\n\n')
        self.assertEqual(list(stream_chat("secret", [{"role": "user", "content": "hi"}])), ["hello"])
        request = urlopen.call_args.args[0]
        self.assertEqual(json.loads(request.data)["model"], "openrouter/free")

    @patch("free_ai_router.chat.urllib.request.urlopen")
    def test_free_only(self, urlopen):
        urlopen.return_value = io.BytesIO(b'data: [DONE]\n')
        list(stream_chat("secret", [], "vendor/model:free"))
        self.assertEqual(json.loads(urlopen.call_args.args[0].data)["model"], "vendor/model:free")
        urlopen.reset_mock()
        for model in ("vendor/model", "vendor/model:free:paid", "vendor/model:free/other"):
            with self.assertRaises(ChatError):
                list(stream_chat("secret", [], model))
        urlopen.assert_not_called()

    @patch("free_ai_router.chat.urllib.request.urlopen")
    def test_incomplete_stream_and_rate_limit(self, urlopen):
        urlopen.return_value = io.BytesIO(b'data: {"choices":[{"delta":{"content":"partial"}}]}\n')
        with self.assertRaises(ChatError):
            list(stream_chat("secret", []))
        urlopen.side_effect = HTTPError("url", 429, "limit", {}, None)
        with self.assertRaisesRegex(ChatError, "사용 한도"):
            list(stream_chat("secret", []))


if __name__ == "__main__":
    unittest.main()
