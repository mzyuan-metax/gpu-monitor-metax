# SPDX-License-Identifier: Apache-2.0
"""
Mock tests for ``gpu_monitor.MXSMLMonitor``.

These tests do NOT require MetaX hardware: the real ``pymxsml`` library is
replaced by ``mocks.mxsml_mock`` via ``gpu_monitor.set_mxsml_backend()``.

Run with::

    python3 tests/test_gpu_monitor_mxsml.py
    # or
    python3 -m pytest tests/test_gpu_monitor_mxsml.py -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gpu_monitor  # noqa: E402
from mocks import mxsml_mock  # noqa: E402

# The exact set of keys produced by the NVIDIA implementation's get_stats()
EXPECTED_STATS_KEYS = {
    "platform",
    "gpu_name",
    "gpu_percent",
    "vram_used_gb",
    "vram_total_gb",
    "vram_percent",
    "temp_c",
    "power_w",
    "product_name",
    "cpu_percent",
    "cpu_model",
    "ram_used_gb",
    "ram_total_gb",
    "ram_percent",
    "hostname",
}

# Numeric fields that the UI relies on being non-None numbers
NUMERIC_KEYS = ("gpu_percent", "vram_used_gb", "vram_total_gb", "vram_percent")

# Number of GPUs simulated by mocks.mxsml_mock
MOCK_GPU_COUNT = 8


def _monitor(device_index=None, **kwargs):
    gpu_monitor.set_mxsml_backend(mxsml_mock)
    return gpu_monitor.MXSMLMonitor(device_index=device_index, **kwargs)


# ---------------------------------------------------------------------------
# basic construction / availability
# ---------------------------------------------------------------------------
def test_monitor_initializes_with_mock():
    mon = _monitor()
    assert mon.available is True
    # by default every GPU is monitored
    assert len(mon.device_ids) == MOCK_GPU_COUNT
    assert mon.device_ids == list(range(MOCK_GPU_COUNT))
    # legacy first-device fields still populated
    assert mon.device_id == 0
    assert mon.device_name.startswith("MetaX MXC500")
    assert mon.bdf_id == "0000:01:00.0"
    mon.cleanup()


def test_aggregates_all_gpus():
    """Flat fields must aggregate every GPU, not just the first one."""
    mon = _monitor()
    stats = mon.get_stats()

    assert stats["device_count"] == MOCK_GPU_COUNT
    assert len(stats["gpus"]) == MOCK_GPU_COUNT

    utils = [42, 5, 78, 0, 55, 91, 23, 67]
    assert abs(stats["gpu_percent"] - sum(utils) / len(utils)) < 0.01

    # every mock GPU reports 64 GB total, 8x64 = 512
    assert abs(stats["vram_total_gb"] - 512.0) < 0.01
    # used = 24+8+40+1+32+56+12+48 = 221
    assert abs(stats["vram_used_gb"] - 221.0) < 0.01
    assert abs(stats["vram_percent"] - (221.0 / 512.0 * 100)) < 0.1

    mon.cleanup()


def test_per_gpu_list_names_and_metrics():
    mon = _monitor()
    stats = mon.get_stats()

    for i, gpu in enumerate(stats["gpus"]):
        assert gpu["index"] == i
        assert gpu["name"] == f"MetaX MXC500 GPU{i + 1:02d}"
        assert 0 <= gpu["gpu_percent"] <= 100
        assert gpu["vram_total_gb"] == 64.0

    assert stats["gpus"][0]["gpu_percent"] == 42
    assert stats["gpus"][0]["vram_used_gb"] == 24.0
    assert stats["gpus"][2]["gpu_percent"] == 78
    # aggregate temp = max, aggregate power = sum
    assert abs(stats["temp_c"] - 72.0) < 1e-6  # hottest hotspot = 7200 -> 72 C
    assert stats["power_w"] > 0
    mon.cleanup()


def test_gpu_slot_names_follow_index_convention():
    mon = _monitor(device_ids=[0])
    single = mon.get_stats()
    # single GPU -> no GPUxx suffix
    assert single["gpus"][0]["name"] == "MetaX MXC500"
    mon.cleanup()

    mon8 = _monitor()
    multi = mon8.get_stats()
    assert multi["gpus"][0]["name"] == "MetaX MXC500 GPU01"
    assert multi["gpus"][7]["name"] == "MetaX MXC500 GPU08"
    mon8.cleanup()


def test_device_ids_capped_at_eight():
    gpu_monitor.set_mxsml_backend(mxsml_mock)
    # ask for more ids than the cap allows
    mon = gpu_monitor.MXSMLMonitor(device_ids=list(range(10)) + [100])
    assert len(mon.device_ids) <= mon.max_devices == 8
    mon.cleanup()


def test_aggregate_stats_helper_skips_unknown_utilization():
    """An unsupported GPU (None util) must not drag the average to zero."""
    agg = gpu_monitor.GPUMonitor.aggregate_stats(
        [
            {"gpu_percent": 80, "vram_used_gb": 10, "vram_total_gb": 64},
            {"gpu_percent": None, "vram_used_gb": None, "vram_total_gb": None},
            {"gpu_percent": 20, "vram_used_gb": 30, "vram_total_gb": 64},
        ]
    )
    assert agg["gpu_percent"] == 50.0  # (80 + 20) / 2
    assert agg["vram_used_gb"] == 40.0
    assert agg["vram_total_gb"] == 128.0
    assert agg["device_count"] == 3


def test_aggregate_stats_empty():
    assert gpu_monitor.GPUMonitor.aggregate_stats([]) == {}


def test_monitor_unavailable_without_backend():
    gpu_monitor.set_mxsml_backend(None)
    # Force the lazy real-import path to fail on hardware-free machines.
    mon = gpu_monitor.MXSMLMonitor()
    stats = mon.get_stats()
    assert isinstance(stats, dict)
    assert stats["gpu_percent"] == 0
    assert "unavailable" in stats["platform"].lower()
    mon.cleanup()
    # restore mock for the remaining tests
    gpu_monitor.set_mxsml_backend(mxsml_mock)


# ---------------------------------------------------------------------------
# data protocol conformance
# ---------------------------------------------------------------------------
def test_stats_contains_full_protocol():
    mon = _monitor()
    stats = mon.get_stats()
    missing = EXPECTED_STATS_KEYS - set(stats.keys())
    assert not missing, f"missing protocol keys: {missing}"
    mon.cleanup()


def test_stats_numeric_types_and_ranges():
    mon = _monitor()
    stats = mon.get_stats()

    for key in NUMERIC_KEYS:
        assert isinstance(stats[key], (int, float)), f"{key} is not numeric: {stats[key]}"

    assert 0 <= stats["gpu_percent"] <= 100
    assert 0 <= stats["vram_percent"] <= 100
    assert 0 < stats["vram_used_gb"] < stats["vram_total_gb"]
    assert isinstance(stats["gpu_name"], str) and stats["gpu_name"]
    assert isinstance(stats["hostname"], str) and stats["hostname"]
    mon.cleanup()


# ---------------------------------------------------------------------------
# unit conversion (the crux of the MXSML -> protocol mapping)
# ---------------------------------------------------------------------------
def test_utilization_mapping_single_device():
    """Single-device restriction still maps xcore usage (%) directly."""
    mon = _monitor(device_index=0)
    stats = mon.get_stats()
    assert abs(stats["gpu_percent"] - 42) < 1e-6
    mon.cleanup()

    mon1 = _monitor(device_index=1)
    stats1 = mon1.get_stats()
    assert abs(stats1["gpu_percent"] - 5) < 1e-6
    mon1.cleanup()


def test_memory_kb_to_gb_conversion_single_device():
    mon = _monitor(device_index=0)
    stats = mon.get_stats()
    # 24 GB used / 64 GB total (KB -> GB = / 1024^2)
    assert abs(stats["vram_used_gb"] - 24.0) < 0.01
    assert abs(stats["vram_total_gb"] - 64.0) < 0.01
    assert abs(stats["vram_percent"] - (24.0 / 64.0 * 100)) < 0.1
    mon.cleanup()


def test_temperature_centi_celsius_to_celsius():
    mon = _monitor(device_index=0)
    stats = mon.get_stats()
    # hotspot 5600 (0.01 C) -> 56.0 C
    assert abs(stats["temp_c"] - 56.0) < 1e-6
    mon.cleanup()


def test_power_mw_summed_to_watts():
    mon = _monitor(device_index=0)
    stats = mon.get_stats()
    # board ways: 120000 + 45000 mW -> 165 W
    assert abs(stats["power_w"] - 165.0) < 1e-6
    mon.cleanup()


# ---------------------------------------------------------------------------
# device selection / PF handling
# ---------------------------------------------------------------------------
def test_device_index_selection():
    mon0 = _monitor(device_index=0)
    mon1 = _monitor(device_index=1)
    assert mon0.device_id == 0
    assert mon1.device_id == 1
    assert mon0.bdf_id != mon1.bdf_id
    mon0.cleanup()
    mon1.cleanup()


def test_pf_device_selection_and_no_vram():
    # 8 native devices (0..7), PF device id is 100 -> overall index 8
    mon = _monitor(device_index=MOCK_GPU_COUNT)
    assert mon.device_id == 100
    stats = mon.get_stats()
    assert stats["gpu_name"] == "MetaX MXC500-PF"
    # PF cannot report memory: the aggregate sums simply exclude it
    assert stats["vram_used_gb"] == 0
    assert stats["vram_total_gb"] == 0
    assert stats["vram_percent"] == 0
    # ... but utilization / temperature / power still work
    assert stats["gpu_percent"] == 20
    assert abs(stats["temp_c"] - 50.0) < 1e-6
    assert abs(stats["power_w"] - 130.0) < 1e-6
    mon.cleanup()


def test_device_index_out_of_range_falls_back_to_all():
    mon = _monitor(device_index=99)
    # out-of-range index now falls back to monitoring every GPU
    assert len(mon.device_ids) == MOCK_GPU_COUNT
    mon.cleanup()


# ---------------------------------------------------------------------------
# history handling
# ---------------------------------------------------------------------------
def test_history_accumulates_and_respects_maxlen():
    mon = _monitor(history_size=5)
    for _ in range(8):
        mon.get_stats()

    history = mon.get_history()
    assert set(history.keys()) == {"gpu_util", "vram_used", "cpu_util", "ram_used"}
    for values in history.values():
        assert len(values) == 5  # maxlen enforced

    # values recorded come from the *aggregated* stats protocol
    expected_util = sum([42, 5, 78, 0, 55, 91, 23, 67]) / 8
    assert abs(history["gpu_util"][-1] - expected_util) < 0.01
    assert abs(history["vram_used"][-1] - 221.0) < 0.01
    mon.cleanup()


# ---------------------------------------------------------------------------
# server integration: lifecycle as used by on_startup / gpu_monitor_loop
# ---------------------------------------------------------------------------
def test_server_lifecycle_emits_double_history():
    """
    Reproduce the server's usage exactly:

        on_startup      -> monitor = create_monitor()
        gpu_monitor_loop-> stats = monitor.get_stats()
                           monitor.update_history(stats)
                           stats["history"] = monitor.get_history()
        on_shutdown     -> monitor.cleanup()

    as dict and broadcasts it over the WebSocket.
    """
    import json

    gpu_monitor.set_mxsml_backend(mxsml_mock)
    monitor = gpu_monitor.create_monitor()
    monitor.init()  # what on_startup would call
    try:
        for _ in range(10):
            stats = monitor.get_stats()
            monitor.update_history(stats)
            stats["history"] = monitor.get_history()

            # the loop broadcasts this over the WebSocket -> must be JSON safe
            message = json.dumps({"type": "gpu_stats", "stats": stats})
            assert '"gpu_stats"' in message
            assert '"history"' in message

        history = stats["history"]
        assert set(history.keys()) == {"gpu_util", "vram_used", "cpu_util", "ram_used"}
        # 10 iterations x 2 update_history() calls each (get_stats + loop) = 20
        for values in history.values():
            assert len(values) == 20
            assert all(isinstance(v, (int, float)) for v in values)
    finally:
        monitor.cleanup()


def test_history_is_capped_by_history_size():
    """The double update must not break the ``history_size`` bound."""
    monitor = _monitor(history_size=6)
    for _ in range(10):
        stats = monitor.get_stats()
        monitor.update_history(stats)
        stats["history"] = monitor.get_history()

    for values in stats["history"].values():
        assert len(values) == 6
    monitor.cleanup()


def test_init_is_idempotent():
    mon = _monitor()
    assert mon.init() is mon
    assert mon.init() is mon
    assert mon.available is True
    mon.cleanup()


def test_init_recovers_unavailable_monitor():
    """A monitor built before the driver was ready must recover via init()."""
    gpu_monitor.set_mxsml_backend(mxsml_mock)
    mon = gpu_monitor.MXSMLMonitor()
    mon.available = False  # simulate "driver not ready at __init__ time"

    mon.init()
    assert mon.available is True

    stats = mon.get_stats()
    assert stats["device_count"] == MOCK_GPU_COUNT
    assert stats["gpu_percent"] > 0
    mon.cleanup()


def test_detect_metax_with_and_without_backend():
    gpu_monitor.set_mxsml_backend(mxsml_mock)
    assert gpu_monitor.detect_metax() is True
    assert gpu_monitor.is_mxsml_available() is True

    gpu_monitor.set_mxsml_backend(None)
    assert gpu_monitor.is_mxsml_available() is False
    # no hardware on this machine -> detection must fail cleanly, not raise
    assert gpu_monitor.detect_metax() is False

    gpu_monitor.set_mxsml_backend(mxsml_mock)


def test_create_monitor_forced_platform():
    gpu_monitor.set_mxsml_backend(mxsml_mock)
    for name in ("metax", "mxsml"):
        mon = gpu_monitor.create_monitor(platform=name)
        assert isinstance(mon, gpu_monitor.MXSMLMonitor)
        mon.cleanup()


# ---------------------------------------------------------------------------
# robustness: partially broken backend must not raise
# ---------------------------------------------------------------------------
def test_partial_failures_are_tolerated():
    class BrokenBackend:
        """Backend where every metric query fails, but enumeration works."""

        MXSML_VERSION_DRIVER = mxsml_mock.MXSML_VERSION_DRIVER
        MXSML_TEMPERATURE_HOTSPOT = mxsml_mock.MXSML_TEMPERATURE_HOTSPOT
        MXSML_TEMPERATURE_CORE = mxsml_mock.MXSML_TEMPERATURE_CORE
        MXSML_TEMPERATURE_SOC = mxsml_mock.MXSML_TEMPERATURE_SOC
        MXSML_PMBUS_SOC = mxsml_mock.MXSML_PMBUS_SOC
        MXSML_USAGE_XCORE = mxsml_mock.MXSML_USAGE_XCORE
        MXSML_USAGE_MMA = mxsml_mock.MXSML_USAGE_MMA
        MXSML_USAGE_VPUD = mxsml_mock.MXSML_USAGE_VPUD

        def __getattr__(self, name):
            if name.startswith("MXSML_"):
                return 0

            def _boom(*args, **kwargs):
                raise mxsml_mock.MXSMLError(3)

            return _boom

        # enumeration must still work
        def mxSmlInit(self):
            return None

        def mxSmlGetDeviceCount(self):
            return 1

        def mxSmlGetPfDeviceCount(self):
            return 0

        def mxSmlGetMacaVersion(self):
            return "broken"

        def mxSmlGetDeviceInfo(self, device_id):
            return mxsml_mock.mxSmlGetDeviceInfo(0)

        def mxSmlGetDeviceVersion(self, device_id, unit):
            return "broken"

        def mxSmlGetDeviceDieCount(self, device_id):
            return 2

    gpu_monitor.set_mxsml_backend(BrokenBackend())
    mon = gpu_monitor.MXSMLMonitor()
    assert mon.available is True
    stats = mon.get_stats()  # must not raise

    assert stats["gpu_percent"] == 0
    assert stats["temp_c"] is None
    assert stats["power_w"] is None
    # aggregates sum over the (unsupported) devices -> 0, never None/NaN
    assert stats["vram_used_gb"] == 0
    assert stats["vram_total_gb"] == 0
    assert stats["vram_percent"] == 0
    mon.cleanup()

    gpu_monitor.set_mxsml_backend(mxsml_mock)


def test_factory_returns_mxsml_monitor():
    gpu_monitor.set_mxsml_backend(mxsml_mock)
    mon = gpu_monitor.create_monitor()
    assert isinstance(mon, gpu_monitor.MXSMLMonitor)
    assert isinstance(mon, gpu_monitor.GPUMonitor)
    mon.cleanup()


def test_fallback_stats_protocol():
    gpu_monitor.set_mxsml_backend(mxsml_mock)
    mon = _monitor()
    mon.available = False  # simulate disabled monitoring
    stats = mon.get_stats()
    assert "unavailable" in stats["platform"].lower()
    missing = EXPECTED_STATS_KEYS - set(stats.keys())
    assert not missing, f"missing protocol keys in fallback: {missing}"
    mon.cleanup()


# ---------------------------------------------------------------------------
# standalone runner
# ---------------------------------------------------------------------------
def _run_all():
    tests = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_")]
    failures = []
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failures.append((name, e))
            print(f"FAIL  {name}: {e}")
        except Exception as e:  # noqa: BLE001
            failures.append((name, e))
            print(f"ERROR {name}: {type(e).__name__}: {e}")

    print(f"\n{len(tests) - len(failures)}/{len(tests)} tests passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run_all())
