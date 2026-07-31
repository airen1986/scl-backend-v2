import json
from datetime import datetime, timedelta, timezone
from typing import Any

from croniter import CroniterBadCronError, croniter
from fastapi import HTTPException

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


def _validate_schedule_fields(
    schedule_type: str,
    cron_expression: str | None,
) -> str | None:
    cron_expression = cron_expression.strip() if cron_expression else None
    if schedule_type != "cron":
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

    schedule_type = row[5]
    new_cron_expression = row[6]
    if request.cron_expression is not None:
        new_cron_expression = request.cron_expression.strip()
    new_is_enabled = row[7] if request.is_enabled is None else request.is_enabled

    next_run_at = _validate_schedule_fields(schedule_type, new_cron_expression)
    existing_task_params = _normalize_json(_loads_json(row[4])) if row[4] is not None else "{}"
    duplicate = cursor.execute(
        scheduler_queries.find_duplicate_schedule,
        (
            task_id,
            existing_task_params,
            schedule_type,
            new_cron_expression,
            request.schedule_id,
        ),
    ).fetchone()
    if duplicate:
        raise HTTPException(status_code=409, detail="Duplicate schedule")

    cursor.execute(
        scheduler_queries.update_schedule,
        (
            new_cron_expression,
            new_is_enabled,
            next_run_at,
            request.schedule_id,
        ),
    )
    return _api_datetime(next_run_at)


def run_schedule(
    cursor,
    user_email: str,
    role_name: str,
    request: scheduler_schemas.RunScheduleRequest,
) -> str:
    row = _get_schedule_row(cursor, request.schedule_id)
    created_by = row[11]
    is_running = row[8]
    is_enabled = row[7]
    _check_schedule_owner(created_by, user_email, role_name)
    if is_running == 1:
        raise HTTPException(status_code=409, detail="Cannot run a running schedule")
    if is_enabled != 1:
        raise HTTPException(status_code=400, detail="Schedule is disabled")

    next_run_at = (datetime.now(timezone.utc) + timedelta(seconds=1)).strftime(DB_TIME_FORMAT)
    cursor.execute(scheduler_queries.update_next_run_at, (next_run_at, request.schedule_id))
    return _api_datetime(next_run_at) or next_run_at


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
    if not _is_super_admin(role_name):
        where_clauses.append("sj.CreatedBy = ?")
        params.append(user_email)

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
