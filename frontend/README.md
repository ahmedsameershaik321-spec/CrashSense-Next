# CrashSense frontend

The frontend is a Next.js App Router application that consumes the existing
FastAPI API. It does not create backend auth or dashboard endpoints.

## Local setup

1. Start PostgreSQL and configure the backend environment in `backend/.env`.
2. From `backend`, run database migrations and the API:

   ```powershell
   .\.venv\Scripts\python.exe -m alembic upgrade head
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
   ```

   The analysis worker is started by the FastAPI application lifespan; there is
   no separate worker command for this setup.
3. From `frontend`, copy `.env.example` to `.env.local` and adjust the backend
   origin if needed:

   ```powershell
   Copy-Item .env.example .env.local
   npm install
   npm run dev
   ```

   Open `http://localhost:3000`.

The default `NEXT_PUBLIC_API_BASE_URL` uses a same-origin Next.js rewrite to
`CRASHSENSE_BACKEND_ORIGIN`, avoiding the need for browser CORS configuration
during local development. Set the origin to the backend host only (for example
`http://localhost:8000`); the rewrite adds `/api/v1`.

The upload limit shown in the browser is configured by
`NEXT_PUBLIC_MAX_VIDEO_UPLOAD_SIZE_MB` (default `100`) and should match the
backend's `MAX_VIDEO_UPLOAD_SIZE_MB`. The backend remains authoritative for
file size, extension, and container-signature checks.

## Authentication and access

- Login calls `POST /api/v1/auth/login`, then fetches the real profile from
  `GET /api/v1/auth/me`.
- Registration calls `POST /api/v1/auth/register` without a role field. The
  backend creates accounts as inactive `pending` users.
- Only active `monitoring_operator` and `administrator` profiles can enter the
  dashboard. The backend remains authoritative for every protected API request.
- The backend currently provides bearer JWTs but no refresh or logout endpoint.
  The frontend therefore keeps the token in memory only; reloading the page
  signs the user out rather than storing credentials in browser storage.
- `GET /api/v1/dashboard/summary` supplies the dashboard's authenticated video,
  analysis, candidate, worker-process, and recent-activity data. Recent activity
  is limited by the API; worker-process state does not establish model readiness.

## Video management API integration

The dashboard uses the existing protected API contract:

- `GET /api/v1/videos?limit=20&offset=0` returns a page of `VideoResponse` records.
- `POST /api/v1/videos/upload` accepts multipart form field `file` and returns
  the created video metadata.
- `GET /api/v1/videos/{video_id}` returns video metadata.
- `GET /api/v1/videos/{video_id}/stream` supports byte-range playback.
- `DELETE /api/v1/videos/{video_id}` returns `204`; active analysis conflicts
  return `409` and are shown without hiding the record.

The API currently has no search endpoint or total-count field. Search/status
filters therefore apply to the currently loaded server page, and the library
uses the API's offset pagination. Upload formats and the default size limit
mirror backend storage validation.

Native HTML video playback cannot attach a bearer header. The detail page
therefore exchanges the in-memory bearer with a same-origin Next.js route for a
short-lived (at most 15-minute), HttpOnly, SameSite=Strict cookie. The cookie is
scoped to `/api/videos`; the Next.js stream route forwards browser `Range`
headers and the bearer to the existing protected FastAPI stream endpoint. The
JWT is never placed in the stream URL, and logout clears the media cookie. The
FastAPI authorization dependency remains authoritative.

## Video analysis jobs

The video library and video details page use the existing protected analysis
job API:

- `POST /api/v1/videos/{video_id}/analysis` submits a job.
- `GET /api/v1/videos/analysis/{analysis_id}` reads its status and backend
  progress.

Queued and processing jobs are refreshed every 2.5 seconds while their panel is
mounted. Polling stops for completed, failed, and cancelled jobs, and also
stops when the user leaves the page. Retry is available for terminal jobs and
submits a new job through the same API; the backend prevents duplicate active
jobs and remains the authorization authority.

The API does not provide a per-video analysis-history list endpoint. The
frontend therefore stores up to 10 analysis IDs per user and video in
`localStorage`, then fetches each job's current status from the API when the
panel is reopened. No job status, progress, or credentials are treated as
browser-persisted truth; if the API cannot retrieve a saved ID, that job is
not shown as available history.

## Analysis history and candidate review

The Monitoring / Analysis history navigation lists up to 50 analysis IDs known
to the current browser and refreshes their status from the protected API.
Completed jobs link to `/dashboard/analysis/{analysis_id}` from the history
list and the video analysis panel.

The results page uses the existing endpoints:

- `GET /api/v1/videos/analysis/{analysis_id}` for current job status.
- `GET /api/v1/videos/analysis/{analysis_id}/results?offset=0&limit=100` for
  the analysis summary, ordered candidate records, and an initial frame page.
- `GET /api/v1/videos/analysis/{analysis_id}/frames?offset=0&limit=100` for
  sampled per-frame detection evidence and subsequent pages.
- `GET /api/v1/videos/{video_id}` for the associated filename and metadata.

Candidate classification, timestamps, track IDs, confidence scores, evidence
summaries, object labels, and event counts are shown from backend responses.
The confidence score is presented as a heuristic score, not a probability.
Candidate responses also include pipeline event state, accident category,
severity, assessment reasoning, missing information, and human-review
requirements. Current assessments report `UNKNOWN` category and severity with
unavailable classification/severity confidence; the interface displays those
values rather than inferring them. `verified_detection` is treated as a pipeline
review flag, not as human confirmation, a confirmed collision, injury, or
medical finding. Reported processing time and throughput are shown when
available; model readiness is not reported by the API.

The backend has no server-side incident record lifecycle, confirmation or
rejection workflow, incident-specific coordinates, incident severity
distribution, historical incident reports, or user-preferences endpoint. The
analysis-review page is therefore a candidate/evidence review of analysis jobs,
not a global incident-management system. History IDs are browser-local, and a
registered camera coordinate remains a scene-location proxy.

The frame endpoint returns JSON metadata (sampled timestamps, dimensions, and
detections with tracks and bounding boxes), not still-image bytes or frame
URLs. The evidence viewer displays those records and uses the existing
protected, range-enabled video stream to seek to the selected sampled
timestamp. If the video or stream is unavailable, the returned candidate and
frame metadata remain reviewable and the playback failure is shown explicitly.

## Location, nearby resources, and notification audit

The analysis results page can display the actual registered camera coordinates
assigned to its video and the nearby resource records returned by the backend.
The map uses Leaflet with OpenStreetMap tiles and attribution. A camera
coordinate is only a scene-location proxy; CrashSense does not extract GPS from
the video or claim that the camera is the incident's precise point of impact.
Nearby hospitals, clinics, ambulance stations, and fire stations come from the
configured Overpass API and are ordered by backend-calculated distance from the
camera. OpenStreetMap coverage can be incomplete or stale, so this information
is for reference and is not dispatch guidance.

Administrators can register a camera and assign or remove it from a video.
Camera names, addresses, and valid latitude/longitude coordinates are stored by
the backend. Active operators can view a video's camera location and request
nearby resources; backend authorization remains authoritative. The lookup sends
the camera coordinates to the configured public Overpass service, and map tile
requests disclose the viewed region to OpenStreetMap tile servers. The default
Overpass endpoint and bounded request timeout are controlled by
`OSM_OVERPASS_URL` and `OSM_OVERPASS_TIMEOUT_SECONDS`.

The corresponding FastAPI routes are `GET /api/v1/cameras`,
`POST /api/v1/cameras` (administrator only),
`PUT /api/v1/videos/{video_id}/camera` (administrator only),
`GET /api/v1/videos/{video_id}/location`, and
`GET /api/v1/videos/{video_id}/resources`. Operator-protected audit routes are
`GET` and `POST /api/v1/videos/analysis/{analysis_id}/alerts`; the POST only
accepts a candidate from completed analysis and records an idempotent
`not_sent` result.

The notification panel is intentionally **audit-only**. An operator must
explicitly acknowledge that recording an entry will not send anything. The
backend writes an idempotent record whose delivery state is always
`not_sent`; there is no provider integration, emergency contact list, dispatch,
or claim of delivery. The panel displays the backend's audit result and errors.
No injury severity or contact data is inferred.

## Checks

```powershell
npm test
npm run lint
npm run typecheck
npm run build
```
