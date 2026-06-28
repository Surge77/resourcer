"""Tests for GPU sampling with an injected fake NVML — no real driver needed."""

from __future__ import annotations

from resourcer.metrics.gpu import GpuSampler, _read_gpu


class _NVMLError(Exception):
    pass


class _Util:
    gpu = 37
    memory = 12


class _Mem:
    used = 2_000_000_000
    total = 4_000_000_000


class FakeNvml:
    """Minimal NVML stand-in. ``fan_supported`` toggles the NotSupported path."""

    NVMLError = _NVMLError
    NVML_TEMPERATURE_GPU = 0

    def __init__(self, count: int = 1, fan_supported: bool = True) -> None:
        self._count = count
        self._fan_supported = fan_supported
        self.init_called = False
        self.shutdown_called = False

    def nvmlInit(self) -> None:
        self.init_called = True

    def nvmlShutdown(self) -> None:
        self.shutdown_called = True

    def nvmlDeviceGetCount(self) -> int:
        return self._count

    def nvmlDeviceGetHandleByIndex(self, index: int) -> int:
        return index

    def nvmlDeviceGetName(self, handle: int) -> str:
        return "NVIDIA Test GPU"

    def nvmlDeviceGetUtilizationRates(self, handle: int) -> _Util:
        return _Util()

    def nvmlDeviceGetMemoryInfo(self, handle: int) -> _Mem:
        return _Mem()

    def nvmlDeviceGetTemperature(self, handle: int, sensor: int) -> int:
        return 55

    def nvmlDeviceGetFanSpeed(self, handle: int) -> int:
        if not self._fan_supported:
            raise _NVMLError("not supported")
        return 42

    def nvmlDeviceGetPowerUsage(self, handle: int) -> int:
        return 75_000  # milliwatts


def test_read_gpu_parses_all_fields() -> None:
    info = _read_gpu(FakeNvml(), 0)
    assert info.name == "NVIDIA Test GPU"
    assert info.util_percent == 37.0
    assert info.mem_percent == 50.0
    assert info.temp_c == 55.0
    assert info.fan_percent == 42.0
    assert info.power_w == 75.0


def test_unsupported_sensor_reported_as_none() -> None:
    info = _read_gpu(FakeNvml(fan_supported=False), 0)
    assert info.fan_percent is None
    assert info.temp_c == 55.0  # others still read


def test_sampler_lifecycle_with_fake() -> None:
    fake = FakeNvml(count=2)
    sampler = GpuSampler(nvml=fake)
    assert sampler.start() is True
    assert fake.init_called is True
    gpus = sampler.sample()
    assert len(gpus) == 2
    sampler.shutdown()
    assert fake.shutdown_called is True


def test_sample_empty_before_start() -> None:
    assert GpuSampler(nvml=FakeNvml()).sample() == []


def test_start_returns_false_when_init_fails() -> None:
    class Failing(FakeNvml):
        def nvmlInit(self) -> None:
            raise _NVMLError("driver missing")

    assert GpuSampler(nvml=Failing()).start() is False
