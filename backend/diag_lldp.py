#!/usr/bin/env python3
"""
LLDP & CDP SNMP 连通性与邻居发现诊断脚本
用法:
    python3 diag_lldp.py <交换机IP> [SNMP团体字]
例如:
    python3 diag_lldp.py 172.16.2.26 public
"""

import sys
import os

# Ensure backend path in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.snmp import (
    snmp_walk,
    build_snmp_getnext_packet,
    decode_asn1,
    OID_IF_DESCR,
    OID_IF_NAME,
    OID_LLDP_LOC_PORT_DESC,
    OID_LLDP_LOC_PORT_ID,
    OID_LLDP_REM_CHASSIS_ID,
    OID_LLDP_REM_PORT_ID,
    OID_LLDP_REM_SYS_NAME,
)
import socket


def _decode_bytes_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, (bytes, bytearray)):
        try:
            return val.decode("utf-8").strip()
        except Exception:
            try:
                return val.decode("gbk").strip()
            except Exception:
                return ":".join(f"{b:02x}" for b in val)
    return str(val).strip()


def _format_chassis_id(val) -> str:
    if isinstance(val, (bytes, bytearray)):
        if len(val) == 6:
            return ":".join(f"{b:02X}" for b in val)
        return _decode_bytes_str(val)
    elif isinstance(val, str):
        return val.strip()
    return ""


def main():
    if len(sys.argv) < 2:
        print("用法: python3 diag_lldp.py <交换机IP> [SNMP团体字, 默认public]")
        sys.exit(1)

    ip = sys.argv[1].strip()
    community = sys.argv[2].strip() if len(sys.argv) > 2 else "public"

    print(f"\n=======================================================")
    print(f" 开始对交换机 [{ip}] 进行 SNMP & LLDP / CDP 连通性诊断")
    print(f" 目标端口: 161/UDP, 团体字: {community}")
    print(f"=======================================================\n")

    # Step 1: 基础 IF-MIB (1.3.6.1.2.1.2)
    print("【步骤 1】检测基础 SNMP 连通性 (IF-MIB: 1.3.6.1.2.1.2.2.1.2)...")
    if_descrs = snmp_walk(ip, community, OID_IF_DESCR, timeout=1.5, max_entries=5)
    if not if_descrs:
        if_descrs = snmp_walk(ip, community, OID_IF_NAME, timeout=1.5, max_entries=5)

    if if_descrs:
        print(f"  [√] 成功！基础 SNMP 通信正常，读取到接口样本:")
        for oid, val in list(if_descrs.items())[:3]:
            print(f"      - {oid} => {_decode_bytes_str(val)}")
    else:
        print(f"  [X] 失败！交换机未响应基础 SNMP 请求。")
        print(f"      原因排查建议:")
        print(f"      1. 交换机 SNMP 团体字是否为 '{community}'？请在 WebWeaver 交换机详情中确认。")
        print(f"      2. 交换机是否配置了 ACL 限制访问？需放行服务器 IP 访问 UDP 161。")
        print(f"      3. 交换机上是否开启了 SNMP 服务 (如华为: snmp-agent sys-info version v2c)。")
        print(f"\n诊断终止。")
        return

    # Step 2: 标准 IEEE 802.1AB LLDP 本地端口表 (1.0.8802.1.1.2.1.3.7)
    print("\n【步骤 2】检测标准 LLDP 本地端口表 (OID: 1.0.8802.1.1.2.1.3.7)...")
    loc_ports = snmp_walk(ip, community, OID_LLDP_LOC_PORT_DESC, timeout=1.5, max_entries=5)
    if not loc_ports:
        loc_ports = snmp_walk(ip, community, OID_LLDP_LOC_PORT_ID, timeout=1.5, max_entries=5)

    if loc_ports:
        print(f"  [√] 成功！交换机已启用标准 LLDP 协议，读取到本地端口条目 {len(loc_ports)} 个。")
    else:
        print(f"  [!] 未读取到标准 LLDP 本地端口数据。")
        print(f"      可能原因:")
        print(f"      1. 交换机未开启 LLDP 功能（国内交换机出厂默认多为关闭）。")
        print(f"         - 华为交换机开启命令: [Huawei] lldp enable")
        print(f"         - 华三 (H3C) 开启命令: [H3C] lldp global enable")
        print(f"         - 锐捷交换机开启命令: Ruijie(config)# lldp enable")
        print(f"         - 思科交换机开启命令: Switch(config)# lldp run")
        print(f"      2. 交换机配置了 SNMP MIB-View 视图限制！")
        print(f"         - 许多管理员配置时写的是 'mib-view include iso-view 1.3.6.1' (即 internet 树)。")
        print(f"         - 但标准 LLDP 的根在 '1.0.8802'，不在 1.3.6.1 下！交换机会拦截该查询。")
        print(f"         - 解决办法: 交换机上配置 'snmp-agent mib-view include all-view iso' (或允许 1.0.8802)。")

    # Step 3: 底层 Raw GetNext 探测 (检测交换机是否支持或跳过了 1.0.8802)
    print("\n【步骤 3】对 1.0.8802.1.1.2.1.4.1.1.5 发起底层单步 GetNext 探针...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    try:
        pkt = build_snmp_getnext_packet(community, OID_LLDP_REM_CHASSIS_ID, request_id=1)
        sock.sendto(pkt, (ip, 161))
        data, _ = sock.recvfrom(4096)
        _, msg, _ = decode_asn1(data)
        ret_oid = msg[2][3][0][0]
        ret_val = msg[2][3][0][1]
        print(f"  [>] 交换机原始返回 OID: {ret_oid}")
        print(f"  [>] 原始 Value: {repr(ret_val)}")
        if str(ret_oid).startswith("1.0.8802."):
            print(f"  [√] 交换机支持标准 LLDP-MIB (1.0.8802)！")
        else:
            print(f"  [!] 关键发现：交换机未支持 1.0.8802 分支，直接跳到了后面的 OID ({ret_oid})！")
            print(f"      说明该白牌交换机固件虽然在 Web 页面上有 LLDP，但在其精简的 SNMP 代理中没有注册 1.0.8802 MIB。")
    except socket.timeout:
        print(f"  [!] 交换机对 1.0.8802 查询超时未响应。")
    except Exception as e:
        print(f"  [!] 异常: {e}")
    finally:
        sock.close()

    # Step 4: 标准 LLDP 远端邻居表 (OID: 1.0.8802.1.1.2.1.4.1.1.5)
    print("\n【步骤 4】遍历标准 LLDP 远端邻居表 (OID: 1.0.8802.1.1.2.1.4.1.1.5)...")
    rem_chassis = snmp_walk(ip, community, OID_LLDP_REM_CHASSIS_ID, timeout=1.5, max_entries=50)
    rem_sysnames = snmp_walk(ip, community, OID_LLDP_REM_SYS_NAME, timeout=1.5, max_entries=50)
    rem_ports = snmp_walk(ip, community, OID_LLDP_REM_PORT_ID, timeout=1.5, max_entries=50)

    if rem_chassis:
        print(f"  [√] 成功！发现 {len(rem_chassis)} 个物理 LLDP 互联邻居条目：")
        for oid, c_val in rem_chassis.items():
            parts = oid.strip(".").split(".")
            loc_idx = parts[-2] if len(parts) >= 2 else "?"
            rem_idx = parts[-1] if len(parts) >= 1 else "?"
            chassis = _format_chassis_id(c_val)
            # Find sysname
            s_name = "-"
            for soid, sval in rem_sysnames.items():
                if soid.endswith(f".{loc_idx}.{rem_idx}"):
                    s_name = _decode_bytes_str(sval)
                    break
            # Find port
            p_name = "-"
            for poid, pval in rem_ports.items():
                if poid.endswith(f".{loc_idx}.{rem_idx}"):
                    p_name = _decode_bytes_str(pval)
                    break
            print(f"      - 本地端口Index {loc_idx} ⟷ 对端设备: {s_name} | 对端端口: {p_name} | 对端MAC: {chassis}")
    else:
        print(f"  [-] 未返回任何标准 LLDP 远端邻居条目。")

    # Step 5: 检测 Cisco CDP 邻居表 (1.3.6.1.4.1.9.9.23.1.2.1.1.6)
    print("\n【步骤 5】检测思科 CDP 协议邻居表 (OID: 1.3.6.1.4.1.9.9.23.1.2.1.1)...")
    cdp_devs = snmp_walk(ip, community, "1.3.6.1.4.1.9.9.23.1.2.1.1.6", timeout=1.5, max_entries=50)
    if cdp_devs:
        print(f"  [√] 发现思科 CDP 邻居条目 {len(cdp_devs)} 个！该交换机当前跑的是 CDP 协议。")
        for oid, d_val in cdp_devs.items():
            print(f"      - 对端CDP设备: {_decode_bytes_str(d_val)}")
    else:
        print(f"  [-] 未检测到 CDP 邻居数据。")

    # Step 6: 检测交换机转发表 (Bridge-MIB dot1dTpFdbPort: 1.3.6.1.2.1.17.4.3.1.2)
    print("\n【步骤 6】检测标准交换机 MAC 转发表 (Bridge-MIB: 1.3.6.1.2.1.17.4.3.1.2)...")
    fdb_ports = snmp_walk(ip, community, "1.3.6.1.2.1.17.4.3.1.2", timeout=1.5, max_entries=10)
    if fdb_ports:
        print(f"  [√] 成功！交换机支持标准 Bridge-MIB 转发表，学习到 {len(fdb_ports)} 条 MAC-端口映射样本！")
    else:
        print(f"  [-] 未响应 Bridge-MIB 转发表。")

    print("\n=======================================================")
    print(" 诊断完成！")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
