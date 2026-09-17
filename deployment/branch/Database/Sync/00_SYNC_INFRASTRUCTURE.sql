USE EmployeePortal;
GO

/* =========================================================
   Employee Portal v2.2.0
   Payroll Auto Sync Infrastructure
   Branch-safe installation
   ========================================================= */


/* 1) Publication Control */
IF OBJECT_ID(N'dbo.payroll_sync_control', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.payroll_sync_control
    (
        id int IDENTITY(1,1) NOT NULL PRIMARY KEY,
        sync_type nvarchar(50) NOT NULL UNIQUE,
        enabled bit NOT NULL
            CONSTRAINT DF_payroll_sync_control_enabled DEFAULT (1),
        max_year smallint NULL,
        max_month tinyint NULL,
        updated_at datetime2(7) NOT NULL
            CONSTRAINT DF_payroll_sync_control_updated_at
            DEFAULT (SYSDATETIME()),

        CONSTRAINT CK_payroll_sync_control_month
        CHECK (max_month IS NULL OR max_month BETWEEN 1 AND 12)
    );
END;
GO


/* إنشاء المفاتيح بدون فتح أي شهر للنشر */
IF NOT EXISTS
(
    SELECT 1
    FROM dbo.payroll_sync_control
    WHERE sync_type = N'PAYSLIP'
)
BEGIN
    INSERT dbo.payroll_sync_control
        (sync_type, enabled, max_year, max_month)
    VALUES
        (N'PAYSLIP', 0, NULL, NULL);
END;

IF NOT EXISTS
(
    SELECT 1
    FROM dbo.payroll_sync_control
    WHERE sync_type = N'WAGE_RECORD'
)
BEGIN
    INSERT dbo.payroll_sync_control
        (sync_type, enabled, max_year, max_month)
    VALUES
        (N'WAGE_RECORD', 0, NULL, NULL);
END;
GO


/* 2) Auto Sync State */
IF OBJECT_ID(N'dbo.payroll_auto_sync_state', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.payroll_auto_sync_state
    (
        sync_type nvarchar(50) NOT NULL PRIMARY KEY,
        last_year smallint NULL,
        last_month tinyint NULL,
        last_source_rows bigint NULL,
        last_success_at datetime2(7) NULL,
        last_check_at datetime2(7) NULL,

        source_fingerprint varchar(64) NULL,
        source_total_amount decimal(38,2) NULL,
        source_employee_count bigint NULL,
        source_band_sum bigint NULL,
        source_sarfia_sum bigint NULL,

        CONSTRAINT CK_payroll_auto_sync_state_month
        CHECK (last_month IS NULL OR last_month BETWEEN 1 AND 12)
    );
END;
GO


IF NOT EXISTS
(
    SELECT 1 FROM dbo.payroll_auto_sync_state
    WHERE sync_type = N'EMPLOYEES'
)
    INSERT dbo.payroll_auto_sync_state(sync_type)
    VALUES(N'EMPLOYEES');

IF NOT EXISTS
(
    SELECT 1 FROM dbo.payroll_auto_sync_state
    WHERE sync_type = N'PAYSLIP'
)
    INSERT dbo.payroll_auto_sync_state(sync_type)
    VALUES(N'PAYSLIP');

IF NOT EXISTS
(
    SELECT 1 FROM dbo.payroll_auto_sync_state
    WHERE sync_type = N'WAGE_RECORD'
)
    INSERT dbo.payroll_auto_sync_state(sync_type)
    VALUES(N'WAGE_RECORD');
GO


/* 3) Sync Log */
IF OBJECT_ID(N'dbo.payroll_sync_log', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.payroll_sync_log
    (
        id bigint IDENTITY(1,1) NOT NULL PRIMARY KEY,
        sync_type nvarchar(50) NOT NULL,
        sync_year smallint NULL,
        sync_month tinyint NULL,
        started_at datetime2(7) NOT NULL,
        finished_at datetime2(7) NULL,
        source_rows bigint NULL,
        status nvarchar(20) NOT NULL,
        error_number int NULL,
        error_message nvarchar(2048) NULL,

        CONSTRAINT CK_payroll_sync_log_status
        CHECK (status IN
        (
            N'RUNNING',
            N'SUCCESS',
            N'FAILED',
            N'SKIPPED'
        )),

        CONSTRAINT CK_payroll_sync_log_month
        CHECK (sync_month IS NULL OR sync_month BETWEEN 1 AND 12)
    );

    CREATE INDEX IX_payroll_sync_log_lookup
    ON dbo.payroll_sync_log
       (sync_type, sync_year, sync_month, started_at);
END;
GO


SELECT N'Sync infrastructure ready' AS Result;
GO

