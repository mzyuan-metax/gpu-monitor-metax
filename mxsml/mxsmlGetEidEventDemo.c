#include "MxSml.h"
#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <stdarg.h>

// link libmxsml.so
// gcc mxsmlGetEidEventDemo.c -I/opt/maca/include/mxsml -L/opt/maca/lib/stub -lmxsml -o mxsmlDemo

// link libmxsml.a
// gcc mxsmlGetEidEventDemo.c -I/opt/maca/include/mxsml -L/opt/maca/lib/stub -lmxsml -lstdc++ -lm -lpthread -o mxsmlDemo

pthread_mutex_t cout_mtx = PTHREAD_MUTEX_INITIALIZER;

void safe_print(const char* fmt, ...)
{
    pthread_mutex_lock(&cout_mtx);
    va_list ap;
    va_start(ap, fmt);
    vprintf(fmt, ap);
    va_end(ap);
    pthread_mutex_unlock(&cout_mtx);
}

void* monitor(void* arg_device_id)
{
    unsigned int device_id = *(int*)arg_device_id;
    free(arg_device_id);

    mxSmlEventSet_t event_set;
    mxSmlReturn_t ret = mxSmlEventSetCreate(&event_set);
    safe_print("device id: %u, create eventset: %d\n", device_id, (int)ret);

    ret = mxSmlDeviceRegisterEvents(device_id, mxSmlEventTypeEid, event_set);
    safe_print("device id: %u, register: %d\n", device_id, (int)ret);

    mxSmlEvent_t data;
    ret = mxSmlEventSetWait(event_set, &data);
    safe_print("device id: %u, wait: %d\n", device_id, (int)ret);
    safe_print("deviceId: %d\neid: 0x%x\nevent data: %s\n", data.deviceId, data.type,data.eventData);

    ret = mxSmlEventSetFree(event_set);
    safe_print("device id: %u, free: %d\n", device_id, (int)ret);
    return NULL;
}

int main()
{
    if(mxSmlInit())
    {
        printf("mxSmlInit failed.");
        return 1;
    }

    unsigned int gpu_count = mxSmlGetDeviceCount();
    pthread_t threads[32];
    for(int i = 0; i < gpu_count; i++)
    {
        int *device_id = malloc(sizeof(int));
        *device_id = i;
        pthread_create(&threads[i], NULL, monitor, device_id);
    }

    for (unsigned int i = 0; i < gpu_count; ++i)
    {
        pthread_join(threads[i], NULL);
    }

    return 0;
}