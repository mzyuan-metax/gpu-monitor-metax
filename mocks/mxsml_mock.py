# SPDX-License-Identifier: Apache-2.0
"""
Mock implementation of the ``pymxsml.mxsml`` module.

Why this file exists
--------------------
The real ``pymxsml`` package resolves ``libmxsml.so`` from ``/opt/...`` at
import time (see ``pymxsml.mxsml._loadMxsmlLibrary``). On a machine without
MetaX hardware/driver, that import fails and the monitor cannot be exercised
at all.

``mocks.mxsml_mock`` exposes the *same* API surface (names, enums, calling
conventions and units) as ``pymxsml.mxsml``, but returns deterministic
simulated data. It can be injected into ``gpu_monitor`` with::

    import gpu_monitor
    from mocks import mxsml_mock
    gpu_monitor.set_mxsml_backend(mxsml_mock)
    monitor = gpu_monitor.MXSMLMonitor()
    print(monitor.get_stats())

Units mirror the real library:
    - memory        : KB
    - temperature   : 0.01 degree Celsius
    - board power   : mW
    - usage         : percent
"""

from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Enums / constants (subset that ``gpu_monitor`` relies on)
# ---------------------------------------------------------------------------
MXSML_SUCCESS = 0

MXSML_VIRTUALIZATION_MODE_NONE = 0
MXSML_VIRTUALIZATION_MODE_PF = 1
MXSML_VIRTUALIZATION_MODE_VF = 2

MXSML_VERSION_BIOS = 0
MXSML_VERSION_DRIVER = 1

MXSML_PMBUS_SOC = 0
MXSML_PMBUS_CORE = 1

MXSML_DPM_DLA = 0
MXSML_DPM_XCORE = 1

MXSML_TEMPERATURE_HOTSPOT = 0
MXSML_TEMPERATURE_SOC = 2
MXSML_TEMPERATURE_CORE = 3

MXSML_USAGE_DLA = 0
MXSML_USAGE_VPUE = 1
MXSML_USAGE_VPUD = 2
MXSML_USAGE_XCORE = 4
MXSML_USAGE_MMA = 5

MXSML_METAX_LINK_NUM = 7


class MXSMLError(Exception):
    """Error type mirroring ``pymxsml.mxsml.MXSMLError``."""

    def __init__(self, value):
        super().__init__(f"MXSML mock error with code {value}")
        self.value = value


# ---------------------------------------------------------------------------
# Simulated device state
# ---------------------------------------------------------------------------
# Per-device raw values, in the units used by the real MXSML API.
#
# The default host simulates 8x MXC500 (device ids 0..7) plus one PF device
# (id 100), so that the multi-GPU aggregation (average utilization / summed
# VRAM) can be exercised the same way as on an 8-card server.

# (usage_xcore, vis_vram_use_kb, hotspot, soc, core, board_power_mw[], vis_vram_total_kb)
_GPU_PROFILES = [
    (42, 24, 5600, 4900, 5200, [120000, 45000], 64),
    (5, 8, 4100, 3800, 3900, [60000, 20000], 64),
    (78, 40, 6800, 6100, 6400, [180000, 60000], 64),
    (0, 1, 3500, 3300, 3400, [45000, 15000], 64),
    (55, 32, 6100, 5500, 5800, [140000, 50000], 64),
    (91, 56, 7200, 6500, 6900, [200000, 70000], 64),
    (23, 12, 4700, 4300, 4500, [80000, 30000], 64),
    (67, 48, 6400, 5800, 6100, [160000, 55000], 64),
]

_DEVICES = {}
for _idx, (
    _usage,
    _vram_use_gb,
    _hotspot,
    _soc,
    _core,
    _board_power,
    _vram_total_gb,
) in enumerate(_GPU_PROFILES):
    _DEVICES[_idx] = {
        "uuid": f"GPU-mock-{_idx:04d}-0000-0000-{_idx:012d}",
        "bdfId": f"0000:{_idx + 1:02x}:00.0",
        "gpuId": _idx,
        "nodeId": 0,
        "brand": 2,  # MXSML_BRAND_C
        "mode": MXSML_VIRTUALIZATION_MODE_NONE,
        "deviceName": "MXC500",
        "die_count": 1,
        "vis_vram_total_kb": _vram_total_gb * 1024 * 1024,
        "vis_vram_use_kb": _vram_use_gb * 1024 * 1024,
        "vram_total_kb": _vram_total_gb * 1024 * 1024,
        "vram_use_kb": _vram_use_gb * 1024 * 1024,
        "hotspot_temp_centi_c": _hotspot,
        "core_temp_centi_c": _core,
        "soc_temp_centi_c": _soc,
        "board_power_mw": list(_board_power),
        "pmbus_power_mw": sum(_board_power),
        "usage_xcore": _usage,
        "usage_mma": max(0, _usage - 5),
        "usage_vpud": max(0, _usage // 4),
        "xcore_ap_usage": [[_usage // 2, _usage], [max(0, _usage - 8), _usage]],
        "session_count": 0,
    }

# PF device: id is offset by 100; cannot report memory, keeps util as int
_DEVICES[100] = {
    "uuid": "GPU-mock-pf00-0000-0000-000000000000",
    "bdfId": "0000:01:00.1",
    "gpuId": 0,
    "nodeId": 0,
    "brand": 2,
    "mode": MXSML_VIRTUALIZATION_MODE_PF,
    "deviceName": "MXC500-PF",
    "die_count": 1,
    "vis_vram_total_kb": 0,  # PF cannot report memory
    "vis_vram_use_kb": 0,
    "vram_total_kb": 0,
    "vram_use_kb": 0,
    "hotspot_temp_centi_c": 5000,
    "core_temp_centi_c": 4700,
    "soc_temp_centi_c": 4500,
    "board_power_mw": [100000, 30000],
    "pmbus_power_mw": 130000,
    "usage_xcore": 20,
    "usage_mma": 18,
    "usage_vpud": 9,
    "xcore_ap_usage": [[5, 10], [8, 12]],
    "session_count": 0,
}

_MACA_VERSION = "2.3.4-mock"
_DRIVER_VERSION = "1.0.0-mock"
_PPTABLE_VERSION = "1.0.0-mock"

# PF devices are enumerated separately (ids offset by 100)
_PF_DEVICES = [100]
_NATIVE_DEVICES = list(range(len(_GPU_PROFILES)))


def _device(device_id):
    if device_id not in _DEVICES:
        raise MXSMLError(6)  # MXSML_ERROR_INVALID_DEVICE_ID
    return _DEVICES[device_id]


# ---------------------------------------------------------------------------
# init / system info
# ---------------------------------------------------------------------------
def mxSmlInit():
    return None


def mxSmlInitWithFlags(flags):
    return None


def mxSmlShutdown():
    return None


def mxSmlGetMacaVersion():
    return _MACA_VERSION


def mxSmlGetDeviceCount():
    return len(_NATIVE_DEVICES)


def mxSmlGetPfDeviceCount():
    return len(_PF_DEVICES)


# ---------------------------------------------------------------------------
# device info
# ---------------------------------------------------------------------------
def mxSmlGetDeviceInfo(device_id):
    dev = _device(device_id)
    return SimpleNamespace(
        deviceId=device_id,
        bdfId=dev["bdfId"],
        gpuId=dev["gpuId"],
        nodeId=dev["nodeId"],
        uuid=dev["uuid"],
        brand=dev["brand"],
        mode=dev["mode"],
        deviceName=dev["deviceName"],
    )


def mxSmlGetLimitedDeviceInfo(device_id):
    return mxSmlGetDeviceInfo(device_id)


def mxSmlGetDeviceDieCount(device_id):
    return _device(device_id)["die_count"]


def mxSmlGetDeviceVersion(device_id, version_unit):
    _device(device_id)
    if version_unit == MXSML_VERSION_DRIVER:
        return _DRIVER_VERSION
    return f"mock-version-{version_unit}"


def mxSmlGetPptableVersion(device_id):
    _device(device_id)
    return _PPTABLE_VERSION


def mxSmlGetDeviceRealPath(device_id):
    _device(device_id)
    return f"/sys/bus/pci/devices/{_device(device_id)['bdfId']}"


# ---------------------------------------------------------------------------
# memory
# ---------------------------------------------------------------------------
def mxSmlGetMemoryInfo(device_id):
    dev = _device(device_id)
    if dev["mode"] == MXSML_VIRTUALIZATION_MODE_PF:
        # PF devices cannot report memory (mirrors the real behaviour)
        raise MXSMLError(3)  # MXSML_ERROR_OPERATION_NOT_SUPPORT
    return SimpleNamespace(
        visVramTotal=dev["vis_vram_total_kb"],
        visVramUse=dev["vis_vram_use_kb"],
        vramTotal=dev["vram_total_kb"],
        vramUse=dev["vram_use_kb"],
        xttTotal=dev["vis_vram_total_kb"],
        xttUse=dev["vis_vram_use_kb"],
    )


def mxSmlGetDieMemoryInfo(device_id, die_id):
    memory = mxSmlGetMemoryInfo(device_id)
    # split evenly across dies for simulation purposes
    die_count = max(1, _device(device_id)["die_count"])
    memory.visVramTotal //= die_count
    memory.visVramUse //= die_count
    memory.vramTotal //= die_count
    memory.vramUse //= die_count
    return memory


# ---------------------------------------------------------------------------
# temperature
# ---------------------------------------------------------------------------
def mxSmlGetTemperatureInfo(device_id, temperature_type):
    dev = _device(device_id)
    if temperature_type == MXSML_TEMPERATURE_HOTSPOT:
        return dev["hotspot_temp_centi_c"]
    if temperature_type == MXSML_TEMPERATURE_CORE:
        return dev["core_temp_centi_c"]
    if temperature_type == MXSML_TEMPERATURE_SOC:
        return dev["soc_temp_centi_c"]
    raise MXSMLError(3)


def mxSmlGetDieTemperatureInfo(device_id, die_id, temperature_type):
    return mxSmlGetTemperatureInfo(device_id, temperature_type)


# ---------------------------------------------------------------------------
# power
# ---------------------------------------------------------------------------
def mxSmlGetBoardPowerInfo(device_id):
    dev = _device(device_id)
    return [
        SimpleNamespace(voltage=800, current=150000, power=power_mw)
        for power_mw in dev["board_power_mw"]
    ]


def mxSmlGetPmbusInfo(device_id, pmbus_unit):
    dev = _device(device_id)
    return SimpleNamespace(
        voltage=800,
        current=200000,
        power=dev["pmbus_power_mw"],
    )


def mxSmlGetBoardPowerLimit(device_id):
    _device(device_id)
    return 250000  # mW


def mxSmlGetBoardPowerDefaultLimit(device_id):
    _device(device_id)
    return 250000


def mxSmlGetBoardPowerLimitConstraints(device_id):
    _device(device_id)
    return (100000, 350000)


# ---------------------------------------------------------------------------
# utilization / usage
# ---------------------------------------------------------------------------
def mxSmlGetDeviceIpUsage(device_id, usage_ip):
    dev = _device(device_id)
    if usage_ip == MXSML_USAGE_XCORE:
        return dev["usage_xcore"]
    if usage_ip == MXSML_USAGE_MMA:
        return dev["usage_mma"]
    if usage_ip == MXSML_USAGE_VPUD:
        return dev["usage_vpud"]
    raise MXSMLError(3)


def mxSmlGetXcoreApUsage(device_id):
    return [list(pair) for pair in _device(device_id)["xcore_ap_usage"]]


def mxSmlGetDieIpUsage(device_id, die_id, usage_ip):
    return mxSmlGetDeviceIpUsage(device_id, usage_ip)


def mxSmlGetDiePmbusInfo(device_id, die_id, pmbus_unit):
    """Per-die pmbus (used as the MCM power fallback)."""
    dev = _device(device_id)
    die_count = max(1, dev["die_count"])
    return SimpleNamespace(
        voltage=800,
        current=200000 // die_count,
        power=dev["pmbus_power_mw"] // die_count,
    )


def mxSmlSetDpmIpMaxPerfLevel(device_id, dpm_ip, level):
    """Pin the DPM max performance level (clock-unlock workaround)."""
    dev = _device(device_id)
    dev["dpm_max_perf_level"] = level
    return None


def mxSmlGetCurrentDpmIpPerfLevel(device_id, dpm_ip):
    return _device(device_id).get("dpm_max_perf_level", 7)


def mxSmlGetDpmIpMaxPerfLevel(device_id, dpm_ip):
    return _device(device_id).get("dpm_max_perf_level", 9)


# ---------------------------------------------------------------------------
# clocks / misc (kept minimal but API-compatible)
# ---------------------------------------------------------------------------
def mxSmlGetClocks(device_id, clock_ip):
    _device(device_id)
    return [1200]


def mxSmlGetDpmIpClockInfo(device_id, dpm_ip):
    _device(device_id)
    return [1200]


def mxSmlGetDpmIpVddInfo(device_id, dpm_ip):
    _device(device_id)
    return [800]


def mxSmlGetCurrentDpmIpPerfLevel(device_id, dpm_ip):
    _device(device_id)
    return 7


def mxSmlGetDpmIpMaxPerfLevel(device_id, dpm_ip):
    _device(device_id)
    return 9


def mxSmlGetCodecStatus(device_id):
    _device(device_id)
    return SimpleNamespace(encoder=1, decoder=2)


def mxSmlGetHbmBandWidth(device_id):
    _device(device_id)
    return SimpleNamespace(hbmBandwidthReqTotal=123456, hbmBandwidthRespTotal=234567)


def mxSmlGetPcieInfo(device_id):
    _device(device_id)
    return SimpleNamespace(speed=16.0, width=16)


def mxSmlGetPcieMaxLinkInfo(device_id):
    _device(device_id)
    return SimpleNamespace(speed=16.0, width=16)


def mxSmlGetPcieThroughput(device_id):
    _device(device_id)
    return SimpleNamespace(rx=1024, tx=2048)


def mxSmlGetChipSerial(device_id):
    _device(device_id)
    return "MOCK-CHIP-SERIAL"


def mxSmlGetBoardSerial(device_id):
    _device(device_id)
    return "MOCK-BOARD-SERIAL"


def mxSmlGetEepromInfo(device_id):
    _device(device_id)
    return SimpleNamespace(content="product=MXC500;vendor=MetaX;serial=MOCK")


def mxSmlGetNumberOfProcess():
    return 0


def mxSmlGetProcessInfo(process_number):
    return []


def mxSmlGetProcessInfo_v2(process_number):
    return []


def mxSmlGetProcessInfo_v3(process_number):
    return []


def mxSmlGetErrorString(result):
    return f"mock error {result}"


def mxSmlGetDeviceState(device_id):
    _device(device_id)
    return 0


def mxSmlGetDeviceUnavailableReason(device_id):
    _device(device_id)
    return SimpleNamespace(unavailableCode=0, unavailableReason="")


def mxSmlGetTotalEccErrors(device_id):
    _device(device_id)
    return SimpleNamespace(sramCE=0, sramUE=0, dramCE=0, dramUE=0, retiredPage=0)
