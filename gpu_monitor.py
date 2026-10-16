# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
GPU Monitoring Module (MetaX / MXSML)
Supports MetaX (MXC / MXN) devices via the MXSML management library.

The output data protocol is kept identical to ``gpu_monitor_nvidia.py`` so that
the rest of the application (UI, history handling, ...) can consume it without
any change.

Protocol (per ``NVMLMonitor.get_stats`` / ``_get_fallback_stats``)::

    {
        "platform": str,            # e.g. "MetaX (MXSML)" / "MetaX ... (monitoring unavailable)"
        "gpu_name": str,
        "product_name": str,        # optional extra field (DGX Spark / branded PC / board name)
        "gpu_percent": float,       # 0-100, 0 when unavailable
        "vram_used_gb": float,
        "vram_total_gb": float,
        "vram_percent": float,
        "temp_c": float | None,
        "power_w": float | None,
        # CPU / RAM block, always present
        "cpu_percent": float,
        "cpu_model": str,
        "ram_used_gb": float,
        "ram_total_gb": float,
        "ram_percent": float,
        "hostname": str,
    }

Unit notes for MXSML (per the MXSML documentation):
    - memory info            : KB
    - temperature            : 0.01 degree Celsius
    - pmbus / board power    : mV / mA / mW
    - usage (DLA / XCORE ...): percentage (0-100)
"""

import logging
import os
import platform
import socket
import subprocess
from abc import ABC, abstractmethod
from collections import deque
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional dependency: psutil (CPU / RAM stats)
# ---------------------------------------------------------------------------
try:
    import psutil
except ImportError:  # pragma: no cover - psutil is a hard requirement in production
    psutil = None


# ---------------------------------------------------------------------------
# MXSML backend abstraction
# ---------------------------------------------------------------------------
MXSML_AVAILABLE = False
MXSML_IMPORT_ERROR: Optional[Exception] = None
mxsml = None

try:  # pragma: no cover - depends on the target machine
    from pymxsml import mxsml as mxsml  # type: ignore

    MXSML_AVAILABLE = True
except Exception as exc:  # pragma: no cover
    MXSML_IMPORT_ERROR = exc


def set_mxsml_backend(backend) -> None:
    """
    Inject a MXSML-compatible backend module.

    This is mainly used by the mock test-suite: because the real MXSML library
    can only be loaded on a machine with MetaX hardware (see
    ``pymxsml.mxsml._loadMxsmlLibrary``), ``gpu_monitor`` gets the module
    injected instead of importing the real one.

    Args:
        backend: a module (or object) exposing the same API as
                 ``pymxsml.mxsml``, e.g. ``mocks.mxsml_mock``.
    """
    global mxsml, MXSML_AVAILABLE, MXSML_IMPORT_ERROR
    mxsml = backend
    MXSML_AVAILABLE = backend is not None
    MXSML_IMPORT_ERROR = None


def _get_mxsml():
    """Return the currently active MXSML backend module (or None)."""
    if mxsml is not None:
        return mxsml

    # Lazy import: only touch the real library when no mock has been injected.
    try:  # pragma: no cover - depends on the target machine
        from pymxsml import mxsml as _mxsml  # type: ignore

        return _mxsml
    except Exception as exc:  # pragma: no cover
        global MXSML_IMPORT_ERROR
        MXSML_IMPORT_ERROR = exc
        return None


def is_mxsml_available() -> bool:
    """
    Return True when a MXSML backend is usable without initializing it.

    Used by the factory (mirroring ``import pynvml`` in the NVIDIA version) so
    that ``create_monitor()`` can decide whether MetaX monitoring is possible
    before constructing a monitor instance.

    Note: this only checks that the Python bindings *can* be imported; the
    native ``libmxsml.so`` is loaded lazily by ``mxSmlInit()``.
    """
    return _get_mxsml() is not None


def get_cpu_model() -> str:
    """
    Get CPU model name in a cross-platform way

    Returns:
        CPU model string, or 'Unknown CPU' if not available
    """
    try:
        system = platform.system()

        if system == "Linux":
            try:
                with open("/proc/cpuinfo", "r") as f:
                    for line in f:
                        if line.startswith("model name"):
                            cpu_name = line.split(":")[1].strip()
                            cpu_name = (
                                cpu_name.replace("(R)", "")
                                .replace("(TM)", "")
                                .replace("(r)", "")
                                .replace("(tm)", "")
                            )
                            cpu_name = cpu_name.replace("  ", " ").strip()
                            return cpu_name
            except Exception:
                pass

        elif system == "Darwin":  # macOS
            try:
                result = subprocess.run(
                    ["sysctl", "-n", "machdep.cpu.brand_string"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip()
            except Exception:
                pass

        elif system == "Windows":
            try:
                result = subprocess.run(
                    ["wmic", "cpu", "get", "name"], capture_output=True, text=True, timeout=1
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split("\n")
                    if len(lines) > 1:
                        return lines[1].strip()
            except Exception:
                pass

        proc = platform.processor()
        if proc and proc.strip():
            return proc.strip()

        return "Unknown CPU"

    except Exception as e:
        logger.warning(f"Failed to get CPU model: {e}")
        return "Unknown CPU"


def get_system_product_info() -> Dict[str, Optional[str]]:
    """
    Get system product information from DMI (Desktop Management Interface)

    Returns:
        Dictionary with keys:
        - product_name: System product name
        - vendor: System vendor/manufacturer
        - board_name: Motherboard name
        - board_vendor: Motherboard vendor
        - display_name: Best descriptive name to show (prioritizes meaningful names)
    """
    result = {
        "product_name": None,
        "vendor": None,
        "board_name": None,
        "board_vendor": None,
        "display_name": None,
    }

    if platform.system() != "Linux":
        return result

    dmi_base = "/sys/class/dmi/id"

    generic_names = {
        "System Product Name",
        "To be filled by O.E.M.",
        "To Be Filled By O.E.M.",
        "Default string",
        "Not Specified",
        "Unknown",
        "",
    }

    try:
        try:
            with open(f"{dmi_base}/product_name", "r") as f:
                result["product_name"] = f.read().strip()
        except Exception:
            pass

        try:
            with open(f"{dmi_base}/sys_vendor", "r") as f:
                result["vendor"] = f.read().strip()
        except Exception:
            pass

        try:
            with open(f"{dmi_base}/board_name", "r") as f:
                result["board_name"] = f.read().strip()
        except Exception:
            pass

        try:
            with open(f"{dmi_base}/board_vendor", "r") as f:
                result["board_vendor"] = f.read().strip()
        except Exception:
            pass

        product = result["product_name"] if result["product_name"] not in generic_names else None
        board = result["board_name"] if result["board_name"] not in generic_names else None

        if product:
            display_name = product
            if result["vendor"]:
                vendor_source = result["vendor"]
            else:
                vendor_source = result["board_vendor"]
        elif board:
            display_name = board
            vendor_source = result["board_vendor"]
        else:
            vendor_source = None
            display_name = None

        if display_name and vendor_source:
            vendor_clean = (
                vendor_source.replace(" Inc.", "")
                .replace(", Inc.", "")
                .replace(" Corporation", "")
                .replace("COMPUTER", "")
                .replace("INC.", "")
                .strip()
            )
            vendor_clean = vendor_clean.replace("ASUSTeK", "ASUS")

            if (
                vendor_clean
                and len(vendor_clean) > 2
                and vendor_clean.lower() not in display_name.lower()
            ):
                if any(
                    v in vendor_clean
                    for v in ["Dell", "HP", "Lenovo", "Acer", "ASUS", "Gigabyte", "MSI", "ASRock"]
                ):
                    display_name = f"{vendor_clean} {display_name}"

        result["display_name"] = display_name

        logger.debug(f"DMI Info: {result}")

    except Exception as e:
        logger.debug(f"Could not read DMI info: {e}")

    return result


class GPUMonitor(ABC):
    """Abstract base class for GPU monitoring"""

    def __init__(self, history_size: int = 60):
        """
        Initialize GPU monitor

        Args:
            history_size: Number of historical data points to keep (default 60 = 1 minute at 1Hz)
        """
        self.history_size = history_size
        self.gpu_util_history = deque(maxlen=history_size)
        self.vram_used_history = deque(maxlen=history_size)
        self.cpu_util_history = deque(maxlen=history_size)
        self.ram_used_history = deque(maxlen=history_size)

    @abstractmethod
    def get_stats(self) -> Dict:
        """Get current GPU and system stats"""
        pass

    @abstractmethod
    def cleanup(self):
        """Cleanup resources"""
        pass

    def init(self) -> "GPUMonitor":
        """
        Idempotent initialization hook.

        The monitor is normally initialized in ``__init__``; this method exists
        so that server-style code (``on_startup``) can explicitly (re)initialize
        monitoring resources without caring about the concrete implementation.
        Calling it multiple times is safe and cheap.
        """
        return self

    def get_cpu_ram_stats(self) -> Dict:
        """Get CPU and RAM stats (common across all platforms)"""
        try:
            if psutil is None:
                raise RuntimeError("psutil is not installed")

            cpu_percent = psutil.cpu_percent(interval=None)
            memory = psutil.virtual_memory()
            hostname = socket.gethostname()
            cpu_model = get_cpu_model()

            return {
                "cpu_percent": cpu_percent,
                "cpu_model": cpu_model,
                "ram_used_gb": memory.used / (1024**3),
                "ram_total_gb": memory.total / (1024**3),
                "ram_percent": memory.percent,
                "hostname": hostname,
            }
        except Exception as e:
            logger.error(f"Error getting CPU/RAM stats: {e}")
            return {
                "cpu_percent": 0,
                "cpu_model": "Unknown CPU",
                "ram_used_gb": 0,
                "ram_total_gb": 0,
                "ram_percent": 0,
                "hostname": socket.gethostname() if hasattr(socket, "gethostname") else "Unknown",
            }

    def update_history(self, stats: Dict):
        """Update historical data"""
        self.gpu_util_history.append(stats.get("gpu_percent", 0) or 0)
        self.vram_used_history.append(stats.get("vram_used_gb", 0) or 0)
        self.cpu_util_history.append(stats.get("cpu_percent", 0) or 0)
        self.ram_used_history.append(stats.get("ram_used_gb", 0) or 0)

    def get_history(self) -> Dict[str, List[float]]:
        """Get historical data as lists"""
        return {
            "gpu_util": list(self.gpu_util_history),
            "vram_used": list(self.vram_used_history),
            "cpu_util": list(self.cpu_util_history),
            "ram_used": list(self.ram_used_history),
        }

    @staticmethod
    def aggregate_stats(devices: List[Dict]) -> Dict:
        """
        Aggregate per-GPU stats into the single-GPU protocol shape.

        The UI keeps consuming one flat record, but the GPU fields now describe
        **all** devices:

        - ``gpu_percent``    : average utilization across all GPUs
        - ``vram_used_gb``   : sum of used VRAM across all GPUs
        - ``vram_total_gb``  : sum of total VRAM across all GPUs
        - ``vram_percent``   : ``vram_used_gb / vram_total_gb * 100``

        The average is taken over the GPUs that actually reported a utilization
        (``None`` metrics are skipped), so an unsupported device does not drag
        the average towards zero.

        Args:
            devices: list of per-GPU dicts (each must contain ``gpu_percent``,
                     ``vram_used_gb``, ``vram_total_gb``)

        Returns:
            ``{}`` when no device is given, otherwise the aggregate fields plus
            ``device_count``, ``vm_total`` and ``vm_used_all``.
        """
        if not devices:
            return {}

        utils = []
        sum_used = 0.0
        sum_total = 0.0
        device_count = 0
        vm_total = 0.0
        vm_used_all = 0.0

        for dev in devices:
            device_count += 1

            gpu_percent = dev.get("gpu_percent")
            if gpu_percent is not None:
                utils.append(float(gpu_percent))

            # Sum VRAM over every device, treating unavailable as 0 so that one
            # unsupported GPU does not wipe out the whole cluster total.
            sum_used += float(dev.get("vram_used_gb") or 0)
            sum_total += float(dev.get("vram_total_gb") or 0)

            # Optional richer breakdown maintained by subclasses.
            for key, target in (
                ("vm_total_gb", "vm_total"),
                ("vm_used_all_gb", "vm_used_all"),
            ):
                value = dev.get(key)
                if value is None:
                    continue
                if target == "vm_total":
                    vm_total += float(value)
                else:
                    vm_used_all += float(value)

        return {
            "gpu_percent": round(sum(utils) / len(utils), 2) if utils else 0,
            "vram_used_gb": sum_used,
            "vram_total_gb": sum_total,
            "vram_percent": round(sum_used / sum_total * 100, 1) if sum_total > 0 else 0,
            "device_count": device_count,
            "vm_total": vm_total,
            "vm_used_all": vm_used_all,
        }

    def get_gpu_stats(self) -> List[Dict]:
        """
        Return per-GPU stats as a list.

        The base implementation returns a single-element list built from
        ``get_stats()`` so that single-GPU monitors (and mocks) still satisfy the
        interface. Multi-GPU monitors override this.

        Returns:
            list of per-GPU dicts with at least ``gpu_percent``,
            ``vram_used_gb``, ``vram_total_gb`` and ``vram_percent``.
        """
        try:
            stats = self.get_stats()
        except Exception as e:
            logger.error(f"Error getting GPU stats: {e}")
            return []

        if not stats:
            return []

        return [
            {
                "index": 0,
                "device_id": stats.get("device_id", 0),
                "gpu_name": stats.get("gpu_name", "N/A"),
                "gpu_percent": stats.get("gpu_percent", 0),
                "vram_used_gb": stats.get("vram_used_gb", 0),
                "vram_total_gb": stats.get("vram_total_gb", 0),
                "vram_percent": stats.get("vram_percent", 0),
                "temp_c": stats.get("temp_c"),
                "power_w": stats.get("power_w"),
                "uuid": stats.get("uuid", ""),
                "bdf_id": stats.get("bdf_id", ""),
            }
        ]


class MXSMLMonitor(GPUMonitor):
    """
    MetaX GPU monitoring using MXSML (MetaX System Management Library).

    Monitors **all** MetaX GPUs on the host and exposes them through the flat
    single-GPU protocol plus a per-device breakdown (``gpus`` / ``gpu_count``):

    - ``gpu_percent``   : **average** utilization across all GPUs
    - ``vram_used_gb``  : **sum** of used VRAM across all GPUs
    - ``vram_total_gb`` : **sum** of total VRAM across all GPUs
    - ``gpus``          : list of per-GPU dicts (index / name / util / vram / temp / power)

    Notes:
        - ``mxSmlGetDeviceCount()`` enumerates native (bare-metal) / VF devices,
          whose ids start at 0. PF (physical function) devices are reported with
          ids offset by 100 (``100 + index``). PF devices cannot report memory,
          so their VRAM is simply excluded from the sums.
        - Memory, temperature and power are reported by the raw device APIs.
          Some of them are not supported on every device class (N-class / C-class /
          VF / PF), therefore every metric is read defensively and falls back to
          ``None`` (or ``0``) when unavailable.
        - Clocks / power need ``set_dpm_max_perf_level()`` (or sudo) on some
          MetaX boards; without it the kernel driver may report 0 MHz / NaN.
    """

    # PF device id offset (see mxsml_demo.py: ``idx + 100``)
    PF_DEVICE_ID_OFFSET = 100

    # Try these usage IPs in order when computing GPU utilization
    _USAGE_FALLBACK_ORDER = ("MXSML_USAGE_XCORE", "MXSML_USAGE_MMA", "MXSML_USAGE_VPUD")

    # DPM levels are 0..max (see the mxsml C++ demo)
    _DPM_MAX_LEVEL = 9

    def __init__(
        self,
        device_index: Optional[int] = None,
        history_size: int = 60,
        device_ids: Optional[List[int]] = None,
        devices: Optional[List[int]] = None,
    ):
        """
        Initialize the MXSML monitor

        Args:
            device_index: Restrict monitoring to a single device index. ``None``
                          (default) monitors **every** MetaX GPU in the system.
            history_size: Number of historical data points to keep
            device_ids:   Explicit list of MXSML device ids to monitor. When
                          given, it takes precedence over ``device_index``.
            devices:      Alias of ``device_ids`` (accepted for compatibility).
        """
        super().__init__(history_size)

        # Selected MXSML device ids (raw ids: native 0-based, PF offset by 100)
        self.device_ids: List[int] = []
        # Number of devices exposed to the UI, capped at 8 (GPU01..GPU08)
        self.max_devices = 8
        self.device_counts: Dict[str, int] = {}

        # Single-device identifiers (first monitored device, kept for
        # backwards compatibility with the original single-GPU protocol)
        self.device_id: Optional[int] = None
        self.device_name = "N/A"
        self.uuid = ""
        self.bdf_id = ""
        self.die_count = 0

        self.available = False
        self.error_logged = False
        self.consecutive_errors = 0
        self.stats_call_count = 0
        self.vram_warning_logged = False
        self.dpm_warning_logged = False

        self.maca_version = ""
        self.driver_version = ""

        # Product / board name (DMI fallback when not a DGX-like system)
        self.product_name = ""
        dmi_info = get_system_product_info()
        if dmi_info["display_name"]:
            self.product_name = dmi_info["display_name"]

        lib = _get_mxsml()

        if lib is None:
            logger.warning(f"MXSML not available: {MXSML_IMPORT_ERROR}")
            self.available = False
            self.error_logged = True
            return

        try:
            lib.mxSmlInit()

            try:
                self.maca_version = lib.mxSmlGetMacaVersion()
            except Exception:
                self.maca_version = ""

            device_count = lib.mxSmlGetDeviceCount()
            pf_count = 0
            try:
                pf_count = lib.mxSmlGetPfDeviceCount()
            except Exception:
                pf_count = 0

            all_device_ids = list(range(device_count)) + [
                self.PF_DEVICE_ID_OFFSET + i for i in range(pf_count)
            ]

            if not all_device_ids:
                logger.warning("MXSML initialized but no MetaX device found")
                self.available = False
                self.error_logged = True
                return

            # ---- resolve which devices to monitor -------------------------
            explicit = device_ids if device_ids is not None else devices

            if explicit is not None:
                self.device_ids = [int(d) for d in explicit]
            elif device_index is not None:
                # Restrict to a single device (index into all_device_ids)
                if 0 <= device_index < len(all_device_ids):
                    self.device_ids = [all_device_ids[device_index]]
                else:
                    logger.warning(
                        f"Requested device index {device_index} out of range "
                        f"(found {len(all_device_ids)} devices), falling back to all devices"
                    )
                    self.device_ids = list(all_device_ids)
            else:
                # Default: monitor every device, capped at max_devices
                self.device_ids = list(all_device_ids)

            if len(self.device_ids) > self.max_devices:
                logger.warning(
                    f"Found {len(self.device_ids)} MetaX devices; "
                    f"monitoring the first {self.max_devices} (GPU01-GPU{self.max_devices:02d})"
                )
                self.device_ids = self.device_ids[: self.max_devices]

            # ---- collect per-device info + counts -------------------------
            for device_id in self.device_ids:
                try:
                    device_info = lib.mxSmlGetDeviceInfo(device_id)
                    name = str(device_info.deviceName).strip() or "MetaX GPU"
                    self.device_counts[name] = self.device_counts.get(name, 0) + 1
                except Exception as e:
                    logger.debug(f"Could not read info for device {device_id}: {e}")

            # First device drives the legacy single-device fields
            self.device_id = self.device_ids[0]
            self.device_name = self._device_display_name(self.device_id)
            self.uuid = self._safe(lambda: str(lib.mxSmlGetDeviceInfo(self.device_id).uuid).strip(), "")
            self.bdf_id = self._safe(
                lambda: str(lib.mxSmlGetDeviceInfo(self.device_id).bdfId).strip(), ""
            )
            self.die_count = self._safe(lambda: lib.mxSmlGetDeviceDieCount(self.device_id), 0)
            self.driver_version = self._safe(
                lambda: lib.mxSmlGetDeviceVersion(self.device_id, lib.MXSML_VERSION_DRIVER), ""
            )

            self.available = True
            logger.info(
                f"MXSML initialized - monitoring {len(self.device_ids)} MetaX GPU(s): "
                f"{self.gpu_model_summary()} (device ids {self.device_ids})"
            )
        except Exception as e:
            logger.warning(f"MXSML not available: {e}")
            self.available = False
            self.error_logged = True

    @staticmethod
    def _safe(fn, default=None):
        """Call ``fn`` and return ``default`` on any exception."""
        try:
            return fn()
        except Exception:
            return default

    @staticmethod
    def _gpu_display_name(index: int, count: int, model: str) -> str:
        """
        Build the display name shown for a GPU slot.

        Single GPU:      "MetaX MXC500"
        Multiple GPUs:   "MetaX MXC500 GPU01" / "MetaX MXC500 GPU08"
        """
        model = (model or "MetaX GPU").strip()
        if not model.upper().startswith("METAX"):
            model = f"MetaX {model}"
        if count <= 1:
            return model
        return f"{model} GPU{index + 1:02d}"

    def _device_display_name(self, device_id: int) -> str:
        """Display name for a specific device id (1-based slot when multiple)."""
        lib = _get_mxsml()
        raw = self._safe(lambda: str(lib.mxSmlGetDeviceInfo(device_id).deviceName).strip(), "")
        try:
            slot = self.device_ids.index(device_id)
        except ValueError:
            slot = 0
        return self._gpu_display_name(slot, len(self.device_ids), raw)

    def gpu_model_summary(self) -> str:
        """Human-readable summary, e.g. ``"8x MXC500"`` or ``"MXC500"``."""
        if not self.device_counts:
            return self.device_name
        parts = [f"{count}x {model}" for model, count in self.device_counts.items()]
        return ", ".join(parts)

    def init(self) -> "MXSMLMonitor":
        """Idempotent startup hook (see ``GPUMonitor.init``)."""
        if not self.available:
            # Retry mxSmlInit() in case the driver became ready after the object
            # was constructed (e.g. the service is started before the KMD).
            lib = _get_mxsml()
            if lib is not None:
                try:
                    lib.mxSmlInit()
                    self.available = True
                    self.error_logged = False
                    self.consecutive_errors = 0
                    logger.info(f"MXSML re-initialized for {self.device_name}")
                except Exception as e:
                    logger.warning(f"MXSML re-initialization failed: {e}")
        return self

    # ------------------------------------------------------------------
    # metric helpers (all take an explicit device id)
    # ------------------------------------------------------------------
    def _read_gpu_percent(self, lib, device_id: int) -> Optional[float]:
        """
        Read GPU (core) utilization in percent.

        Prefers the aggregated XCORE usage; falls back to other usage IPs and,
        as a last resort, to the averaged xcore AP usage array.
        """
        # 1) try dedicated usage IPs
        for name in self._USAGE_FALLBACK_ORDER:
            value = getattr(lib, name, None)
            if value is None:
                continue
            try:
                result = lib.mxSmlGetDeviceIpUsage(device_id, value)
                if result is not None:
                    return float(result)
            except Exception:
                continue

        # 2) fall back to averaged xcore AP usage
        try:
            usage = lib.mxSmlGetXcoreApUsage(device_id)
            flat = []
            for item in usage:
                try:
                    flat.extend(list(item))
                except TypeError:
                    flat.append(item)
            if flat:
                return sum(flat) / len(flat)
        except Exception:
            pass

        return None

    def _read_memory(self, lib, device_id: int) -> Dict[str, Optional[float]]:
        """
        Read VRAM usage.

        MXSML reports memory in KB, ``visVramUse/visVramTotal`` is the value
        visible to the current process (VF aware), ``vramUse/vramTotal`` is the
        raw device counter. ``visVram*`` is preferred, with a fallback to
        ``vram*`` (and finally to the per-die memory info for MCM devices).
        """
        info = None
        try:
            info = lib.mxSmlGetMemoryInfo(device_id)
        except Exception as e:
            if not self.vram_warning_logged:
                logger.warning(
                    f"VRAM monitoring not supported on device {device_id} "
                    f"({self._device_display_name(device_id)}): {e}"
                )
                self.vram_warning_logged = True

        used_kb = total_kb = 0
        if info is not None:
            used_kb = getattr(info, "visVramUse", 0) or 0
            total_kb = getattr(info, "visVramTotal", 0) or 0
            if not total_kb:
                used_kb = getattr(info, "vramUse", 0) or 0
                total_kb = getattr(info, "vramTotal", 0) or 0

        # MCM fallback: sum the per-die memory when the device level is empty
        if not total_kb:
            try:
                die_count = lib.mxSmlGetDeviceDieCount(device_id)
                for die_id in range(die_count):
                    die_info = lib.mxSmlGetDieMemoryInfo(device_id, die_id)
                    used_kb += getattr(die_info, "visVramUse", 0) or 0
                    total_kb += getattr(die_info, "visVramTotal", 0) or 0
            except Exception:
                pass

        if not total_kb:
            return {"vram_used_gb": None, "vram_total_gb": None, "vram_percent": None}

        used_gb = used_kb / (1024**2)
        total_gb = total_kb / (1024**2)
        return {
            "vram_used_gb": used_gb,
            "vram_total_gb": total_gb,
            "vram_percent": (used_gb / total_gb * 100) if total_gb > 0 else 0,
        }

    def _read_temperature(self, lib, device_id: int) -> Optional[float]:
        """
        Read the chip hotspot temperature in degree Celsius.

        MXSML returns the temperature as an integer in 0.01 degree Celsius.
        """
        temp_types = [
            getattr(lib, "MXSML_TEMPERATURE_HOTSPOT", None),
            getattr(lib, "MXSML_TEMPERATURE_CORE", None),
            getattr(lib, "MXSML_TEMPERATURE_SOC", None),
        ]
        for temp_type in temp_types:
            if temp_type is None:
                continue
            try:
                raw = lib.mxSmlGetTemperatureInfo(device_id, temp_type)
                if raw is None:
                    continue
                # 0.01 C -> C ; values already in C are extremely unlikely (>10000)
                return raw / 100.0 if abs(raw) > 1000 else float(raw)
            except Exception:
                continue
        return None

    def _read_power(self, lib, device_id: int) -> Optional[float]:
        """
        Read the board power in Watts.

        Prefers ``mxSmlGetBoardPowerInfo`` (sum of all board power ways, mW),
        falls back to ``mxSmlGetPmbusInfo(MXSML_PMBUS_SOC)`` and then to the
        per-die pmbus CORE power.
        """
        try:
            board_infos = lib.mxSmlGetBoardPowerInfo(device_id)
            total_mw = 0
            found = False
            for info in board_infos:
                power = getattr(info, "power", 0)
                if power:
                    total_mw += power
                    found = True
            if found:
                return total_mw / 1000.0
        except Exception:
            pass

        try:
            pmbus_unit = getattr(lib, "MXSML_PMBUS_SOC", 0)
            pmbus_info = lib.mxSmlGetPmbusInfo(device_id, pmbus_unit)
            power = getattr(pmbus_info, "power", 0)
            if power:
                return power / 1000.0
        except Exception:
            pass

        # MCM fallback: sum the per-die CORE power
        try:
            pmbus_core = getattr(lib, "MXSML_PMBUS_CORE", 1)
            die_count = lib.mxSmlGetDeviceDieCount(device_id)
            total_mw = 0
            for die_id in range(die_count):
                die_info = lib.mxSmlGetDiePmbusInfo(device_id, die_id, pmbus_core)
                total_mw += getattr(die_info, "power", 0) or 0
            if total_mw:
                return total_mw / 1000.0
        except Exception:
            pass

        return None

    def _read_vm_memory(self, lib, device_id: int) -> Optional[float]:
        """Read the total virtual memory (``xttTotal``, KB) of one device."""
        try:
            info = lib.mxSmlGetMemoryInfo(device_id)
            return (getattr(info, "xttTotal", 0) or 0) / (1024**2)  # KB -> GB
        except Exception:
            return None

    # ------------------------------------------------------------------
    # manual clocks workaround
    # ------------------------------------------------------------------
    def set_dpm_max_perf_level(self, level: Optional[int] = None) -> bool:
        """
        Pin the DPM performance level to maximum on every monitored GPU.

        Some MetaX boards report 0 MHz (or NaN) for ``mxSmlGetDpmIpClockInfo``
        until the DPM max level has been set explicitly. This mirrors the C++
        demo::

            mxSmlSetDpmIpMaxPerfLevel(device_id, MXSML_Dpm_Xcore, 7);

        Must be called by an application (the library never changes clocks on
        its own). Returns True when all monitored devices accepted the call.
        """
        lib = _get_mxsml()
        if lib is None or not self.available:
            return False

        level = self._DPM_MAX_LEVEL if level is None else level
        dpm_xcore = getattr(lib, "MXSML_DPM_XCORE", None)
        if dpm_xcore is None:
            logger.warning("MXSML_DPM_XCORE not available, cannot set DPM max level")
            return False

        ok = True
        for device_id in self.device_ids:
            try:
                lib.mxSmlSetDpmIpMaxPerfLevel(device_id, dpm_xcore, level)
            except Exception as e:
                ok = False
                logger.warning(f"Set DPM max level failed on device {device_id}: {e}")
        if ok:
            logger.info(f"DPM max performance level set to {level} on all monitored GPUs")
        return ok

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------
    def get_gpu_stats(self) -> List[Dict]:
        """
        Read every monitored GPU and return a per-GPU list.

        Each entry follows the naming convention used by the UI::

            {"index": 0, "name": "MetaX MXC500 GPU01", "gpu_percent": 42.0,
             "vram_used_gb": 24.0, "vram_total_gb": 64.0, "vram_percent": 37.5,
             "temp_c": 56.0, "power_w": 165.0, "uuid": "...", "bdf_id": "...",
             "device_id": 0}

        The list always contains ``len(self.device_ids)`` entries (up to
        ``max_devices`` = 8 -> GPU01..GPU08). When monitoring is unavailable the
        placeholders are emitted with ``available=False`` so the number of slots
        shown by the UI stays stable.
        """
        lib = _get_mxsml()

        if lib is None or not self.available:
            return [
                {
                    "index": i,
                    "device_id": device_id,
                    "name": self._gpu_display_name(i, len(self.device_ids), self.device_name),
                    "gpu_percent": 0,
                    "vram_used_gb": 0,
                    "vram_total_gb": 0,
                    "vram_percent": 0,
                    "temp_c": None,
                    "power_w": None,
                    "uuid": "",
                    "bdf_id": "",
                    "available": False,
                }
                for i, device_id in enumerate(self.device_ids)
            ]

        total = len(self.device_ids)
        devices: List[Dict] = []

        for index, device_id in enumerate(self.device_ids):
            raw_name = self._safe(
                lambda: str(lib.mxSmlGetDeviceInfo(device_id).deviceName).strip(), ""
            )
            name = self._gpu_display_name(index, total, raw_name or self.device_name)

            memory = self._read_memory(lib, device_id)
            devices.append(
                {
                    "index": index,
                    "device_id": device_id,
                    "name": name,
                    "gpu_name": raw_name or name,
                    "gpu_percent": self._read_gpu_percent(lib, device_id),
                    "vram_used_gb": memory["vram_used_gb"],
                    "vram_total_gb": memory["vram_total_gb"],
                    "vram_percent": memory["vram_percent"],
                    "vm_total_gb": self._read_vm_memory(lib, device_id),
                    "temp_c": self._read_temperature(lib, device_id),
                    "power_w": self._read_power(lib, device_id),
                    "uuid": self._safe(
                        lambda: str(lib.mxSmlGetDeviceInfo(device_id).uuid).strip(), ""
                    ),
                    "bdf_id": self._safe(
                        lambda: str(lib.mxSmlGetDeviceInfo(device_id).bdfId).strip(), ""
                    ),
                    "available": True,
                }
            )

        return devices

    def get_stats(self) -> Dict:
        """
        Get aggregated GPU stats for **all** monitored GPUs plus CPU/RAM.

        The flat fields keep the original single-GPU protocol shape:

        - ``gpu_percent``  : average over all GPUs
        - ``vram_used_gb`` : sum of used VRAM over all GPUs
        - ``vram_total_gb``: sum of total VRAM over all GPUs

        ``gpus`` carries the per-GPU breakdown and ``gpu_count`` the number of
        monitored devices.
        """
        self.stats_call_count += 1

        lib = _get_mxsml()
        if lib is None or not self.available:
            return self._get_fallback_stats()

        try:
            devices = self.get_gpu_stats()
            agg = self.aggregate_stats(devices)
            system_stats = self.get_cpu_ram_stats()

            per_gpu = [
                {
                    "index": dev["index"],
                    "name": dev["name"],
                    "gpu_percent": dev["gpu_percent"] if dev["gpu_percent"] is not None else 0,
                    "vram_used_gb": dev["vram_used_gb"] or 0,
                    "vram_total_gb": dev["vram_total_gb"] or 0,
                    "vram_percent": dev["vram_percent"] or 0,
                    "temp_c": dev["temp_c"],
                    "power_w": dev["power_w"],
                }
                for dev in devices
            ]

            stats = {
                "platform": "MetaX (MXSML)",
                "gpu_name": self.device_name,
                "gpu_model": self.gpu_model_summary(),
                "product_name": self.product_name,
                "uuid": self.uuid,
                "bdf_id": self.bdf_id,
                "device_count": agg.get("device_count", len(devices)),
                "gpus": per_gpu,
                **agg,
                "temp_c": max(
                    [d["temp_c"] for d in devices if d["temp_c"] is not None], default=None
                ),
                "power_w": sum(d["power_w"] for d in devices if d["power_w"] is not None) or None,
                **system_stats,
            }

            self.update_history(stats)

            if self.consecutive_errors > 0:
                self.consecutive_errors = 0
                if self.error_logged:
                    logger.info("GPU monitoring recovered")
                    self.error_logged = False

            return stats

        except Exception as e:
            self.consecutive_errors += 1

            if not self.error_logged:
                logger.error(f"Error getting MXSML stats: {e}")
                self.error_logged = True
            elif self.consecutive_errors % 60 == 0:
                logger.warning(f"MXSML errors continue ({self.consecutive_errors} total errors)")

            # Be lenient with intermittent errors: only disable after many
            # consecutive failures (mirrors the NVML behaviour).
            error_threshold = 240 if self.stats_call_count < 240 else 120
            if self.consecutive_errors > error_threshold:
                if self.available:
                    logger.error(
                        f"Too many consecutive MXSML errors ({error_threshold}+) "
                        "- disabling GPU monitoring"
                    )
                    self.available = False

            return self._get_fallback_stats()

    def _get_fallback_stats(self) -> Dict:
        """Fallback stats when the MetaX GPUs are not available"""
        system_stats = self.get_cpu_ram_stats()

        gpu_name = getattr(self, "device_name", "N/A")
        platform_name = (
            f"MetaX {gpu_name} (monitoring unavailable)"
            if gpu_name != "N/A"
            else "MetaX (MXSML unavailable)"
        )

        devices = self.get_gpu_stats()
        agg = self.aggregate_stats(devices)

        return {
            "platform": platform_name,
            "gpu_name": gpu_name,
            "gpu_model": self.gpu_model_summary(),
            "product_name": getattr(self, "product_name", ""),
            "uuid": getattr(self, "uuid", ""),
            "bdf_id": getattr(self, "bdf_id", ""),
            "device_count": agg.get("device_count", len(devices)),
            "gpus": [
                {
                    "index": d["index"],
                    "name": d["name"],
                    "gpu_percent": 0,
                    "vram_used_gb": 0,
                    "vram_total_gb": 0,
                    "vram_percent": 0,
                    "temp_c": None,
                    "power_w": None,
                }
                for d in devices
            ],
            "gpu_percent": 0,
            "vram_used_gb": 0,
            "vram_total_gb": 0,
            "vram_percent": 0,
            "temp_c": None,
            "power_w": None,
            **system_stats,
        }

    def cleanup(self):
        """Cleanup MXSML resources"""
        if self.available:
            try:
                lib = _get_mxsml()
                if lib is not None and hasattr(lib, "mxSmlShutdown"):
                    lib.mxSmlShutdown()
                logger.info("MXSML shutdown complete")
            except Exception as e:
                logger.error(f"Error during MXSML cleanup: {e}")


def detect_metax() -> bool:
    """
    Auto-detect MetaX hardware / driver availability.

    Mirrors the auto-detection performed by the NVIDIA factory
    (``import pynvml`` -> ``nvmlInit()``): the MXSML bindings are imported
    first, then ``mxSmlInit()`` / ``mxSmlGetDeviceCount()`` are called to check
    that at least one MetaX device is present.

    The MXSML library keeps global init state, so this probe never calls
    ``mxSmlShutdown()`` (which would tear down an already running monitor).

    Returns:
        True when at least one MetaX device is available, False otherwise.
    """
    lib = _get_mxsml()
    if lib is None:
        logger.debug("MetaX not detected: MXSML bindings unavailable")
        return False

    try:
        lib.mxSmlInit()
        device_count = lib.mxSmlGetDeviceCount()
        try:
            pf_count = lib.mxSmlGetPfDeviceCount()
        except Exception:
            pf_count = 0
        if (device_count + pf_count) > 0:
            logger.info(
                f"Auto-detected MetaX GPU (MXSML available, "
                f"{device_count} native + {pf_count} PF device(s))"
            )
            return True
        logger.debug("MetaX not detected: no MXSML device found")
        return False
    except Exception as e:
        logger.debug(f"MetaX not detected: {e}")
        return False


def create_monitor(platform: Optional[str] = None) -> GPUMonitor:
    """
    Factory function to create the appropriate GPU monitor

    Args:
        platform: Force specific platform ('metax' / 'mxsml').
                 If None, auto-detect MetaX hardware via MXSML.

    Returns:
        A ``MXSMLMonitor`` instance. When MetaX hardware cannot be detected the
        monitor is still returned but reports itself as unavailable, so that
        ``get_stats()`` keeps serving the CPU/RAM part of the protocol instead
        of raising (mirrors the NVML fallback behaviour).
    """
    # Force specific platform if requested
    if platform in ("metax", "mxsml"):
        return MXSMLMonitor()

    if platform is not None:
        logger.warning(f"Unknown platform '{platform}', falling back to MXSMLMonitor")
        return MXSMLMonitor()

    # Auto-detect
    if not detect_metax():
        logger.warning("No MetaX GPU detected, using fallback monitor")
    return MXSMLMonitor()
