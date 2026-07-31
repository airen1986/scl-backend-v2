# Scheduler API - Current Backend Contract

## Overview

This document describes the scheduler endpoints that are currently implemented in the backend. It intentionally focuses on the API surface that is available today and omits aspirational or not-yet-implemented behavior.

**Base URL:** `/api/scheduler`

**Authentication:** Every endpoint requires a valid auth token via the `_get_user_from_token` dependency.

**HTTP method:** All implemented scheduler routes use `POST`.

**Timezone note:** API responses expose UTC datetimes as ISO 8601 strings such as `2026-07-30T07:00:00Z`. The scheduler database stores the same values in SQLite text format as `YYYY-MM-DD HH:MM:SS`.

---

## Supported endpoints

### 1. List tasks

**POST `/api/scheduler/tasks`**

Returns the registered task definitions from the scheduler task table.

**Request body:** `{}`

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

### 2. List schedules

**POST `/api/scheduler/schedules`**

Returns schedules joined with their task metadata. `SUPER_ADMIN` users receive all schedules; other users receive only schedules where `created_by` matches their user email.

**Request body:** `{}`

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

### 3. Update a schedule

**POST `/api/scheduler/schedule/update`**

Updates an existing schedule.

**Request body:**
```json
{
  "schedule_id": 1,
  "schedule_description": "Task is running every 15 minutes",
  "schedule_type": "cron",
  "cron_expression": "*/15 * * * *",
  "is_enabled": 0
}
```

**Behavior:**
- `is_enabled` can be toggled on or off.
- `cron_expression` can be changed.
- Only cron schedules are supported.
- Updates are rejected while the schedule is already running.
- A duplicate schedule check is applied before saving the update.

**Response:**
```json
{
  "next_run_at": "2026-07-30T07:15:00Z",
  "message": "Schedule updated successfully"
}
```

---

### 4. List execution history

**POST `/api/scheduler/executions`**

Returns execution rows with optional filters. `SUPER_ADMIN` users can view all execution history and may filter by `created_by`; other users receive only execution history for schedules where `created_by` matches their user email.

**Request body:**
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

**Filters:**
- `schedule_id`
- `task_name`
- `created_by` (`SUPER_ADMIN` only; ignored for other roles)
- `status`
- `started_from`
- `started_to`
- `limit` and `offset` for pagination

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

### 5. Get one execution

**POST `/api/scheduler/execution`**

Returns a single execution record. `SUPER_ADMIN` users can retrieve any execution; other users can retrieve only executions for their own schedules.

**Request body:**
```json
{
  "execution_id": 101
}
```

**Response:** Same shape as one item in the execution list response.

---

### 6. Validate a cron expression

**POST `/api/scheduler/cron/validate`**

Validates a cron string and returns a human-readable description plus preview run times.

**Request body:**
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
  "description": "Every 10 minutes",
  "next_runs": [
    "2026-07-30T07:10:00Z",
    "2026-07-30T07:20:00Z",
    "2026-07-30T07:30:00Z"
  ],
  "message": null
}
```

---

### 7. Get scheduler status

**POST `/api/scheduler/status`**

Returns the current scheduler status summary.

**Request body:** `{}`

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

### 8. Run a schedule immediately

**POST `/api/scheduler/schedule/run`**

Queues a manual execution for an enabled schedule.

**Request body:**
```json
{
  "schedule_id": 5
}
```

**Response:**
```json
{
  "execution_id": 102,
  "message": "Schedule queued for execution"
}
```

---

## Current behavior notes

- The scheduler runner is a separate process and the API only exposes management and inspection endpoints.
- Cron schedules compute a new `next_run_at` after execution.
- A schedule cannot be run concurrently while its `is_running` flag is already set.

---

## Not currently implemented

The following capabilities are not available in the current backend implementation and are therefore not documented as supported API behavior:

- Create-schedule endpoint
- Delete-schedule endpoint
- Separate enable/disable route
- One-time and startup schedule types
- Custom error envelope with `code` and `request_id`
- Frontend UI/page structure or client-side workflow documentation
