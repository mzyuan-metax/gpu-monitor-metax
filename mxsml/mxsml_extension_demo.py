""" If you want to run mxsml_demo.py, please install the following packages beforehand
    - MetaX Driver package
    - MetaX SDK package

    e.g.
    ```
        python3 -m pip install /opt/maca/share/mxsml/pymxsml-*.whl
        python3 mxsml_extension_demo.py
    ```"""

from pymxsml.mxsml_extension import *

print("============ start ============")
mxSmlExInit()

print("---------- error msg ----------")
for item in [
    MXSMLEX_SUCCESS,
    MXSMLEX_ERROR_UNINITIALIZED,
    MXSMLEX_ERROR_INVALID_ARGUMENT,
    MXSMLEX_ERROR_NOT_SUPPORTED,
    MXSMLEX_ERROR_NO_PERMISSION,
    MXSMLEX_ERROR_ALREADY_INITIALIZED,
    MXSMLEX_ERROR_NOT_FOUND,
    MXSMLEX_ERROR_INSUFFICIENT_SIZE,
    MXSMLEX_ERROR_INSUFFICIENT_POWER,
    MXSMLEX_ERROR_DRIVER_NOT_LOADED,
    MXSMLEX_ERROR_TIMEOUT,
    MXSMLEX_ERROR_IRQ_ISSUE,
    MXSMLEX_ERROR_LIBRARY_NOT_FOUND,
    MXSMLEX_ERROR_FUNCTION_NOT_FOUND,
    MXSMLEX_ERROR_CORRUPTED_INFOROM,
    MXSMLEX_ERROR_GPU_IS_LOST,
    MXSMLEX_ERROR_RESET_REQUIRED,
    MXSMLEX_ERROR_OPERATING_SYSTEM,
    MXSMLEX_ERROR_LIB_RM_VERSION_MISMATCH,
    MXSMLEX_ERROR_IN_USE,
    MXSMLEX_ERROR_MEMORY,
    MXSMLEX_ERROR_NO_DATA,
    MXSMLEX_ERROR_VGPU_ECC_NOT_SUPPORTED,
    MXSMLEX_ERROR_INSUFFICIENT_RESOURCES,
    MXSMLEX_ERROR_FREQ_NOT_SUPPORTED,
    MXSMLEX_ERROR_ARGUMENT_VERSION_MISMATCH,
    MXSMLEX_ERROR_DEPRECATED,
    MXSMLEX_ERROR_UNKNOWN,
]:
    print("MXSML_ERROR#" + str(item) + ": " + mxSmlExErrorString(item))

print("---------- system info ----------")
print("Driver version:", mxSmlExSystemGetDriverVersion())
print("Mxsml version:", mxSmlExSystemGetMXSMLEXVersion())


deviceCount = mxSmlExDeviceGetCount()
print("Device count:", str(deviceCount))
if deviceCount > 0:
    index_handle0 = mxSmlExDeviceGetHandleByIndex(0)
    uuid = mxSmlExDeviceGetUUID(index_handle0)
    uuid_handle = mxSmlExDeviceGetHandleByUUID(uuid)
    # busid_handle = mxSmlExDeviceGetHandleByPciBusId("0000:4f:00.0")

    if deviceCount > 1:
        index_handle1 = mxSmlExDeviceGetHandleByIndex(1)
        print("P2P status(MELINK):", mxSmlExDeviceGetP2PStatus(index_handle0, index_handle1, MXSMLEX_P2P_CAPS_INDEX_MXLINK))
        try:
            print("Topology common ancestor:", mxSmlExDeviceGetTopologyCommonAncestor(index_handle0, index_handle1))
        except MXSMLEXError as e:
            print("Get topology common ancestor failed:", e)

for idx in range(deviceCount):
    print("------------ GPU#" + str(idx) + " ------------")
    handle = mxSmlExDeviceGetHandleByIndex(idx)

    print("device name:", mxSmlExDeviceGetName(handle))
    print("UUID:       ", mxSmlExDeviceGetUUID(handle))
    print("Pci info:   ", mxSmlExDeviceGetPciInfo(handle))

    print("Minor number:", mxSmlExDeviceGetMinorNumber(handle))
    print("MetaXLink state:", mxSmlExDeviceGetMetaXLinkState(handle, 0))
    print("CPU affinity:", [affi for affi in mxSmlExDeviceGetCpuAffinity(handle, 1)])
    mxSmlExDeviceResetApplicationsClocks(handle)
    print("Auto boosted clocks enable state:", mxSmlExDeviceGetAutoBoostedClocksEnabled(handle))

    try:
        print("Current pcie width:", mxSmlExDeviceGetCurrPcieLinkWidth(handle))
    except MXSMLEXError as e:
        print("Get current pcie width failed:", e)

    try:
        print("Max pcie width:", mxSmlExDeviceGetMaxPcieLinkWidth(handle))
    except MXSMLEXError as e:
        print("Get max pcie width failed:", e)

    try:
        print("Power management limit:", mxSmlExDeviceGetPowerManagementLimit(handle))
    except MXSMLEXError as e:
        print("Get power management limit failed:", e)

    try:
        print("Board power limit:", mxSmlExDeviceGetBoardPowerLimit(handle), "mW")
        print("Board power default limit:", mxSmlExDeviceGetBoardPowerDefaultLimit(handle), "mW")
        min_limit, max_limit = mxSmlExDeviceGetBoardPowerLimitConstraints(handle)
        print("Board power limit constraints: {} mW - {} mW".format(min_limit, max_limit))
    except MXSMLEXError as e:
        print("Get board power limit info failed:", e)

    print("Processes:")
    processes = mxSmlExDeviceGetComputeRunningProcesses(handle)
    if len(processes) == 0:
        print("no process")
    for proc in processes:
        print(proc)

    print("Memory info:")
    memory_info = mxSmlExDeviceGetMemoryInfo(handle)
    print("  total memory:", memory_info.total)
    print("  free memory: ",memory_info.free)
    print("  used memory: ",memory_info.used)

    print("Compute capability:")
    major, minor = mxSmlExDeviceGetComputeCapability(handle)
    print("  major:", major)
    print("  minor:", minor)

    try:
        print("Pcie throughput:")
        print("  tx:   ", mxSmlExGetPcieThroughput(handle, MXSMLEX_PCIE_UTIL_TX_BYTES))
        print("  rx:   ", mxSmlExGetPcieThroughput(handle, MXSMLEX_PCIE_UTIL_TX_BYTES))
    except MXSMLEXError as e:
        print(e)

    print("Field values:")
    for field in mxSmlExDeviceGetFieldValues(handle, [(MXSMLEX_FI_DEV_METAXLINK_LINK_COUNT, 5), 1]):
        print(field)

    print("Fan info")
    try:
        # Not support: mxSmlExDeviceGetFanSpeed and mxSmlExDeviceGetFanSpeed_v2
        print("Fan speed:  ", mxSmlExDeviceGetFanSpeed(handle))
        print("Fan speed:  ", mxSmlExDeviceGetFanSpeed_v2(handle, 0))
    except MXSMLEXError as e:
        print(e)

    print("Utilization:")
    try:
        # Only support c-class GPU
        util = mxSmlExDeviceGetUtilizationRates(handle)
        print("  gpu:   ", util.gpu)
        print("  memory:", util.memory)
    except MXSMLEXError as e:
        print(e)

    try:
        print("MetaXLink port#4 remote pci info:", mxSmlExDeviceGetMetaXLinkRemotePciInfo(handle, 4))
    except MXSMLEXError as e:
        print("Get metaxlink port#4 remote pci info failed:", e)

    try:
        # Only support c-class GPU
        print("Temperature:", mxSmlExDeviceGetTemperature(handle, MXSMLEX_TEMPERATURE_GPU))
    except MXSMLEXError as e:
        print("Get temperature failed:", e)

    try:
        # Only support c-class GPU
        print("Power usage:", mxSmlExDeviceGetPowerUsage(handle))
    except MXSMLEXError as e:
        print("Get power usage failed:", e)

    try:
        # Only support c-class GPU
        print("Temperature threshold(shutdown):", mxSmlExDeviceGetTemperatureThreshold(handle, MXSMLEX_TEMPERATURE_THRESHOLD_SHUTDOWN))
    except MXSMLEXError as e:
        print("Get temperature threshold failed:", e)

    print("Clock info:")
    try:
        # Only support c-class GPU
        print("  xcore:", mxSmlExDeviceGetClockInfo(handle, MXSMLEX_CLOCK_SM))
        print("  mc0:  ", mxSmlExDeviceGetClockInfo(handle, MXSMLEX_CLOCK_MEM))
        print("  vpue0:", mxSmlExDeviceGetClockInfo(handle, MXSMLEX_CLOCK_VIDEO))
    except MXSMLEXError as e:
        print(e)

    try:
        # Only support c-class GPU
        print("Current clocks throttle reason:", mxSmlExDeviceGetCurrentClocksThrottleReasons(handle))
    except MXSMLEXError as e:
        print("Get current clocks throttle reason failed:", e)

    try:
        # Only support c-class GPU
        print("Supported clocks throttle reason:", mxSmlExDeviceGetSupportedClocksThrottleReasons(handle))
    except MXSMLEXError as e:
        print("Get supported clocks throttle reason failed:", e)


    try:
        # Only support c-class GPU
        print("Supported memory clocks:", mxSmlExDeviceGetSupportedMemoryClocks(handle))
    except MXSMLEXError as e:
        print("Get supported memory clocks failed:", e)

    try:
        # Only support c-class GPU
        print("Supported graphics clocks:", mxSmlExDeviceGetSupportedGraphicsClocks(handle, None))
    except MXSMLEXError as e:
        print("Get supported graphics clocks failed:", e)

    # Only support c-class GPU
    # print("Set applications clocks:", mxSmlExDeviceSetApplicationsClocks(handle, 1800, 1125))

    try:
        # Only support c-class GPU
        print("Applications clock(VPUE0):", mxSmlExDeviceGetApplicationsClock(handle, MXSMLEX_CLOCK_VIDEO))
    except MXSMLEXError as e:
        print("Get applications clock(VPUE0) failed:", e)

    try:
        # Only support n-class GPU
        print("Performance state:", mxSmlExDeviceGetPerformanceState(handle))
    except MXSMLEXError as e:
        print("Get performance state failed:", e)

    # Not support
    # mxSmlExDeviceSetAutoBoostedClocksEnabled(handle, MXSMLEX_FEATURE_ENABLED)

    try:
        print("MetaXLink remote device type:", mxSmlExDeviceGetMetaXLinkRemoteDeviceType(handle, 4))
    except MXSMLEXError as e:
        print("Get MetaXLink remote device type failed:", e)


mxSmlExShutdown()
print("============ end ============")
