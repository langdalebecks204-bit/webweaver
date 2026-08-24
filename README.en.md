[中文](README.md) | English

# WebWeaver (织网)

A tree-structured, automated network status monitoring platform. The backend probes devices on a schedule or on demand (ICMP ping + optional TCP port checks); the frontend shows the device hierarchy and live status as a tree, with probe history and hourly/daily average latency charts.

## Tech Stack

- Backend: Python 3.12 / FastAPI / SQLAlchemy 2 / APScheduler / ping3 / PyJWT / bcrypt
- Frontend: Vue 3 / Vite / Element Plus / Pinia / axios / ECharts
- Database: SQLite (persisted to a volume inside the single container)

## Quick Start (Local Development)

### 1. Start the backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Linux: source .venv/bin/activate
python -m pip install -r requirements-dev.txt
copy .env.example .env              # Linux: cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Default admin: `admin` / `admin123` (change `WEAVER_DEFAULT_ADMIN_PASSWORD` in `.env`).

### 2. Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and log in with the default account.

## Docker Deployment

A single multi-arch image (linux/amd64 + linux/arm64) is published to GitHub Container Registry (`ghcr.io/langdalebecks204-bit/webweaver`). First deployment:

```bash
docker run -d --name weaver \
  -p 8000:8000 \
  --cap-add=NET_RAW \
  -v webweaver-data:/data \
  -e WEAVER_JWT_SECRET=change-me-to-a-long-random-string \
  ghcr.io/langdalebecks204-bit/webweaver:latest
```

- `--cap-add=NET_RAW`: required for ICMP ping (without it only TCP probing works).
- `-v webweaver-data:/data`: persists the SQLite database; data survives container recreation.
- On first start a default admin `admin` / `admin123` is created (make sure to change it via `WEAVER_DEFAULT_ADMIN_PASSWORD` in production).
- Frontend static assets are bundled into the image; just open http://\<host\>:8000 in a browser.

You can also use `docker compose up -d` (see `docker-compose.yml` in the repo; env reference in `compose.env.example`).

### Upgrading

```bash
# Pinned tag (recommended)
docker pull ghcr.io/langdalebecks204-bit/webweaver:0.4.13
docker rm -f weaver
docker run -d --name weaver \
  -p 8000:8000 \
  --cap-add=NET_RAW \
  -v webweaver-data:/data \
  -e WEAVER_JWT_SECRET=change-me-to-a-long-random-string \
  ghcr.io/langdalebecks204-bit/webweaver:0.4.13

# Or with compose
docker compose pull
docker compose up -d
```

- Data lives in the `webweaver-data:/data` volume; removing and recreating the container does **not** lose data.
- After an upgrade, new tables (e.g. probe history) are created automatically at startup; no manual migration is needed.
- Rollback: repeat the steps with an older image tag (e.g. `0.1.0`).

## Monitoring Notes

- The scheduler probes every 5 minutes by default (`WEAVER_POLL_INTERVAL_MINUTES`; adjustable on the devices page in the UI).
- Status rules: ping OK → `online`; ping OK but TCP port fails → `warning`; ping fails → `offline`; not probed yet → `unknown`.
- Each probe writes one history record (status + latency) for every node that has an IP.
- Right-click a tree node to: add child / add sibling / edit / probe now / **view history (nodes with IP)** / delete.
- "View history" opens an average-latency bar chart with hourly/daily granularity over the last 1/7/30 days.
- History is kept for 30 days by default and cleaned up automatically (`WEAVER_PROBE_HISTORY_DAYS`, 1-365).
- The device tree supports horizontal scrolling on mobile for deeply nested levels.
- Devices support image upload (top-right of the detail view), auto-compressed to a max edge of 1600px and ≤300KB.
- Uploads larger than 30MB are rejected; the previous image is kept if processing a new upload fails.
- The topology page offers an in-page fullscreen mode (Fullscreen API) with a back-to-home link; node positions survive hover and polling refreshes and can be rearranged by dragging; nodes render as larger circles with device-type icons.

### Memory Requirements

- Verified on devices with **512MB RAM and above**, including uploading and thumbnailing a 48MP (~8000x6000) phone photo.
- Image upload is **untested below 512MB RAM** — please verify on your own hardware. Peak memory comes from the decode stage; images are downsampled before decoding to reduce the peak.

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -v

cd frontend
npm run test
```

## Environment Variables (see backend/.env.example)

| Variable | Default | Description |
|---|---|---|
| WEAVER_DB_URL | sqlite:///./weaver.db | SQLAlchemy connection string (`sqlite:////data/weaver.db` inside the container) |
| WEAVER_JWT_SECRET | dev-secret-change-me | JWT signing secret (must change in production) |
| WEAVER_TOKEN_EXPIRE_MINUTES | 480 | Token lifetime in minutes |
| WEAVER_POLL_INTERVAL_MINUTES | 5 | Probe interval in minutes |
| WEAVER_PING_CONCURRENCY | 100 | Max concurrent probes |
| WEAVER_PING_TIMEOUT | 1.0 | ICMP timeout in seconds |
| WEAVER_TCP_TIMEOUT | 2.0 | TCP probe timeout in seconds |
| WEAVER_DEFAULT_ADMIN | admin | Default admin created on first start |
| WEAVER_DEFAULT_ADMIN_PASSWORD | admin123 | Default admin password (must change in production) |
| WEAVER_ENABLE_SCHEDULER | true | Enable scheduled probing |
| WEAVER_PROBE_HISTORY_DAYS | 30 | Probe history retention in days (1-365) |
| WEAVER_FRONTEND_DIR | /app/frontend/dist | Frontend static assets directory (container default is fine) |

## API Overview

- `POST /api/auth/login` — log in and get a JWT
- `GET /api/auth/me` — current user
- `GET /api/devices/tree` — device tree (nested JSON)
- `GET|POST /api/devices` — list / create (admin)
- `PUT|DELETE /api/devices/{id}` — update / delete (admin, deletes subtree recursively)
- `POST /api/devices/{id}/recheck` — probe now (including subtree)
- `GET /api/devices/{id}/history?days=7` — probe history (any logged-in user)
- `GET /api/settings/inspection-interval` — probe interval (admin)
- `GET|PUT /api/settings/probe-history-days` — history retention days (admin)
- `GET|POST|PUT|DELETE /api/users` — user management (admin)
- `GET|POST /api/external` — external targets (admin)
- `GET|PUT /api/backup` — backup & restore (admin)

## Roadmap (Phase 3)

WebSocket live status push, MySQL support, packet-loss statistics.
