USE [EmployeePortal]
GO

CREATE PROCEDURE dbo.sp_SyncMonthlyPayslip
    @Year  smallint,
    @Month tinyint
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE
        @MaxYear smallint,
        @MaxMonth tinyint,
        @Enabled bit,
        @SourceRows int = 0,
        @EligibleRows int = 0,
        @InsertedRows int = 0,
        @DeletedRows int = 0,
        @SkippedEmployees int = 0;

    /* ============================
       1) Validate period
       ============================ */
    IF @Month NOT BETWEEN 1 AND 12
        THROW 50001, N'رقم الشهر غير صحيح.', 1;

    SELECT
        @Enabled  = enabled,
        @MaxYear  = max_year,
        @MaxMonth = max_month
    FROM dbo.payroll_sync_control
    WHERE sync_type = N'PAYSLIP';

    IF @Enabled IS NULL
        THROW 50002, N'إعداد PAYSLIP غير موجود في payroll_sync_control.', 1;

    IF @Enabled = 0
        THROW 50003, N'مزامنة شريط المرتب متوقفة.', 1;

    IF @MaxYear IS NOT NULL
       AND (
            @Year > @MaxYear
            OR (@Year = @MaxYear AND @Month > @MaxMonth)
       )
        THROW 50004, N'هذا الشهر محجوب حاليًا من النشر.', 1;


    /* ============================
       2) Source staging
       ============================ */
    CREATE TABLE #Source
    (
        employee_id int NOT NULL,
        band_code   int NOT NULL,
        amount      decimal(12,2) NOT NULL,
        balance     decimal(18,2) NULL,
        PRIMARY KEY (employee_id, band_code)
    );


    /*
       payroll_raseed:
       - عند وجود رصيد > 0:
           amount  = kest_VAL
           balance = raseed_val
       - خلاف ذلك:
           amount  = BAND_VALUE
           balance = NULL
    */
    
    INSERT INTO #Source
    (
        employee_id,
        band_code,
        amount,
        balance
    )
    SELECT
        E.id,
        A.band_code,
        CAST(A.BAND_VALUE AS decimal(12,2)) AS amount,
        CAST(
            CASE
                WHEN ISNULL(A.raseed_val, 0) > 0
                    THEN A.raseed_val
                ELSE NULL
            END
            AS decimal(18,2)
        ) AS balance
    FROM human_r_ash.dbo.payroll_annual_ALL AS A
    INNER JOIN dbo.employees AS E
        ON TRY_CONVERT(bigint, E.employee_code) = A.emp_no
    WHERE A.YEAR_P = @Year
      AND A.MONTH_P = @Month
      AND A.sarfia_no = 1;

    SET @EligibleRows = @@ROWCOUNT;


    /* عدد صفوف المصدر الأصلي */
    SELECT
        @SourceRows = COUNT(*)
    FROM human_r_ash.dbo.payroll_annual_ALL
    WHERE YEAR_P = @Year
      AND MONTH_P = @Month
      AND sarfia_no = 1;


    /* موظفون موجودون بالمصدر وغير موجودين بالبوابة */
    SELECT
        @SkippedEmployees = COUNT(DISTINCT A.emp_no)
    FROM human_r_ash.dbo.payroll_annual_ALL A
    LEFT JOIN dbo.employees E
        ON TRY_CONVERT(bigint, E.employee_code) = A.emp_no
    WHERE A.YEAR_P = @Year
      AND A.MONTH_P = @Month
      AND A.sarfia_no = 1
      AND E.id IS NULL;


    /* ============================
       3) Band mapping
       ============================ */

    CREATE TABLE #BandMap
    (
        band_code int PRIMARY KEY,
        band_name nvarchar(200) NULL,
        band_type nvarchar(20) NOT NULL
    );

    
    INSERT INTO #BandMap
    (
        band_code,
        band_name,
        band_type
    )
    SELECT
        B.BAND_CODE,
        MAX(NULLIF(LTRIM(RTRIM(B.band_name)), N'')),
        CASE
            WHEN MAX(B.band_calc) = 1 THEN N'earning'
            WHEN MAX(B.band_calc) IN (2, 3) THEN N'deduction'
        END
    FROM human_r_ash.dbo.payroll_BAND_Codes AS B
    WHERE B.band_calc IN (1, 2, 3)
    GROUP BY B.BAND_CODE;


    /*
       حماية:
       لو ظهر band_code جديد تمامًا وغير معروف
       لا ننشر بيانات بتصنيف مالي مجهول.
    */
    IF EXISTS
    (
        SELECT 1
        FROM #Source S
        LEFT JOIN #BandMap B
            ON B.band_code = S.band_code
        WHERE B.band_code IS NULL
    )
    BEGIN
        SELECT DISTINCT
            S.band_code AS UnknownBandCode
        FROM #Source S
        LEFT JOIN #BandMap B
            ON B.band_code = S.band_code
        WHERE B.band_code IS NULL
        ORDER BY S.band_code;

        THROW 50005,
              N'يوجد بند جديد غير معروف في payroll_items. تمت إيقاف المزامنة لحماية تصنيف الاستحقاقات والخصومات.',
              1;
    END;


    /* ============================
       4) Atomic replacement
       ============================ */

    BEGIN TRY
        BEGIN TRANSACTION;

        DELETE P
        FROM dbo.payroll_items P
        WHERE P.[year] = @Year
          AND P.[month] = @Month
          AND P.sarfia_no = 1;

        SET @DeletedRows = @@ROWCOUNT;


        INSERT INTO dbo.payroll_items
        (
            employee_id,
            [month],
            [year],
            band_code,
            band_name,
            band_type,
            amount,
            created_at,
            sarfia_no,
            balance
        )
        SELECT
            S.employee_id,
            @Month,
            @Year,
            S.band_code,
            B.band_name,
            B.band_type,
            S.amount,
            SYSDATETIME(),
            1,
            S.balance
        FROM #Source S
        INNER JOIN #BandMap B
            ON B.band_code = S.band_code;

        SET @InsertedRows = @@ROWCOUNT;

        COMMIT TRANSACTION;

    END TRY
    BEGIN CATCH

        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        THROW;

    END CATCH;


    /* ============================
       5) Result
       ============================ */

    SELECT
        N'تمت مزامنة شريط المرتب بنجاح' AS Result,
        @Year AS [Year],
        @Month AS [Month],
        @SourceRows AS SourceRows,
        @EligibleRows AS EligibleRows,
        @DeletedRows AS PreviousPortalRows,
        @InsertedRows AS InsertedRows,
        @SkippedEmployees AS SkippedEmployees,
        SYSDATETIME() AS SyncTime;
END;
GO
