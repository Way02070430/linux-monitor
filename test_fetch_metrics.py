import contextlib
from datetime import datetime, timedelta
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import Mock, patch

import requests

import fetch_metrics as client


def snapshot():
    return {
        "timestamp": "2026-10-24 12:00:00",
        "cpu_percent": 12.5,
        "memory_percent": 23.5,
        "disk_percent": 34.5,
    }


class SnapshotTests(unittest.TestCase):
    def test_valid_and_missing_measurement(self):
        data = snapshot()
        now = datetime(2026, 10, 24, 12, 0, 10)
        self.assertEqual(client.validate_snapshot(data, now), 10)
        data["cpu_percent"] = None
        self.assertEqual(client.validate_snapshot(data, now), 10)
        data["cpu_percent"] = 0
        self.assertEqual(client.validate_snapshot(data, now), 10)

    def test_bad_fields(self):
        now = datetime(2026, 10, 24, 12)
        cases = [[], {}, {**snapshot(), "timestamp": 123},
                 {**snapshot(), "timestamp": "not-a-time"},
                 {**snapshot(), "timestamp": "2026-10-24 12:01:00"}]
        for value in (True, "12", [], {}, -1, 101, float('nan'), float('inf')):
            cases.append({**snapshot(), "cpu_percent": value})
        for data in cases:
            with self.subTest(data=data):
                with self.assertRaises(client.SnapshotError):
                    client.validate_snapshot(data, now)

    def run_client(self, data=None, error=None, age=1):
        output = io.StringIO()
        with (
            patch('fetch_metrics.fetch_metrics', return_value=data, side_effect=error),
            patch('fetch_metrics.validate_snapshot', return_value=age),
            contextlib.redirect_stdout(output),
        ):
            code = client.main([])
        return code, output.getvalue()

    def test_normal_partial_and_stale(self):
        code, text = self.run_client(snapshot())
        self.assertEqual(code, 0)
        self.assertIn('数据新鲜度：正常', text)
        code, text = self.run_client({**snapshot(), 'cpu_percent': None})
        self.assertEqual(code, 4)
        self.assertIn('数据未知', text)
        self.assertNotIn('None %', text)
        code, text = self.run_client(snapshot(), age=31)
        self.assertEqual(code, 3)
        self.assertIn('历史数据', text)
        self.assertEqual(self.run_client(snapshot(), age=30)[0], 0)

    def test_request_errors(self):
        cases = [
            (requests.exceptions.Timeout(), '超时'),
            (requests.exceptions.ConnectionError(), '无法连接'),
            (requests.exceptions.HTTPError('404'), '404'),
            (requests.exceptions.HTTPError('500'), '500'),
            (requests.exceptions.RequestException('test'), '请求失败'),
            (client.SnapshotError('缺少字段'), '数据错误'),
        ]
        for error, expected in cases:
            with self.subTest(error=error):
                code, text = self.run_client(error=error)
                self.assertEqual(code, 2 if isinstance(error, client.SnapshotError) else 1)
                self.assertIn(expected, text)

    def test_json_error_and_response_closed(self):
        response = Mock()
        response.json.side_effect = requests.exceptions.JSONDecodeError('bad', 'x', 0)
        with patch('fetch_metrics.requests.get', return_value=response):
            with self.assertRaises(client.SnapshotError):
                client.fetch_metrics('http://example.test', 3)
        response.close.assert_called_once()

    def test_invalid_cli_seconds(self):
        for text in ('0', '-1', 'nan', 'inf', 'oops'):
            with self.subTest(value=text):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as error:
                        client.main(['--max-age', text])
                self.assertEqual(error.exception.code, 2)


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class HttpIntegrationTests(unittest.TestCase):
    def test_real_local_http(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            now = datetime.now().replace(microsecond=0)
            fresh = {**snapshot(), 'timestamp': now.strftime('%Y-%m-%d %H:%M:%S')}
            old = {**fresh, 'timestamp': (now - timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')}
            for name, data in [('latest.json', fresh), ('stale.json', old), ('missing.json', {})]:
                (root / name).write_text(json.dumps(data))
            (root / 'bad.txt').write_text('hello')
            server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=directory))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = 'http://127.0.0.1:' + str(server.server_port)
                cases = [('latest.json', 0), ('stale.json', 3),
                         ('missing.json', 2), ('bad.txt', 2), ('absent.json', 1)]
                for name, expected in cases:
                    with self.subTest(path=name):
                        with contextlib.redirect_stdout(io.StringIO()):
                            code = client.main(['--url', base + '/' + name])
                        self.assertEqual(code, expected)
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(client.main(['--url', base + '/latest.json']), 1)


if __name__ == '__main__':
    unittest.main()
