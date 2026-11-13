import re
from typing import Optional

# High-frequency OUI prefix dictionary (Hex string 6 chars uppercase -> Vendor Name)
OUI_VENDOR_MAP = {
    # Huawei
    "00E0FC": "Huawei (华为)",
    "707990": "Huawei (华为)",
    "286ED4": "Huawei (华为)",
    "4846FB": "Huawei (华为)",
    "001882": "Huawei (华为)",
    "00259E": "Huawei (华为)",
    "101B54": "Huawei (华为)",
    "24DBAC": "Huawei (华为)",
    "3CDA2A": "Huawei (华为)",
    "4C5499": "Huawei (华为)",
    "80B686": "Huawei (华为)",
    "E468A3": "Huawei (华为)",
    "F4E3FB": "Huawei (华为)",
    "DC3714": "Huawei (华为)",
    "E8088B": "Huawei (华为)",
    # H3C / New H3C
    "000FE2": "H3C (新华三)",
    "3897D6": "H3C (新华三)",
    "70F96B": "H3C (新华三)",
    "80F62E": "H3C (新华三)",
    "B0ADAA": "H3C (新华三)",
    "002389": "H3C (新华三)",
    "000F5D": "H3C (新华三)",
    "D89D67": "H3C (新华三)",
    "600BE7": "H3C (新华三)",
    "74697C": "H3C (新华三)",
    # Cisco
    "00000C": "Cisco (思科)",
    "000142": "Cisco (思科)",
    "000143": "Cisco (思科)",
    "001BD4": "Cisco (思科)",
    "00260B": "Cisco (思科)",
    "00270D": "Cisco (思科)",
    "004096": "Cisco (思科)",
    "046C9D": "Cisco (思科)",
    "28940F": "Cisco (思科)",
    "40F4EC": "Cisco (思科)",
    "706979": "Cisco (思科)",
    "C80084": "Cisco (思科)",
    "E05FB9": "Cisco (思科)",
    # Ruijie / Reyee
    "001AA9": "Ruijie (锐捷)",
    "14144B": "Ruijie (锐捷)",
    "7405A5": "Ruijie (锐捷)",
    "BC1AA5": "Ruijie (锐捷)",
    "944744": "Ruijie (锐捷)",
    "3420E3": "Ruijie (锐捷)",
    "58696C": "Ruijie (锐捷)",
    "D84732": "Ruijie (锐捷)",
    # TP-Link / Mercusys
    "50BD5F": "TP-Link (普联)",
    "000AEB": "TP-Link (普联)",
    "E848B8": "TP-Link (普联)",
    "B09575": "TP-Link (普联)",
    "EC172F": "TP-Link (普联)",
    "30DE4B": "TP-Link (普联)",
    "60A44C": "TP-Link (普联)",
    "7844FD": "TP-Link (普联)",
    "84D81B": "TP-Link (普联)",
    "984265": "TP-Link (普联)",
    "D46E0E": "TP-Link (普联)",
    "DC56E7": "TP-Link (普联)",
    # Hikvision (海康威视)
    "849459": "Hikvision (海康威视)",
    "4419B6": "Hikvision (海康威视)",
    "BC5451": "Hikvision (海康威视)",
    "C42F90": "Hikvision (海康威视)",
    "0018AE": "Hikvision (海康威视)",
    "2857BE": "Hikvision (海康威视)",
    "601971": "Hikvision (海康威视)",
    "A41437": "Hikvision (海康威视)",
    "C056E3": "Hikvision (海康威视)",
    "DCB72E": "Hikvision (海康威视)",
    # Dahua (大华)
    "3CEF8C": "Dahua (大华)",
    "4C11BF": "Dahua (大华)",
    "E0508B": "Dahua (大华)",
    "9002A9": "Dahua (大华)",
    "A0BD1D": "Dahua (大华)",
    "B4A382": "Dahua (大华)",
    # Uniview (宇视)
    "48EA63": "Uniview (宇视)",
    "282C02": "Uniview (宇视)",
    # Apple
    "482C6A": "Apple (苹果)",
    "F01898": "Apple (苹果)",
    "ACBC32": "Apple (苹果)",
    "000393": "Apple (苹果)",
    "000A27": "Apple (苹果)",
    "000A95": "Apple (苹果)",
    "001124": "Apple (苹果)",
    "001451": "Apple (苹果)",
    "0016CB": "Apple (苹果)",
    "18AF61": "Apple (苹果)",
    "28CFDA": "Apple (苹果)",
    "34159E": "Apple (苹果)",
    "70CD60": "Apple (苹果)",
    "784F43": "Apple (苹果)",
    "8C8590": "Apple (苹果)",
    "A483E7": "Apple (苹果)",
    "BC9FEF": "Apple (苹果)",
    "D89E3F": "Apple (苹果)",
    "F4F15A": "Apple (苹果)",
    # Xiaomi
    "6490C1": "Xiaomi (小米)",
    "7C49EB": "Xiaomi (小米)",
    "F0B429": "Xiaomi (小米)",
    "286C07": "Xiaomi (小米)",
    "3480B3": "Xiaomi (小米)",
    "508F4C": "Xiaomi (小米)",
    "5C0214": "Xiaomi (小米)",
    "7811DC": "Xiaomi (小米)",
    "8CBEBE": "Xiaomi (小米)",
    "9C99A0": "Xiaomi (小米)",
    "D4970B": "Xiaomi (小米)",
    # Intel
    "001E67": "Intel (英特尔)",
    "0013E8": "Intel (英特尔)",
    "3413E8": "Intel (英特尔)",
    "001500": "Intel (英特尔)",
    "001B21": "Intel (英特尔)",
    "080046": "Intel (英特尔)",
    "3C5282": "Intel (英特尔)",
    "4851B7": "Intel (英特尔)",
    "6805CA": "Intel (英特尔)",
    "8086F2": "Intel (英特尔)",
    # Dell
    "001422": "Dell (戴尔)",
    "F8DB88": "Dell (戴尔)",
    "1866DA": "Dell (戴尔)",
    "B8AC6F": "Dell (戴尔)",
    "D4BED9": "Dell (戴尔)",
    # HP / HPE / Aruba
    "001B78": "HP (惠普)",
    "3CD92B": "HP (惠普)",
    "002481": "HP (惠普)",
    "10604B": "HP (惠普)",
    "28924A": "HP (惠普)",
    "000B86": "Aruba (安鲁巴)",
    "20A680": "Aruba (安鲁巴)",
    # Lenovo
    "005907": "Lenovo (联想)",
    "507B9D": "Lenovo (联想)",
    "7072CF": "Lenovo (联想)",
    "84A938": "Lenovo (联想)",
    # ZTE (中兴)
    "0019C6": "ZTE (中兴)",
    "002293": "ZTE (中兴)",
    "34DE1A": "ZTE (中兴)",
    "68A0F6": "ZTE (中兴)",
    "84742A": "ZTE (中兴)",
    # Ubiquiti / UniFi
    "002722": "Ubiquiti (优倍快)",
    "24A43C": "Ubiquiti (优倍快)",
    "68D79A": "Ubiquiti (优倍快)",
    "788A20": "Ubiquiti (优倍快)",
    "B4FBE4": "Ubiquiti (优倍快)",
    "DC9FDB": "Ubiquiti (优倍快)",
    "F09FC2": "Ubiquiti (优倍快)",
    # MikroTik
    "000C42": "MikroTik (微控)",
    "488F5A": "MikroTik (微控)",
    "64D154": "MikroTik (微控)",
    "CC2DE0": "MikroTik (微控)",
    "60BEB4": "MikroTik (微控)",
    "B869F4": "MikroTik (微控)",
    # Netgear
    "000FB5": "Netgear (网件)",
    "20E52A": "Netgear (网件)",
    "A00460": "Netgear (网件)",
    # Synology (群晖)
    "001132": "Synology (群晖)",
    # QNAP (威联通)
    "00089B": "QNAP (威联通)",
    "245EBE": "QNAP (威联通)",
    # Realtek
    "00E04C": "Realtek (瑞昱)",
    # Virtualization
    "525400": "QEMU/KVM",
    "000569": "VMware",
    "000C29": "VMware",
    "005056": "VMware",
    "080027": "VirtualBox",
}


def normalize_mac(mac: Optional[str]) -> Optional[str]:
    """Normalize MAC address string into standard uppercase colon format: XX:XX:XX:XX:XX:XX."""
    if not mac or not isinstance(mac, str):
        return None

    cleaned = mac.strip()
    hex_only = re.sub(r"[^0-9a-fA-F]", "", cleaned)

    if len(hex_only) != 12:
        return None

    hex_upper = hex_only.upper()
    return ":".join(hex_upper[i : i + 2] for i in range(0, 12, 2))


def lookup_vendor(mac: Optional[str]) -> str:
    """Lookup hardware vendor name from MAC address using built-in high frequency OUI dictionary."""
    normalized = normalize_mac(mac)
    if not normalized:
        return "未知厂商"

    prefix = normalized.replace(":", "")[:6]
    return OUI_VENDOR_MAP.get(prefix, "未知厂商")
