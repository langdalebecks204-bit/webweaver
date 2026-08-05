import pytest

from app.database import SessionLocal, init_db
from app.inspector.engine import ProbeResult, probe_device, run_inspection
from app.models import Device


@pytest.fixture()
def db():
    init_db()
    with SessionLocal() as session:
        yield session


async def test_probe_online(monkeypatch):
    async def fake_icmp(host, timeout):
        return 12

    async def fake_tcp(host, port, timeout):
        return True

    monkeypatch.setattr("app.inspector.engine.icmp_ping", fake_icmp)
    monkeypatch.setattr("app.inspector.engine.tcp_probe", fake_tcp)
    result = await probe_device("10.0.0.1", 443, 1.0, 2.0)
    assert result == ProbeResult(status="online", latency_ms=12)


async def test_probe_warning_when_port_fails(monkeypatch):
    async def fake_icmp(host, timeout):
        return 12

    async def fake_tcp(host, port, timeout):
        return False

    monkeypatch.setattr("app.inspector.engine.icmp_ping", fake_icmp)
    monkeypatch.setattr("app.inspector.engine.tcp_probe", fake_tcp)
    result = await probe_device("10.0.0.1", 443, 1.0, 2.0)
    assert result == ProbeResult(status="warning", latency_ms=12)


async def test_probe_offline_when_ping_times_out(monkeypatch):
    async def fake_icmp(host, timeout):
        return None

    monkeypatch.setattr("app.inspector.engine.icmp_ping", fake_icmp)
    result = await probe_device("10.0.0.1", None, 1.0, 2.0)
    assert result == ProbeResult(status="offline", latency_ms=None)


async def test_run_inspection_updates_db(monkeypatch, db):
    dev = Device(name="sw", type="switch", ip_address="10.0.0.1", port=22)
    db.add(dev)
    db.commit()

    async def fake_probe(ip, port, ping_timeout, tcp_timeout):
        return ProbeResult(status="online", latency_ms=8)

    monkeypatch.setattr("app.inspector.engine.probe_device", fake_probe)
    results = await run_inspection(db, [dev])
    assert results[0]["status"] == "online"
    assert results[0]["latency_ms"] == 8
    assert dev.last_check is not None