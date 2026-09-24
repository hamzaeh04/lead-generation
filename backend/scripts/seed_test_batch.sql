BEGIN;

-- Test company
INSERT INTO companies (
  id, workspace_id, name, normalized_name, domain, website,
  city, country, industry, employee_count
) VALUES (
  'a1000001-0000-4000-8000-000000000001',
  'ed2989e0-d14e-4b24-8fff-d2a166a685c6',
  'Canvas Digital',
  'canvas digital',
  'canvasdigital.org',
  'https://canvasdigital.org',
  'Karachi',
  'Pakistan',
  'Software',
  50
);

-- Contact 1: Arhan Ahmed
INSERT INTO contacts (
  id, workspace_id, company_id,
  first_name, last_name, full_name, job_title, seniority,
  email, email_status, city, country, industry, company_headcount, status
) VALUES (
  'b1000001-0000-4000-8000-000000000001',
  'ed2989e0-d14e-4b24-8fff-d2a166a685c6',
  'a1000001-0000-4000-8000-000000000001',
  'Arhan', 'Ahmed', 'Arhan Ahmed', 'Software Engineer', 'mid',
  'arhan.ahmed@canvasdigital.org', 'verified',
  'Karachi', 'Pakistan', 'Software', '50', 'new'
);

-- Contact 2: Masroor Alam
INSERT INTO contacts (
  id, workspace_id, company_id,
  first_name, last_name, full_name, job_title, seniority,
  email, email_status, city, country, industry, company_headcount, status
) VALUES (
  'b1000001-0000-4000-8000-000000000002',
  'ed2989e0-d14e-4b24-8fff-d2a166a685c6',
  'a1000001-0000-4000-8000-000000000001',
  'Masroor', 'Alam', 'Masroor Alam', 'Product Manager', 'mid',
  'masroor.alam@canvasdigital.org', 'verified',
  'Karachi', 'Pakistan', 'Software', '50', 'new'
);

-- Contact 3: Will Smith (mailinator test)
INSERT INTO contacts (
  id, workspace_id, company_id,
  first_name, last_name, full_name, job_title, seniority,
  email, email_status, city, country, industry, company_headcount, status
) VALUES (
  'b1000001-0000-4000-8000-000000000003',
  'ed2989e0-d14e-4b24-8fff-d2a166a685c6',
  'a1000001-0000-4000-8000-000000000001',
  'Will', 'Smith', 'Will Smith', 'QA Tester', 'junior',
  'willsmith@mailinator.com', 'verified',
  'Los Angeles', 'United States', 'Software', '50', 'new'
);

-- Search batch
INSERT INTO search_batches (
  id, workspace_id, sequence, provider, category,
  criteria_snapshot, companies_created, contacts_created, created_by
) VALUES (
  'c1000001-0000-4000-8000-000000000001',
  'ed2989e0-d14e-4b24-8fff-d2a166a685c6',
  9,
  'manual_test',
  'person_discovery',
  '{"label":"SMTP campaign test batch","source":"seed"}'::json,
  1,
  3,
  '667b7f97-e5bf-4d3f-8281-c38e459dd132'
);

-- Link contacts to batch
INSERT INTO search_batch_contacts (batch_id, contact_id, is_new) VALUES
  ('c1000001-0000-4000-8000-000000000001', 'b1000001-0000-4000-8000-000000000001', true),
  ('c1000001-0000-4000-8000-000000000001', 'b1000001-0000-4000-8000-000000000002', true),
  ('c1000001-0000-4000-8000-000000000001', 'b1000001-0000-4000-8000-000000000003', true);

COMMIT;

SELECT sb.sequence, sb.provider, sb.contacts_created, c.full_name, c.email
FROM search_batches sb
JOIN search_batch_contacts sbc ON sbc.batch_id = sb.id
JOIN contacts c ON c.id = sbc.contact_id
WHERE sb.id = 'c1000001-0000-4000-8000-000000000001'
ORDER BY c.email;
