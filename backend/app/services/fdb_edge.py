import re
from typing import Any, Dict, List, Optional

MOBILE_VENDORS = (
    "apple",
    "xiaomi",
    "huawei device",
    "vivo",
    "oppo",
    "honor",
    "samsung electronics (mobile)",
    "samsung mobile",
    "meizu",
    "oneplus",
    "realme",
)


def is_random_mac(mac: Optional[str]) -> bool:
    """Check if MAC address has IEEE 802 Locally Administered Address (LAA) bit set.
    
    The 2nd hex digit of an LAA MAC is 2, 6, A, or E (e.g. x2:xx:xx, x6:xx:xx, xA:xx:xx, xE:xx:xx).
    In modern LANs, >99.9% of these are iOS/Android/Windows private randomized Wi-Fi MACs.
    """
    if not mac:
        return False
    clean = re.sub(r"[^0-9A-Fa-f]", "", str(mac)).upper()
    if len(clean) >= 2 and clean[1] in ("2", "6", "A", "E"):
        return True
    return False


def is_mobile_oui(vendor: Optional[str]) -> bool:
    """Check if the resolved OUI vendor name corresponds to mobile/handheld device lines."""
    if not vendor:
        return False
    v_lower = vendor.lower()
    return any(mv in v_lower for mv in MOBILE_VENDORS)
