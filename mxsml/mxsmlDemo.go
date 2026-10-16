package main

// compile
// CGO_CFLAGS="-I /opt/maca/include/mxsml" CGO_LDFLAGS="-L /opt/maca/lib/stub -lmxsml" go build -o mxsmlDemo mxsmlDemo.go

/*
#include "stdio.h"
#include "stdlib.h"
#include "memory.h"
#include "MxSml.h"

*/
import "C"
import "fmt"
import "os"
import "unsafe"

const MX_SML_SUCCESS = C.MXSML_Success
const DEVICE_BDF_ID_SIZE = C.DEVICE_BDF_ID_SIZE
const PROCESS_NAME_SIZE = C.PROCESS_NAME_SIZE
const MAX_GPU_NUM_USED_BY_PROCESS = C.MAX_GPU_NUM_USED_BY_PROCESS

func main() {
    ret := C.mxSmlInit()
    if ret != MX_SML_SUCCESS {
        fmt.Printf("mxSmlInit failed: %u, %s\n", int(ret), C.GoString(C.mxSmlGetErrorString(ret)));
        os.Exit(1)
    }


    var verLen uint32 = 20
    macaVersion := make([]byte, verLen)
    cVersion := C.CString(string(macaVersion))
    if C.mxSmlGetMacaVersion((*C.char)(cVersion), (*C.uint)(unsafe.Pointer(&verLen))) == MX_SML_SUCCESS {
        fmt.Printf("maca version: %s\n", C.GoString(cVersion))
    }

    devNum := C.mxSmlGetDeviceCount()
    for i := 0; i < int(devNum); i++ {
        fmt.Printf("\n\ndevice id: %d\n", i);

        var deviceInfo C.mxSmlDeviceInfo_t
        ret := C.mxSmlGetDeviceInfo(C.uint(i), &deviceInfo)
        if ret != C.MXSML_Success {
            fmt.Printf("get device Info for device %d failed, ret: %d\n", i, int(ret))
            continue
        }
        fmt.Printf("device pci bdf id: %s, name: %s\n", C.GoString(&(deviceInfo.bdfId[0])), C.GoString(&(deviceInfo.deviceName[0])))

        if deviceInfo.mode == C.MXSML_Virtualization_Mode_Vf {
            getStatsForVf(C.uint(i))
        } else {
            getStatsForNative(C.uint(i))
        }
    }
}

func getStatsForVf(deviceId C.uint) {
    // VF only support these stats
    showMemoryInfo(deviceId)
    showDlaUsage(deviceId)
    showVpuStatus(deviceId)
    showDeviceVersion(deviceId)
}

func getStatsForNative(deviceId C.uint) {
    showMemoryInfo(deviceId)
    showTemperatureInfo(deviceId)
    showBoardPowerInfo(deviceId)
    showPmBusInfo(deviceId)
    showClockInfo(deviceId)
    showDPMInfo(deviceId)
    showChipSerial(deviceId)
    showDlaUsage(deviceId)
    showEepromInfo(deviceId)
    showDeviceVersion(deviceId)
    showRasInfo(deviceId)
    showPcieSpeed(deviceId)
    showPowerState(deviceId)
    showVpuStatus(deviceId)
    showHbmBandWidth(deviceId)
    showPcieThroughput(deviceId)
    showDmaBandwidth(deviceId)
    showProcessInfo(deviceId)
    setSmp0FwLogLevel(deviceId)
    setPciDelay(deviceId)
    showMetaxLinkBandwidth(deviceId)
    resetFunctionLevel(deviceId)
}

func showMemoryInfo(deviceId C.uint) {
    var memoryInfo C.mxSmlMemoryInfo_t
    if C.mxSmlGetMemoryInfo(deviceId, &memoryInfo) == MX_SML_SUCCESS {
        fmt.Printf("Device Memory Total(KB): %d, Used(KB): %d\n", int64(memoryInfo.visVramTotal), int64(memoryInfo.visVramUse))
    }
}

func showDeviceVersion(deviceId C.uint) {
    versionSize := C.VERSION_INFO_SIZE
    verBytes := make([]byte, int(versionSize))
    cKmdVersion := C.CString(string(verBytes))
    if C.mxSmlGetDeviceVersion(deviceId, C.MXSML_Version_Driver, (*C.char)(cKmdVersion), (*C.uint)(unsafe.Pointer(&versionSize))) == MX_SML_SUCCESS {
        fmt.Printf("KMD Version: %s\n", C.GoString(cKmdVersion))
    }
}

func showTemperatureInfo(deviceId C.uint) {
    var temp int
    if C.mxSmlGetTemperatureInfo(deviceId, C.MXSML_Temperature_Core, (*C.int)(unsafe.Pointer(&temp))) == MX_SML_SUCCESS {
        fmt.Printf("Core temperature(C): %.2f\n", float64(temp)/100)
    }
}

func showBoardPowerInfo(deviceId C.uint) {
    type boradPowerInfo struct {
        voltage  uint32
        current  uint32
        power    uint32
    }

    var boardInfoSize uint32 = 3
    infoSize := unsafe.Sizeof(C.mxSmlBoardWayElectricInfo_t{})
    boardPower := C.malloc(C.size_t(infoSize) * C.size_t(boardInfoSize))
    defer C.free(boardPower)

    if C.mxSmlGetBoardPowerInfo(deviceId, (*C.uint)(unsafe.Pointer(&boardInfoSize)),
        (*C.mxSmlBoardWayElectricInfo_t)(boardPower)) == MX_SML_SUCCESS {
        // convert boradPowerInfo from c to go
        var totalPower uint32
        for i := 0; i < int(boardInfoSize); i++ {
            goStruct := (*boradPowerInfo)(unsafe.Pointer(uintptr(boardPower) + uintptr(infoSize) * uintptr(i)))
            totalPower += uint32((*goStruct).power)
        }
        fmt.Printf("Board power(W): %.3f\n", float64(totalPower)/1000.0)
    }
}

func showMetaxLinkBandwidth(deviceId C.uint) {
    type metaxLinkBandwidth struct {
        requestBandwidth int32
        responseBandwidth int32
    }

    var size uint32 = 7
    bandwidthStrucSize := unsafe.Sizeof(C.mxSmlMetaXLinkBandwidth_t{})
    bandwidth := C.malloc(C.size_t(bandwidthStrucSize) * C.size_t(size))
    defer C.free(bandwidth)

    if C.mxSmlGetMetaXLinkBandwidth(deviceId, C.MXSML_MetaXLink_Input, (*C.uint)(unsafe.Pointer(&size)),
        (*C.mxSmlMetaXLinkBandwidth_t)(bandwidth)) == MX_SML_SUCCESS {
        fmt.Printf("MetaXLink Input RequestBandwidth(MBytes/s): %d\n", ((*metaxLinkBandwidth)(bandwidth)).requestBandwidth)
    }
}

func showDmaBandwidth(deviceId C.uint) {
    type dmaEngineBandwidth struct {
        readReqBandwidth uint32
        readRespBandwidth uint32
        writeReqBandwidth uint32
        writeRespBandwidth uint32
    }

    var size uint32 = 5
    bandwidthStrucSize := unsafe.Sizeof(C.mxSmlDmaEngineBandwidth_t{})
    bandwidth := C.malloc(C.size_t(bandwidthStrucSize) * C.size_t(size))
    defer C.free(bandwidth)

    if C.mxSmlGetDmaBandwidth(deviceId, (*C.mxSmlDmaEngineBandwidth_t)(bandwidth),
        (*C.uint)(unsafe.Pointer(&size))) == MX_SML_SUCCESS {
        fmt.Printf("Dma ReadReqBandwidth0 Bandwidth(MBytes/s): %d\n", ((*dmaEngineBandwidth)(bandwidth)).readReqBandwidth)
    }
}

func showProcessInfo(deviceId C.uint) {
    var processNumber uint32
    if C.mxSmlGetNumberOfProcess((*C.uint)(unsafe.Pointer(&processNumber))) == MX_SML_SUCCESS {
        fmt.Printf("Process Number: %d\n", processNumber)
    }

    if processNumber <= 0 {
        return
    }

    type gProcessGpuInfo struct {
        bdfId [DEVICE_BDF_ID_SIZE]byte
        gpuId uint32
        gpuMemoryUsage uint
    }
    type gProcessInfo struct {
        processId uint32
        processName [PROCESS_NAME_SIZE]byte
        gpuNumber uint32
        processGpuInfo [MAX_GPU_NUM_USED_BY_PROCESS]gProcessGpuInfo
    }

    processInfoSize := unsafe.Sizeof(C.mxSmlProcessInfo_t{})
    processInfo := C.malloc(C.size_t(processInfoSize) * C.size_t(processNumber))
    C.memset(processInfo, 0, C.size_t(processInfoSize) * C.size_t(processNumber))
    defer C.free(processInfo)

    if C.mxSmlGetProcessInfo(C.uint(processNumber), (*C.mxSmlProcessInfo_t)(processInfo)) == MX_SML_SUCCESS {
        info0 := (*gProcessInfo)(processInfo)
        nameLen := 0
        for k := 0; k < len(info0.processName); k++ {
            if info0.processName[k] == 0 {
                break
            }
            nameLen++
        }
        fmt.Printf("Process0 Id: %d, Process0 Name: %s\n", info0.processId, string(info0.processName[:nameLen]))
    }

    type gProcessGpuInfo_v3 struct {
        bdfId [DEVICE_BDF_ID_SIZE]byte
        gpuId uint32
        gpuMemoryUsage uint
        dieId uint32
        sgpuId int32
    }
    type gProcessInfo_v3 struct {
        processId uint32
        processName [PROCESS_NAME_SIZE]byte
        gpuNumber uint32
        processGpuInfo [MAX_GPU_NUM_USED_BY_PROCESS]gProcessGpuInfo_v3
    }

    processInfoSize_v3 := unsafe.Sizeof(C.mxSmlProcessInfo_v3_t{})
    processInfo_v3 := C.malloc(C.size_t(processInfoSize_v3) * C.size_t(processNumber))
    C.memset(processInfo_v3, 0, C.size_t(processInfoSize_v3) * C.size_t(processNumber))
    defer C.free(processInfo_v3)

    if C.mxSmlGetProcessInfo_v3(C.uint(processNumber), (*C.mxSmlProcessInfo_v3_t)(processInfo_v3)) == MX_SML_SUCCESS {
        baseAddr := uintptr(unsafe.Pointer(processInfo_v3))
        for i := 0; i < int(processNumber); i++ {
            elemAddr := baseAddr + uintptr(i)*processInfoSize_v3
            elemPtr := (*gProcessInfo_v3)(unsafe.Pointer(elemAddr))
            nameLen := 0
            for k := 0; k < len(elemPtr.processName); k++ {
                if elemPtr.processName[k] == 0 {
                    break
                }
                nameLen++
            }
            fmt.Printf("Process %d: Id = %d, Name = %s, gpuId = %d, sgpuId = %d\n",
                i, elemPtr.processId, string(elemPtr.processName[:nameLen]),
                elemPtr.processGpuInfo[0].gpuId, elemPtr.processGpuInfo[0].sgpuId)
        }
    }
}

func showPmBusInfo(deviceId C.uint) {
    var pmbusInfo C.mxSmlPmbusInfo_t
    if C.mxSmlGetPmbusInfo(deviceId, C.MXSML_Pmbus_Core, &pmbusInfo) == MX_SML_SUCCESS {
        fmt.Printf("Core Voltage(V): %.3f\nCore Current(V): %.3f\nCore Power(V): %.3f\n",
            float64(pmbusInfo.voltage)/1000, float64(pmbusInfo.current)/1000, float64(pmbusInfo.power)/1000)
    }
}

func showClockInfo(deviceId C.uint) {
    var clockSize uint32 = 2
    uintSize := unsafe.Sizeof(clockSize)

    cClocks := C.malloc(C.size_t(uintSize) * C.size_t(clockSize))
    defer C.free(cClocks)
    if C.mxSmlGetClocks(deviceId, C.MXSML_Clock_Dla, (*C.uint)(unsafe.Pointer(&clockSize)), (*C.uint)(cClocks)) == MX_SML_SUCCESS {
        fmt.Printf("Dla0 Clock(Mhz): %d\n", *((*uint32)(cClocks)))
    }
}

func showDPMInfo(deviceId C.uint) {
    var clockInfoSize uint32 = 8
    uintSize := unsafe.Sizeof(clockInfoSize)

    cClockInfo := C.malloc(C.size_t(uintSize) * C.size_t(clockInfoSize))
    defer C.free(cClockInfo)
    if C.mxSmlGetDpmIpClockInfo(deviceId, C.MXSML_Dpm_Dla, (*C.uint)(cClockInfo), (*C.uint)(unsafe.Pointer(&clockInfoSize))) == MX_SML_SUCCESS {
        fmt.Printf("Dpm Dla0 Clock(Mhz): %d\n", *((*uint32)(cClockInfo)))
    }

    var voltageInfoSize uint32 = 8
    voltageInfo := C.malloc(C.size_t(uintSize) * C.size_t(voltageInfoSize))
    defer C.free(voltageInfo)
    if C.mxSmlGetDpmIpVddInfo(deviceId, C.MXSML_Dpm_Dla, (*C.uint)(voltageInfo), (*C.uint)(unsafe.Pointer(&voltageInfoSize))) == MX_SML_SUCCESS {
        fmt.Printf("Dpm Dla0 Voltage(V): %.3f\n", float64(*((*uint32)(voltageInfo)))/1000)
    }

    var dpmIpPerfLevel uint32
    if C.mxSmlGetCurrentDpmIpPerfLevel(deviceId, C.MXSML_Dpm_Dla, (*C.uint)(unsafe.Pointer(&dpmIpPerfLevel))) == MX_SML_SUCCESS {
        fmt.Printf("DPM Dla Performance Level: %d\n", dpmIpPerfLevel)
    }

    if C.mxSmlSetDpmIpMaxPerfLevel(deviceId, C.MXSML_Dpm_Xcore, 7) == MX_SML_SUCCESS {
        fmt.Println("Set DPM Xcore performance max level Success")
        var perfLevel uint32
        if C.mxSmlGetCurrentDpmIpPerfLevel(deviceId, C.MXSML_Dpm_Xcore, (*C.uint)(unsafe.Pointer(&perfLevel))) == MX_SML_SUCCESS {
            fmt.Printf("Now, DPM Xcore performance level: %d\n", perfLevel)
        }
    }
}

func showChipSerial(deviceId C.uint) {
    chipSerialSize := C.CHIP_SERIAL_SIZE
    chipSerialBytes := make([]byte, int(chipSerialSize))
    cchipSerialSizeStr := C.CString(string(chipSerialBytes))

    if C.mxSmlGetChipSerial(deviceId, (*C.char)(cchipSerialSizeStr), (*C.uint)(unsafe.Pointer(&chipSerialSize))) == MX_SML_SUCCESS {
        fmt.Printf("Chip Serial: %s\n", C.GoString(cchipSerialSizeStr))
    }
}

func showDlaUsage(deviceId C.uint) {
    var dlaUsage int32
    if C.mxSmlGetDeviceIpUsage(deviceId, C.MXSML_Usage_Dla, (*C.int)(unsafe.Pointer(&dlaUsage))) == MX_SML_SUCCESS {
        fmt.Printf("Dla Usage: %d\n", dlaUsage)
    }
}

func showEepromInfo(deviceId C.uint) {
    var eepromInfo C.mxSmlEepromInfo_t
    if C.mxSmlGetEepromInfo(deviceId, &eepromInfo) == MX_SML_SUCCESS {
        fmt.Printf("Eeprom Information: %s\n", C.GoString(&(eepromInfo.content[0])))
    }
}

func showRasInfo(deviceId C.uint) {
    type rasErrorRegister struct {
        rasIp uint32
        registerIndex uint32
        rasErrorUe uint32
        rasErrorCe uint32
    }

    var rasErrorData C.mxSmlRasErrorData_t
    if C.mxSmlGetRasErrorData(deviceId, &rasErrorData) == MX_SML_SUCCESS {
        register0 := (*rasErrorRegister)(unsafe.Pointer(&rasErrorData.rasErrorRegister[0]))
        fmt.Printf("RAS Error Counter Size: %d, Register0 Ue: %d\n", int(rasErrorData.showRasErrorSize), register0.rasErrorUe)
    }

    type rasStatusRegister struct {
        rasIp uint32
        registerIndex uint32
        registerData int32
    }

    var rasStatusData C.mxSmlRasStatusData_t
    if C.mxSmlGetRasStatusData(deviceId, &rasStatusData) == MX_SML_SUCCESS {
        register0 := (*rasStatusRegister)(unsafe.Pointer(&rasStatusData.rasStatusRegister[0]))
        fmt.Printf("RAS Status Counter Size: %d, Register0 Data: %d\n", int(rasStatusData.showRasStatusSize), register0.registerData)
    }
}

func showPcieSpeed(deviceId C.uint) {
    var pcieInfo C.mxSmlPcieInfo_t
    if C.mxSmlGetPcieInfo(deviceId, &pcieInfo) == MX_SML_SUCCESS {
        fmt.Printf("Pcie Speed: %.1f\n", float64(pcieInfo.speed))
    }

    var pcieMaxLinkInfo C.mxSmlPcieInfo_t
    if C.mxSmlGetPcieMaxLinkInfo(deviceId, &pcieMaxLinkInfo) == MX_SML_SUCCESS {
        fmt.Printf("Pcie Max Speed: %.1f\n", float64(pcieMaxLinkInfo.speed))
    }
}

func showPowerState(deviceId C.uint) {
    var stateSize int32 = 8
    var cint C.int
    powerState := C.malloc(C.size_t(unsafe.Sizeof(cint)) * C.size_t(stateSize))
    defer C.free(powerState)

    if C.mxSmlGetPowerStateInfo(deviceId, C.MXSML_Dpm_Dla, (*C.int)(unsafe.Pointer(powerState)),
        (*C.uint)(unsafe.Pointer(&stateSize))) == MX_SML_SUCCESS {
        fmt.Printf("Dla0 Power State: %d\n", *((*int)(powerState)))
    }

    var pciPowerState C.mxSmlPciPowerState_t
    if C.mxSmlGetPciPowerState(deviceId, &pciPowerState) == MX_SML_SUCCESS {
        fmt.Printf("Pci Power State: %d\n", uint32(pciPowerState))
    }
}

func showVpuStatus(deviceId C.uint) {
    var codecStatus C.mxSmlCodecStatus_t
    if C.mxSmlGetCodecStatus(deviceId, &codecStatus) == MX_SML_SUCCESS {
        fmt.Printf("Encoder Working Codec Num: %d\n", int32(codecStatus.encoder))
        fmt.Printf("Decoder Working Codec Num: %d\n", int32(codecStatus.decoder))
    }
}

func showHbmBandWidth(deviceId C.uint) {
    var hbmBandWidth C.mxSmlHbmBandWidth_t
    if C.mxSmlGetHbmBandWidth(deviceId, &hbmBandWidth) == MX_SML_SUCCESS {
        fmt.Printf("Hbm ReqTotal Bandwidth(MBytes/s): %d\n", int32(hbmBandWidth.hbmBandwidthReqTotal))
    }
}

func showPcieThroughput(deviceId C.uint) {
    var pcieThroughput C.mxSmlPcieThroughput_t
    if C.mxSmlGetPcieThroughput(deviceId, &pcieThroughput) == MX_SML_SUCCESS {
        fmt.Printf("Pcie Rx Throughput(MBytes/s): %d\n", int32(pcieThroughput.rx));
        fmt.Printf("Pcie Tx Throughput(MBytes/s): %d\n", int32(pcieThroughput.tx));
    }
}

func setSmp0FwLogLevel(deviceId C.uint) {
    var fwLoglevel C.mxSmlLoglevel_t
    if C.mxSmlGetFwIpLoglevel(deviceId, C.MXSML_Fw_IpName_SMP0, &fwLoglevel) == MX_SML_SUCCESS {
        fmt.Printf("Smp0 Log level: %d\n", uint32(fwLoglevel))
    }

    if C.mxSmlSetFwLoglevel(deviceId, C.MXSML_Fw_IpName_SMP0, C.MXSML_Loglevel_WARN) == MX_SML_SUCCESS {
        fmt.Println("Set Smp0 Log level Success")
        if C.mxSmlGetFwIpLoglevel(deviceId, C.MXSML_Fw_IpName_SMP0, &fwLoglevel) == MX_SML_SUCCESS {
            fmt.Printf("Now, Smp0 Log level: %d\n", uint32(fwLoglevel))
        }
    }
}

func setPciDelay(deviceId C.uint) {
    var pciDelay uint32
    if C.mxSmlGetPciDelay(deviceId, (*C.uint)(unsafe.Pointer(&pciDelay))) == MX_SML_SUCCESS {
        fmt.Printf("Pci Delay: %d\n", pciDelay)
    }

    if C.mxSmlSetPciDelay(deviceId, C.uint(200)) == MX_SML_SUCCESS {
        fmt.Println("Set Pci Delay Success")
        if C.mxSmlGetPciDelay(deviceId, (*C.uint)(unsafe.Pointer(&pciDelay))) == MX_SML_SUCCESS {
            fmt.Printf("Now, Pci Delay: %d\n", pciDelay)
        }
    }
}

func resetFunctionLevel(deviceId C.uint) {
    if C.mxSmlFunctionLevelReset(deviceId) == MX_SML_SUCCESS {
        fmt.Printf("Function Level Reset Succes\n")
    }
}
