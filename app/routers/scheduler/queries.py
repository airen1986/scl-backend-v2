list_tasks = """SELECT TaskId, TaskName, TaskDescription, MaxRetries, TimeoutSeconds
                FROM SJ_TaskMaster
                ORDER BY TaskName"""

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

find_duplicate_schedule = """SELECT ScheduleId
                             FROM SJ_ScheduledJobs
                             WHERE TaskId = ?
                             AND COALESCE(TaskParams, '{}') = ?
                             AND ScheduleType = ?
                             AND COALESCE(CronExpression, '') = COALESCE(?, '')
                             AND ScheduleId != ?"""

update_schedule = """UPDATE SJ_ScheduledJobs
                     SET ScheduleDescription = ?, TaskParams = ?, ScheduleType = ?,
                         CronExpression = ?, IsEnabled = ?, NextRunAt = ?,
                         UpdatedAt = datetime('now')
                     WHERE ScheduleId = ?"""

execution_base = """FROM SJ_JobExecutions je
                    JOIN SJ_ScheduledJobs sj ON sj.ScheduleId = je.ScheduleId"""

get_execution = """SELECT je.ExecutionId, je.ScheduleId, je.TaskId, je.TaskName, je.Status,
                   je.StartedAt, je.CompletedAt, je.DurationSeconds, je.RetryCount,
                   je.ErrorMessage, je.ResultData, sj.CreatedBy
                   FROM SJ_JobExecutions je
                   JOIN SJ_ScheduledJobs sj ON sj.ScheduleId = je.ScheduleId
                   WHERE je.ExecutionId = ?"""

scheduler_status = """SELECT
                      (SELECT COUNT(*) FROM SJ_ScheduledJobs WHERE IsEnabled = 1),
                      (SELECT COUNT(*) FROM SJ_ScheduledJobs WHERE IsRunning = 1),
                      (SELECT StartedAt FROM SJ_JobExecutions ORDER BY ExecutionId DESC LIMIT 1),
                      (SELECT Status FROM SJ_JobExecutions ORDER BY ExecutionId DESC LIMIT 1)"""

update_schedule_last_run = """UPDATE SJ_ScheduledJobs
                              SET LastRunAt = ?, UpdatedAt = datetime('now')
                              WHERE ScheduleId = ?"""
