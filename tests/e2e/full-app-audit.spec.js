const { test, expect } = require("@playwright/test");

test.describe.configure({ mode: "parallel" });

const roleSuites = [
  {
    name: "super-admin",
    credentials: { email: "admin@school.com", password: "admin123" },
    pages: [
      { path: "/dashboard", text: "Super Admin" },
      { path: "/schools", text: "Greenfield Public School" },
      { path: "/schools/1", text: "Greenfield Public School" },
      { path: "/schools/1/classes?school_id=1", text: "Grade 1 - A" },
      { path: "/classes/1/students?school_id=1", text: "Class Roster" },
      { path: "/attendance?school_id=1&class_id=1", text: "Attendance" },
      { path: "/marks?school_id=1&class_id=1", text: "Marks" },
      { path: "/students/1/details?school_id=1", text: "Student Details" },
      { path: "/finance", text: "Finance Dashboard" },
      { path: "/finance/students?school_id=1&class_id=1", text: "Student Fee Table" },
      { path: "/logs", text: "Logs" },
    ],
    browserPage: { path: "/classes/1/students?school_id=1", text: "Class Roster" },
  },
  {
    name: "school-admin",
    credentials: { email: "admin.greenfield@demo.school", password: "demo123" },
    pages: [
      { path: "/dashboard", text: "School Admin" },
      { path: "/schools/1", text: "Greenfield Public School" },
      { path: "/classes", text: "Grade 1 - A" },
      { path: "/classes/1/students?school_id=1", text: "Class Roster" },
      { path: "/attendance?class_id=1", text: "Attendance" },
      { path: "/marks?class_id=1", text: "Marks" },
      { path: "/students/1/details?school_id=1", text: "Student Details" },
      { path: "/finance", text: "Finance Dashboard" },
      { path: "/finance/students?class_id=1", text: "Student Fee Table" },
      { path: "/logs", text: "Logs" },
    ],
    browserPage: { path: "/classes/1/students?school_id=1", text: "Class Roster" },
  },
  {
    name: "teacher",
    credentials: { email: "teacher.greenfield.g1a.home@demo.school", password: "demo123" },
    pages: [
      { path: "/dashboard", text: "Teacher" },
      { path: "/classes/1/students?school_id=1", text: "Class Roster" },
      { path: "/attendance?class_id=1", text: "Attendance" },
      { path: "/marks?class_id=1", text: "Marks" },
      { path: "/students/1/details?school_id=1", text: "Student Details" },
      { path: "/finance", text: "Finance Dashboard" },
    ],
    browserPage: { path: "/dashboard", text: "Teacher" },
  },
  {
    name: "parent",
    credentials: { email: "parent.greenfield.g1a.01@demo.school", password: "demo123" },
    pages: [
      { path: "/dashboard", text: "Parent" },
      { path: "/notifications", text: "Notifications" },
    ],
    browserPage: { path: "/dashboard", text: "Parent" },
  },
];

function cookieHeader(token) {
  return { Cookie: `access_token=${token}` };
}

async function loginApi(request, credentials, baseURL) {
  const response = await request.post(`${baseURL}/login`, {
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
    },
    data: credentials,
  });
  expect(response.ok(), `Login failed for ${credentials.email}`).toBeTruthy();
  const payload = await response.json();
  expect(payload.forcePasswordChange, `Seeded test account ${credentials.email} unexpectedly requires a password change.`).toBeFalsy();
  return payload.token;
}

function collectBrowserIssues(page) {
  const consoleErrors = [];
  const pageErrors = [];

  page.on("console", (msg) => {
    if (msg.type() === "error" && !msg.text().includes("/favicon.ico")) {
      consoleErrors.push(msg.text());
    }
  });
  page.on("pageerror", (error) => {
    pageErrors.push(error.message);
  });

  return { consoleErrors, pageErrors };
}

for (const suite of roleSuites) {
  test(`${suite.name} audit`, async ({ page, request, baseURL }, testInfo) => {
    const token = await loginApi(request, suite.credentials, baseURL);
    const failedResponses = [];

    for (const pageSpec of suite.pages) {
      const response = await request.get(`${baseURL}${pageSpec.path}`, {
        headers: cookieHeader(token),
      });
      if (response.status() >= 400) {
        failedResponses.push({ path: pageSpec.path, status: response.status() });
      }
      expect(response.status(), `${suite.name} got a bad status for ${pageSpec.path}`).toBeLessThan(400);
      const html = await response.text();
      expect(html, `${suite.name} page missing expected text for ${pageSpec.path}`).toContain(pageSpec.text);
      expect(html).not.toContain("Internal Server Error");
    }

    await page.context().addCookies([
      {
        name: "access_token",
        value: token,
        url: baseURL,
        httpOnly: true,
        sameSite: "Lax",
      },
    ]);
    const browserIssues = collectBrowserIssues(page);
    const browserResponse = await page.goto(suite.browserPage.path, { waitUntil: "domcontentloaded" });
    expect(browserResponse, `${suite.name} browser check did not return a response`).not.toBeNull();
    expect(browserResponse.status(), `${suite.name} browser page failed`).toBeLessThan(400);
    await expect(page.locator("body")).toContainText(suite.browserPage.text);
    await expect(page.locator("body")).not.toContainText("Internal Server Error");

    await testInfo.attach("failed-responses.json", {
      body: JSON.stringify(failedResponses, null, 2),
      contentType: "application/json",
    });
    await testInfo.attach("console-errors.json", {
      body: JSON.stringify(browserIssues.consoleErrors, null, 2),
      contentType: "application/json",
    });
    await testInfo.attach("page-errors.json", {
      body: JSON.stringify(browserIssues.pageErrors, null, 2),
      contentType: "application/json",
    });

    expect(failedResponses, `${suite.name} triggered failing responses`).toEqual([]);
    expect(browserIssues.consoleErrors, `${suite.name} emitted browser console errors`).toEqual([]);
    expect(browserIssues.pageErrors, `${suite.name} emitted uncaught browser errors`).toEqual([]);
  });
}
