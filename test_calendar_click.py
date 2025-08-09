#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright

async def test_calendar():
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Navigate to the app
        print("Navigating to http://34.125.135.2:5173")
        await page.goto("http://34.125.135.2:5173", wait_until="networkidle")
        
        # Wait for the page to load completely
        await page.wait_for_timeout(2000)
        
        # Click on the date button to open calendar
        print("Clicking on date picker button...")
        await page.click('button:has-text("July 10th, 2025")')
        await page.wait_for_timeout(1000)
        
        # Take screenshot after opening calendar
        await page.screenshot(path="calendar_open.png", full_page=True)
        print("Screenshot with calendar open saved as calendar_open.png")
        
        # Check if calendar is visible and analyze its content
        calendar_selectors = ['.rdp', '[role="application"]', '[data-testid="calendar"]', 'div:has(> table)']
        
        for selector in calendar_selectors:
            elements = await page.locator(selector).all()
            if elements:
                print(f"\nFound {len(elements)} calendars with selector: {selector}")
                
                for i, elem in enumerate(elements):
                    # Get the HTML content
                    html = await elem.inner_html()
                    
                    # Check for day names
                    day_names = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']
                    found_days = [day for day in day_names if day in html]
                    
                    if found_days:
                        print(f"Calendar {i} contains day names: {found_days}")
                    else:
                        print(f"Calendar {i} does NOT contain day names - they are hidden!")
                    
                    # Check for specific class
                    if 'rdp-head_row' in html:
                        print("Found .rdp-head_row in HTML")
                        # Check if it's hidden
                        if 'hidden' in html or 'display: none' in html:
                            print("Header row appears to be hidden")
        
        # Also check for the specific header row
        header_count = await page.locator('.rdp-head_row').count()
        if header_count > 0:
            is_visible = await page.locator('.rdp-head_row').is_visible()
            print(f"\n.rdp-head_row found: {header_count} instances, visible: {is_visible}")
            
            # Get computed style
            header = page.locator('.rdp-head_row').first
            display = await header.evaluate('el => window.getComputedStyle(el).display')
            visibility = await header.evaluate('el => window.getComputedStyle(el).visibility')
            print(f"Computed styles - display: {display}, visibility: {visibility}")
        else:
            print("\n.rdp-head_row not found in DOM")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_calendar())