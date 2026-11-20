INSERT INTO employees (employee_id, full_name, department, manager_id, date_joined) VALUES
  ('E101', 'Rhea Menon',   'Engineering', 'E201', '2023-06-12'),
  ('E102', 'Arjun Patel',  'Engineering', 'E201', '2024-02-19'),
  ('E103', 'Sana Qureshi', 'Finance',     'E202', '2022-11-01');

INSERT INTO leave_balances (employee_id, annual_remaining, sick_remaining, casual_remaining, as_of) VALUES
  ('E101', 12, 2, 7, '2026-11-01'),
  ('E102',  9, 4, 3, '2026-11-01'),
  ('E103',  5, 8, 6, '2026-11-01');
