import json
import os
import sys
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext

# Ensure local imports work regardless of current working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from snmp_engine import (
    inspect_system,
    inspect_interfaces,
    inspect_lldp_neighbors,
    inspect_fdb_table,
)


class SnmpLldpInspectorApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("SNMP & LLDP 设备探测诊断小工具 (WebWeaver Inspector)")
        self.geometry("1080x720")
        self.minsize(860, 560)

        # Inspection result store
        self.current_result = {
            "target": {},
            "system": {},
            "interfaces": [],
            "lldp_neighbors": [],
            "fdb_entries": [],
            "logs": [],
        }

        self._scanning = False
        self._init_style()
        self._build_ui()

    def _init_style(self):
        self.style = ttk.Style(self)
        # Use native 'clam' or 'vista' theme if available
        available_themes = self.style.theme_names()
        if "vista" in available_themes:
            self.style.theme_use("vista")
        elif "clam" in available_themes:
            self.style.theme_use("clam")

        self.style.configure("Title.TLabel", font=("Segoe UI", 13, "bold"))
        self.style.configure("Header.TLabel", font=("Segoe UI", 10, "bold"))
        self.style.configure("Status.TLabel", font=("Segoe UI", 9))
        self.style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_ui(self):
        # Top Frame: Config & Action Bar
        top_frame = ttk.LabelFrame(self, text=" 设备连接与探测参数 ", padding=10)
        top_frame.pack(fill=tk.X, padx=12, pady=(8, 4))

        # Row 1: Inputs
        row1 = ttk.Frame(top_frame)
        row1.pack(fill=tk.X, pady=2)

        ttk.Label(row1, text="设备 IP:").pack(side=tk.LEFT, padx=(0, 4))
        self.ip_var = tk.StringVar(value="192.168.1.1")
        self.ip_entry = ttk.Entry(row1, textvariable=self.ip_var, width=16, font=("Consolas", 10))
        self.ip_entry.pack(side=tk.LEFT, padx=(0, 14))
        self.ip_entry.bind("<Return>", lambda e: self.start_scan("all"))

        ttk.Label(row1, text="SNMP 端口:").pack(side=tk.LEFT, padx=(0, 4))
        self.port_var = tk.StringVar(value="161")
        ttk.Entry(row1, textvariable=self.port_var, width=6, font=("Consolas", 10)).pack(side=tk.LEFT, padx=(0, 14))

        ttk.Label(row1, text="团体名 (Community):").pack(side=tk.LEFT, padx=(0, 4))
        self.comm_var = tk.StringVar(value="public")
        ttk.Entry(row1, textvariable=self.comm_var, width=14, font=("Consolas", 10)).pack(side=tk.LEFT, padx=(0, 14))

        ttk.Label(row1, text="版本:").pack(side=tk.LEFT, padx=(0, 4))
        self.ver_var = tk.StringVar(value="v2c")
        ver_combo = ttk.Combobox(row1, textvariable=self.ver_var, values=["v2c", "v1"], width=6, state="readonly")
        ver_combo.pack(side=tk.LEFT, padx=(0, 14))

        ttk.Label(row1, text="超时(秒):").pack(side=tk.LEFT, padx=(0, 4))
        self.timeout_var = tk.StringVar(value="1.5")
        ttk.Entry(row1, textvariable=self.timeout_var, width=5, font=("Consolas", 10)).pack(side=tk.LEFT, padx=(0, 14))

        # Row 2: Action Buttons & Quick Presets
        row2 = ttk.Frame(top_frame)
        row2.pack(fill=tk.X, pady=(8, 2))

        self.btn_scan_all = ttk.Button(row2, text="🔍 一键全盘探测", command=lambda: self.start_scan("all"))
        self.btn_scan_all.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_scan_snmp = ttk.Button(row2, text="⚡ 仅探测系统与端口", command=lambda: self.start_scan("snmp"))
        self.btn_scan_snmp.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_scan_lldp = ttk.Button(row2, text="🔗 仅探测 LLDP 邻居", command=lambda: self.start_scan("lldp"))
        self.btn_scan_lldp.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_scan_fdb = ttk.Button(row2, text="🔀 仅探测 MAC 转发表", command=lambda: self.start_scan("fdb"))
        self.btn_scan_fdb.pack(side=tk.LEFT, padx=(0, 18))

        self.btn_export = ttk.Button(row2, text="💾 导出诊断报告", command=self.export_report)
        self.btn_export.pack(side=tk.RIGHT, padx=4)

        # Quick preset buttons
        ttk.Label(row2, text="快速测试:").pack(side=tk.LEFT, padx=(0, 4))
        btn_local = ttk.Button(row2, text="127.0.0.1", width=9, command=lambda: self.ip_var.set("127.0.0.1"))
        btn_local.pack(side=tk.LEFT, padx=2)
        btn_gw = ttk.Button(row2, text="192.168.1.1", width=11, command=lambda: self.ip_var.set("192.168.1.1"))
        btn_gw.pack(side=tk.LEFT, padx=2)

        # Progress & Status Bar
        status_frame = ttk.Frame(self, padding=(12, 2))
        status_frame.pack(fill=tk.X)
        self.status_var = tk.StringVar(value="就绪。请输入设备 IP 地址并点击【一键全盘探测】。")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, style="Status.TLabel", foreground="#333")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.progress_bar = ttk.Progressbar(status_frame, mode="indeterminate", length=180)

        # Center: Notebook with Tabs
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=12, pady=(4, 8))

        self._build_tab_system()
        self._build_tab_interfaces()
        self._build_tab_lldp()
        self._build_tab_fdb()
        self._build_tab_logs()

    # --- Tab 1: System Info ---
    def _build_tab_system(self):
        tab = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab, text=" 🖥️ 系统概览 ")

        # Left / Right Split or Form
        form_frame = ttk.Frame(tab)
        form_frame.pack(fill=tk.BOTH, expand=True)

        self.sys_fields = {}
        fields = [
            ("sys_name", "设备名称 (sysName):", 0, 0),
            ("vendor", "识别厂商 (Vendor):", 0, 1),
            ("sys_uptime", "运行时间 (sysUpTime):", 1, 0),
            ("base_mac", "Bridge MAC 地址:", 1, 1),
            ("sys_obj_id", "设备 OID (sysObjectID):", 2, 0),
            ("latency", "SNMP 响应延时:", 2, 1),
            ("sys_contact", "联系人 (sysContact):", 3, 0),
            ("sys_location", "位置 (sysLocation):", 3, 1),
        ]

        for key, label_text, row, col in fields:
            cell = ttk.Frame(form_frame, padding=6)
            cell.grid(row=row, column=col, sticky="nsew", padx=6, pady=4)
            ttk.Label(cell, text=label_text, font=("Segoe UI", 9, "bold"), foreground="#555").pack(anchor="w")
            val_lbl = ttk.Label(cell, text="--", font=("Segoe UI", 10), wraplength=420)
            val_lbl.pack(anchor="w", pady=(2, 0))
            self.sys_fields[key] = val_lbl

        form_frame.columnconfigure(0, weight=1)
        form_frame.columnconfigure(1, weight=1)

        # sysDescr Full Box
        desc_frame = ttk.LabelFrame(tab, text=" 固件与系统描述 (sysDescr) ", padding=8)
        desc_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

        self.sys_descr_text = scrolledtext.ScrolledText(desc_frame, height=8, wrap=tk.WORD, font=("Consolas", 9))
        self.sys_descr_text.pack(fill=tk.BOTH, expand=True)
        self.sys_descr_text.insert(tk.END, "暂无系统描述数据。")
        self.sys_descr_text.configure(state="disabled")

    # --- Tab 2: Interfaces ---
    def _build_tab_interfaces(self):
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text=" 🔌 端口列表 (IF-MIB) ")

        # Filter bar
        filter_bar = ttk.Frame(tab)
        filter_bar.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(filter_bar, text="筛选端口:").pack(side=tk.LEFT, padx=(0, 4))
        self.if_filter_var = tk.StringVar()
        self.if_filter_entry = ttk.Entry(filter_bar, textvariable=self.if_filter_var, width=20)
        self.if_filter_entry.pack(side=tk.LEFT, padx=(0, 10))
        self.if_filter_var.trace_add("write", lambda *args: self._filter_interfaces())

        self.if_summary_lbl = ttk.Label(filter_bar, text="共 0 个端口", font=("Segoe UI", 9, "italic"))
        self.if_summary_lbl.pack(side=tk.RIGHT)

        # Treeview
        cols = ("index", "name", "oper", "admin", "speed", "descr", "in_bytes", "out_bytes")
        self.if_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self.if_tree.heading("index", text="索引")
        self.if_tree.heading("name", text="端口名称")
        self.if_tree.heading("oper", text="物理状态")
        self.if_tree.heading("admin", text="管理状态")
        self.if_tree.heading("speed", text="协商速率")
        self.if_tree.heading("descr", text="端口描述")
        self.if_tree.heading("in_bytes", text="接收字节 (In)")
        self.if_tree.heading("out_bytes", text="发送字节 (Out)")

        self.if_tree.column("index", width=55, anchor="center")
        self.if_tree.column("name", width=120, anchor="w")
        self.if_tree.column("oper", width=80, anchor="center")
        self.if_tree.column("admin", width=80, anchor="center")
        self.if_tree.column("speed", width=100, anchor="center")
        self.if_tree.column("descr", width=220, anchor="w")
        self.if_tree.column("in_bytes", width=130, anchor="e")
        self.if_tree.column("out_bytes", width=130, anchor="e")

        vsb = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.if_tree.yview)
        self.if_tree.configure(yscrollcommand=vsb.set)
        self.if_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

    # --- Tab 3: LLDP Neighbors ---
    def _build_tab_lldp(self):
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text=" 🌐 LLDP 邻居链路 (LLDP-MIB) ")

        top_info = ttk.Frame(tab)
        top_info.pack(fill=tk.X, pady=(0, 6))

        self.lldp_summary_lbl = ttk.Label(top_info, text="发现 0 条对端邻居链路 (若为空请检查交换机是否开启 lldp enable)", font=("Segoe UI", 9))
        self.lldp_summary_lbl.pack(side=tk.LEFT)

        cols = ("loc_port", "rem_chassis", "rem_vendor", "rem_sysname", "rem_port", "rem_ip", "rem_desc")
        self.lldp_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self.lldp_tree.heading("loc_port", text="本地端口")
        self.lldp_tree.heading("rem_chassis", text="对端机箱 ID (MAC)")
        self.lldp_tree.heading("rem_vendor", text="对端厂商")
        self.lldp_tree.heading("rem_sysname", text="对端设备系统名")
        self.lldp_tree.heading("rem_port", text="对端连接端口")
        self.lldp_tree.heading("rem_ip", text="对端管理 IP")
        self.lldp_tree.heading("rem_desc", text="对端系统信息")

        self.lldp_tree.column("loc_port", width=110, anchor="w")
        self.lldp_tree.column("rem_chassis", width=140, anchor="center")
        self.lldp_tree.column("rem_vendor", width=110, anchor="w")
        self.lldp_tree.column("rem_sysname", width=140, anchor="w")
        self.lldp_tree.column("rem_port", width=110, anchor="w")
        self.lldp_tree.column("rem_ip", width=120, anchor="center")
        self.lldp_tree.column("rem_desc", width=240, anchor="w")

        vsb = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.lldp_tree.yview)
        self.lldp_tree.configure(yscrollcommand=vsb.set)
        self.lldp_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.lldp_tree.bind("<Double-1>", self._on_lldp_double_click)

    # --- Tab 4: Bridge FDB (MAC Table) ---
    def _build_tab_fdb(self):
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text=" 🔀 MAC 转发表 (Bridge FDB) ")

        bar = ttk.Frame(tab)
        bar.pack(fill=tk.X, pady=(0, 6))

        ttk.Label(bar, text="筛选 MAC / 端口:").pack(side=tk.LEFT, padx=(0, 4))
        self.fdb_filter_var = tk.StringVar()
        entry = ttk.Entry(bar, textvariable=self.fdb_filter_var, width=20)
        entry.pack(side=tk.LEFT, padx=(0, 10))
        self.fdb_filter_var.trace_add("write", lambda *args: self._filter_fdb())

        self.fdb_summary_lbl = ttk.Label(bar, text="共 0 条转发表条目", font=("Segoe UI", 9, "italic"))
        self.fdb_summary_lbl.pack(side=tk.RIGHT)

        cols = ("mac", "vendor", "port", "ifindex", "status")
        self.fdb_tree = ttk.Treeview(tab, columns=cols, show="headings", selectmode="browse")
        self.fdb_tree.heading("mac", text="MAC 地址")
        self.fdb_tree.heading("vendor", text="网卡厂商")
        self.fdb_tree.heading("port", text="BasePort")
        self.fdb_tree.heading("ifindex", text="对应 IfIndex")
        self.fdb_tree.heading("status", text="学习状态")

        self.fdb_tree.column("mac", width=160, anchor="center")
        self.fdb_tree.column("vendor", width=160, anchor="w")
        self.fdb_tree.column("port", width=100, anchor="center")
        self.fdb_tree.column("ifindex", width=100, anchor="center")
        self.fdb_tree.column("status", width=140, anchor="center")

        vsb = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.fdb_tree.yview)
        self.fdb_tree.configure(yscrollcommand=vsb.set)
        self.fdb_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

    # --- Tab 5: Logs & Diagnostics ---
    def _build_tab_logs(self):
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text=" 📜 诊断日志与排障指引 ")

        self.log_text = scrolledtext.ScrolledText(tab, wrap=tk.WORD, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.tag_config("INFO", foreground="#2e7d32")
        self.log_text.tag_config("WARN", foreground="#e65100")
        self.log_text.tag_config("ERROR", foreground="#c62828", font=("Consolas", 9, "bold"))
        self.log_text.tag_config("TITLE", foreground="#1565c0", font=("Consolas", 10, "bold"))

        self._append_log("初始化完毕。就绪中...", "INFO")
        self._append_log("排障小贴士：", "TITLE")
        self._append_log("1. 交换机通常默认关闭 SNMP。例如华为交换机需开启：\n   snmp-agent\n   snmp-agent sys-info version v2c\n   snmp-agent community read public", "INFO")
        self._append_log("2. 若需获取链路拓扑，交换机需全局开启 LLDP：\n   lldp enable", "INFO")

    def _append_log(self, msg: str, level: str = "INFO"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{timestamp}] [{level}] {msg}\n"
        self.log_text.configure(state="normal")
        self.log_text.insert(tk.END, line, level)
        self.log_text.see(tk.END)
        self.log_text.configure(state="disabled")
        self.current_result["logs"].append(line)

    # --- Scanning Workflow ---
    def start_scan(self, mode: str = "all"):
        if self._scanning:
            messagebox.showwarning("提示", "正在探测中，请稍候...")
            return

        ip = self.ip_var.get().strip()
        if not ip:
            messagebox.showerror("错误", "请输入有效的设备 IP 地址！")
            return

        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("错误", "端口必须为数字！")
            return

        community = self.comm_var.get().strip() or "public"
        version = self.ver_var.get().strip() or "v2c"
        try:
            timeout = float(self.timeout_var.get().strip())
        except ValueError:
            timeout = 1.5

        self._scanning = True
        self.btn_scan_all.configure(state="disabled")
        self.btn_scan_snmp.configure(state="disabled")
        self.btn_scan_lldp.configure(state="disabled")
        self.btn_scan_fdb.configure(state="disabled")
        self.progress_bar.pack(side=tk.RIGHT, padx=8)
        self.progress_bar.start(10)

        # Run in background thread
        thread = threading.Thread(
            target=self._scan_worker,
            args=(ip, port, community, version, timeout, mode),
            daemon=True,
        )
        thread.start()

    def _scan_worker(self, ip: str, port: int, community: str, version: str, timeout: float, mode: str):
        self._append_log(f"开始探测目标: {ip}:{port} (版本={version}, 团体名={community}, 超时={timeout}s, 模式={mode})", "TITLE")
        self.status_var.set(f"正在探测设备 {ip}:{port}...")

        self.current_result["target"] = {
            "ip": ip,
            "port": port,
            "community": community,
            "version": version,
            "scan_time": datetime.now().isoformat(),
        }

        # 1. System Info
        if mode in ("all", "snmp"):
            self.status_var.set("正在获取系统基础信息 (sysDescr / sysName / sysUpTime)...")
            sys_info = inspect_system(ip, community, port, version, timeout)
            self.current_result["system"] = sys_info

            if not sys_info.get("reachable"):
                err_msg = sys_info.get("error", "未收到 SNMP 响应")
                self._append_log(f"系统探测失败: {err_msg}", "ERROR")
                self._append_log("建议排查：1. 确认该 IP 能否 Ping 通；2. 确认设备开启了 SNMP 且团体名正确；3. 确认 UDP 161 端口无防火墙阻拦。", "WARN")
                self.after(0, self._update_system_ui, sys_info)
                self.after(0, self._scan_finished, False)
                return

            self._append_log(
                f"系统响应正常！延时: {sys_info['latency_ms']:.1f}ms | 名称: {sys_info['sys_name']} | 厂商: {sys_info['vendor']}",
                "INFO",
            )
            self.after(0, self._update_system_ui, sys_info)

        # 2. Interfaces (IF-MIB)
        if mode in ("all", "snmp"):
            self.status_var.set("正在遍历端口列表 (IF-MIB)...")
            interfaces = inspect_interfaces(ip, community, port, version, timeout)
            self.current_result["interfaces"] = interfaces
            up_count = sum(1 for iface in interfaces if iface["oper_status"] == "UP")
            self._append_log(f"端口探测完成: 发现 {len(interfaces)} 个接口 (其中 {up_count} 个 UP)", "INFO")
            self.after(0, self._update_interfaces_ui, interfaces)

        # 3. LLDP Neighbors (LLDP-MIB)
        if mode in ("all", "lldp"):
            self.status_var.set("正在探测链路层邻居拓扑 (LLDP-MIB)...")
            lldp_neighbors = inspect_lldp_neighbors(ip, community, port, version, timeout)
            self.current_result["lldp_neighbors"] = lldp_neighbors
            if lldp_neighbors:
                self._append_log(f"LLDP 链路探测完成: 发现 {len(lldp_neighbors)} 个对端直连邻居！", "INFO")
                for n in lldp_neighbors:
                    self._append_log(
                        f"  -> 本地[{n['local_port']}] 连接 对端设备[{n['rem_sysname']}] 的 [{n['rem_port']}] (管理IP: {n['rem_mgmt_ip'] or '无'})",
                        "INFO",
                    )
            else:
                self._append_log("LLDP 探测未发现任何邻居条目 (可能设备未开启 LLDP 或下挂设备不支持)", "WARN")
            self.after(0, self._update_lldp_ui, lldp_neighbors)

        # 4. Bridge FDB (MAC Table)
        if mode in ("all", "fdb"):
            self.status_var.set("正在读取 MAC 转发表 (Bridge FDB)...")
            fdb_entries = inspect_fdb_table(ip, community, port, version, timeout)
            self.current_result["fdb_entries"] = fdb_entries
            self._append_log(f"FDB 转发表读取完成: 发现 {len(fdb_entries)} 条 MAC 条目", "INFO")
            self.after(0, self._update_fdb_ui, fdb_entries)

        self._append_log("探测流程全部执行完毕！", "TITLE")
        self.after(0, self._scan_finished, True)

    def _scan_finished(self, success: bool):
        self._scanning = False
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        self.btn_scan_all.configure(state="normal")
        self.btn_scan_snmp.configure(state="normal")
        self.btn_scan_lldp.configure(state="normal")
        self.btn_scan_fdb.configure(state="normal")
        if success:
            self.status_var.set("探测完成！请在上方各个标签页查看详细信息。")
        else:
            self.status_var.set("探测失败：未能连通目标设备的 SNMP 服务，详情请看诊断日志。")

    # --- UI Updaters ---
    def _update_system_ui(self, info: Dict[str, Any]):
        if not info.get("reachable"):
            for k in self.sys_fields:
                self.sys_fields[k].configure(text="-- (连接失败)")
            self.sys_descr_text.configure(state="normal")
            self.sys_descr_text.delete("1.0", tk.END)
            self.sys_descr_text.insert(tk.END, info.get("error", "未收到 SNMP 响应"))
            self.sys_descr_text.configure(state="disabled")
            return

        self.sys_fields["sys_name"].configure(text=info.get("sys_name", "--"))
        self.sys_fields["vendor"].configure(text=info.get("vendor", "--"))
        self.sys_fields["sys_uptime"].configure(text=info.get("sys_uptime", "--"))
        self.sys_fields["base_mac"].configure(text=info.get("base_mac", "--"))
        self.sys_fields["sys_obj_id"].configure(text=info.get("sys_obj_id", "--"))
        self.sys_fields["latency"].configure(text=f"{info.get('latency_ms', 0):.1f} ms")
        self.sys_fields["sys_contact"].configure(text=info.get("sys_contact", "--"))
        self.sys_fields["sys_location"].configure(text=info.get("sys_location", "--"))

        self.sys_descr_text.configure(state="normal")
        self.sys_descr_text.delete("1.0", tk.END)
        self.sys_descr_text.insert(tk.END, info.get("sys_descr", "未知"))
        self.sys_descr_text.configure(state="disabled")

    def _update_interfaces_ui(self, ifaces: List[Dict[str, Any]]):
        self._cached_interfaces = ifaces
        self._filter_interfaces()

    def _filter_interfaces(self):
        if not hasattr(self, "_cached_interfaces"):
            return
        query = self.if_filter_var.get().strip().lower()
        self.if_tree.delete(*self.if_tree.get_children())

        matched = 0
        up_count = 0
        for iface in self._cached_interfaces:
            if query and (query not in iface["name"].lower() and query not in iface["descr"].lower()):
                continue

            matched += 1
            if iface["oper_status"] == "UP":
                up_count += 1

            self.if_tree.insert(
                "",
                tk.END,
                values=(
                    iface["index"],
                    iface["name"],
                    iface["oper_status"],
                    iface["admin_status"],
                    iface["speed_display"],
                    iface["descr"],
                    f"{iface['in_octets']:,}",
                    f"{iface['out_octets']:,}",
                ),
            )

        self.if_summary_lbl.configure(text=f"展示 {matched}/{len(self._cached_interfaces)} 个端口 (UP: {up_count})")

    def _update_lldp_ui(self, neighbors: List[Dict[str, Any]]):
        self.lldp_tree.delete(*self.lldp_tree.get_children())
        for n in neighbors:
            self.lldp_tree.insert(
                "",
                tk.END,
                values=(
                    n["local_port"],
                    n["rem_chassis_id"],
                    n["rem_vendor"],
                    n["rem_sysname"],
                    n["rem_port"],
                    n["rem_mgmt_ip"],
                    n["rem_sysdesc"] or n["rem_port_desc"],
                ),
            )
        self.lldp_summary_lbl.configure(
            text=f"共发现 {len(neighbors)} 条对端邻居物理链路 (双击条目可查看详情)"
        )

    def _on_lldp_double_click(self, event):
        item = self.lldp_tree.selection()
        if not item:
            return
        values = self.lldp_tree.item(item[0], "values")
        if not values:
            return

        detail_text = (
            f"本地连接端口: {values[0]}\n"
            f"对端机箱 ID (MAC): {values[1]}\n"
            f"对端硬件厂商: {values[2]}\n"
            f"对端系统名 (SysName): {values[3]}\n"
            f"对端连接端口: {values[4]}\n"
            f"对端管理 IP: {values[5]}\n\n"
            f"对端系统描述 (SysDesc):\n{values[6]}"
        )
        messagebox.showinfo("LLDP 邻居详情", detail_text)

    def _update_fdb_ui(self, entries: List[Dict[str, Any]]):
        self._cached_fdb = entries
        self._filter_fdb()

    def _filter_fdb(self):
        if not hasattr(self, "_cached_fdb"):
            return
        query = self.fdb_filter_var.get().strip().lower()
        self.fdb_tree.delete(*self.fdb_tree.get_children())

        matched = 0
        for e in self._cached_fdb:
            if query and (query not in e["mac"].lower() and query not in str(e["base_port"]) and query not in e["vendor"].lower()):
                continue
            matched += 1
            self.fdb_tree.insert(
                "",
                tk.END,
                values=(
                    e["mac"],
                    e["vendor"],
                    e["base_port"],
                    e["if_index"],
                    e["status"],
                ),
            )
        self.fdb_summary_lbl.configure(text=f"展示 {matched}/{len(self._cached_fdb)} 条 MAC 记录")

    # --- Export Report ---
    def export_report(self):
        if not self.current_result.get("target"):
            messagebox.showinfo("提示", "当前尚无探测数据，请先执行探测。")
            return

        ip = self.current_result["target"].get("ip", "device")
        default_filename = f"snmp_lldp_report_{ip}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON 数据文件", "*.json"), ("文本报告", "*.txt"), ("所有文件", "*.*")],
            initialfile=default_filename,
            title="保存探测诊断报告",
        )
        if not file_path:
            return

        try:
            if file_path.endswith(".json"):
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(self.current_result, f, ensure_ascii=False, indent=2)
            else:
                # Text format
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("=" * 60 + "\n")
                    f.write("WebWeaver SNMP & LLDP 设备探测诊断报告\n")
                    f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"目标设备: {ip}:{self.current_result['target'].get('port', 161)}\n")
                    f.write("=" * 60 + "\n\n")

                    f.write("【一、系统基础信息】\n")
                    for k, v in self.current_result.get("system", {}).items():
                        f.write(f"  {k}: {v}\n")
                    f.write("\n")

                    f.write("【二、LLDP 链路邻居】\n")
                    for n in self.current_result.get("lldp_neighbors", []):
                        f.write(f"  - 本地端口: {n['local_port']} -> 对端: {n['rem_sysname']} [{n['rem_port']}] (MAC: {n['rem_chassis_id']}, IP: {n['rem_mgmt_ip']})\n")
                    f.write("\n")

                    f.write("【三、端口状态列表 (IF-MIB)】\n")
                    for iface in self.current_result.get("interfaces", []):
                        f.write(f"  - [{iface['index']}] {iface['name']} (状态: {iface['oper_status']}, 速率: {iface['speed_display']})\n")
                    f.write("\n")

                    f.write("【四、诊断日志】\n")
                    for line in self.current_result.get("logs", []):
                        f.write(line)

            messagebox.showinfo("成功", f"报告已成功导出到:\n{file_path}")
        except Exception as e:
            messagebox.showerror("导出失败", f"保存报告时发生异常:\n{e}")


def main():
    app = SnmpLldpInspectorApp()
    app.mainloop()


if __name__ == "__main__":
    main()
