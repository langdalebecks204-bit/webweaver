import re
from typing import Optional

# High-frequency OUI prefix dictionary (Hex string 6 chars uppercase -> Vendor Name)
OUI_VENDOR_MAP = {
    # Huawei
    "00E0FC": "Huawei",
    "707990": "Huawei",
    "286ED4": "Huawei",
    "4846FB": "Huawei",
    "001882": "Huawei",
    "00259E": "Huawei",
    "101B54": "Huawei",
    "24DBAC": "Huawei",
    "3CDA2A": "Huawei",
    "4C5499": "Huawei",
    "80B686": "Huawei",
    "E468A3": "Huawei",
    "F4E3FB": "Huawei",
    "DC3714": "Huawei",
    "E8088B": "Huawei",
    # H3C / New H3C
    "000FE2": "H3C",
    "3897D6": "H3C",
    "70F96B": "H3C",
    "80F62E": "H3C",
    "B0ADAA": "H3C",
    "002389": "H3C",
    "000F5D": "H3C",
    "D89D67": "H3C",
    "600BE7": "H3C",
    "74697C": "H3C",
    # Cisco
    "00000C": "Cisco",
    "000142": "Cisco",
    "000143": "Cisco",
    "001BD4": "Cisco",
    "00260B": "Cisco",
    "00270D": "Cisco",
    "004096": "Cisco",
    "046C9D": "Cisco",
    "28940F": "Cisco",
    "40F4EC": "Cisco",
    "706979": "Cisco",
    "C80084": "Cisco",
    "E05FB9": "Cisco",
    # Ruijie / Reyee
    "001AA9": "Ruijie",
    "14144B": "Ruijie",
    "7405A5": "Ruijie",
    "BC1AA5": "Ruijie",
    "944744": "Ruijie",
    "3420E3": "Ruijie",
    "58696C": "Ruijie",
    "D84732": "Ruijie",
    # TP-Link / Mercusys
    "50BD5F": "TP-Link",
    "000AEB": "TP-Link",
    "E848B8": "TP-Link",
    "B09575": "TP-Link",
    "EC172F": "TP-Link",
    "7405A5": "Ruijie",
    "30DE4B": "TP-Link",
    "60A44C": "TP-Link",
    "7844FD": "TP-Link",
    "84D81B": "TP-Link",
    "984265": "TP-Link",
    "D46E0E": "TP-Link",
    "DC56E7": "TP-Link",
    # Hikvision
    "4419B6": "Hikvision",
    "BC5451": "Hikvision",
    "C42F90": "Hikvision",
    "0018AE": "Hikvision",
    "2857BE": "Hikvision",
    "601971": "Hikvision",
    "A41437": "Hikvision",
    "C056E3": "Hikvision",
    "DCB72E": "Hikvision",
    # Dahua
    "3CEF8C": "Dahua",
    "4C11BF": "Dahua",
    "E0508B": "Dahua",
    "9002A9": "Dahua",
    "A0BD1D": "Dahua",
    "B4A382": "Dahua",
    # Uniview (宇视)
    "48EA63": "Uniview",
    "282C02": "Uniview",
    # Apple
    "482C6A": "Apple",
    "F01898": "Apple",
    "ACBC32": "Apple",
    "000393": "Apple",
    "000A27": "Apple",
    "000A95": "Apple",
    "001124": "Apple",
    "001451": "Apple",
    "0016CB": "Apple",
    "18AF61": "Apple",
    "28CFDA": "Apple",
    "34159E": "Apple",
    "70CD60": "Apple",
    "784F43": "Apple",
    "8C8590": "Apple",
    "A483E7": "Apple",
    "BC9FEF": "Apple",
    "D89E3F": "Apple",
    "F4F15A": "Apple",
    # Xiaomi
    "6490C1": "Xiaomi",
    "7C49EB": "Xiaomi",
    "F0B429": "Xiaomi",
    "286C07": "Xiaomi",
    "3480B3": "Xiaomi",
    "508F4C": "Xiaomi",
    "5C0214": "Xiaomi",
    "7811DC": "Xiaomi",
    "8CBEBE": "Xiaomi",
    "9C99A0": "Xiaomi",
    "D4970B": "Xiaomi",
    # Intel
    "001E67": "Intel",
    "0013E8": "Intel",
    "3413E8": "Intel",
    "001500": "Intel",
    "001B21": "Intel",
    "080046": "Intel",
    "3C5282": "Intel",
    "4851B7": "Intel",
    "6805CA": "Intel",
    "8086F2": "Intel",
    # Dell
    "001422": "Dell",
    "F8DB88": "Dell",
    "1866DA": "Dell",
    "B8AC6F": "Dell",
    "D4BED9": "Dell",
    # HP / HPE / Aruba
    "001B78": "HP",
    "3CD92B": "HP",
    "002481": "HP",
    "10604B": "HP",
    "28924A": "HP",
    "000B86": "Aruba",
    "20A680": "Aruba",
    # Lenovo
    "005907": "Lenovo",
    "507B9D": "Lenovo",
    "7072CF": "Lenovo",
    "84A938": "Lenovo",
    # ZTE (中兴)
    "0019C6": "ZTE",
    "002293": "ZTE",
    "34DE1A": "ZTE",
    "68A0F6": "ZTE",
    "84742A": "ZTE",
    # Ubiquiti / UniFi
    "002722": "Ubiquiti",
    "24A43C": "Ubiquiti",
    "68D79A": "Ubiquiti",
    "788A20": "Ubiquiti",
    "B4FBE4": "Ubiquiti",
    "DC9FDB": "Ubiquiti",
    "F09FC2": "Ubiquiti",
    # MikroTik
    "000C42": "MikroTik",
    "488F5A": "MikroTik",
    "64D154": "MikroTik",
    "CC2DE0": "MikroTik",
    # Netgear
    "000FB5": "Netgear",
    "20E52A": "Netgear",
    "A00460": "Netgear",
    # Espressif (乐鑫 / IoT)
    "240AC4": "Espressif",
    "30AEA4": "Espressif",
    "84F3EB": "Espressif",
    "A4E57C": "Espressif",
    "C44F33": "Espressif",
    # Realtek
    "00E04C": "Realtek",
    "525400": "QEMU/KVM",
    # VMware
    "000569": "VMware",
    "000C29": "VMware",
    "005056": "VMware",
}


def normalize_mac(mac: Optional[str]) -> Optional[str]:
    """Normalize MAC address string into standard uppercase colon format: XX:XX:XX:XX:XX:XX.
    Returns None if the MAC is invalid.
    """
    if not mac or not isinstance(mac, str):
        return None

    # Strip whitespace
    cleaned = mac.strip()
    # Remove colons, hyphens, and dots
    hex_only = re.sub(r"[^0-9a-fA-F]", "", cleaned)

    if len(hex_only) != 12:
        return None

    hex_upper = hex_only.upper()
    return ":".join(hex_upper[i : i + 2] for i in range(0, 12, 2))


def lookup_vendor(mac: Optional[str]) -> str:
    """Lookup hardware vendor name from MAC address using built-in high frequency OUI dictionary.
    Returns '未知厂商' if not found or invalid.
    """
    normalized = normalize_mac(mac)
    if not normalized:
        return "未知厂商"

    prefix = normalized.replace(":", "")[:6]
    return OUI_VENDOR_MAP.get(prefix, "未知厂商")
