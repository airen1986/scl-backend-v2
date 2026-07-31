from fastapi import APIRouter, BackgroundTasks, Depends

from app.connection import master_connection
from app.routers.auth.methods import _get_user_from_token, check_module_access

from . import methods as scheduler_methods
from . import schemas as scheduler_schemas

router = APIRouter()
this_api = "/api/scheduler"


@router.post("/tasks", response_model=scheduler_schemas.TaskListResponse)
def list_tasks(
    user_data: tuple = Depends(_get_user_from_token),
) -> scheduler_schemas.TaskListResponse:
    _useremail, _display_name, role_name = user_data
    with master_connection() as cursor:
        check_module_access(cursor, role_name, this_api)
        tasks = scheduler_methods.list_tasks(cursor)
    return scheduler_schemas.TaskListResponse(tasks=tasks)


@router.post("/schedules", response_model=scheduler_schemas.ScheduleListResponse)
def list_schedules(
    user_data: tuple = Depends(_get_user_from_token),
) -> scheduler_schemas.ScheduleListResponse:
    useremail, _display_name, role_name = user_data
    with master_connection() as cursor:
        check_module_access(cursor, role_name, this_api)
        schedules = scheduler_methods.list_schedules(cursor, useremail, role_name)
    return scheduler_schemas.ScheduleListResponse(schedules=schedules)


@router.post("/schedule/update", response_model=scheduler_schemas.UpdateScheduleResponse)
def update_schedule(
    request: scheduler_schemas.UpdateScheduleRequest,
    user_data: tuple = Depends(_get_user_from_token),
) -> scheduler_schemas.UpdateScheduleResponse:
    useremail, _display_name, role_name = user_data
    with master_connection() as cursor:
        check_module_access(cursor, role_name, this_api)
        next_run_at = scheduler_methods.update_schedule(cursor, useremail, role_name, request)
    return scheduler_schemas.UpdateScheduleResponse(
        next_run_at=next_run_at,
        message="Schedule updated successfully",
    )


@router.post("/executions", response_model=scheduler_schemas.ExecutionListResponse)
def list_executions(
    request: scheduler_schemas.ExecutionFiltersRequest,
    user_data: tuple = Depends(_get_user_from_token),
) -> scheduler_schemas.ExecutionListResponse:
    useremail, _display_name, role_name = user_data
    with master_connection() as cursor:
        check_module_access(cursor, role_name, this_api)
        executions, total_count = scheduler_methods.list_executions(cursor, useremail, role_name, request)
    return scheduler_schemas.ExecutionListResponse(executions=executions, total_count=total_count)


@router.post("/execution", response_model=scheduler_schemas.ExecutionItem)
def get_execution(
    request: scheduler_schemas.ExecutionIdRequest,
    user_data: tuple = Depends(_get_user_from_token),
) -> scheduler_schemas.ExecutionItem:
    useremail, _display_name, role_name = user_data
    with master_connection() as cursor:
        check_module_access(cursor, role_name, this_api)
        return scheduler_methods.get_execution(cursor, useremail, role_name, request.execution_id)


@router.post("/cron/validate", response_model=scheduler_schemas.CronValidateResponse)
def validate_cron(
    request: scheduler_schemas.CronValidateRequest,
    user_data: tuple = Depends(_get_user_from_token),
) -> scheduler_schemas.CronValidateResponse:
    _useremail, _display_name, role_name = user_data
    with master_connection() as cursor:
        check_module_access(cursor, role_name, this_api)
    return scheduler_methods.validate_cron(request.cron_expression, request.count)


@router.post("/status", response_model=scheduler_schemas.SchedulerStatusResponse)
def get_scheduler_status(
    _request: scheduler_schemas.EmptyRequest,
    user_data: tuple = Depends(_get_user_from_token),
) -> scheduler_schemas.SchedulerStatusResponse:
    _useremail, _display_name, role_name = user_data
    with master_connection() as cursor:
        check_module_access(cursor, role_name, this_api)
        return scheduler_methods.get_scheduler_status(cursor)


@router.post("/schedule/run", response_model=scheduler_schemas.RunScheduleResponse)
def run_schedule_now(
    request: scheduler_schemas.ScheduleIdRequest,
    background_tasks: BackgroundTasks,
    user_data: tuple = Depends(_get_user_from_token),
) -> scheduler_schemas.RunScheduleResponse:
    useremail, _display_name, role_name = user_data
    with master_connection() as cursor:
        check_module_access(cursor, role_name, this_api)
        execution_id = scheduler_methods.run_schedule_now(cursor, useremail, role_name, request.schedule_id)
    background_tasks.add_task(scheduler_methods.complete_manual_run, request.schedule_id, execution_id)
    return scheduler_schemas.RunScheduleResponse(execution_id=execution_id, message="Schedule queued for execution")
