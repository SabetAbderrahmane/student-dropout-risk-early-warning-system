import { test, expect, Page, BrowserContext } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';

const root = path.resolve(__dirname, '../..');
const state = JSON.parse(fs.readFileSync(path.join(root, '.venv/e1/session.json'), 'utf8'));
const output = path.join(root, 'output/playwright/e1');
const evidence: any = { base: state.baseURL, api: state.api, requests: [], screenshots: [], errors: [], console_errors: [] };
const data: any = {};
const tokenKey = 'student-dropout-access-token';
let system: Page, academic: Page, advisor: Page, other: Page;
let contexts: BrowserContext[] = [];

function observe(page: Page) {
  page.on('pageerror', error => evidence.errors.push({ page: new URL(page.url()).pathname, message: error.message }));
  page.on('console', message => {
    if (message.type() === 'error' && !message.text().startsWith('Failed to load resource:'))
      evidence.console_errors.push({ page: new URL(page.url()).pathname, message: message.text() });
  });
  page.on('response', response => {
    if (response.url().startsWith(state.api)) evidence.requests.push({ method: response.request().method(), path: response.url().replace(state.api, ''), status: response.status() });
  });
}
async function shot(page: Page, name: string) {
  fs.mkdirSync(path.join(output, 'screenshots'), { recursive: true });
  if (name !== '13-loading-dashboard') await page.waitForLoadState('networkidle');
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: path.join(output, 'screenshots', name + '.png'), fullPage: true });
  evidence.screenshots.push(name + '.png');
}
async function get(page: Page, endpoint: string) {
  const token = await page.evaluate(key => sessionStorage.getItem(key), tokenKey);
  const response = await page.request.get(state.api + endpoint, { headers: { Authorization: 'Bearer ' + token } });
  expect(response.status(), endpoint).toBe(200);
  return response.json();
}
async function mutation(page: Page, method: string, endpoint: string, action: () => Promise<any>, status = 200) {
  const received = page.waitForResponse(r => r.url().split('?')[0] === state.api + endpoint && r.request().method() === method);
  await action(); const response = await received;
  expect(response.status(), method + ' ' + endpoint + ': ' + await response.text()).toBe(status);
  return response.json();
}
async function login(page: Page, role: string, first = true) {
  console.log('UI login:', role);
  const account = state.users[role];
  await page.goto('/login');
  await page.getByLabel('Username or email').fill(account.username);
  await page.getByLabel('Password', { exact: true }).fill(first ? account.initial : account.password);
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  if (first) {
    await expect(page).toHaveURL(/change-password/);
    await page.getByLabel('Current password', { exact: true }).fill(account.initial);
    await page.getByLabel('New password', { exact: true }).fill(account.password);
    await page.getByLabel('Confirm new password').fill(account.password);
    await page.getByRole('button', { name: 'Change password', exact: true }).click();
  }
  await expect(page).toHaveURL(/dashboard/);
  await expect(page.getByRole('heading', { name: /Academic Risk Overview/ })).toBeVisible();
  console.log('UI dashboard:', role);
}
async function confirmAccount(page: Page, title: string) {
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('checkbox').check();
  await dialog.getByRole('button', { name: title, exact: true }).click();
  await expect(dialog).toBeHidden();
}
async function dossier(page: Page) {
  await page.goto('/students/' + data.student.id);
  await expect(page.getByRole('heading', { name: 'E1 Synthetic Amira' })).toBeVisible();
}
async function predict(stage: string) {
  await academic.getByRole('button', { name: 'Run Prediction', exact: true }).first().click();
  const dialog = academic.getByRole('dialog');
  await dialog.getByRole('combobox', { name: 'Prediction stage', exact: true }).selectOption(stage);
  const prediction = await mutation(academic, 'POST', '/students/' + data.student.id + '/predictions',
    () => dialog.getByRole('button', { name: 'Confirm Prediction', exact: true }).click(), 201);
  await expect(dialog).toBeHidden();
  if (stage === 'LEGACY') {
    expect(prediction.model_target_type).toBe('BINARY_DROPOUT');
    expect(prediction.class_probabilities).toBeNull();
    return prediction;
  }
  expect(prediction.prediction_stage).toBe(stage);
  expect(prediction.model_target_type).toBe('MULTICLASS_OUTCOME');
  expect(Object.keys(prediction.class_probabilities).sort()).toEqual(['DROPOUT', 'ENROLLED', 'GRADUATE']);
  expect(Object.values(prediction.class_probabilities).reduce((a: number, b: any) => a + b, 0)).toBeCloseTo(1, 5);
  expect(prediction.top_explanation_factors.length).toBeGreaterThan(0);
  return prediction;
}
async function openCase(page: Page) {
  await dossier(page);
  await page.getByRole('button', { name: 'Interventions', exact: true }).click();
  await page.getByRole('button', { name: 'Open Intervention: E1 Synthetic Support Plan', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('heading', { name: 'E1 Synthetic Support Plan', exact: true })).toBeVisible();
}
async function closeDialog(page: Page) {
  await page.getByRole('dialog').getByRole('button', { name: 'Close dialog', exact: true }).click();
  await expect(page.getByRole('dialog')).toBeHidden();
}

test.describe.serial('E1 actual full-stack acceptance', () => {
  test.beforeAll(async ({ browser }) => {
    fs.mkdirSync(output, { recursive: true });
    for (const role of ['system', 'academic', 'advisor', 'other']) {
      const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, timezoneId: 'Africa/Casablanca' });
      contexts.push(context); const page = await context.newPage(); observe(page);
      page.setDefaultTimeout(15_000);
      if (role === 'system') system = page;
      if (role === 'academic') academic = page;
      if (role === 'advisor') advisor = page;
      if (role === 'other') other = page;
    }
  });
  test.afterEach(async ({}, info) => {
    if (info.status !== info.expectedStatus) {
      for (const [name, page] of Object.entries({ system, academic, advisor, other })) {
        if (!page?.isClosed()) fs.writeFileSync(path.join(output, name + '-failure.txt'), await page.locator('body').ariaSnapshot());
      }
    }
    fs.mkdirSync(output, { recursive: true });
    fs.writeFileSync(path.join(output, 'http-evidence.json'), JSON.stringify(evidence, null, 2));
  });
  test.afterAll(async () => { for (const context of contexts) await context.close(); });

  test('E1-01 System administrator onboarding and user lifecycle', async () => {
    await login(system, 'system');
    await system.goto('/admin/users');
    for (const role of ['academic', 'advisor', 'other_advisor', 'disposable']) {
      console.log('UI create user:', role);
      const account = state.users[role];
      await system.getByRole('button', { name: '+ Create User', exact: true }).click();
      const dialog = system.getByRole('dialog');
      await dialog.getByLabel('Full name', { exact: true }).fill('E1 Synthetic ' + role);
      await dialog.getByLabel('Username', { exact: true }).fill(account.username);
      await dialog.getByLabel('Email', { exact: true }).fill(account.username + '@example.edu');
      await dialog.getByRole('combobox', { name: 'Role', exact: true }).selectOption(role === 'academic' ? 'ACADEMIC_ADMIN' : 'ACADEMIC_ADVISOR');
      await dialog.getByLabel('Temporary password', { exact: true }).fill(account.initial);
      await dialog.getByLabel('Confirm temporary password').fill(account.initial);
      await confirmAccount(system, 'Create User');
    }
    await system.getByRole('button', { name: 'Edit e1_disposable', exact: true }).click();
    await system.getByRole('dialog').getByLabel('Full name', { exact: true }).fill('E1 Synthetic Disposable Updated');
    await confirmAccount(system, 'Edit User');
    await system.getByRole('button', { name: 'Deactivate e1_disposable', exact: true }).click();
    await confirmAccount(system, 'Deactivate User');
    await system.getByRole('button', { name: 'Activate e1_disposable', exact: true }).click();
    await confirmAccount(system, 'Activate User');
    await system.getByRole('button', { name: 'Reset password e1_disposable', exact: true }).click();
    const reset = system.getByRole('dialog');
    await reset.getByLabel('Temporary password', { exact: true }).fill(state.users.disposable.password);
    await reset.getByLabel('Confirm temporary password').fill(state.users.disposable.password);
    await confirmAccount(system, 'Reset Password');
    const accounts = await get(system, '/users?page_size=100');
    data.advisor = accounts.items.find((x: any) => x.username === 'e1_advisor');
    data.otherAdvisor = accounts.items.find((x: any) => x.username === 'e1_other_advisor');
    expect(data.advisor.role).toBe('ACADEMIC_ADVISOR');
    await shot(system, '01-user-administration');
    await login(academic, 'academic');
    await login(advisor, 'advisor');
    await login(other, 'other_advisor');
  });

  test('E1-02 CSV validation, correction, commit and student editing', async () => {
    await academic.goto('/imports');
    const cases = JSON.parse(fs.readFileSync(path.join(root, 'backend/tests/fixtures/outcome_inference_cases.json'), 'utf8')).cases;
    const sample = cases.find((x: any) => x.prediction_stage === 'ENROLLMENT');
    expect(sample).toBeTruthy(); data.features = sample.canonical_features;
    const template = await academic.request.get(state.api + '/imports/template', { headers: { Authorization: 'Bearer ' + await academic.evaluate(k => sessionStorage.getItem(k), tokenKey) } });
    expect(template.status()).toBe(200);
    const headers = (await template.text()).trim().split(',');
    function row(number: string, name: string, invalid = false) {
      const values = { ...data.features, student_number: number, name, admission_method: 'Synthetic general admission', previous_qualification: 'Synthetic secondary education', ...(invalid ? { age_at_enrollment: 'not-a-number' } : {}) };
      return headers.map((key: string) => values[key] ?? '').join(',');
    }
    const csv = headers.join(',') + '\n' + row('E1-001', 'E1 Synthetic Amira') + '\n' + row('E1-002', 'E1 Synthetic Bilal', true) + '\n';
    await academic.getByLabel('CSV file to stage').setInputFiles({ name: 'e1-synthetic-students.csv', mimeType: 'text/csv', buffer: Buffer.from(csv) });
    const batch = await mutation(academic, 'POST', '/imports/staged/csv', () => academic.getByRole('button', { name: 'Stage CSV for Review' }).click(), 201);
    data.batch = batch.id;
    await expect(academic.getByRole('button', { name: 'Commit Included Rows' })).toBeDisabled();
    await shot(academic, '02-staged-validation');
    await academic.getByRole('button', { name: 'Edit CSV row 3', exact: true }).click();
    await academic.getByLabel('Edited age_at_enrollment', { exact: true }).fill('24');
    await academic.getByRole('button', { name: 'Save Correction', exact: true }).click();
    await expect(academic.getByRole('dialog')).toBeHidden();
    await expect(academic.getByRole('button', { name: 'Commit Included Rows' })).toBeEnabled();
    await academic.getByRole('button', { name: 'Commit Included Rows' }).click();
    await mutation(academic, 'POST', '/imports/staged/' + batch.id + '/commit', () => academic.getByRole('button', { name: 'Confirm Commit', exact: true }).click());
    await expect(academic.getByRole('heading', { name: 'Import completed', exact: true })).toBeVisible();
    await shot(academic, '03-committed-import');
    const students = await get(academic, '/students?page_size=100');
    data.student = students.items.find((x: any) => x.student_number === 'E1-001');
    expect(students.items.some((x: any) => x.student_number === 'E1-002')).toBeTruthy();
    await academic.goto('/students');
    await academic.getByRole('button', { name: /Add Student|Create Student/i }).first().click();
    await academic.getByRole('dialog').getByLabel('Student ID', { exact: true }).fill('E1-003');
    await academic.getByRole('dialog').getByLabel('Full name', { exact: true }).fill('E1 Synthetic Chadia');
    await academic.getByRole('button', { name: 'Create student', exact: true }).click();
    await expect(academic.getByRole('dialog')).toBeHidden();
    await dossier(academic);
    await academic.getByRole('button', { name: 'Academic record', exact: true }).click();
    await academic.getByRole('button', { name: 'Edit Student', exact: true }).click();
    await academic.getByRole('dialog').getByLabel('Gender', { exact: true }).fill('Synthetic recorded value');
    await academic.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click();
    await expect(academic.getByRole('dialog')).toBeHidden();
    await shot(academic, '04-student-dossier');
  });

  test('E1-03 System administrator validates and activates stage models', async () => {
    await system.goto('/predictions');
    for (const [stage, version] of [['Enrollment', 'enrollment-outcome-v1'], ['First semester', 'first-semester-outcome-v1']]) {
      const card = system.locator('article').filter({ hasText: version });
      await card.getByRole('button', { name: /Validate/ }).click();
      const dialog = system.getByRole('dialog');
      await dialog.getByLabel('Search students', { exact: true }).fill('E1-001');
      await dialog.getByRole('combobox', { name: 'Validation student', exact: true }).selectOption(data.student.id);
      await dialog.getByRole('checkbox').check();
      await mutation(system, 'POST', '/models/' + version + '/validate', () => dialog.getByRole('button', { name: 'Run validation', exact: true }).click());
      await expect(dialog).toBeHidden();
      await card.getByRole('button', { name: /Activate/ }).click();
      await system.getByRole('dialog').getByRole('checkbox').check();
      await mutation(system, 'POST', '/models/' + version + '/activate', () => system.getByRole('dialog').getByRole('button', { name: 'Activate model', exact: true }).click());
      await expect(system.getByRole('dialog')).toBeHidden();
    }
    const catalog = await get(system, '/models');
    expect(catalog.items).toHaveLength(3);
    expect(catalog.items.every((x: any) => x.artifact_available && x.is_active)).toBeTruthy();
    await shot(system, '05-approved-model-registry');
  });

  test('E1-04 Enrollment assessment, explanation and advisor assignment', async () => {
    await dossier(academic);
    data.enrollment = await predict('ENROLLMENT');
    expect(data.enrollment.risk_level).toBe('MEDIUM');
    await academic.getByRole('button', { name: 'Predictions', exact: true }).click();
    await expect(academic.getByText(data.enrollment.predicted_outcome, { exact: false }).first()).toBeVisible();
    await academic.getByText(/^Recorded explanation factors/).first().click();
    await shot(academic, '06-enrollment-assessment-explanation');
    const profile = await get(academic, '/students/' + data.student.id + '/profile');
    data.warning = profile.warning_history.find((x: any) => x.prediction_id === data.enrollment.id);
    expect(data.warning).toBeTruthy();
    await academic.getByRole('button', { name: 'Warnings', exact: true }).click();
    await academic.getByRole('button', { name: 'Assign Advisor', exact: true }).first().click();
    await academic.getByRole('dialog').getByRole('combobox', { name: 'Assigned advisor', exact: true }).selectOption(data.advisor.id);
    await mutation(academic, 'PATCH', '/warnings/' + data.warning.id + '/assignment', () => academic.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click());
    await expect(academic.getByRole('dialog')).toBeHidden();
    const persisted = await get(academic, '/warnings/' + data.warning.id);
    expect(persisted.assigned_advisor.id).toBe(data.advisor.id);
    await shot(academic, '07-assigned-warning');
  });

  test('E1-05 Advisor reviews warning, creates case, notes and scheduled contact', async () => {
    await advisor.goto('/warnings');
    await expect(advisor.locator('body')).toContainText('E1 Synthetic Amira');
    await dossier(advisor);
    await advisor.getByRole('button', { name: 'Warnings', exact: true }).click();
    await advisor.getByRole('button', { name: 'Review Warning', exact: true }).first().click();
    await advisor.getByRole('dialog').getByLabel(/Review note/).fill('Synthetic advisor review: discuss enrollment support needs with this student.');
    await mutation(advisor, 'POST', '/warnings/' + data.warning.id + '/reviews', () => advisor.getByRole('dialog').getByRole('button', { name: 'Confirm Warning', exact: true }).click(), 201);
    await expect(advisor.getByRole('dialog')).toBeHidden();
    await advisor.getByRole('button', { name: 'Create Intervention', exact: true }).first().click();
    const create = advisor.getByRole('dialog');
    await create.getByRole('combobox', { name: 'Support type', exact: true }).selectOption('ACADEMIC_ADVISING');
    await create.getByLabel(/Title/).fill('E1 Synthetic Support Plan');
    await create.getByLabel(/Description/).fill('Synthetic demonstration: academic advising and a progress contact.');
    data.intervention = await mutation(advisor, 'POST', '/interventions', () => create.getByRole('button', { name: 'Create Intervention', exact: true }).click(), 201);
    await expect(create).toBeHidden();
    await openCase(advisor);
    await advisor.getByRole('dialog').getByRole('button', { name: 'Start Intervention', exact: true }).click();
    await expect(advisor.getByRole('dialog').getByRole('button', { name: 'Mark Action Required', exact: true })).toBeVisible();
    await advisor.getByRole('dialog').getByRole('button', { name: 'Add Note', exact: true }).click();
    await advisor.getByLabel('Case note', { exact: true }).fill('E1 synthetic note: initial advising conversation completed.');
    await mutation(advisor, 'POST', '/interventions/' + data.intervention.id + '/notes', () => advisor.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click(), 201);
    await expect(advisor.getByLabel('Case note', { exact: true })).toBeHidden();
    await advisor.getByRole('dialog').getByRole('button', { name: 'Schedule Follow-Up', exact: true }).click();
    const nextDay = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
    await advisor.getByLabel('Scheduled for (your local time)', { exact: true }).fill(nextDay + 'T10:00');
    await advisor.getByRole('combobox', { name: 'Contact method', exact: true }).selectOption('IN_PERSON');
    await advisor.getByLabel('Follow-up purpose', { exact: true }).fill('E1 synthetic progress check');
    data.follow = await mutation(advisor, 'POST', '/interventions/' + data.intervention.id + '/follow-ups', () => advisor.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click(), 201);
    expect(data.follow.assigned_advisor.id).toBe(data.advisor.id);
    await expect(advisor.getByLabel('Follow-up purpose', { exact: true })).toBeHidden();
    await shot(advisor, '08-advisor-intervention-and-note');
    await closeDialog(advisor);
  });

  test('E1-06 Ownership transfer, unassigned denial and follow-up completion', async () => {
    await openCase(other);
    await expect(other.getByRole('dialog').getByRole('button', { name: 'Add Note', exact: true })).toBeHidden();
    const otherToken = await other.evaluate(k => sessionStorage.getItem(k), tokenKey);
    const denial = await other.request.post(state.api + '/interventions/' + data.intervention.id + '/notes', { headers: { Authorization: 'Bearer ' + otherToken }, data: { note: 'Must be rejected', expected_revision: (await get(other, '/interventions/' + data.intervention.id)).revision } });
    expect(denial.status()).toBe(403);
    await closeDialog(other);
    for (const [target, reason] of [[data.otherAdvisor.id, 'E1 synthetic temporary handover'], [data.advisor.id, 'E1 synthetic return to original advisor']]) {
      await openCase(academic);
      await academic.getByRole('dialog').getByRole('button', { name: 'Transfer Intervention', exact: true }).click();
      await academic.getByRole('dialog').getByRole('combobox', { name: 'Assigned advisor', exact: true }).selectOption(target);
      await academic.getByLabel('Transfer reason', { exact: true }).fill(reason);
      await mutation(academic, 'POST', '/interventions/' + data.intervention.id + '/transfer', () => academic.getByRole('dialog').getByRole('button', { name: 'Save', exact: true }).click());
      await expect(academic.getByLabel('Transfer reason', { exact: true })).toBeHidden();
      expect((await get(academic, '/follow-ups/' + data.follow.id)).assigned_advisor.id).toBe(target);
      await closeDialog(academic);
    }
    await dossier(advisor);
    await advisor.getByRole('button', { name: 'Follow-ups', exact: true }).click();
    await advisor.getByRole('button', { name: 'Open Follow-Up: E1 synthetic progress check', exact: true }).click();
    await advisor.getByRole('dialog').getByRole('button', { name: 'Complete Follow-Up', exact: true }).click();
    await advisor.getByRole('dialog').getByRole('combobox', { name: 'Follow-up outcome', exact: true }).selectOption('PROGRESS_OBSERVED');
    await advisor.getByLabel('Follow-up notes', { exact: true }).fill('E1 synthetic progress: student attended the support session.');
    await mutation(advisor, 'POST', '/follow-ups/' + data.follow.id + '/complete', () => advisor.getByRole('dialog').getByRole('button', { name: 'Record Outcome', exact: true }).click());
    await expect(advisor.getByRole('dialog').getByRole('button', { name: 'Complete Follow-Up', exact: true })).toBeHidden();
    await shot(advisor, '09-completed-follow-up');
    await closeDialog(advisor);
    await openCase(advisor);
    await advisor.getByRole('dialog').getByRole('button', { name: 'Complete Intervention', exact: true }).click();
    await advisor.getByRole('dialog').getByRole('combobox', { name: 'Completion outcome', exact: true }).selectOption('SUPPORT_COMPLETED');
    await advisor.getByLabel('Completion notes', { exact: true }).fill('E1 synthetic support completed with documented follow-up.');
    await mutation(advisor, 'POST', '/interventions/' + data.intervention.id + '/complete', () => advisor.getByRole('dialog').getByRole('button', { name: 'Record Outcome', exact: true }).click());
    await expect(advisor.getByRole('dialog').getByRole('button', { name: 'Complete Intervention', exact: true })).toBeHidden();
    await shot(advisor, '10-completed-intervention');
    await closeDialog(advisor);
    const persisted = await get(advisor, '/interventions/' + data.intervention.id);
    expect(persisted.status).toBe('COMPLETED');
    expect(persisted.notes.some((x: any) => x.author_id === data.advisor.id)).toBeTruthy();
    expect((await get(advisor, '/follow-ups/' + data.follow.id)).stored_status).toBe('COMPLETED');
    evidence.persisted_case = persisted;
  });

  test('E1-07 First-semester update, reassessment and durable case history', async () => {
    await dossier(academic);
    const previousSemester = await predict('FIRST_SEMESTER');
    await academic.getByRole('button', { name: 'Academic record', exact: true }).click();
    await academic.getByRole('button', { name: 'Edit Semester Record', exact: true }).click();
    const dialog = academic.getByRole('dialog');
    for (const [label, value] of Object.entries({ 'Credited Units': '0', 'Enrolled Units': '6', 'Evaluations': '7', 'Approved Units': '6', 'Average Grade': '15', 'Without Evaluations': '0' })) {
      await dialog.getByRole('spinbutton', { name: new RegExp('^' + label + '$', 'i') }).fill(value);
    }
    await mutation(academic, 'PUT', '/students/' + data.student.id + '/semester-1', () => dialog.getByRole('button', { name: 'Save', exact: true }).click());
    await expect(dialog).toBeHidden();
    const stale = await get(academic, '/students/' + data.student.id + '/profile');
    expect(stale.prediction_history.find((x: any) => x.id === previousSemester.id).prediction_freshness).toBe('INPUTS_CHANGED');
    await academic.getByRole('button', { name: 'Predictions', exact: true }).click();
    await expect(academic.getByText(/Historical assessment · Academic inputs changed/).first()).toBeVisible();
    await shot(academic, 'reassessment-required');
    data.semester = await predict('FIRST_SEMESTER');
    const profile = await get(academic, '/students/' + data.student.id + '/profile');
    expect(profile.operational_prediction.id).toBe(data.semester.id);
    expect(profile.prediction_history.some((x: any) => x.id === data.enrollment.id)).toBeTruthy();
    expect(profile.interventions.some((x: any) => x.id === data.intervention.id && x.status === 'COMPLETED')).toBeTruthy();
    expect(profile.follow_ups.some((x: any) => x.id === data.follow.id && x.effective_status === 'COMPLETED')).toBeTruthy();
    await academic.getByRole('button', { name: 'History', exact: true }).click();
    await expect(academic.getByRole('heading', { name: 'Student history', exact: true })).toBeVisible();
    await expect(academic.locator('.dossier-timeline li')).toHaveCount(profile.timeline.length);
    expect(profile.timeline.length).toBeGreaterThan(6);
    await shot(academic, '11-durable-case-history');
    evidence.final_profile = profile;
    evidence.enrollment = data.enrollment; evidence.semester = data.semester;
    await academic.getByRole('button', { name: 'Predictions', exact: true }).click();
    evidence.legacy = await predict('LEGACY');
  });

  test('E1-08 All screens, navigation, desktop/tablet themes, empty/loading/error states', async () => {
    for (const route of ['/dashboard', '/students', '/students/' + data.student.id, '/imports', '/predictions', '/warnings', '/interventions', '/follow-ups', '/admin/users', '/change-password']) {
      const screen = route === '/admin/users' || route === '/predictions' ? system : academic;
      await screen.goto(route);
      await expect(screen.locator('h1').first()).not.toHaveText(/Verifying/);
      await expect(screen.locator('h1').first()).toBeVisible();
      await screen.waitForLoadState('networkidle');
      await expect(screen.locator('[aria-busy="true"]')).toHaveCount(0);
      const badLinks = await screen.locator('a[href]').evaluateAll(links => links.filter(x => !x.getAttribute('href') || x.getAttribute('href') === '#').length);
      expect(badLinks, route + ' placeholder anchors').toBe(0);
      {
        await screen.getByRole('combobox', { name: 'Theme', exact: true }).selectOption('dark');
        await expect(screen.locator('html')).toHaveAttribute('data-theme', 'dark');
        await screen.setViewportSize({ width: 1024, height: 768 });
        expect(await screen.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), route + ' tablet page overflow').toBeTruthy();
        await shot(screen, 'tablet-dark-' + route.replaceAll('/', '-').slice(1));
        await screen.setViewportSize({ width: 768, height: 1024 });
        expect(await screen.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), route + ' portrait tablet overflow').toBeTruthy();
        await shot(screen, 'portrait-dark-' + route.replaceAll('/', '-').slice(1));
        await screen.setViewportSize({ width: 1440, height: 1000 });
        await screen.getByRole('combobox', { name: 'Theme', exact: true }).selectOption('light');
        await expect(screen.locator('html')).toHaveAttribute('data-theme', 'light');
      }
    }
    await system.goto('/dashboard');
    for (const [name, route] of [['Students', '/students'], ['Data Import', '/imports'], ['Risk Predictions', '/predictions'], ['Early Warnings', '/warnings'], ['Interventions', '/interventions'], ['Follow-Ups', '/follow-ups'], ['Users', '/admin/users']]) {
      await system.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name, exact: true }).click();
      await expect(system).toHaveURL(state.baseURL + route);
    }
    await system.setViewportSize({ width: 768, height: 1024 });
    await system.getByRole('button', { name: 'Toggle navigation', exact: true }).click();
    await system.getByRole('navigation', { name: 'Main navigation' }).getByRole('link', { name: 'Students', exact: true }).click();
    await expect(system).toHaveURL(state.baseURL + '/students');
    await expect(system.getByRole('button', { name: 'Toggle navigation', exact: true })).toHaveAttribute('aria-expanded', 'false');
    await system.setViewportSize({ width: 1440, height: 1000 });
    await academic.goto('/students');
    await academic.getByRole('searchbox').first().fill('E1-no-such-synthetic-student');
    await expect(academic.getByText('No students found', { exact: true })).toBeVisible();
    await shot(academic, '12-empty-registry-search');
    let release: () => void = () => {};
    const gate = new Promise<void>(resolve => { release = resolve; });
    await academic.route(state.api + '/dashboard/overview**', async route => { await gate; await route.continue(); });
    await academic.goto('/dashboard');
    await expect(academic.locator('[aria-busy="true"], [aria-label*="Loading"]').first()).toBeVisible();
    await shot(academic, '13-loading-dashboard');
    release(); await academic.unrouteAll({ behavior: 'wait' });
    await expect(academic.getByText('Total Students', { exact: true })).toBeVisible();
    await academic.route(state.api + '/dashboard/overview**', route => route.abort('internetdisconnected'));
    await academic.reload();
    await expect(academic.getByRole('alert').filter({ hasText: /reach|Unable|request|connection/i }).first()).toBeVisible();
    await shot(academic, '14-offline-error-state');
    await academic.unrouteAll();
    await academic.getByRole('button', { name: /Retry/ }).first().click();
    await expect(academic.getByText('Total Students', { exact: true })).toBeVisible();
    const publicPage = await system.context().newPage(); observe(publicPage);
    await publicPage.goto('/');
    await expect(publicPage.getByText(/Review student academic records/)).toBeVisible();
    await expect(publicPage.getByText(/deferred to later phases/)).toBeHidden();
    await publicPage.getByRole('combobox', { name: 'Theme', exact: true }).selectOption('dark');
    await publicPage.setViewportSize({ width: 1024, height: 768 });
    await shot(publicPage, '16-home-tablet-dark');
    await publicPage.getByRole('link', { name: 'Sign in', exact: true }).click();
    await expect(publicPage.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible();
    await shot(publicPage, '17-login-tablet-dark');
    await publicPage.close();
    expect(evidence.errors).toEqual([]); expect(evidence.console_errors).toEqual([]);
  });

  test('E1-09 Role denial, revoked account and expired-session boundary', async () => {
    await advisor.goto('/admin/users');
    await expect(advisor.getByRole('heading', { name: 'Permission denied', exact: true })).toBeVisible();
    await advisor.goto('/imports');
    await expect(advisor.getByRole('heading', { name: 'Import access is restricted', exact: true })).toBeVisible();
    for (const [page, endpoint, method, payload] of [[advisor, '/students', 'post', { student_number: 'DENIED', name: 'Must not persist' }], [academic, '/users', 'get', undefined], [system, '/students', 'post', { student_number: 'DENIED-SYSTEM', name: 'Must not persist' }]] as const) {
      const token = await page.evaluate(k => sessionStorage.getItem(k), tokenKey);
      const response = await page.request.fetch(state.api + endpoint, { method, headers: { Authorization: 'Bearer ' + token }, data: payload });
      expect(response.status()).toBe(403);
    }
    // A genuinely expired signature for this synthetic user's existing claims;
    // no successful response or authorization is mocked or bypassed.
    await academic.goto('/dashboard');
    const token = await academic.evaluate(k => sessionStorage.getItem(k), tokenKey);
    const [head, body] = token!.split('.');
    const claims = JSON.parse(Buffer.from(body, 'base64url').toString());
    claims.iat = Math.floor(Date.now() / 1000) - 7200; claims.exp = claims.iat + 60;
    const unsigned = head + '.' + Buffer.from(JSON.stringify(claims)).toString('base64url');
    const expired = unsigned + '.' + crypto.createHmac('sha256', state.jwt_secret).update(unsigned).digest('base64url');
    await academic.evaluate(([key, value]) => sessionStorage.setItem(key, value), [tokenKey, expired]);
    await academic.reload();
    await expect(academic).toHaveURL(/\/login$/);
    await expect(academic.getByRole('heading', { name: 'Sign in', exact: true })).toBeVisible();
    await shot(academic, '15-expired-session-sign-in');
    await login(academic, 'academic', false);
    await system.goto('/admin/users');
    await system.getByRole('button', { name: 'Deactivate e1_other_advisor', exact: true }).click();
    await confirmAccount(system, 'Deactivate User');
    await other.goto('/dashboard');
    await expect(other).toHaveURL(/\/login$/);
    const students = await get(academic, '/students?page_size=100');
    expect(students.items.some((x: any) => x.student_number.startsWith('DENIED'))).toBeFalsy();
    evidence.final_profile = await get(academic, '/students/' + data.student.id + '/profile');
    evidence.security_checks = { unassigned_note: 403, advisor_student_write: 403, academic_users_read: 403, system_student_write: 403, expired_session_redirect: true, deactivated_session_redirect: true };
    expect(evidence.errors).toEqual([]); expect(evidence.console_errors).toEqual([]);
  });
});
