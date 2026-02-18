// @ts-check
import { test, expect } from '@playwright/test';

const APP_PASSWORD = 'sentsei2026';

async function setupAndNavigate(page, { clearLang = false, clearTheme = false } = {}) {
  await page.goto('/');
  await page.evaluate(({ pw, clearLang, clearTheme }) => {
    localStorage.setItem('sent-say_app_password', pw);
    if (clearLang) {
      localStorage.removeItem('sent-say_target_lang');
      localStorage.removeItem('sent-say_onboarded');
    }
    if (clearTheme) {
      localStorage.removeItem('sentsei-theme');
    }
  }, { pw: APP_PASSWORD, clearLang, clearTheme });
  await page.reload();
  await page.waitForTimeout(1500);
}

async function getToMainView(page) {
  await setupAndNavigate(page, { clearLang: true });

  if (await page.locator('#onboarding-overlay:not(.hidden)').isVisible().catch(() => false)) {
    await page.locator('#onboarding-skip').click();
    await page.waitForTimeout(500);
  }

  const card = page.locator('.picker-card').first();
  if (await card.isVisible().catch(() => false)) {
    await card.click();
    await page.waitForTimeout(500);
  }
}

test.describe('SentSay Smoke Tests', () => {

  test('page loads with correct title', async ({ page }) => {
    await page.goto('/');
    await expect(page).toHaveTitle(/SentSay/);
  });

  test('first visit shows onboarding overlay', async ({ page }) => {
    await setupAndNavigate(page, { clearLang: true });
    const onboarding = page.locator('#onboarding-overlay:not(.hidden)');
    await expect(onboarding).toBeVisible({ timeout: 3000 });
  });

  test('after onboarding, language picker shows', async ({ page }) => {
    await setupAndNavigate(page, { clearLang: true });
    if (await page.locator('#onboarding-overlay:not(.hidden)').isVisible().catch(() => false)) {
      await page.locator('#onboarding-skip').click();
      await page.waitForTimeout(500);
    }
    const picker = page.locator('#language-picker:not(.hidden)');
    await expect(picker).toBeVisible({ timeout: 3000 });
    const count = await page.locator('.picker-card').count();
    expect(count).toBeGreaterThan(0);
  });

  test('selecting language reveals main input', async ({ page }) => {
    await getToMainView(page);
    await expect(page.locator('#sentence')).toBeVisible({ timeout: 3000 });
    await expect(page.locator('#learn-btn')).toBeVisible({ timeout: 3000 });
  });

  test('submit sentence and get translated result', async ({ page }) => {
    await getToMainView(page);
    await page.locator('#sentence').fill('Hello world');
    await page.locator('#learn-btn').click();
    const results = page.locator('#results');
    await expect(results).not.toBeEmpty({ timeout: 50000 });
    const text = await results.textContent();
    expect(text.length).toBeGreaterThan(5);
  });

  test('word chips appear in results', async ({ page }) => {
    await getToMainView(page);
    await page.locator('#sentence').fill('I like coffee');
    await page.locator('#learn-btn').click();
    const chip = page.locator('.word-chip, .word-btn, [data-word]').first();
    await chip.waitFor({ state: 'visible', timeout: 50000 });
    const count = await page.locator('.word-chip, .word-btn, [data-word]').count();
    expect(count).toBeGreaterThan(0);
  });

  test('theme toggle changes persisted theme value', async ({ page }) => {
    await setupAndNavigate(page, { clearTheme: true });
    const themeBtn = page.locator('#theme-toggle');
    await expect(themeBtn).toBeVisible({ timeout: 3000 });
    const before = await page.evaluate(() => localStorage.getItem('sentsei-theme') || '');
    await themeBtn.click();
    await page.waitForTimeout(300);
    const after = await page.evaluate(() => localStorage.getItem('sentsei-theme') || '');
    expect(after).not.toBe(before);
  });

  test('stats modal opens', async ({ page }) => {
    await getToMainView(page);
    await page.locator('#stats-toggle').click();
    await page.waitForTimeout(500);
    const statsVisible = await page.evaluate(() => {
      const modal = document.querySelector('.stats-modal, #stats-modal, [class*="stats-content"]');
      return modal ? !modal.classList.contains('hidden') && modal.offsetParent !== null : false;
    });
    expect(statsVisible).toBeTruthy();
  });
});
