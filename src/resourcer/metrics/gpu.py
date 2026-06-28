"""NVIDIA GPU sensors via NVML (pynvml). Degrades to empty when unavailable.

NVML only sees NVIDIA devices; integrated Intel/AMD GPUs are invisible here. The
NVML library is loaded from the installed driver at runtime — we bundle no native
binary. Optional per-device readings (temperature, fan, power) raise
``NVMLError_NotSupported`` on hardware that lacks them, so each is read behind a
guard and reported as ``None``. The ``nvml`` module is injectable for testing.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from .models import GpuInfo


def _guard(nvml: Any, read: Callable[[], float]) -> Optional[float]:
    """Return a reading, or None if this device doesn't support it."""
    try:
        return read()
    except nvml.NVMLError:
        return None


def _read_gpu(nvml: Any, index: int) -> GpuInfo:
    handle = nvml.nvmlDeviceGetHandleByIndex(index)
    name = nvml.nvmlDeviceGetName(handle)
    if isinstance(name, bytes):
        name = name.decode("utf-8", "replace")
    util = nvml.nvmlDeviceGetUtilizationRates(handle)
    mem = nvml.nvmlDeviceGetMemoryInfo(handle)
    mem_total = int(mem.total)
    mem_used = int(mem.used)
    mem_percent = (mem_used / mem_total * 100.0) if mem_total else 0.0
    return GpuInfo(
        index=index,
        name=str(name),
        util_percent=float(util.gpu),
        mem_used=mem_used,
        mem_total=mem_total,
        mem_percent=mem_percent,
        temp_c=_guard(
            nvml,
            lambda: float(nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU)),
        ),
        fan_percent=_guard(nvml, lambda: float(nvml.nvmlDeviceGetFanSpeed(handle))),
        power_w=_guard(nvml, lambda: nvml.nvmlDeviceGetPowerUsage(handle) / 1000.0),
    )


class GpuSampler:
    def __init__(self, nvml: Any | None = None) -> None:
        self._nvml = nvml
        self._ready = False

    def start(self) -> bool:
        """Initialise NVML; return False (and stay inert) if it isn't available."""
        if self._nvml is None:
            try:
                import pynvml  # provided by the nvidia-ml-py package

                self._nvml = pynvml
            except ImportError:
                return False
        try:
            self._nvml.nvmlInit()
        except self._nvml.NVMLError:
            return False
        self._ready = True
        return True

    def sample(self) -> list[GpuInfo]:
        if not self._ready or self._nvml is None:
            return []
        try:
            count = self._nvml.nvmlDeviceGetCount()
            return [_read_gpu(self._nvml, i) for i in range(count)]
        except self._nvml.NVMLError:
            return []

    def shutdown(self) -> None:
        if self._ready and self._nvml is not None:
            try:
                self._nvml.nvmlShutdown()
            except self._nvml.NVMLError:
                pass
            self._ready = False
