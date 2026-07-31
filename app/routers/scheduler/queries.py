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
                     SET CronExpression = ?, IsEnabled = ?, NextRunAt = ?,
                         UpdatedAt = datetime('now')
                     WHERE ScheduleId = ?"""

update_next_run_at = """UPDATE SJ_ScheduledJobs
                        SET NextRunAt = ?, UpdatedAt = datetime('now')
                        WHERE ScheduleId = ?"""

execution_base = """FROM SJ_JobExecutions je
                    JOIN SJ_ScheduledJobs sj ON sj.ScheduleId = je.ScheduleId"""
