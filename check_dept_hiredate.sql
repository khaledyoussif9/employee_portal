USE EmployeePortal;

SELECT e.employee_code, e.full_name, e.job_title, e.hire_date, e.department_id, d.name AS department_name
FROM employees e
LEFT JOIN departments d ON d.id = e.department_id
WHERE e.employee_code = '30460968';

-- كام موظف إجمالاً معندوش قسم أو تاريخ تعيين
SELECT
    COUNT(*) AS total,
    SUM(CASE WHEN department_id IS NULL THEN 1 ELSE 0 END) AS missing_department,
    SUM(CASE WHEN hire_date IS NULL THEN 1 ELSE 0 END) AS missing_hire_date
FROM employees;
