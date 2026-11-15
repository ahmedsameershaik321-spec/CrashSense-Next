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
The repository checkpoint metadata identifies `yolov8n.pt` as a COCO object
detector with person, bicycle, car, motorcycle, bus, and truck classes. It is
not an accident classifier. At startup, the detector selects road-user classes
from the configured model's own class names and rejects a model with no
supported classes rather than silently applying COCO class IDs to another
model.
The `lap` dependency used by Ultralytics' ByteTrack implementation is installed
explicitly from `requirements.txt` to avoid runtime package auto-installation.

Configure `.env` or the process environment:

```dotenv
DETECTION_MODEL_WEIGHTS=yolov8n.pt
DETECTION_DEVICE=auto
ACCIDENT_CLASSIFIER_WEIGHTS=
ACCIDENT_CLASSIFIER_FRAME_INTERVAL_SECONDS=0.1
ACCIDENT_CLASSIFIER_NORMAL_THRESHOLD=
ACCIDENT_CLASSIFIER_ACCIDENT_THRESHOLD=
DETECTION_CONFIDENCE_THRESHOLD=0.25
DETECTION_IOU_THRESHOLD=0.45
DETECTION_IMAGE_SIZE=640
DETECTION_FRAME_INTERVAL_SECONDS=1.0
DETECTION_MAX_FRAME_DIMENSION=1280
DETECTION_MIN_CANDIDATE_OBSERVATIONS=2
DETECTION_MIN_VERIFIED_OBSERVATIONS=4
DETECTION_MIN_VERIFIED_DURATION_SECONDS=2.0
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
available processing capacity. The reported duration includes model
initialization; the model is cached per process and device for later jobs.

## Accident classifier status

The separate temporal CNN is disabled unless
`ACCIDENT_CLASSIFIER_WEIGHTS` points to a compatible trained checkpoint. With
no checkpoint, every result reports `UNKNOWN` and
`weights_not_configured`; YOLO object detections and heuristic candidates still
run independently. A configured checkpoint that is missing or incompatible
fails the analysis job rather than returning a successful-looking result.
Classifier checkpoints contain their architecture, `NORMAL: 0` /
`ACCIDENT: 1` mapping, and validation-selected thresholds. Optional threshold
environment variables override the stored values and must satisfy
`0 <= normal < accident <= 1`.

The classifier uses 50 samples at the configured interval per temporal window,
then selects 16 frames at 112x112 for inference. Its softmax scores are
unvalidated and uncalibrated; they are not accuracy or confidence claims.
Results include `ACCIDENT`, `NORMAL`, or `UNKNOWN`, raw scores, window evidence,
and `human_review_required: true`. `ACCIDENT` is a review candidate, not a
confirmed incident. A partial trailing window or uncertain score yields
`UNKNOWN`. A fully evaluated video whose windows all meet the normal threshold
can return `NORMAL`; this is not proof that no accident occurred.
When enabled, frames are decoded at the tighter classifier cadence while YOLO
tracking retains the existing detection cadence. This sampling trade-off is
explicitly configured and classifier inference timing is reported separately.
No trained classifier currently exists; do not set a fabricated checkpoint.
For Compose deployments, keep an authorized checkpoint in the git-ignored
repository `weights/` directory and set
`ACCIDENT_CLASSIFIER_WEIGHTS=/app/weights/<checkpoint>.pth` in the root `.env`.
The mount is read-only and optional classification stays disabled when the
setting is blank.

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
met; it does not confirm a collision, injury, or physical severity. The
interaction must also span the configured minimum duration. The additive
`event_state` is `suspected` or `needs_review`; the pipeline never marks an
accident confirmed. Accident category and severity are `UNKNOWN` with null
confidence until suitable accident-specific evidence and validation exist.
Each candidate explains the missing information and requires human review.
Proximity, stopping, and generic YOLO confidence are not used as severity
evidence.

The analysis summary reports measured processing seconds and YOLO detection
frames per second for each run. When classification is enabled, its sampled
frame and model-inference counts are reported separately. These are
workload-specific measurements, not hardware benchmarks.

## Evaluation limitations

The repository includes `test-videos/accident-test.mp4` and
`test-videos/normal-traffic.mp4`, but no frame-level event annotations or
ground-truth labels. They cannot support defensible precision, recall, F1,
false-positive rate, classification performance, or severity performance
claims. The unit suite uses deterministic mocked detections; actual video
inference must be evaluated against independently labeled footage before
production use. Sudden braking, congestion, camera motion, occlusion, and
brief events between sampled frames remain known sources of uncertainty.

## CCD dataset status

The [official CCD repository](https://github.com/Cogito2012/CarCrashDataset)
documents 1,500 trimmed crash clips from YouTube and 3,000 normal clips sampled
from BDD100K. It describes 50 frames at 10 fps per clip and a
`Crash-1500.txt` annotation with 50 binary frame labels per crash clip (`1`
means an accident frame), plus source YouTube ID and scene attributes. The
provided feature files contain detector-produced boxes, not ground-truth
bounding-box annotations.

The repository's [MIT license](https://github.com/Cogito2012/CarCrashDataset/blob/master/LICENSE)
covers its software and documentation; the repository states no license or
usage permission for the videos. Its README links the files on Google Drive and
lists `wb6219@rit.edu` for questions, but no permission has been obtained.
The GitHub issue tracker is disabled. Do not download or use CCD for training
until the relevant rights holders provide written permission for the source
videos, model training, and derived weights. This must cover both YouTube crash
clips and BDD100K normal clips; BDD100K's terms could not be verified during
this review. The README does not specify the annotation file's exact delimiter
or encoding, nor a mapping from numbered normal clips to original BDD100K
video IDs. Those remain unverified without authorized access to the archive
and its metadata.

After authorization, prepare a verified CSV manifest with columns
`video_path,label,source_dataset,source_video_id,frame_labels`. Use
`ACCIDENT` or `NORMAL` labels verified from the annotations; crash rows need
exactly 50 binary frame labels containing at least one `1`, and normal rows
must have an empty `frame_labels` field. Include the original YouTube or
BDD100K source-video ID. Do not substitute clip filenames for missing source
IDs or reuse the repository's train/test split without checking source overlap.
The standard-library preparation script requires a non-empty written
permission-record path, validates paths, required source IDs, labels, frame
annotations, and exact duplicate file hashes, then assigns deterministic
source-grouped 70/15/15 train/validation/test splits:

```powershell
python backend\scripts\prepare_ccd_splits.py `
  --dataset-root datasets\ccd `
  --manifest datasets\ccd\verified_manifest.csv `
  --output datasets\ccd\splits.csv `
  --permission-record datasets\ccd\written_video_use_permission.txt `
  --confirm-authorized-use `
  --seed 2026
```

The permission-record file is an operator attestation, not legal verification;
its presence alone does not establish authorization. This script does not parse
the source annotation file, verify video rights, detect re-encoded visual
duplicates, or train a model. Do not run it on CCD data until the usage
permission is resolved and the manifest has been verified.

The training and evaluation entry points re-check the split manifest, original
source isolation, frame labels, exact file hashes, and permission-record
presence. They also require the explicit `--confirm-authorized-use` flag.
Training reads only the train and validation videos, selects a checkpoint and
thresholds using validation F1/coverage, and never opens test video content.
Evaluation reads the held-out test split without tuning thresholds and writes
the confusion matrix, precision, recall, F1, false-positive/negative rates,
coverage, and end-to-end videos per second:

```powershell
Set-Location backend
.\.venv\Scripts\python.exe -m scripts.train_accident_classifier `
  --dataset-root ..\datasets\ccd `
  --manifest ..\datasets\ccd\splits.csv `
  --permission-record ..\datasets\ccd\written_video_use_permission.txt `
  --confirm-authorized-use `
  --output ..\datasets\ccd\models\accident-classifier.pth `
  --device auto

.\.venv\Scripts\python.exe -m scripts.evaluate_accident_classifier `
  --dataset-root ..\datasets\ccd `
  --manifest ..\datasets\ccd\splits.csv `
  --permission-record ..\datasets\ccd\written_video_use_permission.txt `
  --confirm-authorized-use `
  --weights ..\datasets\ccd\models\accident-classifier.pth `
  --output ..\datasets\ccd\evaluation\held-out-test.json `
  --device auto
```

The current architecture uses an ImageNet-pretrained MobileNetV3-Small spatial
backbone with a temporal convolutional head. The classification head is
fine-tuned from the authorized train split, and no accident checkpoint has
been trained or independently validated. Treat output as experimental and
human-review-only even after a local training run. Keep `datasets/`,
checkpoints, and generated reports out of Git.

## Operational limits

The worker is in-process, with durable job state in PostgreSQL and database
locks for cross-process claiming. A process restart resumes queued jobs and
re-queues stale processing jobs after the configured age. Capacity scales with
backend worker processes and available CPU/GPU resources; this initial
implementation does not include distributed GPU scheduling or a dedicated
broker.

The frontend displays the classifier state alongside heuristic candidate
evidence. Historical results without classifier metadata remain supported and
are shown as not reported; no UI derives accident truth from YOLO detections.
