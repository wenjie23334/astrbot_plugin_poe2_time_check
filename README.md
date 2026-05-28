# poe2_time_check - 流放之路2时间查询插件

AstrBot 插件，用于查询流放之路2 (Path of Exile 2) 国际服和腾讯国服的开服时间、服务器状态、赛季倒计时信息。

## 功能特性

- 多指令触发：`/poe2`、`/流放之路2`、`/poe2时间`
- 同时查询国际服和腾讯国服数据
- 10分钟本地缓存，避免频繁请求
- 完善的错误处理和容错机制
- 兼容私聊和群聊场景

## 数据源

- 国际服：https://poe2db.tw/us/
- 腾讯国服：https://poe2db.tw/cn/

## 安装步骤

### 1. 安装依赖

```bash
pip install httpx beautifulsoup4
```

### 2. 部署插件

将 `poe2_time_check` 文件夹放入 AstrBot 的插件目录：

```
AstrBot/data/plugins/astrbot_plugin_poe2_time_check/
├── main.py
├── metadata.yaml
├── requirements.txt
└── _conf_schema.json
```

### 3. 重载插件

在 AstrBot WebUI 的插件管理页面找到 `poe2_time_check`，点击"重载插件"。

## 指令用法

| 指令 | 说明 |
|------|------|
| `/poe2` | 查询国际服和国服服务器状态 |
| `/流放之路2` | 同上，中文指令 |
| `/poe2时间` | 同上，时间相关指令 |
| `/poe2help` | 显示帮助信息 |

## 配置说明

在 AstrBot 配置文件中添加以下配置项：

```yaml
poe2_time_check:
  cache_duration: 600        # 缓存时长（秒），默认600秒
  request_timeout: 15        # 请求超时时间（秒），默认15秒
  enable_schedule: false     # 是否启用定时推送
  schedule_group_id: ""      # 定时推送的目标群ID
  schedule_interval: 3600    # 定时间隔（秒），默认3600秒
```

### 配置项详解

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `cache_duration` | int | 600 | 数据缓存时长，避免频繁请求数据源 |
| `request_timeout` | int | 15 | 网络请求超时时间 |
| `enable_schedule` | bool | false | 是否启用定时推送功能 |
| `schedule_group_id` | string | "" | 定时推送的目标群聊ID |
| `schedule_interval` | int | 3600 | 定时推送间隔（秒） |

## 页面解析逻辑

### 国际服页面解析

从 `https://poe2db.tw/us/` 页面提取：
- 查找 `<h5>` 标签中的赛季名称（如 "Return of the Ancients 0.5"）
- 提取日期信息（格式：YYYY-MM-DD HH:MM）
- 解析倒计时状态（Starts in / 已运行）

### 腾讯国服页面解析

从 `https://poe2db.tw/cn/` 页面提取：
- 查找 `<h5>` 标签中的赛季名称（如 "远古回响 (腾讯服) 0.5"）
- 提取日期信息和倒计时状态

## 错误处理

插件包含以下错误处理机制：
- 网络请求超时捕获
- 网络连接错误处理
- 页面解析失败处理
- 页面结构变动容错

## 依赖说明

- Python >= 3.8
- httpx >= 0.27.0
- beautifulsoup4 >= 4.12.0

## 许可证

MIT License
