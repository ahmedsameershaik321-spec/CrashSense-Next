
# CrashSense — System Architecture

## 1. Project Overview

CrashSense is an intelligent road accident detection and emergency response platform.

The system analyzes CCTV footage, dashcam recordings and uploaded road videos to identify potential accidents, verify incidents, estimate severity and coordinate emergency responses.

## 2. System Objectives

- Detect potential road accidents using computer vision.
- Track vehicles across video frames.
- Verify detections across multiple observations.
- Reduce false-positive accident alerts.
- Estimate accident severity using visual evidence.
- Identify incident locations using camera metadata or GPS.
- Identify nearby hospitals and emergency resources.
- Notify authorized emergency responders.
- Maintain incident history and audit logs.

## 3. Technology Stack

### Frontend
- Next.js
- React
- TypeScript
- Tailwind CSS
- shadcn/ui
- Leaflet

### Backend
- Python 3.11
- FastAPI
- SQLAlchemy
- Pydantic
- JWT authentication

### Machine Learning
- PyTorch
- Ultralytics YOLO
- ByteTrack
- OpenCV
- NumPy

### Database
- PostgreSQL
- Alembic migrations

### Testing
- Pytest
- Playwright
- HTTPX

### Development
- Git
- GitHub
- VS Code

## 4. System Modules

### Authentication
- User registration
- Login and logout
- Password hashing
- JWT access control
- Role-based authorization
- Administrator approval

### Video Management
- Camera registration
- Camera metadata
- Video uploads
- Video validation
- Camera status monitoring

### Accident Detection
- Vehicle detection
- Accident candidate identification
- Object tracking
- Temporal verification
- Confidence scoring

### Severity Estimation
- Collision characteristics
- Vehicle movement
- Visible damage indicators
- Multi-factor severity estimation

Severity estimates are advisory and must not be treated as confirmed medical assessments.

### Location Management
- Camera GPS metadata
- Incident coordinates
- Reverse geocoding where supported
- Nearby emergency resource discovery

### Emergency Response
- Incident creation
- Hospital identification
- Audit-only alert recording; external notification delivery is disabled
- Response status tracking
- Notification history

### Analytics
- Incident statistics
- Detection performance
- Severity distribution
- Historical reports

## 5. User Roles

### Pending User
- Can access permitted account functionality.
- Cannot access protected videos.
- Cannot access operational monitoring.
- Cannot access incident management.

### Monitoring Operator
- Access authorized monitoring resources.
- Review accident detections.
- Verify incidents.
- Manage authorized incident workflows.

### Administrator
- Manage users and permissions.
- Approve pending registrations.
- Assign operational roles.
- Manage cameras and system configuration.
- Review audit logs and system activity.

Public registration must NEVER grant administrator or monitoring_operator privileges.

## 6. High-Level Architecture

Browser
    |
    v
Next.js Frontend
    |
    v
FastAPI Backend
    |
    +---- Authentication and Authorization
    |
    +---- Video Management
    |
    +---- Incident Management
    |
    +---- Emergency Response
    |
    +---- PostgreSQL Database
    |
    +---- ML Engine
              |
              +---- YOLO Detection
              +---- Object Tracking
              +---- Accident Verification
              +---- Severity Estimation

## 7. Security Requirements

- Hash passwords securely.
- Validate all incoming data.
- Enforce server-side role permissions.
- Protect video and incident endpoints.
- Never expose secrets in frontend code.
- Use environment variables for credentials.
- Apply upload size and file-type restrictions.
- Maintain audit logs for sensitive operations.
- Prevent unauthorized access to monitoring resources.
- Validate authentication and authorization independently.

## 8. Engineering Principles

- Modular architecture.
- Separation of concerns.
- Reusable components.
- Type-safe frontend.
- Documented APIs.
- Database migrations.
- Automated testing.
- Secure defaults.
- Centralized error handling.
- Maintainable code.

## 8.1 Account Management and Deployment

- Initial administrator creation is an explicit, one-time bootstrap operation;
  public registration always creates a pending inactive user.
- Only active administrators may approve pending users, assign operational
  roles, or suspend/reactivate approved accounts. The last active
  administrator is protected from deactivation and demotion.
- PostgreSQL stores account records and analysis jobs. Uploaded videos and
  model cache require persistent storage volumes.
- Alembic migrations run before the API is started in the provided Compose
  deployment. Production debug mode is disabled by default.
- The default frontend integration uses a same-origin Next.js proxy. Direct
  browser-to-API deployments must configure explicit
  `CORS_ALLOWED_ORIGINS`; wildcard origins are rejected.
- Map tiles and nearby resource lookups use OpenStreetMap public services.
  Camera coordinates sent to the resource API are approximate scene-location
  proxies, not verified incident coordinates.
- Alert audit records are constrained to `not_sent`. No external emergency
  notification provider is wired into the application.

## 9. Development Strategy

Development proceeds incrementally.

Each feature must have:
1. Requirements.
2. Implementation.
3. Unit tests.
4. Integration tests where applicable.
5. Security review.
6. Documentation.
7. Git commit.

No feature is considered complete merely because its interface has been generated.

## 10. Important Constraints

- Accident detection must be evaluated using appropriate datasets.
- Confidence scores must not be represented as guaranteed accuracy.
- Severity classification requires validation.
- Emergency notifications must not be sent to real emergency services during development without explicit authorization.
- Camera access must be authorized.
- The system must support manual incident review.
