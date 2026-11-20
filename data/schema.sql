-- Helpdesk demo schema. Runs unchanged on PostgreSQL and SQLite.
CREATE TABLE IF NOT EXISTS employees (
    employee_id   VARCHAR(8) PRIMARY KEY,
    full_name     VARCHAR(120) NOT NULL,
    department    VARCHAR(60)  NOT NULL,
    manager_id    VARCHAR(8),
    date_joined   DATE         NOT NULL
);

CREATE TABLE IF NOT EXISTS leave_balances (
    employee_id        VARCHAR(8) PRIMARY KEY REFERENCES employees(employee_id),
    annual_remaining   INTEGER NOT NULL,
    sick_remaining     INTEGER NOT NULL,
    casual_remaining   INTEGER NOT NULL,
    as_of              DATE    NOT NULL
);
