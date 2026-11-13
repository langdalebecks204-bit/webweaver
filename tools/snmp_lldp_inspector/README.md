# SNMP & LLDP 设备探测诊断小工具 (WebWeaver Inspector)

本工具沉淀自 **织网 (WebWeaver)** 在交换机纳管、网络拓扑自动发现及边缘资产识别中的真实工程经验。作为一个**轻量、独立、纯绿色**的桌面 GUI 排障小工具，支持输入设备 IP 即可快速探测并展示设备的 SNMP 系统信息、接口状态、LLDP 邻居拓扑与 Bridge MAC 转发表。

---

## 🌟 核心特色与功能

1. **零第三方依赖（纯绿便携）**：
   - 基于 Python 3 原生标准库（`tkinter` + `socket`），**无需执行 `pip install` 安装任何依赖包**；
   - 内置纯 Python 实现的轻量 ASN.1 / SNMP v1/v2c 编解码引擎与单调性防死循环算法，跨平台支持 Windows、Linux 与 macOS。
2. **系统概览 (System Overview)**：
   - 提取 `sysDescr`（系统固件信息）、`sysName`（设备名）、`sysUpTime`（开机时长）、`sysObjectID`、`sysContact` 与 `sysLocation`；
   - 提取交换机 Bridge Base MAC，并自动匹配内置 OUI 数据库解析硬件厂商（华为、华三、思科、锐捷、TP-Link、海康、苹果等）；
   - 精确测算 SNMP 交互往返延时（ms）。
3. **端口列表 (IF-MIB)**：
   - 自动遍历全部物理及逻辑接口；
   - 展示端口名/描述、物理状态（UP/DOWN）、管理状态、协商速率（百兆/千兆/万兆）、收发流量字节计数器；
   - 支持实时关键词搜索与筛选。
4. **LLDP 物理链路拓扑 (LLDP-MIB)**：
   - 自动扫描物理邻居连接关系；
   - 提取对端机箱 ID（MAC）、对端厂商、对端系统名称、对端连接端口、对端管理 IP 与系统描述；
   - 双击行条目可弹出完整对端卡片。
5. **MAC 转发表 (Bridge FDB)**：
   - 提取交换机转发表中的终端 MAC 地址与对应 BasePort / IfIndex；
   - 自动匹配网卡厂商，便于快速识别端口下是否接有傻瓜分线器或 AP。
6. **诊断日志与一键导出**：
   - 实时显示各步骤探测日志与耗时；
   - 探测失败自动提供排障指引；
   - 支持将探测结果一键导出为标准的 `.json` 结构化数据或 `.txt` 诊断文本报告。

---

## 🚀 快速启动

### 方式 1：免安装单文件绿色版（最推荐，零环境要求）
直接双击运行目录下的 **`SnmpLldpInspector.exe`** 即可！
- 内置独立完整的运行环境；
- 无黑窗口控制台，点开即用，随拷随走（可直接放到 U 盘或随身运维电脑中）。

### 方式 2：Python 脚本启动（源码运行）
- **Windows**：双击运行 `run.bat`，或在命令行执行：
  ```cmd
  python main.py
  ```
- **Linux / macOS**：
  ```bash
  python3 main.py
  ```
  *(注：Linux 系统若提示缺少 tkinter，可通过 `sudo apt install python3-tk` 安装。)*

---

## 📋 常见交换机 SNMP & LLDP 配置速查

如果探测时提示超时或未收到响应，请确认交换机已开启 SNMP 和 LLDP 服务：

### 1. 华为 / 华三 (Huawei / H3C)
```text
system-view
# 开启 SNMP 并配置团体名
snmp-agent
snmp-agent sys-info version v2c
snmp-agent community read public

# 全局使能 LLDP
lldp enable
```

### 2. 思科 (Cisco)
```text
configure terminal
# 开启 SNMP 读团体名
snmp-server community public RO

# 全局使能 LLDP
lldp run
```

### 3. 锐捷 (Ruijie)
```text
configure terminal
# 开启 SNMP
snmp-server community public ro

# 全局使能 LLDP
lldp enable
```

---

## 📁 目录文件说明

- `main.py`：桌面 GUI 主程序（Tkinter / Ttk 界面与多线程探测调度）；
- `snmp_engine.py`：纯 Python 实现的 SNMP 编解码与 MIB 探测引擎（包含防死循环与容错处理）；
- `oui.py`：高频硬件厂商 MAC / OUI 解析字典；
- `run.bat`：Windows 一键启动批处理脚本。
