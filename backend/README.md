# Beacon AI Backend

## Setup & Run

1.  **Navigate to backend directory**:
    ```bash
    cd backend
    ```

2.  **Create Virtual Environment** (Optional but recommended):
    ```bash
    python -m venv venv
    .\venv\Scripts\Activate.ps1
    ```

3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Environment Variables**:
    Copy `.env.example` to `.env` and update values.
    ```bash
    cp .env.example .env
    ```
    *Note: You need a running PostgreSQL instance for the app to start fully (database connection check).*

5.  **Initialize Database**:
    ```bash
    python -m app.init_db
    ```

6.  **Run Application**:
    ```bash
    python -m app.main
    ```
    The API will be available at `http://localhost:8000`.
    Docs: `http://localhost:8000/api/v1/docs`

6.  **Health Check**:
    GET `http://localhost:8000/health`
