USE msdb;
GO

/* =========================================================
   Employee Portal v2.2.0
   SQL Server Agent Auto Sync
   IMPORTANT:
   Job is created DISABLED initially.
   Enable only after first branch synchronization is verified.
   ========================================================= */

IF EXISTS
(
    SELECT 1
    FROM dbo.sysjobs
    WHERE name = N'Employee Portal Auto Sync'
)
BEGIN
    EXEC dbo.sp_delete_job
        @job_name = N'Employee Portal Auto Sync',
        @delete_unused_schedule = 1;
END;
GO


EXEC dbo.sp_add_job
    @job_name = N'Employee Portal Auto Sync',
    @enabled = 0,
    @description =
        N'Automatic Employee Portal synchronization from human_r_ash. Created disabled for first-install safety.',
    @category_name = N'[Uncategorized (Local)]';
GO


EXEC dbo.sp_add_jobstep
    @job_name = N'Employee Portal Auto Sync',
    @step_name = N'Run Employee Portal Auto Sync',
    @subsystem = N'TSQL',
    @database_name = N'EmployeePortal',
    @command = N'EXEC dbo.sp_AutoSyncPayrollPortal;',
    @on_success_action = 1,
    @on_fail_action = 2,
    @retry_attempts = 2,
    @retry_interval = 1;
GO


EXEC dbo.sp_add_schedule
    @schedule_name = N'Employee Portal Auto Sync - Every 5 Minutes',
    @enabled = 1,
    @freq_type = 4,
    @freq_interval = 1,
    @freq_subday_type = 4,
    @freq_subday_interval = 5,
    @active_start_date = 20260917,
    @active_start_time = 000000;
GO


EXEC dbo.sp_attach_schedule
    @job_name = N'Employee Portal Auto Sync',
    @schedule_name =
        N'Employee Portal Auto Sync - Every 5 Minutes';
GO


EXEC dbo.sp_add_jobserver
    @job_name = N'Employee Portal Auto Sync';
GO


SELECT
    J.name AS JobName,
    J.enabled AS JobEnabled,
    S.name AS ScheduleName,
    S.enabled AS ScheduleEnabled,
    S.freq_subday_interval AS EveryMinutes
FROM dbo.sysjobs J
LEFT JOIN dbo.sysjobschedules JS
    ON JS.job_id = J.job_id
LEFT JOIN dbo.sysschedules S
    ON S.schedule_id = JS.schedule_id
WHERE J.name = N'Employee Portal Auto Sync';
GO
