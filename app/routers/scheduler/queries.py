from typing import Any

list_schedules = """SELECT sj.ScheduleId, sj.ScheduleDescription, sj.TaskId, tm.TaskName,
                    sj.TaskParams, sj.ScheduleType, sj.CronExpression, sj.IsEnabled,
                    sj.IsRunning, sj.LastRunAt, sj.NextRunAt, sj.CreatedBy
                    FROM SJ_ScheduledJobs sj
                    JOIN SJ_TaskMaster tm ON tm.TaskId = sj.TaskId
                    ORDER BY sj.ScheduleId DESC"""

list_schedules_for_owner = """SELECT sj.ScheduleId, sj.ScheduleDescription, sj.TaskId, tm.TaskName,
                              sj.TaskParams, sj.ScheduleType, sj.CronExpression, sj.IsEnabled,
                              sj.IsRunning, sj.LastRunAt, sj.NextRunAt, sj.CreatedBy
                              FROM SJ_ScheduledJobs sj
                              JOIN SJ_TaskMaster tm ON tm.TaskId = sj.TaskId
                              WHERE sj.CreatedBy = ?
                              ORDER BY sj.ScheduleId DESC"""

get_schedule = """SELECT sj.ScheduleId, sj.TaskId, tm.TaskName, sj.ScheduleDescription,
                  sj.TaskParams, sj.ScheduleType, sj.CronExpression, sj.IsEnabled,
                  sj.IsRunning, sj.LastRunAt, sj.NextRunAt, sj.CreatedBy
                  FROM SJ_ScheduledJobs sj
                  JOIN SJ_TaskMaster tm ON tm.TaskId = sj.TaskId
                  WHERE sj.ScheduleId = ?"""

update_schedule = """UPDATE SJ_ScheduledJobs
                     SET CronExpression = ?, IsEnabled = ?, NextRunAt = ?,
                     ScheduleDescription = ?,
                         UpdatedAt = datetime('now')
                     WHERE ScheduleId = ?"""

update_next_run_at = """UPDATE SJ_ScheduledJobs
                        SET NextRunAt = ?, UpdatedAt = datetime('now')
                        WHERE ScheduleId = ?"""

execution_base = """FROM SJ_JobExecutions je
                    JOIN SJ_ScheduledJobs sj ON sj.ScheduleId = je.ScheduleId"""


def get_schedule_executions(schedule_id: int | None, created_by: str | None) -> tuple[str, list[Any]]:
    where_clause = "AND 1 = 1"
    params = []
    if schedule_id is not None:
        where_clause += " AND je.ScheduleId = ?"
        params.append(schedule_id)
    if created_by is not None:
        where_clause += " AND sj.CreatedBy = ?"
        params.append(created_by)
    where_sql = where_clause
    query = f"""SELECT je.ExecutionId, je.ScheduleId, je.TaskId, je.TaskName, je.Status,
               je.StartedAt, je.CompletedAt, je.DurationSeconds, je.RetryCount,
               je.ErrorMessage, je.ResultData
               FROM SJ_JobExecutions je, SJ_ScheduledJobs sj
               WHERE je.ScheduleId = sj.ScheduleId
               {where_sql}
               ORDER BY je.ExecutionId DESC
               LIMIT 50"""
    return query, params


get_task_schedule = """select SJ_ScheduledJobs.CronExpression, SJ_ScheduledJobs.ScheduleId,
                        SJ_ScheduledJobs.IsEnabled,  SJ_ScheduledJobs.CreatedBy,
                        SJ_ScheduledJobs.NextRunAt
                        from SJ_ScheduledJobs, SJ_TaskMaster
                        WHERE SJ_ScheduledJobs.TaskId = SJ_TaskMaster.TaskId
                        and TaskName = 'run_model_task'
                        AND   json_extract(SJ_ScheduledJobs.TaskParams, '$.model_id') = ?
                        AND   json_extract(SJ_ScheduledJobs.TaskParams, '$.task_code') = ?;"""


get_task_id = """SELECT TaskId FROM SJ_TaskMaster WHERE TaskName = ?"""

insert_schedule = """INSERT INTO SJ_ScheduledJobs (TaskId, TaskParams, ScheduleType, CronExpression,
                        IsEnabled, NextRunAt, ScheduleDescription, CreatedBy)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                     RETURNING ScheduleId, NextRunAt"""
