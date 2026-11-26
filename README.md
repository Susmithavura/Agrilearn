# AgriLearn — Farmer Training Management System

AgriLearn is a role-based farmer training management application for the VVITU Software Engineering activity-based learning project (II Year B.Tech – I Semester, Academic Year 2026–27). It manages farmer and trainer records, agricultural training programs, schedules, enrollments, attendance, progress and reports; it is not a general farm-management system.

The frontend uses HTML, CSS, Bootstrap 5, Bootstrap Icons and vanilla JavaScript. The backend uses Python, Flask and MySQL 8.4.

## Requirements

- Windows 10/11
- Python 3.10 or later
- MySQL Server 8.4
- A modern browser

Production uses the included Gunicorn WSGI entry point and requires HTTPS, a persistent MySQL service, and provider-managed environment variables. The Windows development workflow below remains unchanged.

## Local setup

Run commands from the project root unless stated otherwise.

### One-command Windows setup

Open PowerShell in the project directory and run:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\setup.ps1
```

The script checks that MySQL84 is running, prepares a Python virtual environment, installs the declared dependencies, creates a secure `SECRET_KEY` only when missing, and runs the safe database and administrator setup commands. Passwords are requested with terminal prompts that do not echo them. It then starts Flask and the frontend in separate PowerShell windows and verifies the database health endpoint. Use `.\setup.ps1 -SkipStart` to initialize the database and create the first administrator without launching servers.

The script does not reset an existing `DB_PASSWORD`, overwrite any unrelated `.env` values, or delete databases. If an existing MySQL application account has no password configured in `server\.env`, enter its existing password when prompted; the account is never altered to a newly chosen password.

### Manual setup

1. Copy the environment template:

   ```powershell
   Copy-Item server\.env.example server\.env
   ```

2. Run `server\.venv\Scripts\python.exe server\scripts\prepare_environment.py`. This creates `server\.env` if missing and generates a cryptographically secure secret only when the template placeholder is present. Existing database settings are preserved. Keep `FRONTEND_ORIGIN=http://127.0.0.1:8000` if using the frontend command below. Do not commit this file.

3. Create and activate the Python environment, then install the backend dependencies:

   ```powershell
   py -m venv server\.venv
   .\server\.venv\Scripts\Activate.ps1
   python -m pip install -r server\requirements.txt
   ```

4. Initialize MySQL and create the restricted application account:

   ```powershell
   python server\scripts\setup_database.py
   ```

   The command securely prompts for MySQL administrator credentials and, when `DB_PASSWORD` is not already configured, the application-account password. It creates `agrilearn_db` only if absent, creates or verifies tables without deleting data, verifies the least-privilege account, and saves a newly entered application password to the ignored `server\.env`. It does not create sample records.

5. Create demonstration accounts for roles that do not already have an account:

   ```powershell
   python server\scripts\create_demo_accounts.py
   ```

   New demonstration passwords are randomly generated and printed once in the local terminal. Save them securely; they are not stored in plaintext. Existing named demo accounts are reported and their passwords are never changed. The script creates any missing demo account even if an unrelated account already has that role, and repairs a missing profile only for an existing reserved demo farmer/trainer account. The script tests each newly created account through Flask login and its role dashboard. The one-command setup runs this step automatically.

6. Create the first Administrator account only if the previous step did not find or create one:
   ```powershell
   python server\scripts\create_admin.py
   ```

   This prompts for a name, username and password without echoing the password. It refuses to create another bootstrap administrator. All additional accounts and role assignments must be made from the authenticated Administrator portal. The one-command setup runs this step automatically.

7. Start Flask in a PowerShell window:

   ```powershell
   Set-Location server
   python run.py
   ```

8. In another PowerShell window, serve the frontend from the project root:

   ```powershell
   python -m http.server 8000 --bind 127.0.0.1
   ```

9. Open `http://127.0.0.1:8000`. The frontend calls Flask at `http://127.0.0.1:5000/api`, sends session cookies, and obtains CSRF tokens before changing data.

If you change the frontend host or port, update `FRONTEND_ORIGIN` in `server\.env` to the exact browser origin and restart Flask. `localhost` and `127.0.0.1` are different origins; use the same host in the browser and API configuration.

The empty `agrilearn-api-base` meta setting in `index.html` selects the local Flask API automatically on `localhost`/`127.0.0.1`. For production, either leave it empty when the frontend and backend share one HTTPS origin and `/api` is reverse-proxied, or set it to the full HTTPS backend API base (for example `https://api.example.test/api`). Never configure an HTTP API URL for an HTTPS frontend. The browser sends the session cookie with credentialed requests and the API obtains CSRF tokens before state changes.

## Health checks and tests

With Flask running, check:

- `http://127.0.0.1:5000/api/health` — Flask availability
- `http://127.0.0.1:5000/api/health/database` — MySQL connectivity and schema availability

Run the backend tests from the `server` directory:

```powershell
python -m unittest discover -s tests -v
```

The backend unit suite covers validation, CSRF enforcement, session authentication, inactive-account rejection, and role authorization. The opt-in read-only live checks and the application's role-specific manual login checklist are described below.

From the project root, run the full backend suite, including its opt-in **read-only** local-MySQL role, API-scope and repeat-read checks, plus frontend API URL tests:

```powershell
$env:AGRILEARN_RUN_MYSQL_TESTS = "1"
& ".\server\.venv\Scripts\python.exe" -m unittest discover -s ".\server\tests" -v
Remove-Item Env:AGRILEARN_RUN_MYSQL_TESTS
node --test ".\tests\frontend_api_config.test.mjs"
```

The MySQL acceptance tests only read records; they do not create demo data or exercise database writes. Manual role login and write/persistence workflows still require local acceptance.

## Optional demonstration data

After MySQL is initialized and the five reserved demo accounts and their linked farmer/trainer profiles exist, populate repeatable training records with:

```powershell
Set-Location server
.\.venv\Scripts\python.exe scripts\seed_demo_data.py
```

The script uses Flask API endpoints with local test-client sessions tied to active `demo.admin`, `demo.coordinator`, `demo.trainer`, and `demo.farmer` database accounts to exercise API role guards; it does not verify their passwords or perform browser sign-in. It does not need, print, or change passwords. It adds 10 clearly named sample farmers, 3 sample trainers, 5 demonstration programs, 10 sessions, 25 enrollments, 25 attendance records, and 25 progress records. Stable sample identifiers and session markers make repeated runs idempotent. It never resets or deletes existing records. Review the printed MySQL counts after it completes.

## Roles and access

The five database roles are `admin`, `coordinator`, `trainer`, `farmer` and `management`. The selected portal on the sign-in form is only a consistency check; Flask loads and authorizes the role from the stored account. The backend enforces access rules regardless of frontend visibility.

- **Administrator:** account creation and status, system records and reports.
- **Training Coordinator:** farmer/trainer/program/schedule management, enrollment and reports.
- **Trainer:** assigned sessions and programs, enrolled farmer lists, attendance and authorized progress updates.
- **Farmer:** own profile, available programs, enrollment, own sessions, attendance and progress.
- **Management:** read-only operational views and reports.

Passwords are hashed with Werkzeug. Session cookies are HTTP-only and same-site; state-changing API requests require a CSRF token. Configure HTTPS and secure cookies before any non-local deployment.

## Production deployment configuration

The root `Procfile` starts the Flask application with Gunicorn through `server/wsgi.py`; platforms that do not consume a Procfile can use the equivalent start command:

```text
gunicorn --chdir server wsgi:app --bind 0.0.0.0:$PORT --workers 2 --access-logfile - --error-logfile -
```

Deploy on a Gunicorn-supported Linux/POSIX host. Set `PORT` using the host's runtime environment. Do not start production with `python run.py` or Flask's development server.

Configure these values in the hosting provider's environment/secrets manager (never commit `server/.env`):

- `FLASK_ENV=production`, `FLASK_DEBUG=0`, and a unique random `SECRET_KEY` of at least 32 characters.
- `FRONTEND_ORIGIN` set to the one exact public frontend origin, including `https://` and any non-default port, with no path or comma-separated origins.
- `SESSION_COOKIE_SECURE=true`. Keep `SESSION_COOKIE_SAMESITE=Lax` when the frontend and API are same-site (including HTTPS subdomains of one site). For a genuinely cross-site frontend/API pair use `SESSION_COOKIE_SAMESITE=None`; this requires Secure cookies. Cross-site cookies may still be blocked by browser third-party-cookie policies, so same-site hosting or a same-origin `/api` reverse proxy is recommended.
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` for the persistent MySQL provider.
- `DB_APP_ALLOWED_HOST` set to the exact application egress hostname/IP that MySQL should accept for the app account; it is separate from the MySQL server's `DB_HOST`. Wildcards are rejected.
- `DB_SSL_CA` pointing to the provider's trusted CA bundle, plus `DB_SSL_VERIFY_CERT=true` and `DB_SSL_VERIFY_IDENTITY=true`. Production startup validation rejects missing TLS verification settings.
- If hosting the frontend separately, set the `agrilearn-api-base` meta content in `index.html` to the full HTTPS API base URL ending in `/api`. When API and frontend share an origin, leave it empty and proxy `/api` to Flask.

Flask CORS allows credentialed requests only from the configured exact `FRONTEND_ORIGIN`. Cookie authentication and the CSRF token/header checks remain enabled for protected requests; do not broaden CORS to `*` or expose protected endpoints.

### Production database provisioning and upgrades

Provision a persistent MySQL 8.4-compatible database and a dedicated application account. From a secured deployment/administration environment with network access to MySQL, set the database connection variables above and provide `MYSQL_ADMIN_USER` and `MYSQL_ADMIN_PASSWORD` only to the setup/upgrade process, not the web runtime. Set `MYSQL_ADMIN_HOST`/`MYSQL_ADMIN_PORT` if the administrator connection endpoint differs from the application database endpoint. Provide the trusted CA settings for TLS.

For a new database, run `python server\scripts\setup_database.py` once from the project root using the administrator credentials. It creates the database if absent, applies `server/sql/schema.sql` with `CREATE TABLE IF NOT EXISTS`, runs pending numbered SQL upgrades, creates/verifies the narrowly scoped app account (`SELECT`, `INSERT`, `UPDATE`, `DELETE` on this database only), and verifies the app connection. It does not seed demonstration data or delete/reset records.

For an existing database, back it up using the provider's supported backup method, then run `python server\scripts\migrate_database.py`. This applies pending `server/sql/migrations/NNN_*.sql` upgrades and records versions in `schema_migrations`; the runner recognizes the existing `progress_percent` column and marks that legacy change as applied instead of re-running its `ALTER TABLE`. Add future schema changes as new, ordered migration files; do not edit an already-applied migration. MySQL DDL may auto-commit, so review each migration and ensure a recoverable backup before applying it. Neither setup nor migration scripts reset the database.

Local development continues to use `python run.py` and the existing `setup.ps1`; production WSGI startup and configuration are separate. A real production deployment, external MySQL connection, and hosted-browser cookie policy have not been tested by these local checks.

## Main API groups

`/api/auth`, `/api/users`, `/api/farmers`, `/api/trainers`, `/api/programs`, `/api/sessions`, `/api/enrollments`, `/api/attendance`, `/api/progress`, `/api/reports`, and `/api/dashboard`. Responses use JSON `data` and, for list endpoints, pagination `meta`. Protected state changes require an authenticated session and `X-CSRF-Token`.

## Project structure

```text
index.html
assets/
  css/
  images/
  js/
server/
  app/
    routes/
  scripts/
  sql/schema.sql
  sql/migrations/
  tests/
  requirements.txt
  .env.example
  run.py
  wsgi.py
Procfile
```

Training records with history are archived, cancelled or deactivated rather than destructively erased. MySQL foreign keys protect related records. CSV reports are generated from live server results.

## Database backup

Use MySQL's `mysqldump` client, and choose a new output filename each time to avoid overwriting a backup. Enter the password at the prompt rather than putting it in the command:

```powershell
$backup = "C:\Backups\agrilearn-$(Get-Date -Format yyyyMMdd-HHmmss).sql"
if (Test-Path $backup) { throw "Backup already exists: $backup" }
& "C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqldump.exe" --host=127.0.0.1 --user=agrilearn_app --password --single-transaction agrilearn_db "--result-file=$backup"
```

Create the destination directory first if it does not exist. Keep backups private and test restoration separately.
