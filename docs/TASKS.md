
# CrashSense — Development Tracker

Project: CrashSense
Repository: CrashSense-Next
Primary Branch: main
Status: Operator and administrator workflows implemented; deployment configuration prepared

## DEVELOPMENT RULES

1. Follow docs/ARCHITECTURE.md.
2. Never rewrite the entire project without authorization.
3. Implement one feature at a time.
4. Write tests for every feature.
5. Never bypass authentication or authorization.
6. Never commit secrets, API keys or passwords.
7. Never grant operational roles through public registration.
8. Never delete existing working functionality without approval.
9. Review existing files before modifying them.
10. Update this tracker after completing a task.

## PHASE 1 — FOUNDATION

- [ ] Establish project architecture.
- [ ] Configure Git and GitHub.
- [x] Create frontend project.
- [ ] Create backend project.
- [ ] Create ML engine project.
- [ ] Configure environment variables.
- [ ] Configure dependency management.
- [ ] Configure development documentation.

## PHASE 2 — BACKEND

- [ ] Configure FastAPI.
- [ ] Configure PostgreSQL.
- [ ] Configure SQLAlchemy.
- [ ] Configure Alembic.
- [ ] Implement centralized configuration.
- [x] Implement error handling.
- [x] Implement database-aware health check endpoint.
- [x] Implement API versioning.

## PHASE 3 — AUTHENTICATION AND SECURITY

- [x] User registration with pending-only role assignment.
- [x] Secure password hashing.
- [x] User login.
- [x] JWT authentication.
- [ ] Refresh token strategy.
- [x] Role-based access control.
- [x] Pending user approval.
- [x] Administrator role management.
- [x] Audit-only emergency alert history (external delivery disabled).
- [x] Authorization tests.

## PHASE 4 — FRONTEND

- [x] Initialize Next.js.
- [x] Configure TypeScript.
- [x] Configure Tailwind CSS.
- [ ] Configure shadcn/ui.
- [x] Design application layout.
- [x] Build login and registration pages.
- [x] Add accessible password visibility controls to login and registration.
- [x] Build dashboard overview.
- [x] Add authenticated dashboard aggregates and recent analysis activity.
- [x] Integrate frontend authentication with existing backend endpoints.
- [x] Build protected video library, upload, details, playback, and deletion UI.
- [x] Report upload success independently from video-library refresh failures.
- [x] Integrate background analysis job submission, status polling, and history reopening.
- [x] Build analysis result and incident review dashboard with sampled evidence.
- [x] Add camera-location, nearby-resource, and audit-only alert panels to incident review.
- [x] Build operator video, analysis, and incident review workflows.
- [x] Build administrator user-management dashboard.
- [ ] Build incident management interface.
- [ ] Build analytics interface.
- [x] Integrate implemented frontend workflows with backend APIs.

The current review UI operates on analysis candidates and sampled evidence. It
does not complete incident management: the backend has no server-side incident
records, confirmation/rejection workflow, incident-specific coordinates, or
incident analytics endpoints. Keep those items pending rather than presenting
candidate detections as confirmed incidents.

## PHASE 5 — VIDEO MANAGEMENT

- [x] Camera registration.
- [x] Camera metadata management.
- [x] Video upload.
- [x] Video validation.
- [x] Video storage.
- [x] Protected video streaming with HTTP byte-range support.
- [x] Persistent YOLOv8 accident-analysis pipeline.
- [ ] Camera monitoring.
- [x] Video processing pipeline.

## PHASE 6 — COMPUTER VISION

- [x] Dataset research (CCD facts verified; video-use permission unresolved).
- [x] Dataset preparation utility (manifest validation and source-grouped splits; no dataset data used).
- [x] YOLO model selection.
- [ ] Model training or fine-tuning.
- [x] Separate temporal accident-classifier interface (checkpoint remains unavailable).
- [x] Authorization-gated training and held-out evaluation workflow.
- [x] Vehicle detection.
- [x] Object tracking.
- [x] Accident candidate detection.
- [x] Temporal verification.
- [ ] False-positive evaluation.
- [ ] Model evaluation.

The bundled `accident-test.mp4` and `normal-traffic.mp4` clips do not have
ground-truth annotations. Quantitative detection and severity evaluation
therefore remains pending; mocked unit tests are not a substitute for labeled
video evaluation.

CCD is documented in `DETECTION_PIPELINE.md`. Its code repository has an MIT
license, but no video-use terms; do not download or train until written
permission is obtained. The preparation utility and synthetic tests are
implemented, but no CCD files were accessed. Classifier training and
labeled-data evaluation remain pending. The runtime classifier is opt-in and
reports `UNKNOWN` when no trained checkpoint is configured; it is not
production-validated.

## PHASE 7 — SEVERITY ESTIMATION

- [ ] Define severity categories.
- [ ] Identify relevant visual features.
- [ ] Develop severity estimation approach.
- [ ] Evaluate severity predictions.
- [ ] Integrate severity results with incidents.
- [ ] Add manual review.

## PHASE 8 — LOCATION AND EMERGENCY RESPONSE

- [ ] Camera GPS integration.
- [x] Registered camera location assignment to videos (location proxy only).
- [x] Leaflet map integration with OpenStreetMap attribution.
- [x] Nearby hospital and emergency-resource discovery using OpenStreetMap.
- [x] Display and distance-prioritize mapped emergency resources.
- [ ] Notification system.
- [ ] Response tracking.
- [x] Audit-only notification history with delivery constrained to `not_sent`.

## PHASE 9 — ANALYTICS

- [ ] Incident statistics.
- [ ] Severity distribution.
- [ ] Detection performance.
- [ ] Historical incident reports.
- [ ] Exportable reports.

## PHASE 10 — TESTING AND DEPLOYMENT

- [x] Backend unit tests.
- [x] Frontend component tests.
- [x] API integration tests.
- [x] Authentication tests.
- [x] Authorization tests.
- [ ] ML evaluation tests.
- [ ] End-to-end tests.
- [ ] Security review.
- [x] Performance testing (sample-video runtime measured; labeled ML evaluation remains pending).
- [x] Docker Compose deployment configuration with PostgreSQL and persistent volumes.
- [x] Production startup and configuration documentation.

## CURRENT DEVELOPMENT POLICY

Only the active phase and approved tasks should be implemented.

A task can be marked complete only after implementation and relevant tests have passed.
