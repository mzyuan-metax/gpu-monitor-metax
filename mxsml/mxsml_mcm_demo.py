""" If you want to run mxsml_demo.py, please install the following packages beforehand
    - MetaX Driver package
    - MetaX SDK package

    e.g.
    ```
        python3 -m pip install /opt/maca/share/mxsml/pymxsml-*.whl
        python3 mxsml_mcm_demo.py
    ```"""

from pymxsml import *

print("============ start ============")
mxSmlInit()

available_device_ids = [idx for idx in range(mxSmlGetDeviceCount())]
pf_device_ids =[idx + 100 for idx in range(mxSmlGetPfDeviceCount())]
if 0 == (mxSmlGetDeviceCount() + mxSmlGetPfDeviceCount()):
    print("No available device")
    exit(0)

device_id = 0
die_count = mxSmlGetDeviceDieCount(device_id)
print("GPU#0 die count:", die_count)

for die_id in range(die_count):
    print("------------ GPU#0 Die" + str(die_id) + " ------------")

    print("Version:")
    print("  smp0:", mxSmlGetDeviceDieVersion(device_id, die_id, MXSML_VERSION_SMP0))
    print("  smp1:", mxSmlGetDeviceDieVersion(device_id, die_id, MXSML_VERSION_SMP1))

    print("Memory info:")
    try:
        # Can not get memory info of PF device
        memory_info = mxSmlGetDieMemoryInfo(device_id, die_id)
        print("  vis_vram total: " + str(memory_info.visVramTotal))
        print("  vis_vram use:   " + str(memory_info.visVramUse))
        print("  vram total:     " + str(memory_info.vramTotal))
        print("  vram use:       " + str(memory_info.vramUse))
        print("  xtt total:      " + str(memory_info.xttTotal))
        print("  xtt use:        " + str(memory_info.xttUse))
    except MXSMLError as e:
        print(e)

    print("Temperature:")
    try:
        # VF device does not contain temperature
        print("  chip hotspot:", mxSmlGetDieTemperatureInfo(device_id, die_id, MXSML_TEMPERATURE_HOTSPOT))
        print("  board soc:", mxSmlGetDieTemperatureInfo(device_id, die_id, MXSML_TEMPERATURE_SOC))
        print("  board core:", mxSmlGetDieTemperatureInfo(device_id, die_id, MXSML_TEMPERATURE_CORE))
    except MXSMLError as e:
        print(e)

    print("Pmbus info(core):")
    try:
        # VF device does not contain pmbus info
        pmbus_info = mxSmlGetDiePmbusInfo(device_id, die_id, MXSML_PMBUS_CORE)
        print("  voltage:", pmbus_info.voltage)
        print("  current:", pmbus_info.current)
        print("  power:  ", pmbus_info.power)
    except MXSMLError as e:
        print(e)

    print("Clock frequency(vpud):")
    try:
        # VF device does not contain clock frequency info
        clocks = mxSmlGetDieClocks(device_id, die_id, MXSML_CLOCK_VPUD)
        for i, clock in enumerate(clocks):
            print("  VPUD#" + str(i) + ": " + str(clock) + " MHz")
    except MXSMLError as e:
        print(e)

    print("Chip serial:")
    try:
        print("  chip serial: ", mxSmlGetDieChipSerial(device_id, die_id))
    except MXSMLError as e:
        print(e)

    print("Xcore Ap Usage Toggle")
    try:
        print("  Collecting xcore AP usage: ", mxSmlGetDieApUsageToggle(device_id, die_id))
    except MXSMLError as e:
        print(e)

    try:
        # VF device does not contain dpm level info
        print("Current dpm level(xcore):", mxSmlGetCurrentDieDpmIpPerfLevel(device_id, die_id, MXSML_DPM_XCORE))
    except MXSMLError as e:
        print("Get current dpm performance level failed:", e)

    try:
        # VF device does not contain dpm level
        print("Max dpm performance level(xcore):", mxSmlGetDieDpmIpMaxPerfLevel(device_id, die_id, MXSML_DPM_XCORE))
    except MXSMLError as e:
        print("Get max dpm performance level failed:", e)

    try:
        print("Usage(xcore):", mxSmlGetDieIpUsage(device_id, die_id, MXSML_DPM_XCORE))
    except MXSMLError as e:
        print("Get usage failed:", e)

    print("Codec status:")
    try:
        # PF device does not contain codec status info
        status = mxSmlGetDieCodecStatus(device_id, die_id)
        print("  encoder:", status.encoder)
        print("  decoder:", status.decoder)
    except MXSMLError as e:
        print(e)

    print("Xcore ap usage:")
    try:
        # only support C-class device
        usage = mxSmlGetDieXcoreApUsage(device_id, die_id)
        for i, dpc_usage_array in enumerate(usage):
            print("  dpc", i, ":", dpc_usage_array)
    except MXSMLError as e:
        print(e)

    print("Eeprom info:")
    try:
        # VF device does not contain eeprom info
        eeprom_info = mxSmlGetDieEepromInfo(device_id, die_id)
        for content in eeprom_info.content.split(";"):
            if content:
                print("  " + content)
    except MXSMLError as e:
        print(e)

    try:
        # VF device does not contain ecc state info
        print("Ecc state:", mxSmlGetDieEccState(device_id, die_id))
    except MXSMLError as e:
        print(e)

    print("Power state(vpud):")
    try:
        # VF device does not contain power state info
        states = mxSmlGetDiePowerStateInfo(device_id, die_id, MXSML_DPM_VPUD)
        for i, state in enumerate(states):
            print("  VPUD#" + str(i) + ": " + str(state))
    except MXSMLError as e:
        print(e)

    print("Hbm bandwidth:")
    try:
        # VF device does not contain hbm bandwidth info
        bw = mxSmlGetDieHbmBandWidth(device_id, die_id)
        print("  req: ", bw.hbmBandwidthReqTotal)
        print("  resp:", bw.hbmBandwidthRespTotal)
    except MXSMLError as e:
        print(e)

    try:
        print("Pptable version:", mxSmlGetDiePptableVersion(device_id, die_id))
    except MXSMLError as e:
        print(e)

    try:
        reason = mxSmlGetDieUnavailableReason(device_id, die_id)
        print("Get die unavailable reason:", reason.unavailableCode)
        if reason.unavailableCode != 0:
            print(reason.unavailableReason)
    except MXSMLError as e:
        print("Get die unavailable reason failed:", e)

    try:
        eccCounts = mxSmlGetDieTotalEccErrors(device_id, die_id)
        print("Get die ecc sram CE count:", eccCounts)
    except MXSMLError as e:
        print("Get die ecc sram CE failed:", e)

    print()

print("============ end ============")
