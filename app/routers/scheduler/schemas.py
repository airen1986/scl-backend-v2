from typing import Any

from pydantic import BaseModel, field_validator


class ScheduleItem(BaseModel):
    schedule_id: int
    schedule_description: str | None
    task_id: int
    task_name: str
    task_params: dict[str, Any]
    schedule_type: str
    cron_expression: str | None
    is_enabled: int
    is_running: int
    last_run_at: str | None
    next_run_at: str | None
    created_by: str | None


class ScheduleListResponse(BaseModel):
    schedules: list[ScheduleItem]


class ExecutionFiltersRequest(BaseModel):
    schedule_id: int | None = None


class ExecutionItem(BaseModel):
    execution_id: int
    schedule_id: int
    task_id: int
    task_name: str
    status: str
    started_at: str
    completed_at: str | None
    duration_seconds: float | None
    retry_count: int
    error_message: str | None
    result_data: dict[str, Any] | list[Any] | str | int | float | bool | None


class ExecutionListResponse(BaseModel):
    executions: list[ExecutionItem]


class UpdateScheduleRequest(BaseModel):
    schedule_id: int
    cron_expression: str | None = None
    is_enabled: int | None = None

    @field_validator("is_enabled")
    @classmethod
    def validate_flag(cls, value: int | None) -> int | None:
        if value is not None and value not in (0, 1):
            raise ValueError("is_enabled must be 0 or 1")
        return value


class GetTaskScheduleRequest(BaseModel):
    task_code: int
    model_name: str
    project_name: str
    next_run_at: str | None = None


class UpdateScheduleResponse(BaseModel):
    schedule_id: int
    next_run_at: str | None
    message: str


class RunScheduleRequest(BaseModel):
    schedule_id: int


class RunScheduleResponse(BaseModel):
    next_run_at: str
    message: str


class GetTaskScheduleResponse(BaseModel):
    schedule_id: int
    cron_expression: str
    is_enabled: int
    created_by: str
    next_run_at: str | None


class SetTaskScheduleRequest(BaseModel):
    task_id: int
    schedule_id: int | None = None
    model_name: str
    project_name: str
    cron_expression: str
    is_enabled: int

    @field_validator("is_enabled")
    @classmethod
    def validate_flag(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("is_enabled must be 0 or 1")
        return value
