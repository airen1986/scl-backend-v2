# Scheduler API - Current Backend Contract

## Overview

This document describes the scheduler endpoints that are currently implemented in the backend. It intentionally focuses on the API surface that is available today and omits aspirational or not-yet-implemented behavior.

**Base URL:** `/api/scheduler`

**Authentication:** Every endpoint requires a valid auth token via the `_get_user_from_token` dependency.

**HTTP method:** All implemented scheduler routes use `POST`.

**Timezone note:** API responses expose UTC datetimes as ISO 8601 strings such as `2026-07-30T07:00:00Z`. The scheduler database stores the same values in SQLite text format as `YYYY-MM-DD HH:MM:SS`.

---

## Supported endpoints

### 1. List schedules

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

### 2. Update a schedule

**POST `/api/scheduler/schedule/update`**

Updates an existing schedule.

**Request body:**
```json
{
  "schedule_id": 1,
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

### 3. Run a schedule

**POST `/api/scheduler/run`**

Moves a schedule's `next_run_at` to the current UTC time plus one second. `SUPER_ADMIN` users can run any schedule; other users can run only schedules they created. The update is rejected while the schedule is already running.

**Request body:**
```json
{
  "schedule_id": 1
}
```

**Response:**
```json
{
  "next_run_at": "2026-07-30T07:00:01Z",
  "message": "Schedule queued to run"
}
```

---

### 4. List execution history

**POST `/api/scheduler/executions`**

Returns execution rows. `SUPER_ADMIN` users can view all executions; other users receive only executions for schedules they created. `schedule_id` can narrow the result, while `limit` and `offset` control pagination.

**Request body:**
```json
{
  "schedule_id": 1,
  "limit": 50,
  "offset": 0
}
```

**Filters:**
- `schedule_id`
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

## Current behavior notes

- The scheduler runner is a separate process and the API only exposes management and inspection endpoints.
- Cron schedules compute a new `next_run_at` after execution.
- A schedule cannot be updated while its `is_running` flag is already set.

---

## Not currently implemented

The following capabilities are not available in the current backend implementation and are therefore not documented as supported API behavior:

- Create-schedule endpoint
- Delete-schedule endpoint
- List-tasks endpoint
- Get-one-execution endpoint
- Cron-validation endpoint
- Scheduler-status endpoint
- Separate enable/disable route
- One-time and startup schedule types
- Custom error envelope with `code` and `request_id`
- Frontend UI/page structure or client-side workflow documentation
