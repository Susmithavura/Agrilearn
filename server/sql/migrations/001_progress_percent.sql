ALTER TABLE training_progress
    ADD COLUMN progress_percent TINYINT UNSIGNED NOT NULL DEFAULT 0;

UPDATE training_progress
   SET progress_percent = CASE completion_status
       WHEN 'completed' THEN 100
       WHEN 'in_progress' THEN 1
       ELSE 0
   END;
