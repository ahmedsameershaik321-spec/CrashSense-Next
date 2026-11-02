# CrashSense-Next

CrashSense is a protected video-analysis and incident-review application built
with Next.js, FastAPI, PostgreSQL, Alembic, YOLO, ByteTrack, and OpenCV.
Analysis classifications and confidence values are heuristic visual evidence,
not verified accident truth, severity assessments, or medical conclusions.
Emergency notification behavior is audit-only and never sends external alerts.

## Run the complete application with Docker Compose

Docker Engine and the Compose plugin are required. From the repository root:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and replace the database password, JWT secret, and initial
administrator password. Use a unique random JWT secret of at least 32
characters and an administrator password of at least 16 characters. URL-safe
random values avoid interpolation surprises in Compose. Generate a value with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Do not commit `.env`.

Build and start PostgreSQL, migrations, FastAPI, and Next.js:

```powershell
docker compose up --build -d
docker compose ps
```

Create the first administrator once the services are healthy:

```powershell
docker compose exec backend python -m app.bootstrap_admin
```

The bootstrap command refuses to overwrite an existing account or create a
second administrator. After bootstrap, remove `INITIAL_ADMIN_EMAIL` and
`INITIAL_ADMIN_PASSWORD` from `.env` and restart the backend to remove those
credentials from its environment.

Open `http://localhost:3000`. The Next.js server forwards `/backend-api/api/v1`
requests to FastAPI on the private Compose network. PostgreSQL and uploaded
videos use named persistent volumes. The backend health endpoint is available
at `http://localhost:8000/api/v1/health`, bound to loopback by default.

Stop services without deleting persistent data:

```powershell
docker compose down
```

Do not use `docker compose down -v` unless you intend to delete the database,
uploaded videos, and model cache.

## Local development

Use Python 3.11, Node.js 22, npm, and a running PostgreSQL instance. From the
repository root:

```powershell
Copy-Item backend\.env.example backend\.env
```

Edit `backend\.env` with local database credentials and a unique JWT secret.
Use a unique JWT secret of at least 32 characters and an initial administrator
password of at least 16 characters.
```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.bootstrap_admin
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

In another terminal:

```powershell
Set-Location frontend
Copy-Item .env.example .env.local
npm ci
npm run dev
```

The initial-admin bootstrap is intentionally an explicit one-time operation;
public registration always creates a pending, inactive account.

## Account and operational access

- Public registration cannot select a role and creates pending accounts.
- Pending and suspended accounts cannot access operator endpoints.
- Administrator endpoints enforce active administrator authorization on the
  server. The frontend administrator route and navigation are convenience
  controls only.
- Administrators can approve pending users as monitoring operators or
  administrators, change roles of active approved users, and suspend or
  reactivate approved accounts. The last active administrator cannot be
  deactivated or demoted, and administrators cannot suspend or change their
  own account role.
- Bearer access tokens remain in frontend memory. The protected video player
  uses a short-lived HttpOnly, SameSite=Strict cookie scoped to its media route.

## Video, analysis, location, and alerts

Operators can upload, browse, play, delete, analyze, and review protected
videos. Uploads are streamed to private storage, size-limited, signature
checked, assigned generated storage keys, and served through authorized
byte-range streaming. Analysis jobs and results are persisted in PostgreSQL.
The single-process worker runs within the FastAPI lifespan and recovers stale
jobs after restarts.

Administrators can register cameras and assign them to videos. Their
coordinates are an approximate scene-location proxy, not coordinates extracted
from the video or proof of an incident location. Nearby resource data and map
tiles use OpenStreetMap services and may be incomplete or out of date.

The candidate notification UI only records an acknowledged, idempotent audit
entry whose delivery status is constrained to `not_sent`. No notification
provider or emergency dispatch integration is configured.

## Configuration and production notes

- Backend settings are documented in `backend/.env.example`; deployment
  configuration uses the root `.env.example` for Compose.
- Production defaults to `DEBUG=false`. Configure explicit trusted browser
  origins with `CORS_ALLOWED_ORIGINS` when the browser calls FastAPI directly.
  The included Compose setup uses the same-origin Next.js proxy.
- Keep FastAPI and PostgreSQL private behind a TLS-terminating reverse proxy.
  The Compose port bindings are loopback-only by default.
- Database migrations run as a separate Compose service before the API starts.
  Back up PostgreSQL and the video volume together; they are not automatically
  replicated or backed up.
- The first YOLO model may download when analysis is run. The Compose model
  cache volume persists model assets. Outbound network access is needed for
  that initial download and OpenStreetMap resource lookups.
- CPU execution is the portable Compose default. GPU access requires a host
  NVIDIA container runtime and an explicitly configured Compose device
  reservation; `DETECTION_DEVICE=auto` does not expose a host GPU by itself.
- External emergency notifications are intentionally disabled.

## Validation

Frontend:

```powershell
Set-Location frontend
npm ci
npm test
npm run lint
npm run typecheck
npm run build
```

Backend:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m alembic heads
.\.venv\Scripts\python.exe -m alembic upgrade head
```

Repository patch check:

```powershell
Set-Location ..
git diff --check
```
