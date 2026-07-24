-- 1) نتأكد من نسبة اكتمال تواريخ تعيين تانية غير date_taain
USE human_r_ash;

SELECT
    COUNT(*) AS total_rows,
    SUM(CASE WHEN date_job IS NOT NULL THEN 1 ELSE 0 END) AS has_date_job,
    SUM(CASE WHEN actualhire_date_606 IS NOT NULL THEN 1 ELSE 0 END) AS has_actualhire_606,
    SUM(CASE WHEN date_taain IS NOT NULL THEN 1 ELSE 0 END) AS has_date_taain,
    SUM(CASE WHEN date_contrazct_tain IS NOT NULL THEN 1 ELSE 0 END) AS has_date_contract_tain
FROM emply_details_old;

-- 2) نبحث في Human_Resource عن أي جدول فيه كود موظف + اسم قسم مع بعض
SELECT TABLE_NAME, COLUMN_NAME
FROM Human_Resource.INFORMATION_SCHEMA.COLUMNS
WHERE COLUMN_NAME LIKE '%qism%' OR COLUMN_NAME LIKE '%dept%'
   OR COLUMN_NAME LIKE '%edara%' OR COLUMN_NAME LIKE '%idara%'
   OR COLUMN_NAME LIKE '%sector%'
ORDER BY TABLE_NAME;
