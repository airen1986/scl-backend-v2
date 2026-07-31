from enum import Enum
from typing import Any

from pydantic import BaseModel, field_validator


class MessageResponse(BaseModel):
    message: str


class EmptyRequest(BaseModel):
    pass


class ScheduleType(str, Enum):
    CRON = "cron"


class ExecutionStatus(str, Enum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class TaskItem(BaseModel):
    task_id: int
    task_name: str
    task_description: str | None
    max_retries: int
    timeout_seconds: int


class TaskListResponse(BaseModel):
    tasks: list[TaskItem]


class ScheduleItem(BaseModel):
    schedule_id: int
    schedule_description: str | None
    task_id: int
    task_name: str
    task_params: dict[str, Any]
    schedule_type: ScheduleType
    cron_expression: str | None
    is_enabled: int
    is_running: int
    last_run_at: str | None
    next_run_at: str | None
    created_by: str | None


class ScheduleListResponse(BaseModel):
    schedules: list[ScheduleItem]


class UpdateScheduleRequest(BaseModel):
    schedule_id: int
    schedule_description: str | None = None
    task_params: dict[str, Any] | None = None
    schedule_type: ScheduleType
    cron_expression: str | None = None
    is_enabled: int

    @field_validator("is_enabled")
    @classmethod
    def validate_flag(cls, value: int) -> int:
        if value not in (0, 1):
            raise ValueError("is_enabled must be 0 or 1")
        return value


class UpdateScheduleResponse(BaseModel):
    next_run_at: str | None
    message: str


class ScheduleIdRequest(BaseModel):
    schedule_id: int


class ExecutionFiltersRequest(BaseModel):
    schedule_id: int | None = None
    task_name: str | None = None
    created_by: str | None = None
    status: ExecutionStatus | None = None
    started_from: str | None = None
    started_to: str | None = None
    limit: int = 50
    offset: int = 0

    @field_validator("limit")
    @classmethod
    def validate_limit(cls, value: int) -> int:
        if value < 1 or value > 200:
            raise ValueError("limit must be between 1 and 200")
        return value

    @field_validator("offset")
    @classmethod
    def validate_offset(cls, value: int) -> int:
        if value < 0:
            raise ValueError("offset must be greater than or equal to 0")
        return value


class ExecutionItem(BaseModel):
    execution_id: int
    schedule_id: int
    task_id: int
    task_name: str
    status: ExecutionStatus
    started_at: str
    completed_at: str | None
    duration_seconds: float | None
    retry_count: int
    error_message: str | None
    result_data: dict[str, Any] | list[Any] | str | int | float | bool | None


class ExecutionListResponse(BaseModel):
    executions: list[ExecutionItem]
    total_count: int


class ExecutionIdRequest(BaseModel):
    execution_id: int


class CronValidateRequest(BaseModel):
    cron_expression: str
    count: int = 5

    @field_validator("count")
    @classmethod
    def validate_count(cls, value: int) -> int:
        if value < 1 or value > 20:
            raise ValueError("count must be between 1 and 20")
        return value


class CronValidateResponse(BaseModel):
    is_valid: bool
    description: str | None
    next_runs: list[str]
    message: str | None


class SchedulerStatusResponse(BaseModel):
    is_alive: bool
    last_poll_at: str | None
    enabled_schedules: int
    running_schedules: int
    last_execution_status: str | None


class RunScheduleResponse(BaseModel):
    execution_id: int
    message: str
