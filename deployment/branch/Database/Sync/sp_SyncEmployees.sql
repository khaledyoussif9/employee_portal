
CREATE   PROCEDURE dbo.sp_SyncEmployees
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE
        @SourceEmployees int = 0,
        @EmployeesEligible int = 0,
        @EmployeesInserted int = 0,
        @EmployeesUpdated int = 0,
        @EmployeesUnchanged int = 0,
        @NewEmployeesExcluded900_999 int = 0,
        @SyncTime datetime2(7) = SYSDATETIME();

    BEGIN TRY
        BEGIN TRANSACTION;

        ------------------------------------------------------------
        -- 1)  ÃÂÌ“ »Ì«‰«  Human Resource
        ------------------------------------------------------------
        IF OBJECT_ID('tempdb..#EmployeeSource') IS NOT NULL
            DROP TABLE #EmployeeSource;

        SELECT
            CONVERT(nvarchar(40), E.emptid) AS employee_code,

            NULLIF(LTRIM(RTRIM(E.empname)), N'') AS full_name,

            NULLIF(
                LTRIM(RTRIM(CONVERT(nvarchar(28), E.qwmee_no))),
                N''
            ) AS national_id,

            NULLIF(LTRIM(RTRIM(E.Mobile1)), N'') AS phone,

            TRY_CONVERT(date, E.date_taain) AS hire_date,

            NULLIF(LTRIM(RTRIM(E.jobname)), N'') AS job_title,

            CASE
                WHEN E.CODE_SARF IS NULL THEN NULL
                ELSE CONVERT(nvarchar(40), E.CODE_SARF)
            END AS code_sarf,

            E.CODE_SARF AS code_sarf_int,

            NULLIF(LTRIM(RTRIM(E.Email)), N'') AS email,

            CASE
                WHEN E.Emp_Bank_Code IS NULL THEN NULL
                ELSE CONVERT(nvarchar(40), E.Emp_Bank_Code)
            END AS bank_employee_code,

            E.deparments AS hr_department_code,

            NULLIF(LTRIM(RTRIM(H.help_name)), N'')
                AS hr_department_name,

            D.id AS department_id

        INTO #EmployeeSource

        FROM human_r_ash.dbo.emply_details_old E

        LEFT JOIN human_r_ash.dbo.help_all H
            ON H.id_help = E.deparments
           AND H.catogry = 9
           AND E.deparments <> 9272

        LEFT JOIN dbo.departments D
            ON LTRIM(RTRIM(D.name)) COLLATE Arabic_CI_AS
             =
               LTRIM(RTRIM(H.help_name)) COLLATE Arabic_CI_AS

        WHERE E.emptid IS NOT NULL;


        ------------------------------------------------------------
        -- 2) ≈Ã„«·Ì ”Ã·«  «·„’œ—
        ------------------------------------------------------------
        SELECT
            @SourceEmployees = COUNT(*)
        FROM #EmployeeSource;


        ------------------------------------------------------------
        -- 3) «·„ÊŸ›Ê‰ «·Ãœœ «·„” »⁄œÊ‰
        --
        -- €Ì— „ÊÃÊœ »«·»Ê«»…
        -- ÊﬂÊœ «·’—› «·Õ«·Ì 900 ≈·Ï 999
        ------------------------------------------------------------
        SELECT
            @NewEmployeesExcluded900_999 = COUNT(*)

        FROM #EmployeeSource S

        WHERE
            S.code_sarf_int BETWEEN 900 AND 999

            AND NOT EXISTS
            (
                SELECT 1
                FROM dbo.employees P
                WHERE
                    P.employee_code COLLATE Arabic_CI_AS
                    =
                    S.employee_code COLLATE Arabic_CI_AS
            );


        ------------------------------------------------------------
        -- 4) «·„ÊŸ›Ê‰ «·„ÊÃÊœÊ‰ «·–Ì‰ ·œÌÂ„  €ÌÌ— ÕﬁÌﬁÌ
        --
        -- ‰ÕœÀ ›ﬁÿ:
        -- CODE_SARF
        -- «·ÊŸÌ›…
        -- «·≈œ«—…
        --
        -- «·„ÊŸ› «·„ÊÃÊœ ·« ‰Õ–›Â ·Ê √’»Õ 900-999
        ------------------------------------------------------------
        UPDATE P

        SET
            P.code_sarf = S.code_sarf,

            P.job_title = S.job_title,

            P.department_id =
                CASE
                    -- ·«ÌÊÃœ: «Õ ›Ÿ »«·≈œ«—… «·„ÊÃÊœ…
                    WHEN S.hr_department_code = 9272
                        THEN P.department_id

                    --  ÊÃœ ≈œ«—… ’ÕÌÕ… Ê„—»Êÿ…
                    WHEN S.department_id IS NOT NULL
                        THEN S.department_id

                    -- ·« ÌÊÃœ Mapping: «Õ ›Ÿ »«·Õ«·Ì…
                    ELSE P.department_id
                END,

            P.updated_at = @SyncTime

        FROM dbo.employees P

        INNER JOIN #EmployeeSource S
            ON P.employee_code COLLATE Arabic_CI_AS
             =
               S.employee_code COLLATE Arabic_CI_AS

        WHERE

            --------------------------------------------------------
            -- CODE_SARF  €Ì—
            --------------------------------------------------------
            ISNULL(P.code_sarf, N'') COLLATE Arabic_CI_AS
            <>
            ISNULL(S.code_sarf, N'') COLLATE Arabic_CI_AS

            OR

            --------------------------------------------------------
            -- «·ÊŸÌ›…  €Ì— 
            --------------------------------------------------------
            ISNULL(P.job_title, N'') COLLATE Arabic_CI_AS
            <>
            ISNULL(S.job_title, N'') COLLATE Arabic_CI_AS

            OR

            --------------------------------------------------------
            -- «·≈œ«—…  €Ì— 
            --------------------------------------------------------
            (
                S.hr_department_code <> 9272
                AND S.department_id IS NOT NULL
                AND ISNULL(P.department_id, -1)
                    <> S.department_id
            );

        SET @EmployeesUpdated = @@ROWCOUNT;


        ------------------------------------------------------------
        -- 5) ≈÷«›… «·„ÊŸ›Ì‰ «·Ãœœ
        --
        -- „Â„:
        -- «·„ÊŸ› «·ÃœÌœ CODE_SARF 900-999 ·« ÌœŒ· «·»Ê«»…
        ------------------------------------------------------------
        INSERT INTO dbo.employees
        (
            employee_code,
            full_name,
            national_id,
            phone,
            hire_date,
            department_id,
            job_title,
            status,
            created_at,
            updated_at,
            insurance_number,
            code_sarf,
            email,
            bank_employee_code
        )

        SELECT
            S.employee_code,

            COALESCE(S.full_name, N'»œÊ‰ «”„'),

            S.national_id,

            S.phone,

            S.hire_date,

            CASE
                WHEN S.hr_department_code = 9272
                    THEN NULL
                ELSE S.department_id
            END,

            S.job_title,

            N'active',

            @SyncTime,

            @SyncTime,

            NULL,

            S.code_sarf,

            S.email,

            S.bank_employee_code

        FROM #EmployeeSource S

        WHERE
            NOT EXISTS
            (
                SELECT 1
                FROM dbo.employees P
                WHERE
                    P.employee_code COLLATE Arabic_CI_AS
                    =
                    S.employee_code COLLATE Arabic_CI_AS
            )

            -- «” »⁄«œ «·„ÊŸ› «·ÃœÌœ ≈–« ﬂ«‰ 900-999
            AND
            (
                S.code_sarf_int IS NULL
                OR S.code_sarf_int NOT BETWEEN 900 AND 999
            );

        SET @EmployeesInserted = @@ROWCOUNT;


        ------------------------------------------------------------
        -- 6) ⁄œœ «·„ÊŸ›Ì‰ «·–Ì‰  ⁄«„·‰« „⁄Â„ ›⁄·Ì«
        --
        -- ‰” »⁄œ «·„ÊŸ›Ì‰ «·Ãœœ 900-999
        ------------------------------------------------------------
        SET @EmployeesEligible =
            @SourceEmployees - @NewEmployeesExcluded900_999;


        ------------------------------------------------------------
        -- 7) Õ”«» €Ì— «·„ €Ì—Ì‰
        ------------------------------------------------------------
        SET @EmployeesUnchanged =
            @EmployeesEligible
            - @EmployeesInserted
            - @EmployeesUpdated;

        IF @EmployeesUnchanged < 0
            SET @EmployeesUnchanged = 0;


        COMMIT TRANSACTION;


        ------------------------------------------------------------
        -- 8)  ﬁ—Ì— «·„“«„‰…
        ------------------------------------------------------------
        SELECT
            N' „  „“«„‰… «·„ÊŸ›Ì‰ »‰Ã«Õ' AS Result,

            @SourceEmployees AS SourceEmployees,

            @EmployeesInserted AS EmployeesInserted,

            @EmployeesUpdated AS EmployeesUpdated,

            @EmployeesUnchanged AS EmployeesUnchanged,

            @NewEmployeesExcluded900_999
                AS NewEmployeesExcluded900_999,

            @SyncTime AS SyncTime;

    END TRY

    BEGIN CATCH

        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;

        THROW;

    END CATCH;
END;

