USE EmployeePortal;
GO

SET NOCOUNT ON;
SET XACT_ABORT ON;
GO

IF COL_LENGTH(N'dbo.payroll_items', N'balance') IS NULL
BEGIN
    ALTER TABLE dbo.payroll_items
    ADD balance DECIMAL(18, 2) NULL;
END;
GO

BEGIN TRY
    BEGIN TRANSACTION;

    /* إزالة الربط السابق حتى لا تبقى بنود عادية ظهرت كأقساط بسبب رصيد صفر. */
    UPDATE dbo.payroll_items
    SET balance = NULL
    WHERE balance IS NOT NULL;

    ;WITH Balances AS
    (
        SELECT
            emp_no,
            MONTH_P,
            YEAR_P,
            sarfia_no,
            band_code,
            MAX(raseed_val) AS raseed_val
        FROM human_r_ash.dbo.payroll_annual_ALL
        WHERE raseed_val > 0
        GROUP BY emp_no, MONTH_P, YEAR_P, sarfia_no, band_code
    )
    UPDATE p
    SET p.balance = b.raseed_val
    FROM dbo.payroll_items AS p
    INNER JOIN dbo.employees AS e
        ON e.id = p.employee_id
    INNER JOIN Balances AS b
        ON b.emp_no = TRY_CONVERT(BIGINT, e.employee_code)
       AND b.MONTH_P = p.month
       AND b.YEAR_P = p.year
       AND b.sarfia_no = p.sarfia_no
       AND b.band_code = p.band_code;

    DECLARE @UpdatedRows INT = @@ROWCOUNT;
    COMMIT TRANSACTION;

    SELECT @UpdatedRows AS updated_installment_rows;
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
GO

SELECT TOP (200)
    e.employee_code,
    e.full_name,
    p.band_code,
    p.band_name,
    p.amount AS installment_value,
    p.balance AS remaining_balance,
    p.month,
    p.year,
    p.sarfia_no
FROM dbo.payroll_items AS p
INNER JOIN dbo.employees AS e
    ON e.id = p.employee_id
WHERE p.balance IS NOT NULL
ORDER BY p.year DESC, p.month DESC, e.employee_code, p.band_code;
GO
