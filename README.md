
# GPU Monitor

Metax mxsml API 

## Structure

```
gpu_monitor_nvidia.py   # 数据协议定义 (参考实现, NVIDIA/NVML)
gpu_monitor.py          # 基于 MXSML 的 MetaX 多卡 GPU 监控实现
mocks/mxsml_mock.py     # MXSML mock 后端 (8x MXC500 仿真, 无硬件可测)
tests/test_gpu_monitor_mxsml.py  # mock 测试
```

## Data protocol

`gpu_monitor.py` 的 `MXSMLMonitor.get_stats()` 保持 `gpu_monitor_nvidia.py` 的
**单卡扁平字段**，但字段值语义升级为 **多卡聚合**，并新增 `gpus` 明细：

```python
{
    # ---- 聚合字段（所有 GPU 汇总）----
    "platform": str,           # "MetaX (MXSML)"
    "gpu_name": str,           # 首卡显示名
    "gpu_model": str,          # "8x MXC500"
    "product_name": str,
    "uuid": str,               # 首卡
    "bdf_id": str,             # 首卡
    "device_count": int,       # 已监控 GPU 数（上限 8）
    "gpu_percent": float,      # ★ 所有 GPU 的平均利用率
    "vram_used_gb": float,     # ★ 所有 GPU 显存用量之和
    "vram_total_gb": float,    # ★ 所有 GPU 显存总量之和
    "vram_percent": float,     # used / total * 100
    "temp_c": float | None,    # 各卡最高温
    "power_w": float | None,   # 各卡功耗之和
    # ---- 每卡明细（GPU01..GPU08）----
    "gpus": [
        {"index": 0, "name": "MetaX MXC500 GPU01",
         "gpu_percent": 42.0, "vram_used_gb": 24.0, "vram_total_gb": 64.0,
         "vram_percent": 37.5, "temp_c": 56.0, "power_w": 165.0},
        # ...
    ],
    # ---- CPU/RAM（与单卡版一致）----
    "cpu_percent": float, "cpu_model": str,
    "ram_used_gb": float, "ram_total_gb": float, "ram_percent": float,
    "hostname": str,
}
```

### 聚合规则

| 字段 | 规则 | 说明 |
|------|------|------|
| `gpu_percent` | **平均** | 只对成功上报的卡求平均；不支持的卡不会把均值拉低 |
| `vram_used_gb` / `vram_total_gb` | **求和** | 不可用（如 PF）按 0 计入，不污染整机总量 |
| `temp_c` | **取最大** | 显示最热的一张卡 |
| `power_w` | **求和** | 整机 GPU 总功耗 |

> 使用 `get_gpu_stats()` 可只取 `gpus` 明细列表；`aggregate_stats()` 是可独立复用的聚合函数。

## MXSML 单位换算

| 指标 | MXSML 原始单位 | 协议单位 | 换算 |
|------|----------------|----------|------|
| 显存 | KB | GB | `/ 1024**2` |
| 温度 | 0.01 °C | °C | `/ 100` |
| 板卡功率 | mW | W | `/ 1000` |
| 利用率 | % | % | 直接使用 |

## 与 WebUI Server 的集成契约

服务端（`server.py`）通过以下 API 调用 `gpu_monitor`，本模块全部予以支持：

| 调用点 | 代码 | 说明 |
|---|---|---|
| `on_startup` | `gpu_monitor = create_monitor()` | 工厂函数，自动探测 MetaX（`detect_metax()`），失败时返回不可用实例而非抛异常 |
| `on_startup` | `monitor.init()` | 幂等启动钩子；驱动后起可用它恢复监控 |
| `gpu_monitor_loop` | `stats = monitor.get_stats()` | 内部已调用一次 `update_history` |
| `gpu_monitor_loop` | `monitor.update_history(stats)` | 循环再显式调用一次（历史长度按 2× 速率增长，受 `history_size` 上限约束） |
| `gpu_monitor_loop` | `stats["history"] = monitor.get_history()` | 返回 dict of list，可直接 `json.dumps` 广播 |
| `on_shutdown` | `monitor.cleanup()` | 关闭 MXSML |

> 注意：`get_stats()` 内部已调用 `update_history()`，服务端循环再调用一次属于既有行为。
> 两者叠加使 1Hz 采样对应 2Hz 历史记录，`deque(maxlen=history_size)` 保证不会无限增长。

## Usage

生产环境（有 MetaX 硬件与驱动）：

```python
from gpu_monitor import create_monitor

monitor = create_monitor()
monitor.init()               # on_startup
stats = monitor.get_stats()  # gpu_monitor_loop
stats["history"] = monitor.get_history()
monitor.cleanup()            # on_shutdown
```

无硬件环境（mock 测试）：

```python
import gpu_monitor
from mocks import mxsml_mock

gpu_monitor.set_mxsml_backend(mxsml_mock)   # 注入 mock
monitor = gpu_monitor.create_monitor()
print(monitor.get_stats())
```

### 可用的公开 API

| 名称 | 说明 |
|---|---|
| `create_monitor(platform=None)` | 工厂；`platform` 可为 `"metax"`/`"mxsml"` 强制指定，`None` 为自动探测 |
| `detect_metax()` | 探测是否有 MetaX 设备（等价于 NVIDIA 版的 `import pynvml` + `nvmlInit`） |
| `is_mxsml_available()` | 仅检查 Python 绑定是否可导入（不触发设备探测） |
| `set_mxsml_backend(lib)` | 依赖注入，用于 mock / 替换后端 |
| `GPUMonitor.aggregate_stats(devices)` | 静态聚合：平均利用率 + 显存求和 |
| `MXSMLMonitor.init()` | 幂等初始化，可在驱动后起时恢复监控 |
| `MXSMLMonitor.get_stats()` | 多卡聚合统计（含 `gpus` 明细 + CPU/RAM），失败自动降级 |
| `MXSMLMonitor.get_gpu_stats()` | 仅返回每卡明细列表 |
| `MXSMLMonitor.set_dpm_max_perf_level()` | 手动锁最大 DPM 频率（部分 MetaX 卡不锁会读到 0 MHz / NaN） |

### 构造参数

```python
MXSMLMonitor(
    device_index=None,   # 指定单卡索引；None（默认）= 监控全部 GPU
    history_size=60,
    device_ids=None,     # 显式指定 MXSML device id 列表（优先于 device_index）
)
```

GPU 槽位命名规则（与 UI 显示约定一致）：

- 单卡：`MetaX MXC500`
- 多卡：`MetaX MXC500 GPU01` … `MetaX MXC500 GPU08`（数量上限 8，超出时只监控前 8 张并告警）

### 时钟 / 功耗已知限制

部分 MetaX 板卡在未设置 DPM 最大性能档时会返回 `0 MHz` 或 `NaN`（内核驱动行为，
libmxsml 不会自动改频）。需要应用侧显式调用：

```python
monitor.set_dpm_max_perf_level()   # 等价于 C++ demo 的 mxSmlSetDpmIpMaxPerfLevel(dev, MXSML_Dpm_Xcore, 7)
```

## Tests

```bash
python3 tests/test_gpu_monitor_mxsml.py
# 或
python3 -m pytest tests/test_gpu_monitor_mxsml.py -v
```

依赖：`psutil`（CPU/RAM 统计）。

## Prompt

```
根据 gpu_monitor_nvidia.py 数据协议定义，根据 mxsml 内容 

实现基于 mxsml 的 gpu_monitor.py 功能 

环境无法测试，可进行mock测试
```
