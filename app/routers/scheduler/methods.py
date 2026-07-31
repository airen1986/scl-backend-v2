import json
from datetime import datetime, timezone
from typing import Any

from cron_descriptor import CasingTypeEnum, ExpressionDescriptor, Options
from croniter import CroniterBadCronError, croniter
from fastapi import HTTPException

from scheduler import methods as scheduler_db_methods
from scheduler import queries as runner_queries
from scheduler.runner import execute_single_task

from . import queries as scheduler_queries
from . import schemas as scheduler_schemas

DB_TIME_FORMAT = "%Y-%m-%d %H:%M:%S"


def _normalize_json(value: dict[str, Any]) -> str:
    return json.dumps(value or {}, sort_keys=True, separators=(",", ":"))


_JSON_FALLBACK_UNSET = object()


def _loads_json(value: str | None, fallback: Any = _JSON_FALLBACK_UNSET) -> Any:
    if value is None or value == "":
        return {} if fallback is _JSON_FALLBACK_UNSET else fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _parse_api_datetime(value: str | None, field_name: str) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{field_name} must be a valid UTC ISO 8601 datetime")
    if parsed.tzinfo is None:
        raise HTTPException(status_code=400, detail=f"{field_name} must include a UTC timezone")
    return parsed.astimezone(timezone.utc)


def _db_datetime(value: str | None, field_name: str) -> str | None:
    parsed = _parse_api_datetime(value, field_name)
    if parsed is None:
        return None
    return parsed.strftime(DB_TIME_FORMAT)


def _api_datetime(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.strptime(value, DB_TIME_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return value
    return parsed.isoformat().replace("+00:00", "Z")


def _next_cron_run(cron_expression: str) -> str:
    try:
        return croniter(cron_expression, datetime.now(timezone.utc)).get_next(datetime).strftime(DB_TIME_FORMAT)
    except CroniterBadCronError:
        raise HTTPException(status_code=400, detail="Invalid cron expression")


def _cron_description(cron_expression: str) -> str | None:
    options = Options()
    options.casing_type = CasingTypeEnum.Sentence
    options.use_24hour_time_format = True
    try:
        return ExpressionDescriptor(cron_expression, options).get_description()
    except Exception:
        return None


def _validate_schedule_fields(
    schedule_type: scheduler_schemas.ScheduleType,
    cron_expression: str | None,
) -> str | None:
    cron_expression = cron_expression.strip() if cron_expression else None
    if schedule_type != scheduler_schemas.ScheduleType.CRON:
        raise HTTPException(status_code=400, detail="Only cron schedules are supported")
    if not cron_expression:
        raise HTTPException(status_code=400, detail="cron_expression is required for cron schedules")
    return _next_cron_run(cron_expression)


def _execution_item(row) -> scheduler_schemas.ExecutionItem:
    return scheduler_schemas.ExecutionItem(
        execution_id=row[0],
        schedule_id=row[1],
        task_id=row[2],
        task_name=row[3],
        status=row[4],
        started_at=_api_datetime(row[5]) or row[5],
        completed_at=_api_datetime(row[6]),
        duration_seconds=row[7],
        retry_count=row[8],
        error_message=row[9],
        result_data=_loads_json(row[10], fallback=None),
    )


def list_tasks(cursor) -> list[scheduler_schemas.TaskItem]:
    rows = cursor.execute(scheduler_queries.list_tasks).fetchall()
    return [
        scheduler_schemas.TaskItem(
            task_id=row[0],
            task_name=row[1],
            task_description=row[2],
            max_retries=row[3],
            timeout_seconds=row[4],
        )
        for row in rows
    ]


def _is_super_admin(role_name: str) -> bool:
    return role_name == "SUPER_ADMIN"


def list_schedules(cursor, user_email: str, role_name: str) -> list[scheduler_schemas.ScheduleItem]:
    schedules = []
    query = scheduler_queries.list_schedules
    params = ()
    if not _is_super_admin(role_name):
        query = scheduler_queries.list_schedules_for_owner
        params = (user_email,)
    for row in cursor.execute(query, params).fetchall():
        schedule_item = scheduler_schemas.ScheduleItem(
            schedule_id=row[0],
            schedule_description=row[1],
            task_id=row[2],
            task_name=row[3],
            task_params=_loads_json(row[4]),
            schedule_type=row[5],
            cron_expression=row[6],
            is_enabled=row[7],
            is_running=row[8],
            last_run_at=_api_datetime(row[9]),
            next_run_at=_api_datetime(row[10]),
            created_by=row[11],
        )
        schedules.append(schedule_item)
    return schedules


def _get_schedule_row(cursor, schedule_id: int):
    row = cursor.execute(scheduler_queries.get_schedule, (schedule_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return row


def _check_schedule_owner(created_by: str, user_email: str, role_name: str) -> None:
    if not _is_super_admin(role_name) and created_by != user_email:
        raise HTTPException(status_code=403, detail="You do not have permission to modify this schedule")


def update_schedule(
    cursor,
    user_email: str,
    role_name: str,
    request: scheduler_schemas.UpdateScheduleRequest,
) -> str | None:
    row = _get_schedule_row(cursor, request.schedule_id)
    created_by = row[11]
    is_running = row[8]
    task_id = row[1]
    _check_schedule_owner(created_by, user_email, role_name)
    if is_running == 1:
        raise HTTPException(status_code=409, detail="Cannot update a running schedule")
    next_run_at = _validate_schedule_fields(request.schedule_type, request.cron_expression)
    task_params = _normalize_json(request.task_params) if request.task_params is not None else row[4] or "{}"
    duplicate = cursor.execute(
        scheduler_queries.find_duplicate_schedule,
        (
            task_id,
            task_params,
            request.schedule_type.value,
            request.cron_expression,
            request.schedule_id,
        ),
    ).fetchone()
    if duplicate:
        raise HTTPException(status_code=409, detail="Duplicate schedule")

    description = _cron_description(request.cron_expression or "")

    cursor.execute(
        scheduler_queries.update_schedule,
        (
            description,
            task_params,
            request.schedule_type.value,
            request.cron_expression,
            request.is_enabled,
            next_run_at,
            request.schedule_id,
        ),
    )
    return _api_datetime(next_run_at)


def list_executions(
    cursor,
    user_email: str,
    role_name: str,
    request: scheduler_schemas.ExecutionFiltersRequest,
) -> tuple[list, int]:
    where_clauses = []
    params: list[Any] = []
    if request.schedule_id is not None:
        where_clauses.append("je.ScheduleId = ?")
        params.append(request.schedule_id)
    if request.task_name:
        where_clauses.append("je.TaskName = ?")
        params.append(request.task_name)
    if _is_super_admin(role_name) and request.created_by:
        where_clauses.append("sj.CreatedBy = ?")
        params.append(request.created_by)
    elif not _is_super_admin(role_name):
        where_clauses.append("sj.CreatedBy = ?")
        params.append(user_email)
    if request.status:
        where_clauses.append("je.Status = ?")
        params.append(request.status.value)
    if request.started_from:
        where_clauses.append("je.StartedAt >= ?")
        params.append(_db_datetime(request.started_from, "started_from"))
    if request.started_to:
        where_clauses.append("je.StartedAt <= ?")
        params.append(_db_datetime(request.started_to, "started_to"))

    where_sql = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    count_query = f"SELECT COUNT(*) {scheduler_queries.execution_base}{where_sql}"
    list_query = f"""SELECT je.ExecutionId, je.ScheduleId, je.TaskId, je.TaskName, je.Status,
                     je.StartedAt, je.CompletedAt, je.DurationSeconds, je.RetryCount,
                     je.ErrorMessage, je.ResultData
                     {scheduler_queries.execution_base}
                     {where_sql}
                     ORDER BY je.ExecutionId DESC
                     LIMIT ? OFFSET ?"""
    total_count = cursor.execute(count_query, tuple(params)).fetchone()[0]
    rows = cursor.execute(list_query, (*params, request.limit, request.offset)).fetchall()
    return [_execution_item(row) for row in rows], total_count


def get_execution(cursor, user_email: str, role_name: str, execution_id: int) -> scheduler_schemas.ExecutionItem:
    row = cursor.execute(scheduler_queries.get_execution, (execution_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Execution not found")
    created_by = row[11]
    if not _is_super_admin(role_name) and created_by != user_email:
        raise HTTPException(status_code=404, detail="Execution not found")
    return _execution_item(row)


def validate_cron(cron_expression: str, count: int) -> scheduler_schemas.CronValidateResponse:
    try:
        iterator = croniter(cron_expression, datetime.now(timezone.utc))
        next_runs = [iterator.get_next(datetime).isoformat().replace("+00:00", "Z") for _ in range(count)]
    except Exception as exc:
        return scheduler_schemas.CronValidateResponse(is_valid=False, description=None, next_runs=[], message=str(exc))
    return scheduler_schemas.CronValidateResponse(
        is_valid=True,
        description=_cron_description(cron_expression),
        next_runs=next_runs,
        message=None,
    )


def get_scheduler_status(cursor) -> scheduler_schemas.SchedulerStatusResponse:
    enabled, running, last_started, last_status = cursor.execute(scheduler_queries.scheduler_status).fetchone()
    return scheduler_schemas.SchedulerStatusResponse(
        is_alive=True,
        last_poll_at=_api_datetime(last_started),
        enabled_schedules=enabled,
        running_schedules=running,
        last_execution_status=last_status,
    )


def run_schedule_now(cursor, user_email: str, role_name: str, schedule_id: int) -> int:
    row = _get_schedule_row(cursor, schedule_id)
    created_by = row[11]
    task_id = row[1]
    task_name = row[2]
    is_enabled = row[7]
    is_running = row[8]
    execution_id = None
    _check_schedule_owner(created_by, user_email, role_name)
    if is_enabled != 1:
        raise HTTPException(status_code=400, detail="Schedule is disabled")
    if is_running == 1:
        raise HTTPException(status_code=409, detail="Schedule is already running")

    started_at = datetime.now(timezone.utc).strftime(DB_TIME_FORMAT)
    running_guard = cursor.execute(runner_queries.update_schedule_running_status, (1, schedule_id, 0)).fetchone()
    if not running_guard:
        raise HTTPException(status_code=409, detail="Schedule is already running")
    new_row = cursor.execute(
        runner_queries.insert_job_execution,
        (schedule_id, task_id, task_name, "running", started_at, None, None, 0, None, None),
    ).fetchone()
    if not new_row:
        raise HTTPException(status_code=500, detail="Failed to log job execution")
    execution_id = new_row[0]
    return execution_id


async def complete_manual_run(schedule_id: int, execution_id: int) -> None:
    from app.connection import master_connection

    with master_connection() as cursor:
        row = _get_schedule_row(cursor, schedule_id)
    started = datetime.now(timezone.utc)

    task_name = row[2]
    task_params = row[4] or "{}"
    created_by = row[11]
    success, result, error = await execute_single_task(task_name, task_params, 0, created_by)
    completed = datetime.now(timezone.utc)
    completed_at = completed.strftime(DB_TIME_FORMAT)
    duration = (completed - started).total_seconds()
    await scheduler_db_methods.update_job_execution(
        schedule_id,
        execution_id,
        "success" if success else "failed",
        completed_at,
        duration,
        error_message=error,
        result_data=json.dumps(result) if result is not None else None,
    )
    with master_connection() as cursor:
        cursor.execute(scheduler_queries.update_schedule_last_run, (completed_at, schedule_id))
