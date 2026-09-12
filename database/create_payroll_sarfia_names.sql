USE EmployeePortal;
GO

IF OBJECT_ID(N'dbo.payroll_sarfia_names', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.payroll_sarfia_names (
        id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
        sarfia_no INT NOT NULL,
        sarfia_month TINYINT NOT NULL,
        sarfia_year SMALLINT NOT NULL,
        sarfia_desc_id INT NULL,
        sarfia_name NVARCHAR(250) NOT NULL,
        updated_at DATETIME2 NOT NULL
            CONSTRAINT DF_payroll_sarfia_names_updated_at DEFAULT SYSDATETIME(),
        CONSTRAINT UQ_payroll_sarfia_names
            UNIQUE (sarfia_no, sarfia_month, sarfia_year)
    );
END;
GO

;WITH source_data AS (
    SELECT
        s.Sarfia_no AS sarfia_no,
        s.Sarfia_Month AS sarfia_month,
        s.Sarfia_Year AS sarfia_year,
        MAX(s.SarfiaDesc_ID) AS sarfia_desc_id,
        MAX(CONVERT(NVARCHAR(250), NULLIF(LTRIM(RTRIM(d.SarfiaDesc_Desc)), '')))
            AS sarfia_name
    FROM human_r_ash.dbo.Payroll_Sarfiat AS s
    INNER JOIN human_r_ash.dbo.payroll_SarfiaDesc AS d
        ON d.SarfiaDesc_ID = s.SarfiaDesc_ID
    GROUP BY s.Sarfia_no, s.Sarfia_Month, s.Sarfia_Year
)
MERGE dbo.payroll_sarfia_names AS target
USING source_data AS source
   ON target.sarfia_no = source.sarfia_no
  AND target.sarfia_month = source.sarfia_month
  AND target.sarfia_year = source.sarfia_year
WHEN MATCHED AND source.sarfia_name IS NOT NULL THEN
    UPDATE SET
        sarfia_desc_id = source.sarfia_desc_id,
        sarfia_name = source.sarfia_name,
        updated_at = SYSDATETIME()
WHEN NOT MATCHED BY TARGET AND source.sarfia_name IS NOT NULL THEN
    INSERT (sarfia_no, sarfia_month, sarfia_year, sarfia_desc_id, sarfia_name)
    VALUES (source.sarfia_no, source.sarfia_month, source.sarfia_year,
            source.sarfia_desc_id, source.sarfia_name);
GO

SELECT TOP (100)
    sarfia_no,
    sarfia_month,
    sarfia_year,
    sarfia_name,
    updated_at
FROM dbo.payroll_sarfia_names
ORDER BY sarfia_year DESC, sarfia_month DESC, sarfia_no;
