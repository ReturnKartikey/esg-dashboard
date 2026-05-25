# Breathe ESG Ingestion Engine & Review Ledger - Deployment Guide

This guide details how to build, verify, and deploy the Breathe ESG application using containerization and various cloud options.

---

## 1. Local Production Verification (Using Docker)

Before deploying to the cloud, verify that the production build works locally. The repository includes a multi-stage `Dockerfile` that packages the React frontend (Vite + TypeScript) and serves it directly through Django (using WhiteNoise) inside a single container.

### Step-by-Step Local Run

1. **Ensure Docker is running** on your system.
2. **Build the container image**:
   ```bash
   docker build -t esg-dashboard .
   ```
3. **Run the container**:
   ```bash
   docker run -p 8000:8000 --name esg-dashboard-app esg-dashboard
   ```
4. **Access the application**:
   Open [http://localhost:8000/](http://localhost:8000/) in your web browser.
5. **Shut down the container**:
   ```bash
   docker stop esg-dashboard-app
   docker rm esg-dashboard-app
   ```

---

## 2. Deploying to Railway (Recommended - Fastest Setup)

Railway automatically detects the root `Dockerfile`, builds it, sets up the web server port, and exposes a public domain.

1. **Commit and push** all changes to your GitHub repository.
2. Log in to [Railway](https://railway.app/).
3. Click **New Project** ➔ **Deploy from GitHub repo**.
4. Authorize and select your repository.
5. Railway will automatically start building the multi-stage image.
6. Once the build finishes, go to the service settings and click **Generate Domain** to get your public live URL.
7. Django migrations and database seeding (`seed_db.py`) run automatically on startup.

---

## 3. Deploying to Render (Free Container Hosting)

Render supports hosting Docker containers directly from a connected Git repository on their free tier.

1. Push your code changes to GitHub.
2. Log in to [Render](https://render.com/).
3. Click **New** ➔ **Web Service**.
4. Connect your GitHub repository.
5. Set the following configuration options:
   * **Runtime**: `Docker`
   * **Instance Type**: `Free` (or any preferred tier)
6. Add the following **Environment Variable**:
   * `PORT` = `8000` (Render defaults to routing port 10000, setting `PORT = 8000` tells Render where the container is listening).
7. Click **Deploy Web Service**.

---

## 4. Deploying to Google Cloud Run (Scale-to-Zero/Serverless)

Google Cloud Run is an excellent, cost-effective serverless platform for hosting Docker containers.

### Prerequisites
* Install the Google Cloud SDK (`gcloud` command-line tool).
* Create a Google Cloud Project and enable Billing.

### Step-by-Step CLI Deployment

1. **Authenticate and configure project**:
   ```bash
   gcloud auth login
   gcloud config set project [YOUR_PROJECT_ID]
   ```
2. **Enable required Google API services**:
   ```bash
   gcloud services enable run.googleapis.com containerregistry.googleapis.com artifactregistry.googleapis.com
   ```
3. **Deploy the application**:
   Run the following command in the root folder of the project (where the `Dockerfile` resides). This builds the image in the cloud using Google Cloud Build and deploys it to Cloud Run:
   ```bash
   gcloud run deploy esg-dashboard --source . --port 8000 --allow-unauthenticated --region us-central1
   ```
4. **Access your service**:
   The CLI output will display the generated Service URL (e.g. `https://esg-dashboard-xxxxxx-uc.a.run.app`).

---

## 5. Production Database Considerations (SQLite vs PostgreSQL)

By default, the application runs on SQLite (`db.sqlite3`). 

> [!WARNING]
> SQLite stores data inside the running container. If the container restarts, stops, or scales down (which happens frequently on serverless platforms like Cloud Run or Render's Free tier), any new uploads or changes will be lost.

### To transition to PostgreSQL for a production environment:

1. **Install database adapter**:
   Add `dj-database-url` and `psycopg2-binary` to `backend/requirements.txt`.
2. **Update Database Configuration**:
   Modify `backend/config/settings.py` to check for a database URL environment variable:
   ```python
   import dj_database_url
   import os

   DATABASES = {
       'default': dj_database_url.config(
           default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
           conn_max_age=600
       )
   }
   ```
3. **Provide Database Connection String**:
   Provision a PostgreSQL database instance (e.g. on Railway, Supabase, Neon, or GCP Cloud SQL) and supply the connection string as a `DATABASE_URL` environment variable in your host's application settings.
