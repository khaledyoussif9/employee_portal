
CREATE   PROCEDURE dbo.sp_AutoSyncPayrollPortal
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE
        @LockResult int,
        @LogId bigint,

        @Year smallint,
        @Month tinyint,

        @Enabled bit,
        @MaxYear smallint,
        @MaxMonth tinyint,

        @Rows bigint,
        @Employees bigint,
        @TotalAmount decimal(38,2),
        @BandSum bigint,
        @SarfiaSum bigint,

        @OldRows bigint,
        @OldEmployees bigint,
        @OldTotalAmount decimal(38,2),
        @OldBandSum bigint,
        @OldSarfiaSum bigint,

        @NeedSync bit;


    /* ==============================================
       „‰⁄  ‘€Ì· ⁄„·Ì Ì‰ ›Ì ‰›” «·Êﬁ 
       ============================================== */

    EXEC @LockResult = sys.sp_getapplock
        @Resource = N'EmployeePortal_AutoSync',
        @LockMode = N'Exclusive',
        @LockOwner = N'Session',
        @LockTimeout = 0;

    IF @LockResult < 0
    BEGIN
        SELECT
            N'SKIPPED -  ÊÃœ „“«„‰… √Œ—Ï  ⁄„· Õ«·Ì«' AS Result,
            SYSDATETIME() AS CheckTime;
        RETURN;
    END;


    BEGIN TRY

        /* ==============================================
           1) «·„ÊŸ›Ê‰
           ============================================== */

        INSERT INTO dbo.payroll_sync_log
        (
            sync_type,
            started_at,
            status
        )
        VALUES
        (
            N'EMPLOYEES',
            SYSDATETIME(),
            N'RUNNING'
        );

        SET @LogId = SCOPE_IDENTITY();


        BEGIN TRY

            EXEC dbo.sp_SyncEmployees;

            UPDATE dbo.payroll_auto_sync_state
            SET
                last_success_at = SYSDATETIME(),
                last_check_at = SYSDATETIME()
            WHERE sync_type = N'EMPLOYEES';


            UPDATE dbo.payroll_sync_log
            SET
                finished_at = SYSDATETIME(),
                status = N'SUCCESS'
            WHERE id = @LogId;

        END TRY
        BEGIN CATCH

            UPDATE dbo.payroll_sync_log
            SET
                finished_at = SYSDATETIME(),
                status = N'FAILED',
                error_number = ERROR_NUMBER(),
                error_message = ERROR_MESSAGE()
            WHERE id = @LogId;

            THROW;

        END CATCH;


        /* ==============================================
           2) PAYSLIP - sarfia_no = 1
           ============================================== */

        SET @Enabled = NULL;
        SET @MaxYear = NULL;
        SET @MaxMonth = NULL;

        SELECT
            @Enabled = enabled,
            @MaxYear = max_year,
            @MaxMonth = max_month
        FROM dbo.payroll_sync_control
        WHERE sync_type = N'PAYSLIP';


        IF ISNULL(@Enabled, 0) = 1
        BEGIN

            SET @Year = NULL;
            SET @Month = NULL;

            /* √ÕœÀ ‘Â— „ÊÃÊœ Ê„”„ÊÕ »«·‰‘— */
            SELECT TOP (1)
                @Year = CAST(YEAR_P AS smallint),
                @Month = CAST(MONTH_P AS tinyint)
            FROM human_r_ash.dbo.payroll_annual_ALL
            WHERE sarfia_no = 1
              AND MONTH_P BETWEEN 1 AND 12
              AND
              (
                    @MaxYear IS NULL
                    OR YEAR_P < @MaxYear
                    OR
                    (
                        YEAR_P = @MaxYear
                        AND MONTH_P <= @MaxMonth
                    )
              )
            GROUP BY YEAR_P, MONTH_P
            ORDER BY YEAR_P DESC, MONTH_P DESC;


            IF @Year IS NOT NULL
            BEGIN

                SELECT
                    @Rows = COUNT_BIG(*),
                    @Employees = COUNT(DISTINCT emp_no),
                    @TotalAmount =
                        SUM(CAST(BAND_VALUE AS decimal(38,2))),
                    @BandSum =
                        SUM(CAST(band_code AS bigint))
                FROM human_r_ash.dbo.payroll_annual_ALL
                WHERE YEAR_P = @Year
                  AND MONTH_P = @Month
                  AND sarfia_no = 1;


                SELECT
                    @OldRows = last_source_rows,
                    @OldEmployees = source_employee_count,
                    @OldTotalAmount = source_total_amount,
                    @OldBandSum = source_band_sum
                FROM dbo.payroll_auto_sync_state
                WHERE sync_type = N'PAYSLIP';


                SET @NeedSync =
                    CASE
                        WHEN NOT EXISTS
                        (
                            SELECT 1
                            FROM dbo.payroll_auto_sync_state
                            WHERE sync_type = N'PAYSLIP'
                              AND last_year = @Year
                              AND last_month = @Month
                        )
                        THEN 1

                        WHEN ISNULL(@OldRows, -1)
                             <> ISNULL(@Rows, -1)
                        THEN 1

                        WHEN ISNULL(@OldEmployees, -1)
                             <> ISNULL(@Employees, -1)
                        THEN 1

                        WHEN ISNULL(@OldTotalAmount, -1)
                             <> ISNULL(@TotalAmount, -1)
                        THEN 1

                        WHEN ISNULL(@OldBandSum, -1)
                             <> ISNULL(@BandSum, -1)
                        THEN 1

                        ELSE 0
                    END;


                IF @NeedSync = 1
                BEGIN

                    INSERT INTO dbo.payroll_sync_log
                    (
                        sync_type,
                        sync_year,
                        sync_month,
                        started_at,
                        source_rows,
                        status
                    )
                    VALUES
                    (
                        N'PAYSLIP',
                        @Year,
                        @Month,
                        SYSDATETIME(),
                        @Rows,
                        N'RUNNING'
                    );

                    SET @LogId = SCOPE_IDENTITY();


                    BEGIN TRY

                        EXEC dbo.sp_SyncMonthlyPayslip
                            @Year = @Year,
                            @Month = @Month;


                        UPDATE dbo.payroll_auto_sync_state
                        SET
                            last_year = @Year,
                            last_month = @Month,
                            last_source_rows = @Rows,
                            source_employee_count = @Employees,
                            source_total_amount = @TotalAmount,
                            source_band_sum = @BandSum,
                            source_sarfia_sum = NULL,
                            last_success_at = SYSDATETIME(),
                            last_check_at = SYSDATETIME()
                        WHERE sync_type = N'PAYSLIP';


                        UPDATE dbo.payroll_sync_log
                        SET
                            finished_at = SYSDATETIME(),
                            status = N'SUCCESS'
                        WHERE id = @LogId;

                    END TRY
                    BEGIN CATCH

                        UPDATE dbo.payroll_sync_log
                        SET
                            finished_at = SYSDATETIME(),
                            status = N'FAILED',
                            error_number = ERROR_NUMBER(),
                            error_message = ERROR_MESSAGE()
                        WHERE id = @LogId;

                        THROW;

                    END CATCH;

                END
                ELSE
                BEGIN
                    UPDATE dbo.payroll_auto_sync_state
                    SET last_check_at = SYSDATETIME()
                    WHERE sync_type = N'PAYSLIP';
                END;

            END;

        END;


        /* ==============================================
           3) WAGE RECORD - sarfia_no > 1
           ============================================== */

        SET @Enabled = NULL;
        SET @MaxYear = NULL;
        SET @MaxMonth = NULL;

        SET @Rows = NULL;
        SET @Employees = NULL;
        SET @TotalAmount = NULL;
        SET @BandSum = NULL;
        SET @SarfiaSum = NULL;

        SET @OldRows = NULL;
        SET @OldEmployees = NULL;
        SET @OldTotalAmount = NULL;
        SET @OldBandSum = NULL;
        SET @OldSarfiaSum = NULL;


        SELECT
            @Enabled = enabled,
            @MaxYear = max_year,
            @MaxMonth = max_month
        FROM dbo.payroll_sync_control
        WHERE sync_type = N'WAGE_RECORD';

        /* =====================================================
           Õ„«Ì… “„‰Ì… ·”Ã· «·√ÃÊ—
           «·‘Â— «·Õ«·Ì ·« Ì„ﬂ‰ ‰‘— ’—›Ì« Â.
           Ì’»Õ «·‘Â— ﬁ«»·« ··‰‘— »œ«Ì… «·‘Â— «· «·Ì.
           ===================================================== */

        DECLARE @PreviousWageMonth date =
            DATEADD(
                MONTH,
                -1,
                DATEFROMPARTS(YEAR(GETDATE()), MONTH(GETDATE()), 1)
            );

        DECLARE @AutoWageMaxYear smallint =
            YEAR(@PreviousWageMonth);

        DECLARE @AutoWageMaxMonth tinyint =
            MONTH(@PreviousWageMonth);

        /*
          «·”ﬁ› «·›⁄·Ì = «·√ﬁ· »Ì‰:
          - Õ«Ã“ «·‰‘— «·ÌœÊÌ
          - «·‘Â— «·”«»ﬁ
        */
        IF @MaxYear IS NULL
           OR @MaxYear > @AutoWageMaxYear
           OR
           (
               @MaxYear = @AutoWageMaxYear
               AND ISNULL(@MaxMonth, 12) > @AutoWageMaxMonth
           )
        BEGIN
            SET @MaxYear = @AutoWageMaxYear;
            SET @MaxMonth = @AutoWageMaxMonth;
        END;


        IF ISNULL(@Enabled, 0) = 1
        BEGIN

            SET @Year = NULL;
            SET @Month = NULL;

            SELECT TOP (1)
                @Year = CAST(YEAR_P AS smallint),
                @Month = CAST(MONTH_P AS tinyint)
            FROM human_r_ash.dbo.payroll_annual_ALL
            WHERE sarfia_no > 1
              AND MONTH_P BETWEEN 1 AND 12
              AND
              (
                    @MaxYear IS NULL
                    OR YEAR_P < @MaxYear
                    OR
                    (
                        YEAR_P = @MaxYear
                        AND MONTH_P <= @MaxMonth
                    )
              )
            GROUP BY YEAR_P, MONTH_P
            ORDER BY YEAR_P DESC, MONTH_P DESC;


            IF @Year IS NOT NULL
            BEGIN

                SELECT
                    @Rows = COUNT_BIG(*),
                    @Employees = COUNT(DISTINCT emp_no),
                    @TotalAmount =
                        SUM(CAST(BAND_VALUE AS decimal(38,2))),
                    @BandSum =
                        SUM(CAST(band_code AS bigint)),
                    @SarfiaSum =
                        SUM(CAST(sarfia_no AS bigint))
                FROM human_r_ash.dbo.payroll_annual_ALL
                WHERE YEAR_P = @Year
                  AND MONTH_P = @Month
                  AND sarfia_no > 1;


                SELECT
                    @OldRows = last_source_rows,
                    @OldEmployees = source_employee_count,
                    @OldTotalAmount = source_total_amount,
                    @OldBandSum = source_band_sum,
                    @OldSarfiaSum = source_sarfia_sum
                FROM dbo.payroll_auto_sync_state
                WHERE sync_type = N'WAGE_RECORD';


                SET @NeedSync =
                    CASE
                        WHEN NOT EXISTS
                        (
                            SELECT 1
                            FROM dbo.payroll_auto_sync_state
                            WHERE sync_type = N'WAGE_RECORD'
                              AND last_year = @Year
                              AND last_month = @Month
                        )
                        THEN 1

                        WHEN ISNULL(@OldRows, -1)
                             <> ISNULL(@Rows, -1)
                        THEN 1

                        WHEN ISNULL(@OldEmployees, -1)
                             <> ISNULL(@Employees, -1)
                        THEN 1

                        WHEN ISNULL(@OldTotalAmount, -1)
                             <> ISNULL(@TotalAmount, -1)
                        THEN 1

                        WHEN ISNULL(@OldBandSum, -1)
                             <> ISNULL(@BandSum, -1)
                        THEN 1

                        WHEN ISNULL(@OldSarfiaSum, -1)
                             <> ISNULL(@SarfiaSum, -1)
                        THEN 1

                        ELSE 0
                    END;


                IF @NeedSync = 1
                BEGIN

                    INSERT INTO dbo.payroll_sync_log
                    (
                        sync_type,
                        sync_year,
                        sync_month,
                        started_at,
                        source_rows,
                        status
                    )
                    VALUES
                    (
                        N'WAGE_RECORD',
                        @Year,
                        @Month,
                        SYSDATETIME(),
                        @Rows,
                        N'RUNNING'
                    );

                    SET @LogId = SCOPE_IDENTITY();


                    BEGIN TRY

                        EXEC dbo.sp_SyncMonthlyWageRecord
                            @Year = @Year,
                            @Month = @Month;


                        UPDATE dbo.payroll_auto_sync_state
                        SET
                            last_year = @Year,
                            last_month = @Month,
                            last_source_rows = @Rows,
                            source_employee_count = @Employees,
                            source_total_amount = @TotalAmount,
                            source_band_sum = @BandSum,
                            source_sarfia_sum = @SarfiaSum,
                            last_success_at = SYSDATETIME(),
                            last_check_at = SYSDATETIME()
                        WHERE sync_type = N'WAGE_RECORD';


                        UPDATE dbo.payroll_sync_log
                        SET
                            finished_at = SYSDATETIME(),
                            status = N'SUCCESS'
                        WHERE id = @LogId;

                    END TRY
                    BEGIN CATCH

                        UPDATE dbo.payroll_sync_log
                        SET
                            finished_at = SYSDATETIME(),
                            status = N'FAILED',
                            error_number = ERROR_NUMBER(),
                            error_message = ERROR_MESSAGE()
                        WHERE id = @LogId;

                        THROW;

                    END CATCH;

                END
                ELSE
                BEGIN
                    UPDATE dbo.payroll_auto_sync_state
                    SET last_check_at = SYSDATETIME()
                    WHERE sync_type = N'WAGE_RECORD';
                END;

            END;

        END;


        EXEC sys.sp_releaseapplock
            @Resource = N'EmployeePortal_AutoSync',
            @LockOwner = N'Session';


        SELECT
            N' „ ›Õ’ «·„“«„‰… «· ·ﬁ«∆Ì… »‰Ã«Õ' AS Result,
            SYSDATETIME() AS CheckTime;

    END TRY

    BEGIN CATCH

        EXEC sys.sp_releaseapplock
            @Resource = N'EmployeePortal_AutoSync',
            @LockOwner = N'Session';

        THROW;

    END CATCH;
END;

