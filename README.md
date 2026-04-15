<div align="center">
  <h1>🎓 TestR — Examination Management System</h1>
  <p>A production-grade, full-stack academic examination and result management platform built for modern universities and educational institutions.</p>

  [![Python version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
  [![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-D71F00.svg?logo=sqlalchemy)](https://www.sqlalchemy.org/)
  [![MySQL](https://img.shields.io/badge/MySQL-Async-4479A1.svg?logo=mysql)](https://www.mysql.com/)
  [![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker)](https://www.docker.com/)
  [![Railway](https://img.shields.io/badge/Deployed_on-Railway-131415.svg?logo=railway)](https://railway.app)
</div>

---

## 🔗 Live Deployment

> **https://testr-wheat-three.vercel.app/static/pages/index.html**

---

## 🌟 Overview

**TestR** facilitates the entire academic examination lifecycle — from user registration and course enrollment to exam creation, live proctoring, automated grading, and result publishing. The platform handles the complexities of university logistics seamlessly with a strong emphasis on security and data integrity.

### Key Capabilities

| Area | Features |
|---|---|
| **User Management** | Role-based access (Admin, Teacher, Student), bulk CSV import, SSO-ready email patterns, password reset tokens |
| **Course Management** | Course creation, student enrollment (single & bulk), teacher assignment, active/inactive toggling |
| **Examinations** | MCQ + subjective question support, exam scheduling, timed attempts, auto-submission, publish/lock lifecycle |
| **Live Proctoring** | Tab-switch detection, fullscreen enforcement, copy-paste blocking, violation logging with severity levels |
| **Results & Grading** | Auto-grading for MCQs, manual grading interface for teachers, gradebook exports (PDF), result publishing |
| **Discussion Forum** | Course-scoped discussion threads, replies, role-based moderation |
| **Notifications** | Real-time in-app notification system with read/unread state and bulk creation |
| **Audit & Logging** | System logs, audit trails, IP logging for login/logout/exam events, CSV export |

---

## 🛠️ Tech Stack & Architecture

### Backend (Python 3.10+)

| Layer | Technology | Purpose |
|---|---|---|
| **Framework** | [FastAPI](https://fastapi.tiangolo.com/) | High-performance async REST APIs with auto-generated OpenAPI docs |
| **ORM** | [SQLAlchemy 2.0](https://www.sqlalchemy.org/) + `aiomysql` | Fully asynchronous, non-blocking MySQL interactions |
| **Validation** | [Pydantic v2](https://docs.pydantic.dev/) | Request/response schemas, settings management, field-level validation |
| **Authentication** | `python-jose` (JWT) + `passlib` (Bcrypt) | Stateless HttpOnly cookie-based auth with token rotation |
| **Data Processing** | `pandas` + `python-multipart` | Bulk CSV/Excel imports for users, enrollments, and assignments |
| **PDF Generation** | `reportlab` | Gradebook exports and certificate generation |
| **Cloud Storage** | `google-cloud-storage` | File uploads and asset management |
| **Migrations** | `alembic` | Database schema versioning and migration management |

### Frontend

| Layer | Technology | Purpose |
|---|---|---|
| **Structure** | Semantic HTML5 | Accessible, SEO-friendly page structure |
| **Styling** | [Bootstrap 5.3](https://getbootstrap.com/) | Responsive layouts with custom theming |
| **Logic** | ES6+ Vanilla JavaScript | Async `fetch`-based API communication — no heavy frameworks |
| **Theming** | Custom implementation | Light/Dark mode toggle with persistent `localStorage` |
| **Icons** | [Bootstrap Icons](https://icons.getbootstrap.com/) | Consistent iconography across all dashboards |

### Infrastructure

| Tool | Purpose |
|---|---|
| **Docker** | Multi-stage production build (`python:3.11-slim`) |
| **Docker Compose** | Local development with MySQL service |
| **Railway** | Cloud deployment with auto-injected MySQL env vars |
| **Gunicorn + Uvicorn** | Production-grade ASGI server with worker management |

---

## 📁 Project Structure

```
TestR/
├── Resources/              # UML diagrams, requirement docs, PDFs
├── app/
│   ├── core/               # Config, database, security, dependencies, rate limiter
│   │   ├── config.py       # Pydantic settings (env-aware for local/Railway/Docker)
│   │   ├── database.py     # Async engine + session factory
│   │   ├── dependencies.py # Auth dependency injection (get_current_user, role guards)
│   │   ├── security.py     # JWT creation/verification, bcrypt, cookie management
│   │   ├── rate_limiter.py # In-memory rate limiting per action
│   │   ├── exceptions.py   # Custom exception hierarchy
│   │   └── gcs.py          # Google Cloud Storage integration
│   ├── models/             # SQLAlchemy ORM models (14 models)
│   │   ├── user.py         # User, UserRole, StudentProfile, PasswordResetToken
│   │   ├── auth.py         # ActiveSession, IPLog
│   │   ├── course.py       # Course, CourseEnrollment, CourseTeacherAssignment
│   │   ├── exam.py         # Exam, Question, QuestionOption
│   │   ├── attempt.py      # ExamAttempt, AttemptAnswer
│   │   ├── result.py       # Result, GradeComposition
│   │   ├── proctor.py      # ProctoringViolation
│   │   ├── discussion.py   # DiscussionThread, DiscussionReply
│   │   ├── notification.py # Notification
│   │   └── log.py          # SystemLog, AuditLog
│   ├── routers/            # API route handlers (7 routers)
│   │   ├── auth.py         # Login, logout, refresh, /me, change-password
│   │   ├── admin.py        # Full admin panel APIs (users, courses, schools, logs)
│   │   ├── teacher.py      # Exam CRUD, question management, grading, gradebook
│   │   ├── student.py      # Dashboard, exam attempts, results, transcript
│   │   ├── discussion.py   # Course discussion threads
│   │   └── notifications.py# Notification management
│   ├── schemas/            # Pydantic request/response models
│   ├── services/           # Business logic layer (11 services)
│   ├── scripts/            # Database reset, seeding, startup scripts
│   ├── tests/              # Unit + integration tests (pytest)
│   ├── utils/              # Email validation, pagination, helpers
│   ├── static/             # Frontend (HTML, CSS, JS)
│   │   ├── pages/          # Role-specific dashboards (admin/, teacher/, student/)
│   │   ├── js/             # Client-side logic, auth guards, proctoring engine
│   │   └── css/            # Custom styles and theme overrides
│   ├── alembic/            # Database migration scripts
│   └── main.py             # FastAPI app entry point with middleware stack
├── Dockerfile              # Multi-stage production Docker build
├── docker-compose.yml      # Local development with MySQL
├── requirements.txt        # Python dependencies
└── README.md
```

---

## 📐 System Architecture & Documentation

<details>
<summary><b>🖼️ Click to expand System Diagrams</b></summary>
<br>

### 1. Component Diagrams
<p align="center">
  <img src="./Resources/Component%20diagram%20-%20Exam%20Creation%20&%20Scheduling%20Module.jpeg" alt="Exam Creation Component" width="45%">
  &nbsp; &nbsp;
  <img src="./Resources/Component%20diagram%20-%20User%20Management%20Module.jpeg" alt="User Management Component" width="45%">
</p>
<p align="center">
  <img src="./Resources/Component%20diagram%20-%20Discussion%20Forum%20Module.jpeg" alt="Discussion Forum Component" width="45%">
</p>

### 2. Sequence Diagrams
<p align="center">
  <img src="./Resources/Sequence%20diagram%20-%20Student%20Exam%20Process.jpeg" alt="Student Exam Process" width="45%">
  &nbsp; &nbsp;
  <img src="./Resources/Sequence%20diagram%20-%20Teacher%20Exam%20Creation.jpeg" alt="Teacher Exam Creation" width="45%">
</p>
<p align="center">
  <img src="./Resources/Sequence%20diagram%20-%20Admin%20User%20Management.jpeg" alt="Admin User Management" width="45%">
</p>

### 3. Class & Activity Diagrams
<p align="center">
  <img src="./Resources/Class%20diagram.jpeg" alt="Class Diagram" width="50%">
</p>
<p align="center">
  <img src="./Resources/Activity%20diagram%201.jpeg" alt="Activity Diagram 1" width="45%">
  &nbsp; &nbsp;
  <img src="./Resources/Activity%20diagram%202.jpeg" alt="Activity Diagram 2" width="45%">
</p>

*(Full detailed project analytics, requirement analysis PDFs, and additional documentation can be found in the [`/Resources`](./Resources) folder.)*
</details>

---

## 🔒 Security Architecture

TestR implements a multi-layered security model designed for production environments:

| Layer | Implementation |
|---|---|
| **Authentication** | JWT access + refresh tokens stored in `HttpOnly`, `Secure`, `SameSite=Lax` cookies |
| **Token Rotation** | Refresh endpoint issues new token pair and invalidates the old one in-place |
| **Concurrent Login Prevention** | Only one active session per user — new login kills the previous session |
| **Password Security** | Bcrypt hashing with salt, minimum 8 characters, complexity enforcement (uppercase, digit) |
| **CSRF Protection** | Custom middleware requires `X-Requested-With` header on all state-changing requests |
| **Rate Limiting** | In-memory rate limiter on login (5/min) and token refresh (20/min) endpoints |
| **Security Headers** | `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, CSP headers |
| **IP Logging** | Every login attempt, logout, and exam event is logged with client IP and timestamp |
| **Forced Password Reset** | Admin-generated reset tokens (64-char hex, 48h expiry, single-use) |
| **Exam Immutability** | Published exams are locked from structural edits to preserve academic integrity |

---

## 🚀 Quick Start (Local Development)

### Prerequisites
- Python 3.10+
- MySQL Server running locally (or Docker)

### 1. Clone & Install

```bash
git clone https://github.com/13Mahir/TestR.git
cd TestR

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment

Create `app/.env` with your local MySQL credentials:

```env
APP_ENV=development
APP_PORT=8000
DB_HOST=localhost
DB_PORT=3306
DB_NAME=testr
DB_USER=root
DB_PASSWORD=
JWT_SECRET_KEY=your-secret-key-here
```

### 3. Initialize Database

```bash
cd app

# Drop and recreate all tables from SQLAlchemy models
python scripts/reset.py

# Populate with sample university data (schools, branches, users, courses, exams)
python scripts/seed.py
```

### 4. Start the Server

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The application will be available at **http://localhost:8000**

### Alternative: Docker Compose

```bash
docker-compose up --build
```

This starts both the MySQL database and the application server.

---

## 🔑 Default Test Accounts

After running `seed.py`, log in with these sample accounts:

| Role | Email | Password | Capabilities |
|---|---|---|---|
| **Admin** | `admin@clg.ac.in` | `admin123` | User CRUD, course management, system logs, audit trails |
| **Teacher** | `john.doe@clg.ac.in` | `T1Pass123` | Exam creation, question management, grading, gradebook export |
| **Student** | `24bcp261@se.clg.ac.in` | `Student@123` | Dashboard, exam attempts, results, transcript |

> **Note:** Admin accounts are forced to reset their password on first login for security purposes.

---

## 📡 API Architecture

All API routes are prefixed and organized by role:

| Prefix | Router | Description |
|---|---|---|
| `/api/auth` | `auth.py` | Login, logout, token refresh, `/me`, change-password |
| `/api/admin` | `admin.py` | User management, course management, school/branch setup, logs |
| `/api/teacher` | `teacher.py` | Exam lifecycle, question CRUD, grading, gradebook PDF export |
| `/api/student` | `student.py` | Dashboard stats, exam attempts, results, transcript |
| `/api/notifications` | `notifications.py` | Fetch, mark read, bulk operations |
| `/api/discussions` | `discussion.py` | Course-scoped threads and replies |

Interactive API documentation is auto-generated at:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

---

## ☁️ Deployment (Railway)

TestR is **Railway-ready** out of the box. The configuration layer (`app/core/config.py`) natively maps Railway's auto-injected environment variables:

1. Provision a **MySQL Database** service on Railway.
2. Provision a **Python Deployment** service linked to this GitHub repo.
3. The app automatically detects and maps `MYSQLHOST`, `MYSQLPORT`, `MYSQLUSER`, `MYSQLPASSWORD`, and `MYSQLDATABASE` — no manual variable configuration needed.

The multi-stage `Dockerfile` ensures a minimal production image using `python:3.11-slim` with Gunicorn + Uvicorn workers.

---

## 🧪 Testing

```bash
cd app

# Install test dependencies
pip install -r ../requirements-test.txt

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=. --cov-report=term-missing
```

---

## 👥 Role-Based Frontend Pages

| Role | Pages |
|---|---|
| **Public** | Landing page, Login, Reset Password, 403/404 error pages |
| **Admin** | Overview dashboard, User management, Course management, School/Branch setup, System & Audit logs |
| **Teacher** | Course list, Exam creation, Question editor, Grading interface, Proctor reports, Gradebook export |
| **Student** | Dashboard, Course list, Exam lobby, Exam attempt (proctored), Results, Transcript |
| **Shared** | Discussion forum, Notifications, Change password, Dark/Light theme |

---

## 📄 License

This project was built as an academic software engineering project.

---

<div align="center">
  <sub>Built with ❤️ using FastAPI + Vanilla JS</sub>
</div>
