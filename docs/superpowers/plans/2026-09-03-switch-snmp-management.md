# Switch SNMP Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add switch SNMP management capability to WebWeaver, displaying port status (Up/Down) and real-time in/out bandwidth.

**Architecture:** Extend FastAPI backend with an SNMP client service (IF-MIB polling) and real-time bandwidth calculation. Enhance Vue 3 frontend with a switch port matrix modal, interface metrics table, and real-time ECharts bandwidth graph.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Vue 3, Element Plus, ECharts.

## Global Constraints

- Backend tests must run with `pytest tests -v`
- Frontend code must fit existing Vue 3 + Element Plus standards
- Backward compatibility for non-switch devices must be maintained

---

### Task 1: Database Model & Schema Extension

**Files:**
- Modify: `backend/app/models.py:13-37`
- Modify: `backend/app/schemas.py:20-45`
- Test: `backend/tests/test_models.py`

**Interfaces:**
- Consumes: Existing `Device` SQLAlchemy model
- Produces: `snmp_community`, `snmp_version`, `snmp_port` columns on `Device`

- [ ] **Step 1: Write failing model test for SNMP fields**

```python
# backend/tests/test_models.py
def test_device_snmp_fields(db_session):
    from app.models import Device
    device = Device(
        name="Test Switch",
        type="switch",
        ip_address="172.16.2.26",
        snmp_community="public",
        snmp_version="v2c",
        snmp_port=161
    )
    db_session.add(device)
    db_session.commit()
    
    saved = db_session.query(Device).filter_by(name="Test Switch").first()
    assert saved.snmp_community == "public"
    assert saved.snmp_version == "v2c"
    assert saved.snmp_port == 161
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_models.py -v`
Expected: FAIL due to missing attributes on `Device`

- [ ] **Step 3: Update Device model & schemas**

Modify `backend/app/models.py`:
```python
    snmp_community: Mapped[str | None] = mapped_column(String(50), nullable=True, default="public")
    snmp_version: Mapped[str | None] = mapped_column(String(10), nullable=True, default="v2c")
    snmp_port: Mapped[int | None] = mapped_column(Integer, nullable=True, default=161)
```

Modify `backend/app/schemas.py`:
```python
class DeviceBase(BaseModel):
    ...
    snmp_community: Optional[str] = "public"
    snmp_version: Optional[str] = "v2c"
    snmp_port: Optional[int] = 161
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/models.py backend/app/schemas.py backend/tests/test_models.py
git commit -m "feat(backend): add snmp configuration fields to Device model"
```

---

### Task 2: Backend SNMP Service & Real-Time Bandwidth Engine

**Files:**
- Create: `backend/app/services/snmp.py`
- Test: `backend/tests/test_snmp_service.py`

**Interfaces:**
- Consumes: Device IP, SNMP port, community, version
- Produces: `get_switch_interfaces(ip, community, port, version)` returning a list of dicts with `if_index`, `if_name`, `status` ('up'/'down'), `speed_mbps`, `in_rate_bps`, `out_rate_bps`

- [ ] **Step 1: Write failing test for SNMP Service with mock socket data**

```python
# backend/tests/test_snmp_service.py
from unittest.mock import patch
from app.services.snmp import get_switch_interfaces, calculate_bandwidth

def test_calculate_bandwidth():
    # 100,000 bytes over 5 seconds = 20,000 Bps = 160,000 bps = 160 Kbps
    rate = calculate_bandwidth(prev_bytes=1000, curr_bytes=101000, time_delta_sec=5.0)
    assert rate == 160000.0

def test_calculate_bandwidth_counter_overflow():
    # 32-bit counter overflow handling
    rate = calculate_bandwidth(prev_bytes=4294960000, curr_bytes=10000, time_delta_sec=5.0, max_bytes=2**32)
    assert rate > 0
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_snmp_service.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `app/services/snmp.py`**

Implement robust SNMP IF-MIB helper using standard library socket or pure Python SNMP PDU encoder/decoder to query OIDs:
- `1.3.6.1.2.1.2.2.1.2` (ifDescr / ifName)
- `1.3.6.1.2.1.2.2.1.8` (ifOperStatus)
- `1.3.6.1.2.1.2.2.1.5` (ifSpeed)
- `1.3.6.1.2.1.31.1.1.1.6` (ifHCInOctets) & `1.3.6.1.2.1.31.1.1.1.10` (ifHCOutOctets)

Maintain an in-memory cache `{ (device_id, if_index): (timestamp, in_bytes, out_bytes) }` to calculate real-time Bps rates.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_snmp_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/snmp.py backend/tests/test_snmp_service.py
git commit -m "feat(backend): implement SNMP IF-MIB polling and bandwidth calculation service"
```

---

### Task 3: Backend FastAPI Router Endpoint for Switch Interfaces

**Files:**
- Modify: `backend/app/routers/devices.py`
- Test: `backend/tests/test_device_snmp_api.py`

**Interfaces:**
- Consumes: `GET /api/devices/{id}/snmp/interfaces`
- Produces: JSON response `{ "device_id": 1, "interfaces": [...], "timestamp": "..." }`

- [ ] **Step 1: Write failing test for Device SNMP API**

```python
# backend/tests/test_device_snmp_api.py
def test_get_device_snmp_interfaces_not_switch(client, auth_headers, test_device):
    # test_device type is 'group' or 'server'
    resp = client.get(f"/api/devices/{test_device.id}/snmp/interfaces", headers=auth_headers)
    assert resp.status_code == 400
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_device_snmp_api.py -v`
Expected: FAIL with 440 / 404

- [ ] **Step 3: Implement API endpoint in `backend/app/routers/devices.py`**

```python
@router.get("/{device_id}/snmp/interfaces")
def get_device_snmp_interfaces(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")
    if device.type != "switch":
        raise HTTPException(status_code=400, detail="Device is not a switch")
    if not device.ip_address:
        raise HTTPException(status_code=400, detail="Switch IP address not configured")
        
    interfaces = get_switch_interfaces(
        device_id=device.id,
        ip=device.ip_address,
        community=device.snmp_community or "public",
        port=device.snmp_port or 161,
        version=device.snmp_version or "v2c"
    )
    return {"device_id": device.id, "interfaces": interfaces, "timestamp": datetime.now(timezone.utc).isoformat()}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_device_snmp_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/devices.py backend/tests/test_device_snmp_api.py
git commit -m "feat(backend): expose GET /api/devices/{id}/snmp/interfaces endpoint"
```

---

### Task 4: Frontend Switch Panel & Real-Time Bandwidth UI

**Files:**
- Create: `frontend/src/components/SwitchPanel.vue`
- Create: `frontend/src/components/SwitchPortsModal.vue`
- Modify: `frontend/src/api/devices.js`
- Modify: `frontend/src/components/DeviceFormModal.vue`
- Modify: `frontend/src/views/DevicesView.vue`

- [ ] **Step 1: Add frontend API method**

In `frontend/src/api/devices.js`:
```javascript
export function getDeviceSnmpInterfaces(id) {
  return request({
    url: `/devices/${id}/snmp/interfaces`,
    method: 'get'
  })
}
```

- [ ] **Step 2: Build `SwitchPanel.vue` and `SwitchPortsModal.vue` components**
- `SwitchPanel.vue`: RJ45 Ethernet port matrix (shows 8/16/24/48 ports, green LED for Up, gray LED for Down, tooltip with speed & bandwidth).
- `SwitchPortsModal.vue`: Dialog with auto-refresh toggle, interface table, and ECharts line graph showing In/Out Mbps over time.

- [ ] **Step 3: Integrate with Device Views**
- Update `DeviceFormModal.vue` to allow configuring `SNMP Community`, `SNMP Port`, and `SNMP Version` when device type is `switch`.
- Update `DevicesView.vue` right-click tree menu & detail header to add "Switch Ports & Bandwidth (SNMP)" button.

- [ ] **Step 4: Manual & Automated Frontend Verification**
Run `npm run build` or dev server to verify Vue components compile without errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/SwitchPanel.vue frontend/src/components/SwitchPortsModal.vue frontend/src/api/devices.js frontend/src/components/DeviceFormModal.vue frontend/src/views/DevicesView.vue
git commit -m "feat(frontend): add switch port matrix panel and real-time bandwidth modal"
```
