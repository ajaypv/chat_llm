-- Add source column to embedding table if missing (safe for re-runs)

DECLARE
  col_exists NUMBER := 0;
BEGIN
  SELECT COUNT(*)
  INTO col_exists
  FROM user_tab_columns
  WHERE table_name = '${PREFIX}_EMBEDDING'
    AND column_name = 'SOURCE';
  
  IF col_exists = 0 THEN
    EXECUTE IMMEDIATE 'ALTER TABLE ${PREFIX}_embedding ADD (source VARCHAR2(100))';
  END IF;
END;
/
