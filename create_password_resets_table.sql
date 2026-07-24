USE EmployeePortal;

CREATE TABLE password_resets (
    id            INT IDENTITY(1,1) PRIMARY KEY,
    employee_id   INT NOT NULL,
    code          VARCHAR(10) NOT NULL,
    expires_at    DATETIME2 NOT NULL,
    used          BIT NOT NULL DEFAULT 0,
    created_at    DATETIME2 NOT NULL DEFAULT GETDATE(),

    CONSTRAINT fk_password_resets_employee
        FOREIGN KEY (employee_id) REFERENCES employees(id)
        ON DELETE CASCADE
);

CREATE INDEX idx_password_resets_lookup ON password_resets (employee_id, code, used);
