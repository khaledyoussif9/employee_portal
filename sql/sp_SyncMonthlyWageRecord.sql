USE [EmployeePortal]
GO

CREATE PROCEDURE dbo.sp_SyncMonthlyWageRecord
    @Year  smallint,
    @Month tinyint
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE
        @Enabled bit,
        @MaxYear smallint,
        @MaxMonth tinyint,
        @SourceRows int = 0,
        @EligibleRows int = 0,
        @DeletedRows int = 0,
        @InsertedRows int = 0,
        @SkippedEmployees int = 0,
        @SarfiaNamesUpdated int = 0;

    /* =========================================
       1) التحقق من الشهر وحاجز النشر
       ========================================= */

    IF @Month NOT BETWEEN 1 AND 12
        THROW 50101, N'رقم الشهر غير صحيح.', 1;

    SELECT
        @Enabled  = enabled,
        @MaxYear  = max_year,
        @MaxMonth = max_month
    FROM dbo.payroll_sync_control
    WHERE sync_type = N'WAGE_RECORD';

    IF @Enabled IS NULL
        THROW 50102,
              N'إعداد WAGE_RECORD غير موجود في payroll_sync_control.',
              1;

    IF @Enabled = 0
        THROW 50103, N'مزامنة سجل الأجور متوقفة.', 1;

    IF @MaxYear IS NOT NULL
       AND
       (
           @Year > @MaxYear
           OR
           (
               @Year = @MaxYear
               AND @Month > @MaxMonth
           )
       )
        THROW 50104,
              N'هذا الشهر محجوب حاليًا من النشر.',
              1;


    /* =========================================
       2) عدد صفوف المصدر
       ========================================= */

    SELECT
        @SourceRows = COUNT(*)
    FROM human_r_ash.dbo.payroll_annual_ALL
    WHERE YEAR_P = @Year
      AND MONTH_P = @Month
      AND sarfia_no > 1;


    /* =========================================
       3) تجهيز بيانات المصدر
       ========================================= */

    CREATE TABLE #Source
    (
        employee_id int NOT NULL,
        sarfia_no   int NOT NULL,
        band_code   int NOT NULL,
        amount      decimal(12,2) NOT NULL,

        PRIMARY KEY
        (
            employee_id,
            sarfia_no,
            band_code
        )
    );


    INSERT INTO #Source
    (
        employee_id,
        sarfia_no,
        band_code,
        amount
    )
    SELECT
        E.id,
        A.sarfia_no,
        A.band_code,
        CAST(A.BAND_VALUE AS decimal(12,2))

    FROM human_r_ash.dbo.payroll_annual_ALL A

    INNER JOIN dbo.employees E
        ON TRY_CONVERT(bigint, E.employee_code) = A.emp_no

    WHERE A.YEAR_P = @Year
      AND A.MONTH_P = @Month
      AND A.sarfia_no > 1;

    SET @EligibleRows = @@ROWCOUNT;


    /* =========================================
       4) عدد الموظفين المستبعدين
       ========================================= */

    SELECT
        @SkippedEmployees = COUNT(DISTINCT A.emp_no)

    FROM human_r_ash.dbo.payroll_annual_ALL A

    LEFT JOIN dbo.employees E
        ON TRY_CONVERT(bigint, E.employee_code) = A.emp_no

    WHERE A.YEAR_P = @Year
      AND A.MONTH_P = @Month
      AND A.sarfia_no > 1
      AND E.id IS NULL;


    /* =========================================
       5) خريطة البنود
       ========================================= */

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


    /* لا نخمن تصنيف بند مالي جديد */
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


        THROW 50105,
              N'يوجد بند مالي جديد غير معروف. تم إيقاف المزامنة لحماية تصنيف الاستحقاقات والخصومات.',
              1;
    END;


    /* =========================================
       6) تجهيز أسماء الصرفيات
       ========================================= */

    CREATE TABLE #SarfiaNames
    (
        sarfia_no      int NOT NULL,
        sarfia_desc_id int NULL,
        sarfia_name    nvarchar(500) NOT NULL,

        PRIMARY KEY (sarfia_no)
    );


    INSERT INTO #SarfiaNames
    (
        sarfia_no,
        sarfia_desc_id,
        sarfia_name
    )
    SELECT
        S.Sarfia_no,
        MAX(S.SarfiaDesc_ID),
        MAX(
            COALESCE(
                NULLIF(
                    LTRIM(RTRIM(D.SarfiaDesc_Desc)),
                    ''
                ),
                N'صرفية رقم ' + CONVERT(nvarchar(20), S.Sarfia_no)
            )
        )

    FROM human_r_ash.dbo.Payroll_Sarfiat S

    LEFT JOIN human_r_ash.dbo.payroll_SarfiaDesc D
        ON D.SarfiaDesc_ID = S.SarfiaDesc_ID

    WHERE S.Sarfia_Year = @Year
      AND S.Sarfia_Month = @Month
      AND S.Sarfia_no > 1

    GROUP BY S.Sarfia_no;


    /* أي صرفية موجودة في المرتبات ولم نجد اسمها */
    INSERT INTO #SarfiaNames
    (
        sarfia_no,
        sarfia_desc_id,
        sarfia_name
    )
    SELECT DISTINCT
        X.sarfia_no,
        NULL,
        N'صرفية رقم ' + CONVERT(nvarchar(20), X.sarfia_no)

    FROM #Source X

    WHERE NOT EXISTS
    (
        SELECT 1
        FROM #SarfiaNames N
        WHERE N.sarfia_no = X.sarfia_no
    );


    /* =========================================
       7) التنفيذ داخل Transaction واحدة
       ========================================= */

    BEGIN TRY

        BEGIN TRANSACTION;


        /* -------------------------------
           تحديث أسماء صرفيات هذا الشهر
           ------------------------------- */

        DELETE FROM dbo.payroll_sarfia_names
        WHERE sarfia_year = @Year
          AND sarfia_month = @Month;


        INSERT INTO dbo.payroll_sarfia_names
        (
            sarfia_no,
            sarfia_month,
            sarfia_year,
            sarfia_desc_id,
            sarfia_name,
            updated_at
        )
        SELECT
            sarfia_no,
            @Month,
            @Year,
            sarfia_desc_id,
            sarfia_name,
            SYSDATETIME()

        FROM #SarfiaNames;

        SET @SarfiaNamesUpdated = @@ROWCOUNT;


        /* -------------------------------
           حذف سجل الشهر القديم فقط
           ------------------------------- */

        DELETE FROM dbo.payroll_items
        WHERE [year] = @Year
          AND [month] = @Month
          AND sarfia_no > 1;

        SET @DeletedRows = @@ROWCOUNT;


        /* -------------------------------
           إدخال سجل الأجور الجديد
           ------------------------------- */

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
            S.sarfia_no,
            NULL

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


    /* =========================================
       8) تقرير النتيجة
       ========================================= */

    SELECT
        N'تمت مزامنة سجل الأجور بنجاح' AS Result,
        @Year AS [Year],
        @Month AS [Month],
        @SourceRows AS SourceRows,
        @EligibleRows AS EligibleRows,
        @DeletedRows AS PreviousPortalRows,
        @InsertedRows AS InsertedRows,
        @SkippedEmployees AS SkippedEmployees,
        @SarfiaNamesUpdated AS SarfiaNamesUpdated,
        SYSDATETIME() AS SyncTime;

END;
GO
