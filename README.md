# Breathe ESG Ingestion Engine & Review Ledger

A fully functional Django REST Framework and React (Vite + TS) prototype for ESG data ingestion, proration normalization, and analyst sign-off review.

---

## 🚀 Local Development Setup

### 1. Backend Setup (Django)

1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Create and activate a Python virtual environment:
   ```bash
   # Windows (PowerShell/CMD)
   python -m venv venv
   .\venv\Scripts\activate

   # macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Run migrations and seed the database:
   ```bash
   python manage.py migrate
   python seed_db.py
   ```
5. Start the Django development server:
   ```bash
   python manage.py runserver
   ```
   The backend API will run at `http://127.0.0.1:8000/`.

### 2. Frontend Setup (React + Vite + TypeScript)

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install npm dependencies:
   ```bash
   npm install
   ```
3. Start the Vite development server:
   ```bash
   npm run dev
   ```
   The React frontend will run at `http://localhost:5173/` and is pre-configured to proxy API calls to port 8000.

---

## 🧪 Running Automated Tests

Run the backend unit tests to verify carbon calculations (Haversine flight distances), proration logic, CSV parsing, and multi-tenant security separation:
```bash
cd backend
.\venv\Scripts\activate # or source venv/bin/activate
python manage.py test
```

---

## ☁️ Deploying to the Cloud

Our workspace includes a multi-stage `Dockerfile` in the root directory. This makes cloud deployment simple and cloud-agnostic.

### Deploying to Railway (Recommended - Fastest)
1. Push this Git repository to a private or public GitHub repository.
2. Go to [Railway](https://railway.app/) and click **New Project** ➔ **Deploy from GitHub repo**.
3. Select your repository.
4. Railway will automatically detect the root `Dockerfile` and build it.
5. In the service settings, click **Generate Domain** to get your public live URL.
6. The database migrations and seeding script (`seed_db.py`) will automatically execute during the startup phase.

### Deploying to Render
1. Push this Git repository to GitHub.
2. Log in to [Render](https://render.com/) and create a new **Web Service**.
3. Link your GitHub repository.
4. Select **Docker** as the runtime environment.
5. In the **Environment Variables** section, add `PORT = 8000` (Render defaults to this, but defining it is a safe fallback).
6. Click **Deploy Web Service**.

---

## 👥 Mock Accounts & Multi-Tenancy

For review and evaluation convenience, the system is seeded with mock user sessions. Use the dropdown switcher in the navbar header to test data isolation and permissions:

| Mock Username | Password | Organization (Tenant) | Role | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **`acme_analyst`** | `password123` | Acme Corporation | **Analyst** | Can upload files, edit records, approve/reject |
| **`acme_auditor`** | `password123` | Acme Corporation | **Auditor** | Read-only access to Acme data, cannot edit/approve |
| **`eco_analyst`** | `password123` | EcoSphere Industries | **Analyst** | Can upload files, edit records, approve/reject |
| **`eco_auditor`** | `password123` | EcoSphere Industries | **Auditor** | Read-only access to EcoSphere data |

*Strict Tenant Separation*: When logged in as `acme_analyst`, you will not see any data uploaded by `eco_analyst` because queries are filtered dynamically based on the profile tenant FK.
