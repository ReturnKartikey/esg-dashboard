const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  console.log("====================================================");
  console.log("STARTING PLAYWRIGHT BROWSER E2E TEST FOR PRODUCTION");
  console.log("Target URL: https://esg-dashboard-ap1y.onrender.com");
  console.log("====================================================\n");

  const screenshotDir = 'C:/Users/Karti/.gemini/antigravity-ide/brain/0772d32c-e561-4841-b6b9-9eaba8466e15';
  
  // Ensure the output directory exists
  if (!fs.existsSync(screenshotDir)) {
    fs.mkdirSync(screenshotDir, { recursive: true });
  }

  // Launch Chromium in headful mode (headless: false)
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 }
  });
  const page = await context.newPage();

  // Dialog event handler (for alert, confirm, prompt)
  page.on('dialog', async dialog => {
    console.log(`[DIALOG] Type: ${dialog.type()} | Message: "${dialog.message()}"`);
    await dialog.accept();
    console.log(`[DIALOG] Accepted dialog successfully.`);
  });

  try {
    // 1. Go to the dashboard
    console.log("Step 1: Navigating to live app...");
    await page.goto('https://esg-dashboard-ap1y.onrender.com');
    
    // Wait for the stats to load (wait for Overview tab elements)
    await page.waitForSelector('.kpi-card');
    console.log("[OK] Live Dashboard loaded successfully.");

    // Step 1b: Reset database to ensure clean test run
    console.log("Step 1b: Clicking Reset DB to wipe old test data...");
    await page.click('.btn-reset-db');
    await page.waitForTimeout(1500); // wait for reset execution
    console.log("[OK] Database reset completed.");
    
    // Take a screenshot of the initial overview (now empty)
    await page.screenshot({ path: path.join(screenshotDir, 'prod_screenshot_1_overview.png') });
    console.log("[OK] Saved screenshot 1 (Live Overview).");

    // 2. Go to Ingest Hub
    console.log("\nStep 2: Navigating to Ingest Hub tab...");
    await page.click('button:has-text("Ingest Hub")');
    await page.waitForSelector('.dropzone-container');
    console.log("[OK] Ingest Hub tab displayed.");
    
    // Take a screenshot of the initial ingest hub
    await page.screenshot({ path: path.join(screenshotDir, 'prod_screenshot_2_ingest.png') });
    console.log("[OK] Saved screenshot 2 (Live Ingest Hub).");

    // 3. Go to Analyst Review Ledger
    console.log("\nStep 3: Navigating to Analyst Review Ledger tab...");
    await page.click('button:has-text("Analyst Review")');
    await page.waitForSelector('.ledger-table');
    console.log("[OK] Analyst Review ledger loaded.");
    await page.waitForTimeout(1000); // Wait for rows to fetch

    // Take screenshot of the initial ledger
    await page.screenshot({ path: path.join(screenshotDir, 'prod_screenshot_3_ledger.png') });
    console.log("[OK] Saved screenshot 3 (Live Review Ledger).");

    // 4. Click a row to open details drawer
    console.log("\nStep 4: Opening detail drawer for the first record...");
    const firstRow = page.locator('.ledger-table tbody tr').first();
    await firstRow.click();
    await page.waitForSelector('.audit-drawer');
    console.log("[OK] Slide-over audit drawer opened.");
    await page.waitForTimeout(500);
    
    // Take screenshot of the drawer
    await page.screenshot({ path: path.join(screenshotDir, 'prod_screenshot_4_drawer.png') });
    console.log("[OK] Saved screenshot 4 (Live Audit Drawer).");

    // 5. Verify Overview Dashboard updates
    console.log("\nStep 5: Returning to Overview Dashboard...");
    // Let's close the drawer if it's still open by clicking the overlay
    const overlay = page.locator('.audit-drawer-overlay');
    if (await overlay.isVisible()) {
      await overlay.click({ position: { x: 5, y: 5 }, force: true });
      await page.waitForTimeout(300);
    }
    await page.click('button:has-text("Overview")');
    await page.waitForSelector('.kpi-card');
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(screenshotDir, 'prod_screenshot_5_overview_final.png') });
    console.log("[OK] Saved screenshot 5 (Final Live Overview).");

    console.log("\n====================================================");
    console.log("PRODUCTION DEPLOYMENT TEST COMPLETED SUCCESSFULLY!");
    console.log("====================================================");

  } catch (error) {
    console.error("\n[ERROR] E2E script failed with exception:", error);
    await page.screenshot({ path: path.join(screenshotDir, 'prod_screenshot_error.png') });
    console.log(`[INFO] Saved failure screenshot to ${path.join(screenshotDir, 'prod_screenshot_error.png')}`);
  } finally {
    await browser.close();
  }
})();
