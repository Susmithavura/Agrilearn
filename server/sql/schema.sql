CREATE TABLE IF NOT EXISTS users (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    full_name VARCHAR(160) NOT NULL,
    username VARCHAR(80) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role ENUM('admin', 'coordinator', 'trainer', 'farmer', 'management') NOT NULL,
    email VARCHAR(254) NULL,
    phone VARCHAR(32) NULL,
    account_status ENUM('active', 'inactive') NOT NULL DEFAULT 'active',
    language_preference VARCHAR(8) NOT NULL DEFAULT 'en',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_users_username (username),
    UNIQUE KEY uq_users_email (email),
    KEY idx_users_role_status (role, account_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS farmers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    farmer_id VARCHAR(40) NOT NULL,
    user_id BIGINT UNSIGNED NULL,
    full_name VARCHAR(160) NOT NULL,
    village VARCHAR(160) NOT NULL,
    phone VARCHAR(32) NOT NULL,
    email VARCHAR(254) NULL,
    record_status ENUM('active', 'inactive') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_farmers_farmer_id (farmer_id),
    UNIQUE KEY uq_farmers_user (user_id),
    KEY idx_farmers_name (full_name),
    KEY idx_farmers_village (village),
    CONSTRAINT fk_farmers_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS trainers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    trainer_id VARCHAR(40) NOT NULL,
    user_id BIGINT UNSIGNED NULL,
    full_name VARCHAR(160) NOT NULL,
    specialization VARCHAR(255) NOT NULL,
    phone VARCHAR(32) NOT NULL,
    email VARCHAR(254) NULL,
    record_status ENUM('active', 'inactive') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_trainers_trainer_id (trainer_id),
    UNIQUE KEY uq_trainers_user (user_id),
    KEY idx_trainers_name (full_name),
    CONSTRAINT fk_trainers_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS training_programs (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    program_name VARCHAR(200) NOT NULL,
    category VARCHAR(120) NOT NULL,
    level ENUM('Foundation', 'Intermediate', 'Advanced') NOT NULL DEFAULT 'Foundation',
    description TEXT NOT NULL,
    objectives TEXT NULL,
    duration VARCHAR(80) NOT NULL,
    status ENUM('active', 'draft', 'archived') NOT NULL DEFAULT 'active',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_programs_name (program_name),
    KEY idx_programs_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS training_sessions (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    program_id BIGINT UNSIGNED NOT NULL,
    trainer_id BIGINT UNSIGNED NOT NULL,
    session_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NULL,
    location VARCHAR(200) NOT NULL,
    session_details TEXT NULL,
    status ENUM('scheduled', 'completed', 'cancelled') NOT NULL DEFAULT 'scheduled',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_sessions_date (session_date),
    KEY idx_sessions_trainer_date (trainer_id, session_date),
    KEY idx_sessions_program_date (program_id, session_date),
    CONSTRAINT fk_sessions_program FOREIGN KEY (program_id) REFERENCES training_programs (id) ON DELETE RESTRICT,
    CONSTRAINT fk_sessions_trainer FOREIGN KEY (trainer_id) REFERENCES trainers (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS program_farmers (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    program_id BIGINT UNSIGNED NOT NULL,
    farmer_id BIGINT UNSIGNED NOT NULL,
    enrollment_date DATE NOT NULL DEFAULT (CURRENT_DATE),
    participation_status ENUM('enrolled', 'active', 'completed', 'withdrawn') NOT NULL DEFAULT 'enrolled',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_program_farmer (program_id, farmer_id),
    KEY idx_enrollments_farmer_status (farmer_id, participation_status),
    CONSTRAINT fk_enrollments_program FOREIGN KEY (program_id) REFERENCES training_programs (id) ON DELETE RESTRICT,
    CONSTRAINT fk_enrollments_farmer FOREIGN KEY (farmer_id) REFERENCES farmers (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS attendance (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    session_id BIGINT UNSIGNED NOT NULL,
    farmer_id BIGINT UNSIGNED NOT NULL,
    attendance_status ENUM('present', 'absent') NOT NULL,
    recorded_by BIGINT UNSIGNED NOT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_attendance_session_farmer (session_id, farmer_id),
    KEY idx_attendance_farmer_status (farmer_id, attendance_status),
    KEY idx_attendance_recorded_by (recorded_by),
    CONSTRAINT fk_attendance_session FOREIGN KEY (session_id) REFERENCES training_sessions (id) ON DELETE RESTRICT,
    CONSTRAINT fk_attendance_farmer FOREIGN KEY (farmer_id) REFERENCES farmers (id) ON DELETE RESTRICT,
    CONSTRAINT fk_attendance_user FOREIGN KEY (recorded_by) REFERENCES users (id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS training_progress (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    farmer_id BIGINT UNSIGNED NOT NULL,
    program_id BIGINT UNSIGNED NOT NULL,
    progress_details TEXT NULL,
    progress_percent TINYINT UNSIGNED NOT NULL DEFAULT 0,
    completion_status ENUM('not_started', 'in_progress', 'completed') NOT NULL DEFAULT 'not_started',
    result VARCHAR(255) NULL,
    updated_by BIGINT UNSIGNED NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_progress_farmer_program (farmer_id, program_id),
    KEY idx_progress_program_status (program_id, completion_status),
    CONSTRAINT chk_progress_percent CHECK (progress_percent BETWEEN 0 AND 100),
    CONSTRAINT fk_progress_farmer FOREIGN KEY (farmer_id) REFERENCES farmers (id) ON DELETE RESTRICT,
    CONSTRAINT fk_progress_program FOREIGN KEY (program_id) REFERENCES training_programs (id) ON DELETE RESTRICT,
    CONSTRAINT fk_progress_user FOREIGN KEY (updated_by) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id BIGINT UNSIGNED NULL,
    action VARCHAR(80) NOT NULL,
    entity_type VARCHAR(80) NOT NULL,
    entity_id BIGINT UNSIGNED NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_audit_user_time (user_id, created_at),
    KEY idx_audit_entity (entity_type, entity_id),
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
