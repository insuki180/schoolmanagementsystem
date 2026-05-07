const { test, expect } = require("@playwright/test");

const roles = [
  { name: "super-admin", email: "admin@school.com", password: "admin123", expectedCard: "Schools" },
  { name: "school-admin", email: "admin.greenfield@demo.school", password: "demo123", expectedCard: "Teachers & Staff" },
  { name: "teacher", email: "teacher.greenfield.g1a.home@demo.school", password: "demo123", expectedCard: "Mark Attendance" },
  { name: "parent", email: "parent.greenfield.g1a.01@demo.school", password: "demo123", expectedCard: "Notifications" },
];

async function loginViaApi(request, baseURL, credentials) {
  const response = await request.post(`${baseURL}/login`, {
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    data: credentials,
  });
  expect(response.ok()).toBeTruthy();
  const payload = await response.json();
  expect(payload.forcePasswordChange).toBeFalsy();
  return payload.token;
}

test.describe("launchpad dashboards", () => {
  for (const role of roles) {
    test(`${role.name} sees role launchpad`, async ({ page, request, baseURL }) => {
      const token = await loginViaApi(request, baseURL, { email: role.email, password: role.password });
      await page.context().addCookies([{ name: "access_token", value: token, url: baseURL, httpOnly: true, sameSite: "Lax" }]);

      await page.goto("/dashboard", { waitUntil: "domcontentloaded" });
      await expect(page.locator(".launchpad-card").filter({ hasText: role.expectedCard }).first()).toBeVisible();
      await expect(page.getByRole("link", { name: /SchoolMS dashboard home/i })).toBeVisible();
    });
  }

  test("logo returns user to dashboard and mobile bottom nav is visible", async ({ page, request, baseURL }) => {
    const token = await loginViaApi(request, baseURL, {
      email: "teacher.greenfield.g1a.home@demo.school",
      password: "demo123",
    });
    await page.context().addCookies([{ name: "access_token", value: token, url: baseURL, httpOnly: true, sameSite: "Lax" }]);

    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto("/marks?class_id=1", { waitUntil: "domcontentloaded" });
    await page.getByRole("link", { name: /SchoolMS dashboard home/i }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("navigation", { name: "Mobile" })).toBeVisible();
  });
});
