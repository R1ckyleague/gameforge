"""
GPU usage monitoring with auto-detect for NVIDIA, AMD and Intel.

Priority:
  1. nvidia-smi  (NVIDIA, fast, no overhead)
  2. Windows PDH counters via win32pdh  (all vendors, fast after first call)
  3. PowerShell fallback  (all vendors, ~500 ms per call)
"""
import subprocess
import threading
import time
from typing import Callable, Optional

# ---------------------------------------------------------------------------
# GPU usage backends
# ---------------------------------------------------------------------------

def _nvidia_usage() -> Optional[float]:
    """Query NVIDIA GPU load via nvidia-smi."""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=3,
        )
        if r.returncode == 0:
            vals = [float(v) for v in r.stdout.strip().splitlines() if v.strip()]
            return max(vals, default=0.0)
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError):
        pass
    return None


def _pdh_usage_win32() -> Optional[float]:
    """Query GPU engine utilization using the win32pdh PDH wrapper."""
    try:
        import win32pdh  # noqa: PLC0415

        query = win32pdh.OpenQuery()
        counter = win32pdh.AddCounter(
            query,
            r"\GPU Engine(*)\Utilization Percentage",
        )
        win32pdh.CollectQueryData(query)
        time.sleep(0.05)
        win32pdh.CollectQueryData(query)

        _, items = win32pdh.GetFormattedCounterArray(counter, win32pdh.PDH_FMT_DOUBLE)
        total = sum(v for _, v in items if v > 0)
        win32pdh.CloseQuery(query)
        return min(100.0, total)
    except Exception:
        return None


def _pdh_usage_powershell() -> Optional[float]:
    """Fallback: query GPU utilisation via a one-liner PowerShell command."""
    try:
        ps = (
            "try {"
            "  $s = (Get-Counter '\\GPU Engine(*)\\Utilization Percentage'"
            "         -ErrorAction Stop).CounterSamples;"
            "  ($s | Measure-Object -Property CookedValue -Sum).Sum"
            "} catch { 0 }"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=8,
        )
        val = r.stdout.strip()
        return min(100.0, float(val)) if val else None
    except (subprocess.TimeoutExpired, ValueError):
        return None


# ---------------------------------------------------------------------------
# Monitor class
# ---------------------------------------------------------------------------

class GPUMonitor:
    """
    Polls GPU load in a background thread and fires callbacks when load
    crosses *threshold* (percent).

    on_high  — called once when load rises above threshold
    on_low   — called once when load drops back below threshold
    """

    def __init__(
        self,
        *,
        threshold: int = 25,
        interval: int = 3,
        on_high: Optional[Callable] = None,
        on_low: Optional[Callable] = None,
    ) -> None:
        self.threshold = threshold
        self.interval = interval
        self.on_high = on_high
        self.on_low = on_low

        self._running = False
        self._above = False
        self._thread: Optional[threading.Thread] = None
        self._has_nvidia = self._detect_nvidia()
        self._has_win32pdh = self._detect_win32pdh()

    # ------------------------------------------------------------------ public

    def usage(self) -> float:
        """Return current GPU usage in the range 0–100."""
        if self._has_nvidia:
            v = _nvidia_usage()
            if v is not None:
                return v
        if self._has_win32pdh:
            v = _pdh_usage_win32()
            if v is not None:
                return v
        v = _pdh_usage_powershell()
        return v if v is not None else 0.0

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="gpu-monitor"
        )
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    # ----------------------------------------------------------------- private

    def _detect_nvidia(self) -> bool:
        try:
            subprocess.run(["nvidia-smi"], capture_output=True, timeout=3)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def _detect_win32pdh(self) -> bool:
        try:
            import win32pdh  # noqa: F401, PLC0415
            return True
        except ImportError:
            return False

    def _loop(self) -> None:
        while self._running:
            try:
                u = self.usage()
                if u >= self.threshold and not self._above:
                    self._above = True
                    if self.on_high:
                        self.on_high()
                elif u < self.threshold and self._above:
                    self._above = False
                    if self.on_low:
                        self.on_low()
            except Exception:
                pass
            time.sleep(self.interval)
