""" If you want to run mxsml_demo.py, please install the following packages beforehand
    - MetaX Driver package
    - MetaX SDK package

    e.g.
    ```
        python3 -m pip install /opt/maca/share/mxsml/pymxsml-*.whl
        python3 mxsml_demo.py
    ```"""

from pymxsml import *
import threading

print("============ start ============")
mxSmlInit()

print("---------- error msg ----------")
for item in [
    MXSML_ERROR_FAILURE,
    MXSML_ERROR_NO_DEVICE,
    MXSML_ERROR_OPERATION_NOT_SUPPORT,
    MXSML_ERROR_SYSFS_ERROR,
    MXSML_ERROR_SYSFS_WRITE_ERROR,
    MXSML_ERROR_INVALID_DEVICE_ID,
    MXSML_ERROR_INVALID_DID_ID,
    MXSML_ERROR_PERMISSION_DENIED,
    MXSML_ERROR_INVALID_INPUT,
    MXSML_ERROR_INSUFFICIENT_SIZE,
    MXSML_ERROR_RESERVED3,
    MXSML_ERROR_IO_CONTROL_FAILURE,
    MXSML_ERROR_MMAP_FAILURE,
    MXSML_ERROR_UN_MMAP_FAILURE,
    MXSML_ERROR_INVALID_INPUT_FOR_MMAP,
    MXSML_ERROR_RESERVED1,
    MXSML_ERROR_RESERVED2,
    MXSML_ERROR_TARGET_VF_NOT_FOUND,
    MXSML_ERROR_INVALID_FREQUENCY,
    MXSML_ERROR_FLR_NOT_READY,
    MXSML_ERROR_OPEN_DEVICE_FILE_FAILURE,
    MXSML_ERROR_CLOSE_DEVICE_FILE_FAILURE,
    MXSML_ERROR_BUSY_DEVICE,
    MXSML_ERROR_MMIO_NOT_ENOUGH,
    MXSML_ERROR_GET_PCI_BRIDGE_FAILURE,
    MXSML_ERROR_LOAD_DLL_FAILURE,
]:
    print("MXSML_ERROR#" + str(item) + ": " + mxSmlGetErrorString(item))

print("---------- system info ----------")
print("MACA version:", mxSmlGetMacaVersion())

print("Limited device info:")
limited_devices = mxSmlGetAllLimitedDevices()
limited_count = limited_devices.number
limited_ids = []
for i in range(limited_count):
    limited_ids.append(limited_devices.deviceId[i])
print("  number:", limited_count)
print("  ids:   ", limited_ids)

available_device_ids = [idx for idx in range(mxSmlGetDeviceCount())]
pf_device_ids =[idx + 100 for idx in range(mxSmlGetPfDeviceCount())]
all_device_ids = available_device_ids + pf_device_ids
print("All devices:", all_device_ids)

for device_id in all_device_ids:
    print("------------ GPU#" + str(device_id) + " ------------")
    device = mxSmlGetDeviceInfo(device_id)
    print("Device uuid:", device.uuid)
    print("Device id:", device.deviceId)
    print("Device bdf id:", device.bdfId)
    print("Device gpu id:", device.gpuId)
    print("Device node id:", device.nodeId)
    print("Device brand:", device.brand)
    print("Device mode:", device.mode)
    print("Device name:", device.deviceName)

    try:
        # VF device does not contain chip serial info
        print("Device serial:", mxSmlGetChipSerial(device_id))
    except MXSMLError as e:
        print("Get device serial failed:", e)

    print("Version:")
    print("  KMD: ", mxSmlGetDeviceVersion(device_id, MXSML_VERSION_DRIVER))
    print("  smp0:", mxSmlGetDeviceVersion(device_id, MXSML_VERSION_SMP0))
    print("  smp1:", mxSmlGetDeviceVersion(device_id, MXSML_VERSION_SMP1))

    if device.mode == MXSML_VIRTUALIZATION_MODE_PF:
        print("Corresponding virtual device info:")
        virtual_devices = mxSmlGetVirtualDevicesByPhysicalId(device_id)
        virtual_count = virtual_devices.number
        virtual_ids = []
        for i in range(virtual_count):
            virtual_ids.append(virtual_devices.deviceId[i])
        print("  number:", virtual_count)
        print("  ids:   ", virtual_ids)

    try:
        # N-class device does not contain pptable version info
        print("Pptable version:", mxSmlGetPptableVersion(device_id))
    except MXSMLError as e:
        print(e)

    print("Memory info:")
    try:
        # Can not get memory info of PF device
        memory_info = mxSmlGetMemoryInfo(device_id)
        print("  vis_vram total: " + str(memory_info.visVramTotal))
        print("  vis_vram use:   " + str(memory_info.visVramUse))
        print("  vram total:     " + str(memory_info.vramTotal))
        print("  vram use:       " + str(memory_info.vramUse))
        print("  xtt total:      " + str(memory_info.xttTotal))
        print("  xtt use:        " + str(memory_info.xttUse))
    except MXSMLError as e:
        print(e)

    print("Pmbus info(soc):")
    try:
        # VF device does not contain pmbus info
        pmbus_info = mxSmlGetPmbusInfo(device_id, MXSML_PMBUS_SOC)
        print("  voltage:", pmbus_info.voltage)
        print("  current:", pmbus_info.current)
        print("  power:  ", pmbus_info.power)
    except MXSMLError as e:
        print(e)

    print("Temperature:")
    try:
        # VF device does not contain temperature
        print("  chip hotspot:", mxSmlGetTemperatureInfo(device_id, MXSML_TEMPERATURE_HOTSPOT))
        print("  board soc:", mxSmlGetTemperatureInfo(device_id, MXSML_TEMPERATURE_SOC))
        print("  board core:", mxSmlGetTemperatureInfo(device_id, MXSML_TEMPERATURE_CORE))
    except MXSMLError as e:
        print(e)

    print("Board Power info(soc):")
    try:
        # VF device does not contain board power info
        board_infos = mxSmlGetBoardPowerInfo(device_id)
        for i, info in enumerate(board_infos):
            print("  Way" + str(i))
            print("    voltage:", info.voltage)
            print("    current:", info.current)
            print("    power:  ", info.power)
    except MXSMLError as e:
        print(e)

    print("Eeprom info:")
    try:
        # VF device does not contain eeprom info
        eeprom_info = mxSmlGetEepromInfo(device_id)
        for content in eeprom_info.content.split(";"):
            if content:
                print("  " + content)
    except MXSMLError as e:
        print(e)

    print("Ras error data:")
    try:
        # VF device does not contain ras error data
        ras = mxSmlGetRasErrorData(device_id)
        print("  size:", ras.showRasErrorSize)
    except MXSMLError as e:
        print(e)

    print("Ras v2 error data:")
    try:
        # VF device does not contain ras error data
        ras = mxSmlGetRasErrorData_v2(device_id)
        print("  size:", ras.showRasErrorSize)
    except MXSMLError as e:
        print(e)

    print("Ras status data:")
    try:
        # VF device does not contain ras status data
        ras = mxSmlGetRasStatusData(device_id)
        print("  size:", ras.showRasStatusSize)
    except MXSMLError as e:
        print(e)

    print("Pcie info:")
    try:
        # VF device does not contain pcie info
        pcie_info = mxSmlGetPcieInfo(device_id)
        print("  speed:", pcie_info.speed)
        print("  width:", pcie_info.width)
    except MXSMLError as e:
        print(e)

    print("Pcie max info:")
    try:
        # VF device does not contain pcie max info
        pcie_info = mxSmlGetPcieMaxLinkInfo(device_id)
        print("  speed:", pcie_info.speed)
        print("  width:", pcie_info.width)
    except MXSMLError as e:
        print(e)

    print("Power state(vpud):")
    try:
        # VF device does not contain power state info
        states = mxSmlGetPowerStateInfo(device_id, MXSML_DPM_VPUD)
        for i, state in enumerate(states):
            print("  VPUD#" + str(i) + ": " + str(state))
    except MXSMLError as e:
        print(e)

    try:
        # VF device does not contain pci power state info
        print("Pci power state:", mxSmlGetPciPowerState(device_id))
    except MXSMLError as e:
        print(e)

    print("Codec status:")
    try:
        # PF device does not contain codec status info
        status = mxSmlGetCodecStatus(device_id)
        print("  encoder:", status.encoder)
        print("  decoder:", status.decoder)
    except MXSMLError as e:
        print(e)

    print("Clock frequency(vpud):")
    try:
        # VF device does not contain clock frequency info
        clocks = mxSmlGetClocks(device_id, MXSML_CLOCK_VPUD)
        for i, clock in enumerate(clocks):
            print("  VPUD#" + str(i) + ": " + str(clock) + " MHz")
    except MXSMLError as e:
        print(e)

    print("Hbm bandwidth:")
    try:
        # VF device does not contain hbm bandwidth info
        bw = mxSmlGetHbmBandWidth(device_id)
        print("  req: ", bw.hbmBandwidthReqTotal)
        print("  resp:", bw.hbmBandwidthRespTotal)
    except MXSMLError as e:
        print(e)

    print("Pcie through put:")
    try:
        # VF device does not contain pcie through put info
        through_put = mxSmlGetPcieThroughput(device_id)
        print("  rx:", through_put.rx)
        print("  tx:", through_put.tx)
    except MXSMLError as e:
        print(e)

    print("Dma bandwidth:")
    try:
        # VF device does not contain dma bandwidth info
        bandwidths = mxSmlGetDmaBandwidth(device_id)
        for i, bw in enumerate(bandwidths):
            print("  dma#" + str(i))
            print("    read req:  ", bw.readReqBandwidth)
            print("    read resp: ", bw.readRespBandwidth)
            print("    write req: ", bw.writeReqBandwidth)
            print("    write resp:", bw.writeRespBandwidth)
    except MXSMLError as e:
        print(e)

    print("MetaXLink bandwidth(INPUT):")
    try:
        # VF device does not contain metaxlink bandwidth info
        bw = mxSmlGetMetaXLinkBandwidth(device_id, MXSML_METAXLINK_INPUT)
        for i, item in enumerate(bw):
            print("  PORT#" + str(i + 1))
            print("    request: ", item.requestBandwidth)
            print("    response:", item.responseBandwidth)
    except MXSMLError as e:
        print(e)

    print("MetaXLink remote info:")
    for port in range(1, MXSML_METAX_LINK_NUM + 1):
        try:
            # VF device does not contain metaxlink remote info
            remote = mxSmlGetMetaXLinkRemoteInfo(device_id, port)
            print("  PORT#" + str(port))
            print("    device id:", remote.deviceId)
            print("    bdf id   :", remote.bdfId)
        except MXSMLError_OperationNotSupport as e:
            print(e)
            break
        except MXSMLError_NoDevice:
            pass
        except MXSMLError_Failure:
            pass

    print("Topo info:")
    try:
        # PF device does not contain topo info
        for dst in available_device_ids:
            topo = mxSmlGetDeviceTopology(device_id, dst)
            print("  ->GPU#" + str(dst) + ": " + str(topo))
    except MXSMLError as e:
        print(e)

    print("Distance:")
    try:
        # PF device does not contain distance info
        for dst in available_device_ids:
            distance = mxSmlGetDeviceDistance(device_id, dst)
            print("  ->GPU#" + str(dst) + ": " + str(distance))
    except MXSMLError as e:
        print(e)

    print("CPU affinity:")
    try:
        # PF device does not contain cpu affinity info
        cpu_set = mxSmlGetCpuAffinity(device_id, 5)
        for item in cpu_set:
            print(item)
    except MXSMLError as e:
        print(e)

    print("Node affinity:")
    try:
        # PF device does not contain node affinity info
        node_set = mxSmlGetNodeAffinity(device_id, 5)
        for item in cpu_set:
            print(item)
    except MXSMLError as e:
        print(e)

    try:
        # C-class device and VF device does not contain pci delay info
        print("Pci delay:", mxSmlGetPciDelay(device_id))
    except MXSMLError as e:
        print("Get pci delay failed:", e)

    try:
        # VF device does not contain dpm clock info
        print("Dpm clock info(xcore):", mxSmlGetDpmIpClockInfo(device_id, MXSML_DPM_XCORE))
    except MXSMLError as e:
        print("Get dpm clock info failed:", e)

    try:
        # VF device does not contain dpm vdd info
        print("Dpm vdd info(xcore):", mxSmlGetDpmIpVddInfo(device_id, MXSML_DPM_XCORE))
    except MXSMLError as e:
        print("Get dpm vdd info failed:", e)

    try:
        # VF device does not contain dpm level info
        print("Current dpm performance level(xcore):", mxSmlGetCurrentDpmIpPerfLevel(device_id, MXSML_DPM_XCORE))
    except MXSMLError as e:
        print("Get current dpm performance level failed:", e)

    try:
        # VF device does not contain dpm level
        print("Max dpm performance level(xcore):", mxSmlGetDpmIpMaxPerfLevel(device_id, MXSML_DPM_XCORE))
    except MXSMLError as e:
        print("Get max dpm performance level failed:", e)

    try:
        print("Current usage(xcore):", mxSmlGetDeviceIpUsage(device_id, MXSML_DPM_XCORE))
    except MXSMLError as e:
        print("Get current usage failed:", e)

    print("Xcore ap usage:")
    try:
        # only support C-class device
        usage = mxSmlGetXcoreApUsage(device_id)
        for i, dpc_usage_array in enumerate(usage):
            print("  dpc", i, ":", dpc_usage_array)
    except MXSMLError as e:
        print(e)

    try:
        # PF device does not contain xcore ap usage toggle info
        print("Xcore ap usage toggle:", mxSmlGetApUsageToggle(device_id))
    except MXSMLError as e:
        print(e)

    print("Firmware level:")
    try:
        # VF device does not contain firmware level info
        print("  smp0:", mxSmlGetFwIpLoglevel(device_id, MXSML_FW_IPNAME_SMP0))
        print("  ccx0:", mxSmlGetFwIpLoglevel(device_id, MXSML_FW_IPNAME_CCX0))
    except MXSMLError as e:
        print(e)

    print("Firmware level(all):")
    try:
        # VF device does not contain firmware log level info
        log_level = mxSmlGetFwLoglevel(device_id)
        for i in range(log_level.smpCount):
            print("  smp" + str(i) + ": " + str(log_level.smp[i]))
        for i in range(log_level.ccxCount):
            print("  ccx" + str(i) + ": " + str(log_level.ccx[i]))
    except MXSMLError as e:
        print(e)

    try:
        # VF device does not contain ecc state info
        print("Ecc state:", mxSmlGetEccState(device_id))
    except MXSMLError as e:
        print(e)

    print("MetaXLink info:")
    try:
        # VF and PF device does not contain metaxlink info
        mxlk_info_v2 = mxSmlGetMetaXLinkInfo_v2(device_id)
        for id, info in enumerate(mxlk_info_v2, 1):
            print("  Link#" + str(id))
            print("    speed:", info.speed)
            print("    width:", info.width)

        mxlk_info = mxSmlGetMetaXLinkInfo(device_id)  # dprecated
        for i in range(MXSML_METAX_LINK_NUM):
            print("  Link#" + str(i + 1))
            print("    speed:", mxlk_info.speed[i])
            print("    width:", mxlk_info.width[i])
    except MXSMLError as e:
        print(e)

    try:
        # VF device does not contain sriov state info
        print("Sriov state:", mxSmlGetSriovState(device_id))
    except MXSMLError as e:
        print("get sriov state failed:", e)

    try:
        # Call this Function requires sudo permission
        print("pcie slot:", mxSmlGetDeviceSlot(device_id))
    except MXSMLError as e:
        print("get pcie slot failed:", e)

    print("Optical module status:")
    try:
        status_array = mxSmlGetOpticalModuleStatus(device_id)
        for status in status_array:
            print(status)
    except MXSMLError as e:
        print("get optical module status failed:", e)

    print("Optical module info:")
    try:
        info_array = mxSmlGetOpticalModuleInfo(device_id)
        for info in info_array:
            print(info)
    except MXSMLError as e:
        print("get optical module info failed:", e)

    print("Real path:", mxSmlGetDeviceRealPath(device_id))

    try:
        print("Clocks throttle reason:", mxSmlGetCurrentClocksThrottleReason(device_id))
    except MXSMLError as e:
        print("Get clocks throttle reason failed:", e)

    try:
        print("Thermal design power:", mxSmlGetBoardPowerLimit(device_id))
    except MXSMLError as e:
        print("Get thermal design power failed:", e)

    try:
        reason = mxSmlGetDeviceUnavailableReason(device_id)
        print("Get device unavailable reason:", reason.unavailableCode)
        if reason.unavailableCode != 0:
            print(reason.unavailableReason)
    except MXSMLError as e:
        print("Get device unavailable reason failed:", e)

    try:
        eccCounts = mxSmlGetTotalEccErrors(device_id)
        print("Get device ecc sram CE count:", eccCounts)
    except MXSMLError as e:
        print("Get device ecc sram CE failed:", e)

    try:
        topoInfo = mxSmlGetMetaXLinkTopo(device_id)
        print("Get device metaxlink topo info:", topoInfo)
    except MXSMLError as e:
        print("Get device metaxlink topo info failed:", e)

for device_id in limited_ids:
    print("------------ GPU#" + str(device_id) + "(limited device) ------------")
    device = mxSmlGetLimitedDeviceInfo(device_id)
    print("Device uuid:", device.uuid)
    print("Device id:", device.deviceId)
    print("Device bdf id:", device.bdfId)
    print("Device gpu id:", device.gpuId)
    print("Device node id:", device.nodeId)
    print("Device brand:", device.brand)
    print("Device mode:", device.mode)
    print("Device name:", device.deviceName)


print("------------ Process Info ------------")
proc_number = mxSmlGetNumberOfProcess()
print("Process number:", proc_number)

if proc_number != 0:
    for proc in mxSmlGetProcessInfo(proc_number):
        print("  pid:" + str(proc.processId) + "  process: " + str(proc.processName))

    for proc in mxSmlGetProcessInfo_v2(proc_number):
        print("  (v2)pid:" + str(proc.processId) + "  process: " + str(proc.processName))

    for proc in mxSmlGetProcessInfo_v3(proc_number):
        print("  (v3)pid:" + str(proc.processId) + "  process: " + str(proc.processName)
            + "  gpuid: " + str(proc.processGpuInfo[0].gpuId) + "  sgpuid: " + str(proc.processGpuInfo[0].sgpuId))

    for i in available_device_ids:
        print("  GPU#" + str(i))
        for proc in mxSmlGetSingleGpuProcess(i):
            print("    pid:" + str(proc.processId) + "  process: " + str(proc.processName))

        for proc in mxSmlGetSingleGpuProcess_v2(i):
            print("    (v2)pid:" + str(proc.processId) + "  process: " + str(proc.processName))

try:
    mxSmlInitWithFlags(MXSML_INIT_FLAG_REINIT)
    print("reinit successful")
except MXSMLError as e:
    print("reinit failed:", e)

print("============ end ============")


## Setting function ##
# import time

# print("Set dpm max level(xcore->8):", mxSmlSetDpmIpMaxPerfLevel(device_id, MXSML_DPM_XCORE, 9))

# print("Dump vbios:", mxSmlDumpVbios(device_id, 60, "/xxx/xxx/metax_vbios.bin"))
# print(os.path.exists("/xxx/xxx/metax_vbios" + str(device_id) + ".bin"))

# print("Upgrade vbios:", mxSmlVbiosUpgrade(device_id, 60, <vbios bin path>))

# print("Unlock key:", mxSmlSetUnlockKey(device_id, <privilege key id>))

# print("Set cpu affinity:", mxSmlSetCpuAffinity(device_id))

# print("Clear cpu affinity:", mxSmlClearCpuAffinity(device_id))

# print("Warm reset:", mxSmlReset(device_id))
# time.sleep(10)

# print("Set pcie speed(gen4):", mxSmlSetPciSpeed(device_id, MXSML_PCI_GEN_4))

# print("Set pcie delay(90ms):", mxSmlSetPciDelay(device_id, 90))

# print("Set firmware log level(all-info):", mxSmlSetFwLoglevel(device_id, MXSML_FW_IPNAME_ALL, MXSML_LOGLEVEL_INFO))

# print("Set ap usage toggle(enable):", mxSmlSetApUsageToggle(device_id, 1))

# print("Set ecc state(enable):", mxSmlSetEccState(device_id, 1))

# print("Function reset:", mxSmlFunctionLevelReset(device_id))
# time.sleep(10)

# print("Function reset:", mxSmlFunctionLevelResetVfFromPf(device_id))
# time.sleep(10)

## Get Eid Demo ##
# def GetEidEvent(device_id):
#         event_set = mxSmlEventSetCreate()
#         mxSmlDeviceRegisterEvents(device_id, mxSmlEventTypeEid, event_set)
#         event_data = mxSmlEventSetWait(event_set)
#         print("Function EventSetWait device id:", event_data.deviceId)
#         print("Function EventSetWait eid:", event_data.type)
#         print("Function EventSetWait data:", event_data.eventData)
#         mxSmlEventSetFree(event_set)

# thread_list = []
# for device_id in all_device_ids:
#     t = threading.Thread(target=GetEidEvent, args=(device_id,))
#     thread_list.append(t)
#     t.start()

# for t in thread_list:
#     t.join()