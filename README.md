<div align="center">
  <h1>🎓 EMS — Examination Management System (TestR)</h1>
  <p>A robust, full-stack academic examination and result management platform designed for modern universities and educational institutions.</p>
  
  [![Python version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com/)
  [![MySQL](https://img.shields.io/badge/MySQL-Async-4479A1.svg?logo=mysql)](https://www.mysql.com/)
  [![Railway](https://img.shields.io/badge/Deployed_on-Railway-131415.svg?logo=railway)](https://railway.app)
</div>

---

## 🌟 Overview

**TestR** facilitates the entire academic examination lifecycle. From user registration and course enrollment to exam creation, live proctoring, and automated result publishing, this platform handles the complexities of university logistics seamlessly and securely.

---

## 🛠️ Tech Stack & Architecture

### **Backend** (Python 3.10+)
*   **Framework**: [FastAPI](https://fastapi.tiangolo.com/) for high-performance, asynchronous REST APIs.
*   **Database ORM**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/) with `aiomysql` for non-blocking MySQL interactions.
*   **Validation**: [Pydantic v2](https://docs.pydantic.dev/) for data integrity and precise settings management.
*   **Security**: 
    *   `python-jose`: JWT (JSON Web Tokens) for stateless, HttpOnly cookie-based authentication.
    *   `passlib`: Bcrypt hashing for secure password storage.
*   **Data Processing**: `pandas` + `python-multipart` for handling bulk Excel/CSV data imports.
*   **Exporting**: `reportlab` for generating PDF grade books and certificates.

### **Frontend**
*   **Structure**: Semantic HTML5.
*   **Styling**: [Bootstrap 5.3](https://getbootstrap.com/) for responsive layouts.
*   **Logic**: ES6+ Vanilla JavaScript utilizing asynchronous `fetch` for API communication. No heavy frameworks!
*   **Theming**: Custom Light/Dark mode implementation with persistent `localStorage`.

---

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- Python 3.10+
- MySQL Server running locally

### 2. Installation
Clone the repository and install the dependencies:
```bash
git clone https://github.com/13Mahir/TestR.git
cd TestR/app

# Create a virtual environment and activate it
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 3. Database Configuration
Ensure your local MySQL server is running. Create a database named `testr`.
In the `app/` directory, create or modify the `.env` file depending on your local MySQL credentials:
```env
DB_HOST=localhost
DB_PORT=3306
DB_NAME=testr
DB_USER=root
# Leave DB_PASSWORD empty if your local root user has no password
DB_PASSWORD=
```

### 4. Database Setup & Seeding
We provide helper scripts to automatically generate your database tables and populate them with sample users, courses, and exams:
```bash
# Safely clear and recreate all tables based on SQLAlchemy models
python scripts/reset.py

# Seed the database with sample university data
python scripts/seed.py
```

### 5. Start the Server
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```
The application will be served at `http://localhost:8000`.

---

## ☁️ Deployment (Railway)

This application is **Railway-ready**. The configuration object (`app/core/config.py`) natively supports Railway's auto-injected environment variables. 

When deploying to [Railway.app](https://railway.app):
1. Provision a **MySQL Database** service on Railway.
2. Provision a **Python Deployment** service (linked to this GitHub repo).
3. The app will securely and automatically map Railway's `MYSQLHOST`, `MYSQLPORT`, `MYSQLUSER`, `MYSQLPASSWORD`, and `MYSQLDATABASE` without requiring any manual variable configuration!

---

## 🔑 Default Test Accounts (Generated via Seed)

If you ran the `seed.py` script, you can log in immediately with these sample accounts:

| Role | Email | Password |
|---|---|---|
| **Student** | `24bcp261@se.clg.ac.in` | `Student@123` |
| **Teacher** | `john.doe@clg.ac.in` | `T1Pass123` |
| **System Admin** | `admin@clg.ac.in` | `admin123` |

*(Note for admins: You are forced to reset your password on first login for security purposes).*

---

## 🔒 Security & Architecture Rules

*   **Stateless sessions**: Authentication strictly relies on JWT served inside HttpOnly cookies to prevent XSS-based token theft.
*   **Data Integrity**: Automatic `total_marks` recomputation occurs securely server-side whenever teachers update exam questions.
*   **Error Handling**: Global exception handlers capture raw tracebacks in development, returning clean JSON errors to the frontend.
*   **Immutability**: Published exams are locked from structural edits to preserve absolute academic integrity.
