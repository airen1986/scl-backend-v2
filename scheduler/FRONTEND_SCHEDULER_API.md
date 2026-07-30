# Scheduler API - Frontend Integration Document

## Overview

The Scheduler system manages recurring background jobs for the Supply Chain Lite backend. It consists of **TaskMaster** records (what to run), **ScheduledJobs** records (when to run), and **JobExecutions** records (execution history). The scheduler runs as a separate async process that polls the database for due jobs.

**Base URL:** `/api/scheduler`

**Authentication:** All endpoints require a valid auth token via `_get_user_from_token` dependency.

**HTTP Method:** All scheduler API endpoints use `POST`, including list, detail, update, and delete operations. Frontend clients should send JSON request bodies for every scheduler endpoint; use `{}` when no filters or parameters are needed.

**Timezone Policy:** All datetime values sent to or returned from the scheduler API must be UTC ISO 8601 strings. Frontend clients should convert to the user's local timezone only for display.

Example: `2026-07-30T07:00:00Z`

---

## Database Schema

### SJ_TaskMaster (Programs/Tasks)

| Column | Type | Description |
|--------|------|-------------|
| TaskId | INTEGER (PK, AUTO) | Unique task identifier |
| TaskName | TEXT (UNIQUE) | Program name (e.g. `celery_task_update`) |
| TaskDescription | TEXT | Human-readable description |
| MaxRetries | INTEGER | Max retry attempts on failure (default: 3) |
| TimeoutSeconds | INTEGER | Max execution time in seconds (default: 300) |
| JSONData | TEXT | Extensible JSON metadata |
| CreatedAt | TEXT | UTC ISO datetime |
| UpdatedAt | TEXT | UTC ISO datetime |

### SJ_ScheduledJobs (Schedules)

| Column | Type | Description |
|--------|------|-------------|
| ScheduleId | INTEGER (PK, AUTO) | Unique schedule identifier |
| TaskId | INTEGER (FK -> SJ_TaskMaster) | Linked task |
| ScheduleDescription | TEXT | Human-readable schedule description |
| TaskParams | TEXT | JSON string of parameters for this schedule. API requests/responses expose this as a JSON object. |
| ScheduleType | TEXT | `cron`, `run_once`, or `run_at_startup` |
| CronExpression | TEXT | Standard cron expression (minute hour dom month dow) |
| IsEnabled | INTEGER | 1 = active, 0 = disabled |
| IsRunning | INTEGER | 1 = currently executing, 0 = idle |
| LastRunAt | TEXT | UTC ISO datetime of last execution |
| NextRunAt | TEXT | UTC ISO datetime of next scheduled run |
| CreatedBy | TEXT | User who created the schedule (nullable for seeded data) |
| JSONData | TEXT | Extensible JSON metadata |
| CreatedAt | TEXT | UTC ISO datetime |
| UpdatedAt | TEXT | UTC ISO datetime |

### SJ_JobExecutions (Execution Log)

| Column | Type | Description |
|--------|------|-------------|
| ExecutionId | INTEGER (PK, AUTO) | Unique execution identifier |
| ScheduleId | INTEGER (FK) | Linked schedule |
| TaskId | INTEGER (FK) | Linked task |
| TaskName | TEXT | Denormalized task name |
| Status | TEXT | `running`, `success`, or `failed` |
| StartedAt | TEXT | UTC ISO datetime |
| CompletedAt | TEXT | UTC ISO datetime (null if still running) |
| DurationSeconds | REAL | Execution time in seconds |
| RetryCount | INTEGER | Number of retries attempted |
| ErrorMessage | TEXT | Error details if failed |
| ResultData | TEXT | JSON result output. API responses expose this as a JSON object when possible. |
| JSONData | TEXT | Extensible JSON metadata |

---

## Registered Programs (Tasks)

| Task Name | Description | Default Cron | Schedule Type |
|-----------|-------------|--------------|---------------|
| `celery_task_update` | Updates task statuses from Celery broker | `* * * * *` (every minute) | cron |
| `cleanup_temp_files` | Cleans temp files, logs, vacuums DBs | `0 * * * *` (hourly) | cron |
| `revoke_stale_tasks` | Revokes PENDING tasks stuck > timeout | `*/5 * * * *` (every 5 min) | cron |
| `cancel_long_running_tasks` | Cancels tasks exceeding max run time | `*/5 * * * *` (every 5 min) | cron |

### Schedule Types

- **`cron`** - Runs on a recurring schedule defined by a cron expression
- **`run_once`** - Executes once at `run_at` / `next_run_at`, then auto-disables (IsEnabled -> 0)
- **`run_at_startup`** - Executes when the scheduler process starts; only system/admin schedules should use this type

---

## Scheduler Execution Code Mapping

The frontend API contract is designed around the current scheduler execution code in the `scheduler` package:

| Contract Area | Current Code |
|---------------|--------------|
| Database tables and seed schedules | `scheduler/database.py` creates `SJ_TaskMaster`, `SJ_ScheduledJobs`, and `SJ_JobExecutions`, then seeds records from `scheduler/task_init_data.py`. |
| Existing schedule description refresh | `scheduler/database.py` derives cron schedule descriptions with `cron-descriptor` during `init_scheduler_db()` and updates existing cron schedules. |
| Enabled schedule lookup | `scheduler/methods.py` reads enabled jobs with `get_enabled_jobs()`, backed by `scheduler/queries.py`. |
| Due-job detection | `scheduler/runner.py` checks `ScheduleType`, `LastRunAt`, and `NextRunAt` before execution. |
| Cron next-run calculation | `scheduler/runner.py` uses `croniter` to calculate the next `NextRunAt`. |
| Task execution | `scheduler/tasks.py` maps `TaskName` to async task handlers and executes them via `run_task()`. |
| Execution logging | `scheduler/methods.py` creates and updates rows in `SJ_JobExecutions`. |
| Running guard | `scheduler/methods.py` atomically flips `IsRunning` from 0 to 1 before logging a running execution. |

The scheduler execution layer exists today. The `/api/scheduler/*` FastAPI router described below is still a frontend integration contract and needs to be implemented separately before the UI can call it.

---

## API Endpoints

### 1. List All Programs (Tasks)

**`POST /api/scheduler/tasks`**

Returns all registered task definitions from `SJ_TaskMaster`.

**Request Body:** `{}` (empty, no filters needed)

**Response:**
```json
{
  "tasks": [
    {
      "task_id": 1,
      "task_name": "celery_task_update",
      "task_description": "Celery task update job",
      "max_retries": 3,
      "timeout_seconds": 300
    }
  ]
}
```

---

### 2. List All Schedules

**`POST /api/scheduler/schedules`**

**Request Body:** `{}` (empty, no filters needed)

**Response:**
```json
{
  "schedules": [
    {
      "schedule_id": 1,
      "schedule_description": "Running every minute",
      "task_id": 1,
      "task_name": "celery_task_update",
      "task_params": {},
      "schedule_type": "cron",
      "cron_expression": "* * * * *",
      "is_enabled": 1,
      "is_running": 0,
      "last_run_at": "2026-07-30T07:00:00Z",
      "next_run_at": "2026-07-30T07:01:00Z",
      "created_by": "admin"
    }
  ]
}
```

---

### 3. Create Schedule

**`POST /api/scheduler/schedule/create`**

Creates a new schedule for an existing task.

**Request Body:**
```json
{
  "task_id": 1,
  "schedule_description": "Run celery task updates every 10 minutes",
  "task_params": {},
  "schedule_type": "cron",
  "cron_expression": "*/10 * * * *",
  "run_at": null,
  "is_enabled": 1
}
```

**Validation Rules:**
- `task_id` must exist in `SJ_TaskMaster`
- `schedule_type` must be one of: `cron`, `run_once`, `run_at_startup`
- `cron_expression` is required when `schedule_type` is `cron`
- `cron_expression` must be null/empty for `run_once` and `run_at_startup`
- `run_at` is required when `schedule_type` is `run_once`; backend stores it as `NextRunAt`
- `run_at` must be null/omitted for `cron` and `run_at_startup`
- Duplicate check: cannot create same `task_id` + `task_params` + `schedule_type` + `cron_expression` + `run_at`
- `task_params` must be a JSON object in API requests and responses; backend serializes it to `SJ_ScheduledJobs.TaskParams`
- `created_by` is taken from auth cookie; user must have Admin or SUPER_ADMIN role to create a schedule
- `run_at_startup` schedules should be restricted to SUPER_ADMIN users unless the backend explicitly allows Admin users

**Response:**
```json
{
  "schedule_id": 5,
  "next_run_at": "2026-07-30T07:10:00Z",
  "message": "Schedule created successfully"
}
```

---

### 4. Update Schedule

**`POST /api/scheduler/schedule/update`**

Updates an existing schedule's configuration.

**Request Body:**
```json
{
  "schedule_id": 1,
  "schedule_description": "Task is running every 15 minutes",
  "schedule_type": "cron",
  "cron_expression": "*/15 * * * *",
  "run_at": null,
  "is_enabled": 0
}
```

**Rules:**
- Can toggle `is_enabled` to enable/disable a schedule
- Can change `cron_expression` and `schedule_type`
- `run_at` is required when changing `schedule_type` to `run_once`
- Cannot modify `is_running` (managed by scheduler)
- Cannot modify `last_run_at` or `next_run_at` directly (managed by scheduler)
- Backend recalculates `next_run_at` when a cron expression changes or a disabled schedule is re-enabled
- Schedule can be updated only when `created_by` matches the current user or the current user is SUPER_ADMIN
- Backend should reject updates to schedules where `is_running = 1`

**Response:**
```json
{
  "next_run_at": "2026-07-30T07:15:00Z",
  "message": "Schedule updated successfully"
}
```

---

### 5. Delete Schedule

**`POST /api/scheduler/schedule/delete`**

Deletes a schedule by ID using a POST request. Does not delete the task definition.

**Request Body:**
```json
{
  "schedule_id": 5
}
```

**Rules:**
- Schedule can be deleted only when `created_by` matches the current user or the current user is SUPER_ADMIN
- Backend should reject deletion when `is_running = 1`

**Response:**
```json
{
  "message": "Schedule deleted successfully"
}
```

---

### 6. Get Job Execution History

**`POST /api/scheduler/executions`**

Returns job execution logs with optional filters.

**Request Body:**
```json
{
  "schedule_id": null,
  "task_name": null,
  "created_by": null,
  "status": null,
  "started_from": null,
  "started_to": null,
  "limit": 50,
  "offset": 0
}
```

**Filters (all optional):**
- `schedule_id` - Filter by specific schedule
- `task_name` - Filter by task name
- `created_by` - Filter by user
- `status` - Filter by status: `running`, `success`, `failed`
- `started_from` - UTC ISO datetime lower bound for `started_at`
- `started_to` - UTC ISO datetime upper bound for `started_at`
- `limit` - Max results (default 50, max 200)
- `offset` - Pagination offset

**Response:**
```json
{
  "executions": [
    {
      "execution_id": 101,
      "schedule_id": 1,
      "task_id": 1,
      "task_name": "celery_task_update",
      "status": "success",
      "started_at": "2026-07-30T07:00:00Z",
      "completed_at": "2026-07-30T07:00:02Z",
      "duration_seconds": 2.34,
      "retry_count": 0,
      "error_message": null,
      "result_data": {"status": "completed"}
    }
  ],
  "total_count": 150
}
```

---

### 7. Get Execution Detail

**`POST /api/scheduler/execution`**

Returns full details of a single execution using a POST request.

**Request Body:**
```json
{
  "execution_id": 101
}
```

**Response:** Same as single item from Executions list.

---

### 8. Validate Cron Expression

**`POST /api/scheduler/cron/validate`**

Validates a cron expression and returns upcoming run times for preview.

**Request Body:**
```json
{
  "cron_expression": "*/10 * * * *",
  "count": 5
}
```

**Response:**
```json
{
  "is_valid": true,
  "next_runs": [
    "2026-07-30T07:10:00Z",
    "2026-07-30T07:20:00Z",
    "2026-07-30T07:30:00Z"
  ],
  "message": null
}
```

---

### 9. Get Scheduler Status

**`POST /api/scheduler/status`**

Returns dashboard-level health for the separate scheduler process.

**Request Body:** `{}` (empty, no filters needed)

**Response:**
```json
{
  "is_alive": true,
  "last_poll_at": "2026-07-30T07:00:00Z",
  "enabled_schedules": 4,
  "running_schedules": 1,
  "last_execution_status": "success"
}
```

---

### 10. Run Schedule Now

**`POST /api/scheduler/schedule/run`**

Manually triggers an enabled schedule immediately. This should use the same running guard as the scheduler loop.

**Request Body:**
```json
{
  "schedule_id": 5
}
```

**Rules:**
- User must have permission to update the schedule
- Backend should reject the request when `is_running = 1`
- Manual execution should create an `SJ_JobExecutions` row
- Cron schedules keep their existing future `next_run_at` unless the backend intentionally recalculates it

**Response:**
```json
{
  "execution_id": 102,
  "message": "Schedule queued for execution"
}
```

---

## Error Response Format

All scheduler endpoints should return a consistent error body:

```json
{
  "detail": "Invalid cron expression",
  "code": "INVALID_CRON",
  "request_id": "7f9f1e7a-9f3a-4c1a-9c4d-2f8e7d8c0b11"
}
```

Common status codes:
- `400` - Invalid request, invalid cron expression, invalid schedule type, invalid JSON
- `401` - Missing or invalid authentication
- `403` - User does not have permission for this scheduler operation
- `404` - Task, schedule, or execution not found
- `409` - Duplicate schedule or schedule is already running
- `422` - Request body shape is invalid

---

## Frontend UI Components

### Scheduler Dashboard

The main scheduler page should display:

1. **Status Bar**
   - Fields: Scheduler Health, Last Poll, Enabled Schedules, Running Schedules, Last Execution Status

2. **Programs Table** (`SJ_TaskMaster`)
   - Columns: Task Name, Description, Max Retries, Timeout, Actions
   - Actions: View Schedules, Create Schedule

3. **Schedules Table** (`SJ_ScheduledJobs`)
   - Columns: Task Name, Schedule Type, Cron Expression / Run At, Enabled Toggle, Status, Last Run, Next Run, Created By, Actions
   - Actions: Edit, Enable/Disable Toggle, Run Now, Delete
   - Show visual indicator when `is_running = 1`

4. **Execution History Table** (`SJ_JobExecutions`)
   - Columns: Task Name, Status (color-coded), Started At, Duration, Retries, Error (expandable)
   - Filters: By task, by user, by status, by date range
   - Pagination

### Cron Expression Helper

Provide a UI helper for building cron expressions:
```text
#  * * * * *
#  | | | | |
#  | | | | +-- day of week (0-6, Sun=0)
#  | | | +---- month (1-12)
#  | | +------ day of month (1-31)
#  | +-------- hour (0-23)
#  +---------- minute (0-59)
* * * * *
```

**Common presets:**
- Every minute: `* * * * *`
- Every 5 minutes: `*/5 * * * *`
- Every hour: `0 * * * *`
- Daily at midnight: `0 0 * * *`
- Weekly Sunday: `0 0 * * 0`
- Monthly 1st: `0 0 1 * *`

### Status Indicators

- **Enabled/Disabled:** Toggle switch
- **Running:** Spinner/pulse animation when `is_running = 1`
- **Execution Status:**
  - `success` - Green badge
  - `failed` - Red badge
  - `running` - Blue badge with spinner

---

## Sample Frontend Page Structure

```text
/scheduler
|-- Status Bar
|   |-- Scheduler health | Running schedules | Last poll
|-- Programs Tab
|   |-- [Table] Task Name | Description | Retries | Timeout | Actions
|-- Schedules Tab
|   |-- [Table] Task | Type | Cron/Run At | Enabled | Status | Last/Next Run | Created By | Actions
|   |-- [Modal] Create/Edit Schedule
|       |-- Task (dropdown from TaskMaster)
|       |-- Schedule Type (radio: cron / run_once / run_at_startup)
|       |-- Cron Expression (text + helper widget + validation preview)
|       |-- Run At (UTC datetime input for run_once)
|       |-- Task Params (JSON editor)
|       |-- Enabled (checkbox)
|-- Executions Tab
    |-- [Filters] Task Name | Created By | Status | Date Range
    |-- [Table] Task | Status | Started | Duration | Retries | Error
    |-- [Detail Modal] Full execution details + ResultData JSON viewer
```

---

## Key Behavioral Notes

1. **Scheduler runs separately:** `python -m scheduler.runner [poll_interval_seconds]`
2. **Polling interval:** Default 60 seconds. The scheduler checks for due jobs every N seconds.
3. **Startup jobs:** `run_at_startup` tasks execute immediately when scheduler starts, before entering main loop.
4. **Auto-disable:** `run_once` schedules are automatically disabled (IsEnabled -> 0) after execution.
5. **Next run calculation:** For cron schedules, `NextRunAt` is computed from the cron expression after each successful run and when a cron schedule is created, edited, or re-enabled.
6. **Concurrency:** Multiple due jobs run concurrently via `asyncio.gather`.
7. **Retry logic:** Failed tasks retry with exponential backoff (2^retry_count seconds).
8. **Running guard:** A schedule cannot execute if `IsRunning = 1` (prevents overlapping runs).
9. **Cleanup task** also handles: vacuuming SQLite DBs, deleting old execution logs, cleaning SQL history, and creating system backups.
