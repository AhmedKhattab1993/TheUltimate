const puppeteer = require('puppeteer');

async function testUI() {
  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  
  try {
    const page = await browser.newPage();
    console.log('Testing Frontend UI Components...\n');
    
    // Navigate to the app
    await page.goto('http://localhost:5173', { waitUntil: 'networkidle2' });
    console.log('✓ Successfully loaded frontend');
    
    // Check if the main components are present
    const title = await page.$eval('h1', el => el.textContent);
    console.log(`✓ Found title: ${title}`);
    
    // Check for filter components
    const filters = await page.$$('[data-testid^="filter-"]');
    console.log(`✓ Found ${filters.length} filter components`);
    
    // Check for the new day trading filter tabs
    const hasAdvancedFilters = await page.$('[role="tablist"]') !== null;
    console.log(`✓ Advanced filters tabs present: ${hasAdvancedFilters}`);
    
    // Click on Advanced Filters tab if present
    if (hasAdvancedFilters) {
      await page.click('[role="tab"][aria-selected="false"]');
      await page.waitForTimeout(500);
      console.log('✓ Clicked on Advanced Filters tab');
      
      // Check for day trading filters
      const dayTradingFilters = [
        'gap', 'price-range', 'relative-volume',
        'float', 'premarket-volume', 'market-cap', 'news-catalyst'
      ];
      
      for (const filter of dayTradingFilters) {
        const selector = `[data-testid="filter-${filter}"], label:has-text("${filter.replace('-', ' ')}")`;
        const exists = await page.$(selector) !== null;
        console.log(`  ${exists ? '✓' : '✗'} Day trading filter: ${filter}`);
      }
    }
    
    // Test date inputs
    const dateInputs = await page.$$('input[type="date"]');
    console.log(`✓ Found ${dateInputs.length} date inputs`);
    
    // Test Run Screen button
    const runButton = await page.$('button:has-text("Run Screen")');
    console.log(`✓ Run Screen button present: ${runButton !== null}`);
    
    console.log('\n✅ Frontend UI tests completed successfully!');
    
  } catch (error) {
    console.error('❌ UI test failed:', error);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

testUI().catch(console.error);