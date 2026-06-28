"""Tests for metrics/sampler.py — psutil monkeypatched at the boundary.

No real psutil readings and no Qt event loop: every psutil call is replaced
with a fake, and the monotonic clock is injected so rate math is deterministic.
"""

from __future__ import annotations

from types import SimpleNamespace

import psutil
import pytest

from resourcer.metrics.sampler import Sampler


class FakeClock:
    """Deterministic monotonic clock the sampler reads for elapsed time."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now


def _patch_metrics(
    monkeypatch: pytest.MonkeyPatch,
    *,
    cpu: float,
    per_core: list[float],
    mem: SimpleNamespace,
    disk: SimpleNamespace | None,
    net: SimpleNamespace,
) -> None:
    def cpu_percent(interval: float | None = None, percpu: bool = False):
        return list(per_core) if percpu else cpu

    monkeypatch.setattr(psutil, "cpu_percent", cpu_percent)
    monkeypatch.setattr(psutil, "virtual_memory", lambda: mem)
    monkeypatch.setattr(psutil, "disk_io_counters", lambda: disk)
    monkeypatch.setattr(psutil, "net_io_counters", lambda: net)


def _mem(percent: float = 41.0) -> SimpleNamespace:
    return SimpleNamespace(percent=percent, used=8 * 1024**3, total=16 * 1024**3)


class TestRateMath:
    def test_first_sample_has_zero_rates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        clock = FakeClock(10.0)
        _patch_metrics(
            monkeypatch,
            cpu=20.0,
            per_core=[10.0, 30.0],
            mem=_mem(),
            disk=SimpleNamespace(read_bytes=1000, write_bytes=2000),
            net=SimpleNamespace(bytes_sent=500, bytes_recv=900),
        )
        sampler = Sampler(clock=clock)
        sample = sampler.sample_metrics()
        assert sample.disk_read_rate == 0.0
        assert sample.net_recv_rate == 0.0

    def test_rate_is_delta_over_elapsed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        clock = FakeClock(10.0)
        _patch_metrics(
            monkeypatch,
            cpu=20.0,
            per_core=[10.0, 30.0],
            mem=_mem(),
            disk=SimpleNamespace(read_bytes=1000, write_bytes=2000),
            net=SimpleNamespace(bytes_sent=500, bytes_recv=900),
        )
        sampler = Sampler(clock=clock)
        sampler.sample_metrics()  # prime previous counters

        clock.now = 12.0  # 2 seconds later
        _patch_metrics(
            monkeypatch,
            cpu=25.0,
            per_core=[20.0, 30.0],
            mem=_mem(),
            disk=SimpleNamespace(read_bytes=3000, write_bytes=2000),
            net=SimpleNamespace(bytes_sent=500, bytes_recv=1900),
        )
        sample = sampler.sample_metrics()
        assert sample.disk_read_rate == (3000 - 1000) / 2.0  # 1000 B/s
        assert sample.disk_write_rate == 0.0
        assert sample.net_recv_rate == (1900 - 900) / 2.0    # 500 B/s

    def test_negative_delta_clamps_to_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        clock = FakeClock(10.0)
        _patch_metrics(
            monkeypatch,
            cpu=20.0,
            per_core=[10.0],
            mem=_mem(),
            disk=SimpleNamespace(read_bytes=5000, write_bytes=5000),
            net=SimpleNamespace(bytes_sent=100, bytes_recv=100),
        )
        sampler = Sampler(clock=clock)
        sampler.sample_metrics()

        clock.now = 11.0
        _patch_metrics(  # counters reset lower → negative delta
            monkeypatch,
            cpu=20.0,
            per_core=[10.0],
            mem=_mem(),
            disk=SimpleNamespace(read_bytes=10, write_bytes=10),
            net=SimpleNamespace(bytes_sent=1, bytes_recv=1),
        )
        sample = sampler.sample_metrics()
        assert sample.disk_read_rate == 0.0
        assert sample.net_sent_rate == 0.0

    def test_disk_counters_none_is_handled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        clock = FakeClock(10.0)
        _patch_metrics(
            monkeypatch,
            cpu=20.0,
            per_core=[10.0],
            mem=_mem(),
            disk=None,  # some systems expose no disk counters
            net=SimpleNamespace(bytes_sent=1, bytes_recv=1),
        )
        sampler = Sampler(clock=clock)
        sample = sampler.sample_metrics()
        assert sample.disk_read_rate == 0.0
        assert sample.disk_write_rate == 0.0


class TestNetInterfaces:
    @staticmethod
    def _patch(monkeypatch: pytest.MonkeyPatch, nics: dict) -> None:
        monkeypatch.setattr(psutil, "net_io_counters", lambda pernic=False: nics)

    def test_first_sample_rates_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch(monkeypatch, {
            "eth0": SimpleNamespace(bytes_sent=1000, bytes_recv=2000),
        })
        result = Sampler(clock=FakeClock(5.0)).sample_net_interfaces()
        assert result[0].name == "eth0"
        assert result[0].sent_rate == 0.0
        assert result[0].recv_rate == 0.0

    def test_rate_is_per_nic_delta(self, monkeypatch: pytest.MonkeyPatch) -> None:
        clock = FakeClock(5.0)
        self._patch(monkeypatch, {
            "eth0": SimpleNamespace(bytes_sent=1000, bytes_recv=2000),
            "wifi": SimpleNamespace(bytes_sent=10, bytes_recv=10),
        })
        sampler = Sampler(clock=clock)
        sampler.sample_net_interfaces()  # prime

        clock.now = 7.0  # +2s
        self._patch(monkeypatch, {
            "eth0": SimpleNamespace(bytes_sent=1000, bytes_recv=6000),
            "wifi": SimpleNamespace(bytes_sent=10, bytes_recv=10),
        })
        rates = {r.name: r for r in sampler.sample_net_interfaces()}
        assert rates["eth0"].recv_rate == (6000 - 2000) / 2.0  # 2000 B/s
        assert rates["eth0"].sent_rate == 0.0
        assert rates["wifi"].recv_rate == 0.0


class TestMetricsValues:
    def test_cpu_and_memory_passthrough(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_metrics(
            monkeypatch,
            cpu=23.0,
            per_core=[10.0, 36.0],
            mem=_mem(percent=41.0),
            disk=SimpleNamespace(read_bytes=0, write_bytes=0),
            net=SimpleNamespace(bytes_sent=0, bytes_recv=0),
        )
        sampler = Sampler(clock=FakeClock())
        sample = sampler.sample_metrics()
        assert sample.cpu_overall == 23.0
        assert sample.cpu_per_core == (10.0, 36.0)
        assert sample.mem_percent == 41.0
        assert sample.mem_total == 16 * 1024**3


class FakeProc:
    def __init__(self, info: dict, raises: type[Exception] | None = None) -> None:
        self._info = info
        self._raises = raises

    @property
    def info(self) -> dict:
        if self._raises is not None:
            raise self._raises(self._info.get("pid", 0))
        return self._info


class TestProcessSampling:
    @pytest.fixture(autouse=True)
    def _no_real_connections(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Default the boundary call to empty so tests never touch the real OS;
        # individual tests override this to exercise connection attribution.
        monkeypatch.setattr(psutil, "net_connections", lambda kind="inet": [])

    def test_maps_processes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        procs = [
            FakeProc({
                "pid": 1, "name": "python.exe", "cpu_percent": 12.5,
                "memory_info": SimpleNamespace(rss=4096),
            }),
            FakeProc({
                "pid": 2, "name": "explorer.exe", "cpu_percent": 1.0,
                "memory_info": SimpleNamespace(rss=8192),
            }),
        ]
        monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: iter(procs))
        sampler = Sampler(clock=FakeClock())
        result = sampler.sample_processes()
        assert [p.pid for p in result] == [1, 2]
        assert result[0].mem_rss == 4096

    def test_skips_access_denied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        procs = [
            FakeProc({"pid": 1, "name": "ok.exe", "cpu_percent": 0.0,
                      "memory_info": SimpleNamespace(rss=1)}),
            FakeProc({"pid": 2}, raises=psutil.AccessDenied),
            FakeProc({"pid": 3}, raises=psutil.NoSuchProcess),
        ]
        monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: iter(procs))
        sampler = Sampler(clock=FakeClock())
        result = sampler.sample_processes()
        assert [p.pid for p in result] == [1]

    def test_partitions_mapped_and_unreadable_skipped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        parts = [
            SimpleNamespace(mountpoint="C:\\", fstype="NTFS"),
            SimpleNamespace(mountpoint="D:\\", fstype=""),  # empty CD drive
        ]
        monkeypatch.setattr(psutil, "disk_partitions", lambda all=False: parts)

        def disk_usage(mount: str) -> SimpleNamespace:
            if mount == "D:\\":
                raise PermissionError("no media")
            return SimpleNamespace(total=500, used=200, percent=40.0)

        monkeypatch.setattr(psutil, "disk_usage", disk_usage)
        result = Sampler(clock=FakeClock()).sample_partitions()
        assert [p.mountpoint for p in result] == ["C:\\"]
        assert result[0].percent == 40.0
        assert result[0].used == 200

    def test_connection_counts_attributed_to_pids(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        procs = [
            FakeProc({"pid": 1, "name": "browser.exe", "cpu_percent": 0.0,
                      "memory_info": SimpleNamespace(rss=1)}),
            FakeProc({"pid": 2, "name": "idle.exe", "cpu_percent": 0.0,
                      "memory_info": SimpleNamespace(rss=1)}),
        ]
        monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: iter(procs))
        conns = [
            SimpleNamespace(pid=1), SimpleNamespace(pid=1),
            SimpleNamespace(pid=1), SimpleNamespace(pid=None),  # None PID skipped
        ]
        monkeypatch.setattr(psutil, "net_connections", lambda kind="inet": conns)
        result = {p.pid: p for p in Sampler(clock=FakeClock()).sample_processes()}
        assert result[1].conn_count == 3
        assert result[2].conn_count == 0

    def test_connection_counts_denied_yields_zero(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        procs = [FakeProc({"pid": 1, "name": "x.exe", "cpu_percent": 0.0,
                           "memory_info": SimpleNamespace(rss=1)})]
        monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: iter(procs))

        def denied(kind: str = "inet"):
            raise psutil.AccessDenied()

        monkeypatch.setattr(psutil, "net_connections", denied)
        result = Sampler(clock=FakeClock()).sample_processes()
        assert result[0].conn_count == 0

    def test_missing_name_falls_back(self, monkeypatch: pytest.MonkeyPatch) -> None:
        procs = [FakeProc({"pid": 5, "name": None, "cpu_percent": None,
                           "memory_info": None})]
        monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: iter(procs))
        sampler = Sampler(clock=FakeClock())
        result = sampler.sample_processes()
        assert result[0].name == "?"
        assert result[0].cpu_percent == 0.0
        assert result[0].mem_rss == 0

    def test_enriched_fields_mapped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        procs = [FakeProc({
            "pid": 7, "name": "svc.exe", "cpu_percent": 3.0,
            "memory_info": SimpleNamespace(rss=2048),
            "status": "running", "num_threads": 12,
            "username": "DESKTOP-ABC\\Tejas", "create_time": 1700.0,
        })]
        monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: iter(procs))
        result = Sampler(clock=FakeClock()).sample_processes()
        proc = result[0]
        assert proc.status == "running"
        assert proc.num_threads == 12
        assert proc.username == "Tejas"          # DOMAIN\ prefix stripped
        assert proc.create_time == 1700.0

    def test_enriched_fields_default_when_absent(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        procs = [FakeProc({"pid": 8, "name": "x", "cpu_percent": 0.0,
                           "memory_info": None})]
        monkeypatch.setattr(psutil, "process_iter", lambda attrs=None: iter(procs))
        proc = Sampler(clock=FakeClock()).sample_processes()[0]
        assert proc.status == ""
        assert proc.num_threads == 0
        assert proc.username == ""
        assert proc.create_time == 0.0
