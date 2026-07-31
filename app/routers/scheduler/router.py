from fastapi import APIRouter, Depends

from app.connection import master_connection
from app.routers.auth.methods import _get_user_from_token, check_module_access

from . import methods as scheduler_methods
from . import schemas as scheduler_schemas

router = APIRouter()
this_api = "/api/scheduler"


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


@router.post("/run", response_model=scheduler_schemas.RunScheduleResponse)
def run_schedule(
    request: scheduler_schemas.RunScheduleRequest,
    user_data: tuple = Depends(_get_user_from_token),
) -> scheduler_schemas.RunScheduleResponse:
    useremail, _display_name, role_name = user_data
    with master_connection() as cursor:
        check_module_access(cursor, role_name, this_api)
        next_run_at = scheduler_methods.run_schedule(cursor, useremail, role_name, request)
    return scheduler_schemas.RunScheduleResponse(
        next_run_at=next_run_at,
        message="Schedule queued to run",
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
