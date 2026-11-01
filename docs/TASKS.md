
# CrashSense — Development Tracker

Project: CrashSense
Repository: CrashSense-Next
Primary Branch: main
Status: Architecture Foundation

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
- [ ] Create frontend project.
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
- [ ] Implement error handling.
- [ ] Implement health check endpoint.
- [ ] Implement API versioning.

## PHASE 3 — AUTHENTICATION AND SECURITY

- [ ] User registration.
- [ ] Secure password hashing.
- [ ] User login.
- [ ] JWT authentication.
- [ ] Refresh token strategy.
- [ ] Role-based access control.
- [ ] Pending user approval.
- [ ] Administrator role management.
- [ ] Audit logging.
- [ ] Authorization tests.

## PHASE 4 — FRONTEND

- [ ] Initialize Next.js.
- [ ] Configure TypeScript.
- [ ] Configure Tailwind CSS.
- [ ] Configure shadcn/ui.
- [ ] Design application layout.
- [ ] Build login and registration pages.
- [ ] Build dashboard.
- [ ] Build monitoring interface.
- [ ] Build administrator interface.
- [ ] Build incident management interface.
- [ ] Build analytics interface.
- [ ] Integrate backend APIs.

## PHASE 5 — VIDEO MANAGEMENT

- [ ] Camera registration.
- [ ] Camera metadata management.
- [ ] Video upload.
- [ ] Video validation.
- [ ] Video storage.
- [ ] Camera monitoring.
- [ ] Video processing pipeline.

## PHASE 6 — COMPUTER VISION

- [ ] Dataset research.
- [ ] Dataset preparation.
- [ ] YOLO model selection.
- [ ] Model training or fine-tuning.
- [ ] Vehicle detection.
- [ ] Object tracking.
- [ ] Accident candidate detection.
- [ ] Temporal verification.
- [ ] False-positive evaluation.
- [ ] Model evaluation.

## PHASE 7 — SEVERITY ESTIMATION

- [ ] Define severity categories.
- [ ] Identify relevant visual features.
- [ ] Develop severity estimation approach.
- [ ] Evaluate severity predictions.
- [ ] Integrate severity results with incidents.
- [ ] Add manual review.

## PHASE 8 — LOCATION AND EMERGENCY RESPONSE

- [ ] Camera GPS integration.
- [ ] Incident location management.
- [ ] Leaflet map integration.
- [ ] Nearby hospital discovery.
- [ ] Emergency resource management.
- [ ] Notification system.
- [ ] Response tracking.
- [ ] Notification audit history.

## PHASE 9 — ANALYTICS

- [ ] Incident statistics.
- [ ] Severity distribution.
- [ ] Detection performance.
- [ ] Historical incident reports.
- [ ] Exportable reports.

## PHASE 10 — TESTING AND DEPLOYMENT

- [ ] Backend unit tests.
- [ ] Frontend component tests.
- [ ] API integration tests.
- [ ] Authentication tests.
- [ ] Authorization tests.
- [ ] ML evaluation tests.
- [ ] End-to-end tests.
- [ ] Security review.
- [ ] Performance testing.
- [ ] Deployment configuration.
- [ ] Production documentation.

## CURRENT DEVELOPMENT POLICY

Only the active phase and approved tasks should be implemented.

A task can be marked complete only after implementation and relevant tests have passed.
