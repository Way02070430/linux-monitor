import contextlib
import io
import json
import runpy
import unittest
from types import SimpleNamespace
from unittest.mock import mock_open, patch

import monitor


class CollectorTests(unittest.TestCase):
    def test_collectors_are_independent(self):
        # 正常、任意单项失败和全部失败；两类预期采集异常都验证。
        for error_type in (OSError, monitor.psutil.Error):
            for failed in ((), (0,), (1,), (2,), (0, 1, 2)):
                with self.subTest(error=error_type.__name__, failed=failed):
                    with (
                        patch('monitor.psutil.cpu_percent', return_value=12.5) as cpu,
                        patch('monitor.psutil.virtual_memory', return_value=SimpleNamespace(percent=23.5)) as memory,
                        patch('monitor.psutil.disk_usage', return_value=SimpleNamespace(percent=34.5)) as disk,
                        patch('monitor.logging.exception') as errors,
                    ):
                        collectors = (cpu, memory, disk)
                        for index in failed:
                            collectors[index].side_effect = error_type('模拟采集失败')
                        expected = tuple(None if i in failed else v for i, v in enumerate((12.5, 23.5, 34.5)))
                        self.assertEqual(monitor.collect_metrics(), expected)
                        for collector in collectors:
                            collector.assert_called_once()
                        self.assertEqual(errors.call_count, len(failed))

    def test_missing_value_display_and_snapshot(self):
        self.assertEqual(monitor.format_metric(None), '采集失败')
        self.assertEqual(monitor.format_metric(0), '0%')
        fake_file = mock_open()
        with patch('builtins.open', fake_file):
            monitor.save_snapshot('test-time', None, 23.5, None)
        serialized = ''.join(call.args[0] for call in fake_file().write.call_args_list)
        self.assertEqual(json.loads(serialized), {
            'timestamp': 'test-time', 'cpu_percent': None,
            'memory_percent': 23.5, 'disk_percent': None,
        })

    def test_main_continues_after_cpu_failure(self):
        # 第一轮 CPU 失败，第二轮成功；第二轮等待时模拟 Ctrl+C。
        output = io.StringIO()
        with (
            patch('psutil.cpu_percent', side_effect=[OSError('模拟失败'), 12.5]),
            patch('psutil.virtual_memory', return_value=SimpleNamespace(percent=23.5)),
            patch('psutil.disk_usage', return_value=SimpleNamespace(percent=34.5)),
            patch('time.sleep', side_effect=[None, KeyboardInterrupt]),
            patch('logging.basicConfig'),
            patch('logging.exception') as errors,
            patch('logging.info'),
            patch('builtins.open', mock_open()),
            contextlib.redirect_stdout(output),
        ):
            runpy.run_path(monitor.__file__, run_name='__main__')
        text = output.getvalue()
        self.assertIn('CPU 使用率： 采集失败', text)
        self.assertIn('CPU 使用率： 12.5%', text)
        self.assertEqual(text.count('内存使用率： 23.5%'), 2)
        self.assertEqual(text.count('磁盘使用率： 34.5%'), 2)
        self.assertIn('监控已停止', text)
        errors.assert_called_once_with('CPU 采集失败')


if __name__ == '__main__':
    unittest.main()
