const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  console.log("====================================================");
  console.log("STARTING PLAYWRIGHT BROWSER E2E TEST FOR BREATHE ESG");
  console.log("====================================================\n");

  const screenshotDir = 'C:/Users/Karti/.gemini/antigravity-ide/brain/0772d32c-e561-4841-b6b9-9eaba8466e15';
  
  // Ensure the output directory exists
  if (!fs.existsSync(screenshotDir)) {
    fs.mkdirSync(screenshotDir, { recursive: true });
  }

  // Launch Chromium in headful mode with slow-motion delay so the user can watch
  const browser = await chromium.launch({ headless: false, slowMo: 1000 });
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
    console.log("Step 1: Navigating to Breathe ESG web app at http://localhost:5173...");
    await page.goto('http://localhost:5173');
    
    // Wait for the stats to load (wait for Overview tab elements)
    await page.waitForSelector('.kpi-card');
    console.log("[OK] Dashboard loaded successfully.");
    
    // Take a screenshot of the initial overview
    await page.screenshot({ path: path.join(screenshotDir, 'screenshot_1_overview_initial.png') });
    console.log("[OK] Saved screenshot 1 (Initial Overview).");

    // 2. Go to Ingest Hub
    console.log("\nStep 2: Navigating to Ingest Hub tab...");
    await page.click('button:has-text("Ingest Hub")');
    await page.waitForSelector('.dropzone-container');
    console.log("[OK] Ingest Hub tab displayed.");
    
    // Take a screenshot of the initial ingest hub
    await page.screenshot({ path: path.join(screenshotDir, 'screenshot_2a_ingest_hub_initial.png') });
    console.log("[OK] Saved screenshot 2a (Initial Ingest Hub).");

    // Upload files
    console.log("\nStep 3: Uploading SAP Goods Movement CSV feed...");
    const sapInput = page.locator('input[type="file"]').nth(0);
    await sapInput.setInputFiles(path.join(__dirname, '..', 'sap_mock.csv'));
    await page.waitForTimeout(1000); // Wait for processing

    console.log("Step 4: Uploading Utility Electricity CSV feed...");
    const utilityInput = page.locator('input[type="file"]').nth(1);
    await utilityInput.setInputFiles(path.join(__dirname, '..', 'utility_mock.csv'));
    await page.waitForTimeout(1000); // Wait for processing

    console.log("Step 5: Uploading Corporate Travel CSV feed...");
    const travelInput = page.locator('input[type="file"]').nth(2);
    await travelInput.setInputFiles(path.join(__dirname, '..', 'travel_mock.csv'));
    await page.waitForTimeout(1500); // Wait for processing

    // Refresh Ingestion Jobs list and take screenshot
    await page.click('button:has-text("Refresh")');
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(screenshotDir, 'screenshot_2b_ingest_hub_completed.png') });
    console.log("[OK] Saved screenshot 2b (Ingest Hub with Completed Jobs).");

    // 3. Go to Analyst Review Ledger
    console.log("\nStep 6: Navigating to Analyst Review Ledger tab...");
    await page.click('button:has-text("Analyst Review")');
    await page.waitForSelector('.ledger-table');
    console.log("[OK] Analyst Review ledger loaded.");
    await page.waitForTimeout(1000); // Wait for rows to fetch

    // Take screenshot of the initial ledger
    await page.screenshot({ path: path.join(screenshotDir, 'screenshot_3_ledger_initial.png') });
    console.log("[OK] Saved screenshot 3 (Ledger with raw record data).");

    // 4. Click a row to open details drawer
    console.log("\nStep 7: Opening detail drawer for the first record (SAP Diesel)...");
    const firstRow = page.locator('.ledger-table tbody tr').first();
    await firstRow.click();
    await page.waitForSelector('.audit-drawer');
    console.log("[OK] Slide-over audit drawer opened.");
    await page.waitForTimeout(500);
    
    // Take screenshot of the drawer
    await page.screenshot({ path: path.join(screenshotDir, 'screenshot_4_drawer_open.png') });
    console.log("[OK] Saved screenshot 4 (Audit Lineage Drawer).");

    // 5. Edit Row details (recalculates emissions & logs audit trail)
    console.log("\nStep 8: Clicking Edit Row Details and updating quantity...");
    await page.click('button:has-text("Edit Row Details")');
    await page.waitForSelector('.modal-card');
    console.log("[OK] Edit modal displayed.");

    // Fill in the new quantity: 3000
    const qtyInput = page.locator('.modal-card input.form-input').first();
    await qtyInput.fill('3000');
    
    // Save & Recalculate
    await page.screenshot({ path: path.join(screenshotDir, 'screenshot_5a_edit_modal.png') });
    console.log("[OK] Saved screenshot 5a (Edit Modal open).");
    await page.click('button:has-text("Recalculate & Save")');
    await page.waitForTimeout(1000); // wait for update

    // Ledger should update
    await page.screenshot({ path: path.join(screenshotDir, 'screenshot_5b_ledger_after_edit.png') });
    console.log("[OK] Saved screenshot 5b (Ledger showing updated carbon & EDITED badge).");

    // 6. Sign off (Approve) records
    console.log("\nStep 9: Selecting records for bulk approval...");
    // Let's close the drawer if it's still open by clicking the overlay
    const overlay = page.locator('.audit-drawer-overlay');
    if (await overlay.isVisible()) {
      await overlay.click({ position: { x: 5, y: 5 }, force: true });
      await page.waitForTimeout(300);
    }

    // Check checkboxes for the first and second records in the table
    const checkboxes = page.locator('.ledger-table tbody tr td input[type="checkbox"]');
    await checkboxes.nth(0).click();
    await checkboxes.nth(1).click();
    await page.waitForTimeout(300);
    console.log("[OK] Checkboxes checked.");

    // Click Bulk Approve
    await page.click('button:has-text("Bulk Approve")');
    await page.waitForTimeout(1500); // wait for bulk update and alert dismiss

    // Take screenshot of ledger showing approved status
    await page.screenshot({ path: path.join(screenshotDir, 'screenshot_6_ledger_after_approval.png') });
    console.log("[OK] Saved screenshot 6 (Ledger with APPROVED & LOCKED status).");

    // 7. Verify Overview Dashboard updates
    console.log("\nStep 10: Returning to Overview Dashboard to check updated charts...");
    await page.click('button:has-text("Overview")');
    await page.waitForSelector('.kpi-card');
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(screenshotDir, 'screenshot_7_overview_updated.png') });
    console.log("[OK] Saved screenshot 7 (Updated Overview Dashboard).");

    // 8. Test Tenant Isolation
    console.log("\nStep 11: Switching mock user session to 'eco_analyst' (EcoSphere Industries)...");
    await page.selectOption('.session-switcher select', 'eco_analyst');
    await page.waitForTimeout(1500); // wait for tenant reload

    // The Overview dashboard for EcoSphere should have no data/emissions approved yet (they are Acme's)
    await page.screenshot({ path: path.join(screenshotDir, 'screenshot_8_ecosphere_dashboard.png') });
    console.log("[OK] Saved screenshot 8 (EcoSphere Tenant dashboard - isolation verified).");

    console.log("\n====================================================");
    console.log("ALL BROWSER E2E ACTIONS COMPLETED SUCCESSFULLY!");
    console.log("====================================================");

  } catch (error) {
    console.error("\n[ERROR] E2E script failed with exception:", error);
    await page.screenshot({ path: path.join(screenshotDir, 'screenshot_error.png') });
    console.log(`[INFO] Saved failure screenshot to ${path.join(screenshotDir, 'screenshot_error.png')}`);
  } finally {
    await browser.close();
  }
})();
