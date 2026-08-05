import asyncio
from dataclasses import dataclass

try:
    from ping3.asyncio import async_ping
except ImportError:
    import ping3

    async def async_ping(host: str, timeout: float, unit: str) -> float | None:
        return await asyncio.to_thread(ping3.ping, host, timeout=timeout, unit=unit)

from app.config import settings
from app.models import Device, utcnow
from app.services.device_service import device_to_dict


@dataclass
class ProbeResult:
    status: str
    latency_ms: int | None = None


async def icmp_ping(host: str, timeout: float) -> int | None:
    try:
        latency = await async_ping(host, timeout=timeout, unit="ms")
    except Exception:
        return None
    if latency is None or latency is False:
        return None
    return int(round(latency))


async def tcp_probe(host: str, port: int, timeout: float) -> bool:
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=timeout
        )
        writer.close()
        await writer.wait_closed()
        return True
    except Exception:
        return False


async def probe_device(
    ip: str, port: int | None, ping_timeout: float, tcp_timeout: float
) -> ProbeResult:
    latency = await icmp_ping(ip, ping_timeout)
    if latency is None:
        return ProbeResult(status="offline")
    if port is not None:
        ok = await tcp_probe(ip, port, tcp_timeout)
        if not ok:
            return ProbeResult(status="warning", latency_ms=latency)
    return ProbeResult(status="online", latency_ms=latency)


async def run_inspection(db, devices: list[Device]) -> list[dict]:
    semaphore = asyncio.Semaphore(settings.ping_concurrency)

    async def check_one(device: Device) -> dict:
        async with semaphore:
            result = await probe_device(
                device.ip_address, device.port, settings.ping_timeout, settings.tcp_timeout
            )
        device.status = result.status
        device.latency_ms = result.latency_ms
        device.last_check = utcnow()
        return device_to_dict(device)

    results = await asyncio.gather(*(check_one(d) for d in devices))
    db.commit()
    return list(results)
