# EMS — Examination Management System (TestR)

EMS is a robust, full-stack academic examination and result management platform designed for universities and educational institutions. It facilitates the entire examination lifecycle from user registration and course enrollment to exam creation, proctoring, and automated result publishing.

---

## 🛠️ Tech Stack & Architecture

### **Backend (Python 3.10+)**
*   **Framework**: [FastAPI](https://fastapi.tiangolo.com/) for high-performance, asynchronous REST APIs.
*   **Database ORM**: [SQLAlchemy 2.0](https://www.sqlalchemy.org/) with `asyncio` support.
*   **Database Driver**: `aiomysql` for non-blocking MySQL interactions.
*   **Validation**: [Pydantic v2](https://docs.pydantic.dev/) for data integrity and settings management.
*   **Security**: 
    *   `python-jose`: JWT (JSON Web Tokens) for stateless authentication.
    *   `passlib`: Bcrypt hashing for secure password storage.
    *   `python-multipart`: Handling file uploads (e.g., CSV bulk creation).
*   **Data Processing**: `pandas` for handling bulk Excel/CSV data for students and teachers.
*   **PDF Generation**: `reportlab` for exporting grade books and certificates.

### **Frontend (Vanilla Web Standards)**
*   **Structure**: Semantic HTML5.
*   **Styling**: [Bootstrap 5.3](https://getbootstrap.com/) for responsive layouts and components.
*   **Icons**: [Bootstrap Icons](https://icons.getbootstrap.com/).
*   **Logic**: Pure JavaScript (ES6+) utilizing asynchronous `fetch` for API communication.
*   **Theming**: Custom Light/Dark mode implementation with persistent storage via `localStorage`.

---

## 🏗️ System Interactions

The application follows a strict **Controller-Service-Repository** pattern:
1.  **Routers (`routers/`)**: Handle incoming HTTP requests, dependency injection (authentication/DB sessions), and return structured JSON responses via Pydantic schemas.
2.  **Services (`services/`)**: Contain the core business logic. All database mutations and external system interactions (like writing logs or emitting notifications) occur here.
3.  **Schemas (`schemas/`)**: Define the data contracts for requests and responses, ensuring strict typing between frontend and backend.
4.  **Models (`models/`)**: Define the MySQL database structure using SQLAlchemy classes.

---

## 📡 API Endpoints & Functions

### **1. Authentication (`/api/auth`)**
*   **`POST /login`**: Validates credentials and sets `access_token` and `refresh_token` as HttpOnly cookies. Resolves concurrent session conflicts.
*   **`POST /logout`**: Clears authentication cookies and invalidates the active session in the database.
*   **`POST /refresh`**: Rotates the current access token using a valid refresh token.
*   **`GET /me`**: Returns the profile of the currently logged-in user, including role and whether a password reset is required.
*   **`POST /change-password`**: Updates the user's password. Clears any "reset pending" flag on the account.

### **2. Administrative Console (`/api/admin`)**
*   **`GET /overview-stats`**: Aggregates system metrics (user counts, course status, exam totals) and recent logs for the dashboard.
*   **`GET /users`**: Paginated retrieval of users with support for role and status filtering.
*   **`POST /users/single`**: Manual creation of a single user account.
*   **`POST /users/bulk-students`**: Automated generation of student accounts based on range parameters (e.g., Year/Branch).
*   **`POST /users/bulk-teachers`**: Ingests a CSV file to create multiple teacher accounts in one transaction.
*   **`POST /users/bulk-deactivate`**: Batch deactivates student accounts based on graduation conditions.
*   **`POST /users/bulk-activate`**: Batch reactivates account access.
*   **`PATCH /users/{id}/toggle-active`**: Enables or disables a specific user account.
*   **`POST /users/{id}/force-reset`**: Triggers a mandatory "change password" flow for the user on their next login attempts.
*   **`POST /courses`**: Initializes a new course catalog entry.
*   **`GET /courses`**: Retrieves the list of all courses with their current activation status.
*   **`PATCH /courses/{id}/toggle`**: Toggles whether a course is accepting enrollments.
*   **`POST /courses/enroll`**: Maps students to courses (supports single ID or bulk range).
*   **`POST /teachers/assign`**: Links teachers to their respective course responsibilities.
*   **`GET /system-logs`**: Audit trail of low-level application events.
*   **`GET /audit-logs`**: High-level log of administrative interventions and security changes.

### **3. Teacher Operations (`/api/teacher`)**
*   **`GET /courses`**: Returns courses specifically assigned to the authenticated teacher.
*   **`POST /exams`**: Creates a new examination draft linked to a specific course.
*   **`GET /exams`**: Lists all examinations created by the teacher.
*   **`PATCH /exams/{id}`**: Updates exam window, duration, or grading rules (only allowed for unpublished drafts).
*   **`POST /exams/{id}/publish`**: Enforces validation (requires at least 1 question) and makes the exam visible to students.
*   **`POST /exams/{id}/questions/mcq`**: Adds a Multiple Choice Question with automated marking support.
*   **`POST /exams/{id}/questions/subjective`**: Adds an essay/short-answer question for manual grading.
*   **`DELETE /questions/{id}`**: Removes a question and automatically re-calculates the `total_marks` for the associated exam.

### **4. Notifications (`/api/notifications`)**
*   **`GET /`**: Paginated list of user-specific notifications (Exam alerts, Result announcements).
*   **`GET /unread-count`**: Lightweight endpoint used for front-end bell icon badge polling (default: 30s).
*   **`POST /mark-read`**: Clears unread markers for specific notifications or the entire inbox.
*   **`DELETE /{id}`**: Removes a notification from the user's view.

---

## 🗄️ Database Management

New scripts are provided in the `app/scripts/` directory to help with development and testing:

*   **`reset.py`**: Drops all existing tables and recreates them based on the current SQLAlchemy models. Useful for wiping the database clean.
    ```bash
    # Run from the 'app' directory
    python scripts/reset.py
    ```

*   **`seed.py`**: Populates the database with initial data including:
    *   System Admin (`admin@clg.ac.in`)
    *   Schools and Branches
    *   Sample Teachers and Students
    *   Sample Courses, Assignments, and Enrollments
    *   A Sample Exam with Questions
    ```bash
    # Run from the 'app' directory
    python scripts/seed.py
    ```

---

## 🔒 Technical Constraints & Security Rules

1.  **Concurrency Control**:
    *   `Exam` configurations cannot have overlapping time blocks within the same course.
    *   Published exams are **immutable** to preserve academic integrity.

2.  **Stateless sessions**:
    *   Authentication is handled via JWT in HttpOnly cookies to prevent XSS-based token theft.

3.  **Data Integrity**:
    *   Automatic `total_marks` recomputation on the `Exam` entity occurs whenever questions are modified.

4.  **Error Handling**:
    *   Global exception handlers in `main.py` capture tracebacks in development mode and return clean JSON errors to the frontend.
