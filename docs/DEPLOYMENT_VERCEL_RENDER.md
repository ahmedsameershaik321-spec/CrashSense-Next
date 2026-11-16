# Production deployment: Vercel and Render

The Next.js frontend runs on Vercel. The FastAPI API, PostgreSQL database,
analysis worker, and persistent video/model files run on Render. The API
service must stay at one instance because its analysis worker is process-local.

## Render backend

1. Create the Vercel project first so its production domain is known.
2. Sign in to Render with access to this repository and create a Blueprint
   from `render.yaml` on the `main` branch.
3. Set `CORS_ALLOWED_ORIGINS` to a JSON array containing the exact Vercel
   production origin, for example `["https://crashsense.vercel.app"]`. Also set
   `INITIAL_ADMIN_EMAIL` and a unique `INITIAL_ADMIN_PASSWORD` in the Blueprint
   prompt. Render generates the JWT secret and database credentials stay
   inside the managed Postgres URL.
4. Create the Blueprint resources and wait for the API health check to pass.
5. Record the API service's public origin, such as
   `https://crashsense-api.onrender.com`, without an `/api/v1` suffix.
6. Run the one-time administrator bootstrap from the API service shell:

   ```sh
   python -m app.bootstrap_admin
   ```

7. Remove `INITIAL_ADMIN_EMAIL` and `INITIAL_ADMIN_PASSWORD` from the API's
   environment and redeploy after the administrator has been created.

The Blueprint creates a paid 1 CPU / 2 GB API service, a 20 GB persistent
disk, and a 256 MB managed Postgres database. The disk retains uploaded videos
and the downloaded YOLO checkpoint across restarts. PostgreSQL and persistent
video storage are required; ephemeral service filesystems are not suitable.
At current Render list rates, these resources are about $36/month before
bandwidth and usage charges: [API compute](https://render.com/pricing),
[Postgres](https://render.com/pricing), and [persistent disk](https://render.com/docs/disks).

## Vercel frontend

1. Import the GitHub repository as a Vercel project.
2. Set the project Root Directory to `frontend` and keep the Next.js framework
   preset and default build command.
3. Add these environment variables to Production, replacing the API origin
   with the Render service origin:

   ```dotenv
   NEXT_PUBLIC_API_BASE_URL=https://crashsense-api.onrender.com/api/v1
   CRASHSENSE_BACKEND_ORIGIN=https://crashsense-api.onrender.com
   NEXT_PUBLIC_MAX_VIDEO_UPLOAD_SIZE_MB=100
   ```

4. Deploy the frontend. Verify login, upload a representative video, playback,
   and analysis submission on the deployed domains before inviting users.

Preview deployments need their own matching origin in Render's
`CORS_ALLOWED_ORIGINS` value before browser API calls will work there.

Browser API calls go directly to Render so large uploads do not pass through a
Vercel function or its request proxy. The Render CORS allowlist must contain
the exact Vercel production origin. The video stream route still uses
`CRASHSENSE_BACKEND_ORIGIN` to forward the protected media cookie and range
requests. Verify large uploads and long video streams with representative
files after deployment.

## Operating notes

- Choose a Vercel plan that matches the site's intended use and traffic.
- Render plan, disk, database, and bandwidth charges apply. Review current
  provider pricing before creating resources.
- The API performs YOLO inference on CPU. Processing speed depends on video
  length and the Render service plan; the dashboard submits analysis as a job.
- The first analysis downloads YOLO26n to the persistent model cache.
- Set `INITIAL_ADMIN_*` only for the one-time bootstrap, then remove both
  variables from the service.
- Configure backups and retention for the database and video disk before
  storing important production footage.
