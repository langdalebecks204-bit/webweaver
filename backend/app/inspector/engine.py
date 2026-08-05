import asyncio
import socket
from dataclasses import dataclass

try:
    from ping3.asyncio import async_ping
except ImportError:
    import ping3

    async def async_ping(host: str, timeout: float, unit: str) -> float | None:
        return await asyncio.to_thread(ping3.ping, host, timeout=timeout, unit=unit)

from app.config import settings
from app.models import Device, ExternalTarget, utcnow
from app.services.device_service import device_to_dict
from app.services.external_service import external_target_to_dict


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


async def resolve_domain(domain: str) -> str | None:
    loop = asyncio.get_running_loop()
    try:
        infos = await asyncio.wait_for(
            loop.getaddrinfo(domain, None), timeout=settings.ping_timeout
        )
    except Exception:
        return None
    fallback = None
    for info in infos:
        ip = info[4][0] if info[4] else None
        if not ip:
            continue
        if info[0] == socket.AF_INET:
            return ip
        if fallback is None:
            fallback = ip
    return fallback


async def run_external_inspection(db, targets: list[ExternalTarget]) -> list[dict]:
    semaphore = asyncio.Semaphore(settings.ping_concurrency)

    async def check_one(target: ExternalTarget) -> dict:
        async with semaphore:
            if target.ip_address:
                result = await probe_device(
                    target.ip_address, target.port, settings.ping_timeout, settings.tcp_timeout
                )
                target.ip_status = result.status
                target.ip_latency_ms = result.latency_ms
                target.ip_last_check = utcnow()
            if target.domain:
                ip = await resolve_domain(target.domain)
                if ip is None:
                    target.domain_status = "offline"
                    target.domain_latency_ms = None
                else:
                    result = await probe_device(
                        ip, target.port, settings.ping_timeout, settings.tcp_timeout
                    )
                    target.domain_status = result.status
                    target.domain_latency_ms = result.latency_ms
                target.domain_last_check = utcnow()
        return external_target_to_dict(target)

    results = await asyncio.gather(*(check_one(t) for t in targets))
    db.commit()
    return list(results)
