# Video Accident-Detection Pipeline

The backend analyzes uploaded videos asynchronously. Analysis jobs and sampled
detection results are persisted in PostgreSQL. A lifecycle-managed worker claims
queued jobs with `FOR UPDATE SKIP LOCKED`; this allows multiple backend
processes to share the queue without claiming the same job. Stale processing
jobs are re-queued after the configured lease period.

## Runtime setup

From `backend`, install a CPU build of PyTorch and the backend dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements.txt
```

For CUDA, install the matching `torch` and `torchvision` packages using the
official PyTorch installation selector for the host's CUDA and Python versions,
then install the backend requirements. Do not mix incompatible CUDA builds.

The default weights setting is `yolov8n.pt`. Ultralytics downloads those weights
on first model initialization if they are not in its cache and network access is
available. For offline deployments, provision the weights file and set
`DETECTION_MODEL_WEIGHTS` to its path. Missing packages, unavailable weights,
or model-load errors fail the analysis job; the pipeline never returns
substitute or simulated detections.
The `lap` dependency used by Ultralytics' ByteTrack implementation is installed
explicitly from `requirements.txt` to avoid runtime package auto-installation.

Configure `.env` or the process environment:

```dotenv
DETECTION_MODEL_WEIGHTS=yolov8n.pt
DETECTION_DEVICE=auto
DETECTION_CONFIDENCE_THRESHOLD=0.25
DETECTION_IOU_THRESHOLD=0.45
DETECTION_FRAME_INTERVAL_SECONDS=1.0
DETECTION_MAX_FRAME_DIMENSION=1280
DETECTION_MIN_CANDIDATE_OBSERVATIONS=2
DETECTION_MIN_VERIFIED_OBSERVATIONS=4
DETECTION_MIN_MOTION_EVENTS=2
DETECTION_INTERACTION_DISTANCE_RATIO=0.08
DETECTION_MIN_SPEED_PIXELS_PER_SECOND=12
DETECTION_STOP_SPEED_RATIO=0.2
DETECTION_WORKER_POLL_SECONDS=1
DETECTION_STALE_JOB_MINUTES=60
```

Apply the database migration and run the existing FastAPI application:

```powershell
alembic upgrade head
uvicorn app.main:app --reload
```

`DETECTION_DEVICE=auto` uses CUDA when available and otherwise selects CPU.
`cpu` forces CPU execution. Frame sampling and resizing limit image memory use;
the video itself is decoded sequentially. The default sampled evidence interval
is one second. Adjust the frame interval for the expected video duration and
available processing capacity.

## API

All routes require an active monitoring operator or administrator bearer token.
The existing server-side `require_operator` dependency protects every analysis
route.

Start analysis:

```http
POST /api/v1/videos/{video_id}/analysis
Authorization: Bearer <access-token>
```

Returns `202 Accepted` and a queued job representation. A second active job for
the same video returns `409 Conflict`.

Check status and progress:

```http
GET /api/v1/videos/analysis/{analysis_id}
Authorization: Bearer <access-token>
```

Retrieve candidates, sampled frame detections, or a combined paginated result:

```http
GET /api/v1/videos/analysis/{analysis_id}/candidates
GET /api/v1/videos/analysis/{analysis_id}/frames?offset=0&limit=100
GET /api/v1/videos/analysis/{analysis_id}/results?offset=0&limit=100
```

Cancel a queued job or request cancellation at the next sampled frame:

```http
DELETE /api/v1/videos/analysis/{analysis_id}
Authorization: Bearer <access-token>
```

Frame evidence contains timestamps, sampled frame dimensions, class labels,
detector confidence, bounding boxes, ByteTrack IDs, and approximate motion
measurements. It does not store video frame images. Candidate evidence
references point to sampled frame indexes/timestamps and can be aligned with
the protected video stream for playback.

## Candidate interpretation

YOLOv8 uses COCO classes for people, bicycles, cars, motorcycles, buses, and
trucks. Ultralytics ByteTrack supplies persistent IDs during a video's
processing run. Candidate detection uses repeated close interactions together
with abrupt deceleration or direction-change observations; bounding-box overlap
alone is insufficient. Interaction episodes are retained after they end and
evaluated alongside active episodes when candidate results are generated. A gap
between close observations ends an episode; a later interaction between the
same tracks is evaluated as a separate episode.

Candidate confidence is a heuristic evidence score, not a calibrated
probability. `suspected` indicates limited temporal evidence.
`verified_detection` means the configured multi-frame evidence thresholds were
met; it does not confirm a collision, injury, or physical severity. Operator
review remains required.

## Operational limits

The worker is in-process, with durable job state in PostgreSQL and database
locks for cross-process claiming. A process restart resumes queued jobs and
re-queues stale processing jobs after the configured age. Capacity scales with
backend worker processes and available CPU/GPU resources; this initial
implementation does not include distributed GPU scheduling or a dedicated
broker.

The current repository has no frontend source files. The authenticated API and
OpenAPI schema provide the integration contract for a future video timeline,
progress display, and evidence playback UI.
