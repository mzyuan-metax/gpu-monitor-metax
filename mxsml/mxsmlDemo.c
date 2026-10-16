#include <stdio.h>
#include "MxSml.h"

// link libmxsml.so
// MXN device: gcc mxsmlDemo.c -I/opt/mxn100/include/mxsml -L/opt/mxn100/lib -lmxsml -o mxsmlDemo
// MXC device: gcc mxsmlDemo.c -I/opt/maca/include/mxsml -L/opt/maca/lib/stub -lmxsml -o mxsmlDemo

// link libmxsml.a
// MXN device: gcc mxsmlDemo.c -I/opt/mxn100/include/mxsml -L/opt/mxn100/lib -lmxsml -lstdc++ -lm -lpthread -o mxsmlDemo
// MXC device: gcc mxsmlDemo.c -I/opt/maca/include/mxsml -L/opt/maca/lib/stub -lmxsml -lstdc++ -lm -lpthread -o mxsmlDemo

int GetNativeAndPfCommonStats(unsigned int deviceId);

int GetStatsForVf(unsigned int deviceId);

int GetStatsForPf(unsigned int deviceId);

int GetStatsForNative(unsigned int deviceId);

int main()
{
    mxSmlReturn_t ret = mxSmlInit();
    if(ret != MXSML_Success)
    {
        printf("mxSmlInit failed: %u, %s\n", ret, mxSmlGetErrorString(ret));
        return 1;
    }

    char l_macaVersion[20];
    unsigned int l_len = 20;
    if(mxSmlGetMacaVersion(l_macaVersion, &l_len) == MXSML_Success)
    {
        printf("maca version: %s\n", l_macaVersion);
    }

    int deviceNum = mxSmlGetDeviceCount();
    for(int i = 0; i < deviceNum; i++)
    {
        printf("\n\ndevice id: %d\n", i);

        mxSmlDeviceInfo_t deviceInfo;
        if(mxSmlGetDeviceInfo(i, &deviceInfo) == MXSML_Success)
        {
            printf("device pci bdf id: %s, name: %s\n", deviceInfo.bdfId, deviceInfo.deviceName);
        }

        int deviceState;
        if(mxSmlGetDeviceState(i, &deviceState) == MXSML_Success)
        {
            printf("device state: %d\n", deviceState);
        }

        if(MXSML_Virtualization_Mode_Vf == deviceInfo.mode)
        {
            GetStatsForVf(i);
        }
        else
        {
            GetStatsForNative(i);
        }
    }

    int pfNum = mxSmlGetPfDeviceCount();
    for(int i = 100; i < 100+pfNum; i++)
    {
        printf("\n\npf device id: %d\n", i);

        mxSmlDeviceInfo_t deviceInfo;
        if(mxSmlGetDeviceInfo(i, &deviceInfo) == MXSML_Success)
        {
            printf("device pci bdf id: %s, name: %s\n", deviceInfo.bdfId, deviceInfo.deviceName);
        }

        GetStatsForPf(i);
    }

    return 0;
}

int GetStatsForPf(unsigned int deviceId)
{
    return GetNativeAndPfCommonStats(deviceId);
}

int GetStatsForNative(unsigned int deviceId)
{
    mxSmlMemoryInfo_t memoryInfo;
    if(mxSmlGetMemoryInfo(deviceId, &memoryInfo) == MXSML_Success)
    {
        printf("Device Memory Total(KB): %ld, Used(KB): %ld\n", memoryInfo.visVramTotal, memoryInfo.visVramUse);
    }

    return GetNativeAndPfCommonStats(deviceId);
}

int GetStatsForVf(unsigned int deviceId)
{
    // VF only support these stats
    mxSmlMemoryInfo_t memoryInfo;
    if(mxSmlGetMemoryInfo(deviceId, &memoryInfo) == MXSML_Success)
    {
        printf("Device Memory Total(KB): %ld, Used(KB): %ld\n", memoryInfo.visVramTotal, memoryInfo.visVramUse);
    }

    int dlaUsage;
    if(mxSmlGetDeviceIpUsage(deviceId, MXSML_Usage_Dla, &dlaUsage) == MXSML_Success)
    {
        printf("Dla Usage: %d\n", dlaUsage);
    }

    mxSmlCodecStatus_t codecStatus;
    if(mxSmlGetCodecStatus(deviceId, &codecStatus) == MXSML_Success)
    {
        printf("Encoder Working Codec Num: %d\n", codecStatus.encoder);
        printf("Decoder Working Codec Num: %d\n", codecStatus.decoder);
    }

    unsigned int versionSize = VERSION_INFO_SIZE;
    char version[VERSION_INFO_SIZE];
    if(mxSmlGetDeviceVersion(deviceId, MXSML_Version_Driver, version, &versionSize) == MXSML_Success)
    {
        printf("KMD Version: %s\n", version);
    }

    return 0;
}

int GetNativeAndPfCommonStats(unsigned int deviceId)
{
    int temp;
    if(mxSmlGetTemperatureInfo(deviceId, MXSML_Temperature_Core, &temp) == MXSML_Success)
    {
        printf("Core temperature(C): %.2f\n", (float)temp/100);
    }

    mxSmlBoardWayElectricInfo_t boardPower[3];
    unsigned int l_size = 3;
    if(mxSmlGetBoardPowerInfo(deviceId, &l_size, boardPower) == MXSML_Success)
    {
        if(l_size == 2)
            printf("Board power(W): %.3f\n", (float)(boardPower[0].power + boardPower[1].power)/1000);
        else
            printf("Board power(W): %.3f\n", (float)(boardPower[0].power + boardPower[1].power + boardPower[2].power)/1000);
    }

    mxSmlPmbusInfo_t pmbusInfo;
    if(mxSmlGetPmbusInfo(deviceId, MXSML_Pmbus_Core, &pmbusInfo) == MXSML_Success)
    {
        printf("Core Voltage(V): %.3f\nCore Current(V): %.3f\nCore Power(V): %.3f\n",
                (float)pmbusInfo.voltage/1000, (float)pmbusInfo.current/1000, (float)pmbusInfo.power/1000);
    }

    unsigned int l_clocks[2];
    l_size = 2;
    if(mxSmlGetClocks(deviceId, MXSML_Clock_Dla, &l_size, l_clocks) == MXSML_Success)
    {
        printf("Dla0 Clock(Mhz): %u\n", l_clocks[0]);
    }

    unsigned int clockInfoSize = 8;
    unsigned int clockInfo[clockInfoSize];
    if(mxSmlGetDpmIpClockInfo(deviceId, MXSML_Dpm_Dla, clockInfo, &clockInfoSize) == MXSML_Success)
    {
        printf("Dpm Dla0 Clock(Mhz): %u\n", clockInfo[0]);
    }

    unsigned int voltageInfoSize = 8;
    unsigned int voltageInfo[voltageInfoSize];
    if(mxSmlGetDpmIpVddInfo(deviceId, MXSML_Dpm_Dla, voltageInfo, &voltageInfoSize) == MXSML_Success)
    {
        printf("Dpm Dla0 Voltage(V): %.3f\n", (float)voltageInfo[0]/1000);
    }

    unsigned int dpmIpPerfLevel;
    if(mxSmlGetCurrentDpmIpPerfLevel(deviceId, MXSML_Dpm_Dla, &dpmIpPerfLevel) == MXSML_Success)
    {
        printf("DPM Dla Performance Level: %u\n", dpmIpPerfLevel);
    }

    if(mxSmlSetDpmIpMaxPerfLevel(deviceId, MXSML_Dpm_Xcore, 7) == MXSML_Success)
    {
        printf("Set DPM Xcore performance max level Success\n");
        unsigned int perfLevel;
        if(mxSmlGetCurrentDpmIpPerfLevel(deviceId, MXSML_Dpm_Xcore, &perfLevel) == MXSML_Success)
        {
            printf("Now, DPM Xcore performance level: %u\n", perfLevel);
        }
    }

    char chipSerial[CHIP_SERIAL_SIZE];
    unsigned int chipSerialSize = CHIP_SERIAL_SIZE;
    if(mxSmlGetChipSerial(deviceId, chipSerial, &chipSerialSize) == MXSML_Success)
    {
        printf("Chip Serial: %s\n", chipSerial);
    }

    int dlaUsage;
    if(mxSmlGetDeviceIpUsage(deviceId, MXSML_Usage_Dla, &dlaUsage) == MXSML_Success)
    {
        printf("Dla Usage: %d\n", dlaUsage);
    }

    mxSmlEepromInfo_t eepromInfo;
    if(mxSmlGetEepromInfo(deviceId, &eepromInfo) == MXSML_Success)
    {
        printf("Eeprom Information: %s\n", eepromInfo.content);
    }

    unsigned int versionSize = VERSION_INFO_SIZE;
    char version[VERSION_INFO_SIZE];
    if(mxSmlGetDeviceVersion(deviceId, MXSML_Version_Driver, version, &versionSize) == MXSML_Success)
    {
        printf("KMD Version: %s\n", version);
    }

    mxSmlRasErrorData_t rasErrorData;
    if(mxSmlGetRasErrorData(deviceId, &rasErrorData) == MXSML_Success)
    {
        printf("RAS Error Counter Size: %d, Register0 Ue: %d\n",\
                rasErrorData.showRasErrorSize, rasErrorData.rasErrorRegister[0].rasErrorUe);
    }

    mxSmlRasStatusData_t rasStatusData;
    if(mxSmlGetRasStatusData(deviceId, &rasStatusData) == MXSML_Success)
    {
        printf("RAS Status Counter Size: %d, Register0 Data: %d\n",\
                rasStatusData.showRasStatusSize, rasStatusData.rasStatusRegister[0].registerData);
    }

    mxSmlPcieInfo_t pcieInfo;
    if(mxSmlGetPcieInfo(deviceId, &pcieInfo) == MXSML_Success)
    {
        printf("Pcie Speed: %.1f\n", pcieInfo.speed);
    }

    mxSmlPcieInfo_t pcieMaxLinkInfo;
    if(mxSmlGetPcieMaxLinkInfo(deviceId, &pcieMaxLinkInfo) == MXSML_Success)
    {
        printf("Pcie Max Speed: %.1f\n", pcieMaxLinkInfo.speed);
    }

    int powerState[8];
    unsigned int stateSize = 8;
    if(mxSmlGetPowerStateInfo(deviceId, MXSML_Dpm_Dla, powerState, &stateSize) == MXSML_Success)
    {
        printf("Dla0 Power State: %d\n", powerState[0]);
    }

    mxSmlPciPowerState_t pciPowerState;
    if(mxSmlGetPciPowerState(deviceId, &pciPowerState) == MXSML_Success)
    {
        printf("Pci Power State: %u\n", pciPowerState);
    }

    mxSmlCodecStatus_t codecStatus;
    if(mxSmlGetCodecStatus(deviceId, &codecStatus) == MXSML_Success)
    {
        printf("Encoder Working Codec Num: %d\n", codecStatus.encoder);
        printf("Decoder Working Codec Num: %d\n", codecStatus.decoder);
    }

    mxSmlHbmBandWidth_t hbmBandWidth;
    if(mxSmlGetHbmBandWidth(deviceId, &hbmBandWidth) == MXSML_Success)
    {
        printf("Hbm ReqTotal Bandwidth(MBytes/s): %d\n", hbmBandWidth.hbmBandwidthReqTotal);
    }

    mxSmlPcieThroughput_t pcieThroughput;
    if(mxSmlGetPcieThroughput(deviceId, &pcieThroughput) == MXSML_Success)
    {
        printf("Pcie Rx Throughput(MBytes/s): %d\n", pcieThroughput.rx);
        printf("Pcie Tx Throughput(MBytes/s): %d\n", pcieThroughput.tx);
    }

    unsigned int size = 5;
    mxSmlDmaEngineBandwidth_t dmaBandwidth[size];
    if(mxSmlGetDmaBandwidth(deviceId, dmaBandwidth, &size) == MXSML_Success)
    {
        printf("Dma ReadReqBandwidth0 Bandwidth(MBytes/s): %d\n", dmaBandwidth[0].readReqBandwidth);
    }

    unsigned int processNumber = 0;
    if(mxSmlGetNumberOfProcess(&processNumber) == MXSML_Success)
    {
        printf("Process Number: %u\n", processNumber);
    }

    mxSmlProcessInfo_t processInfo[processNumber];
    if(mxSmlGetProcessInfo(processNumber, processInfo) == MXSML_Success)
    {
        printf("Process Id: %d, Process Name: %s\n", processInfo[0].processId, processInfo[0].processName);
    }

    mxSmlProcessInfo_v3_t processInfo_v3[processNumber];
    if(mxSmlGetProcessInfo_v3(processNumber, processInfo_v3) == MXSML_Success)
    {
        printf("Process Id: %d, Process Name: %s, Gpu Id: %d, Sgpu Id: %d\n", processInfo_v3[0].processId,
            processInfo_v3[0].processName, processInfo_v3[0].processGpuInfo->gpuId, processInfo_v3[0].processGpuInfo->sgpuId);
    }

    mxSmlLoglevel_t fwLoglevel;
    if(mxSmlGetFwIpLoglevel(deviceId, MXSML_Fw_IpName_SMP0, &fwLoglevel) == MXSML_Success)
    {
        printf("Smp0 Log level: %u\n", fwLoglevel);
    }

    if(mxSmlSetFwLoglevel(deviceId, MXSML_Fw_IpName_SMP0, MXSML_Loglevel_WARN) == MXSML_Success)
    {
        printf("Set Smp0 Log level Success\n");
        if(mxSmlGetFwIpLoglevel(deviceId, MXSML_Fw_IpName_SMP0, &fwLoglevel) == MXSML_Success)
        {
            printf("Now, Smp0 Log level: %u\n", fwLoglevel);
        }
    }

    unsigned int pciDelay = 0;
    if(mxSmlGetPciDelay(deviceId, &pciDelay) == MXSML_Success)
    {
        printf("Pci Delay: %u\n", pciDelay);
    }

    if(mxSmlSetPciDelay(deviceId, (unsigned int)200) == MXSML_Success)
    {
        printf("Set Pci Delay Success\n");
        if(mxSmlGetPciDelay(deviceId, &pciDelay) == MXSML_Success)
        {
            printf("Now, Pci Delay: %u\n", pciDelay);
        }
    }

    mxSmlMetaXLinkBandwidth_t metaxLinkBandwidth[7];
    unsigned int arraySize = 7;
    if(mxSmlGetMetaXLinkBandwidth(deviceId, MXSML_MetaXLink_Input, &arraySize, metaxLinkBandwidth) == MXSML_Success)
    {
        printf("MetaXLink Input RequestBandwidth(MBytes/s): %d\n", metaxLinkBandwidth[0].requestBandwidth);
    }

    if(mxSmlFunctionLevelReset(deviceId) == MXSML_Success)
    {
        printf("Function Level Reset Success\n");
    }

    return 0;
}

