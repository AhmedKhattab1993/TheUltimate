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
        
        # Take initial screenshot
        await page.screenshot(path="page_loaded.png")
        print("Initial page screenshot saved as page_loaded.png")
        
        # Try to find and click the date picker button
        print("Looking for date picker...")
        
        # Try different selectors
        selectors = [
            'button:has(svg)',  # Button with calendar icon
            'button >> text=/Select.*date/i',  # Button with text containing "Select" and "date"
            '[role="button"]',  # Any element with button role
            'button'  # Any button
        ]
        
        for selector in selectors:
            try:
                elements = await page.locator(selector).all()
                print(f"Found {len(elements)} elements with selector: {selector}")
                
                # Click the first date picker we find
                if elements:
                    for i, elem in enumerate(elements):
                        text = await elem.text_content()
                        print(f"  Element {i}: {text}")
                        if 'date' in (text or '').lower() or 'select' in (text or '').lower():
                            await elem.click()
                            print(f"Clicked on element: {text}")
                            await page.wait_for_timeout(1000)
                            break
            except:
                pass
        
        # Take screenshot after clicking
        await page.screenshot(path="after_click.png")
        print("Screenshot after click saved as after_click.png")
        
        # Check if calendar is visible
        calendar_selectors = ['.rdp', '[role="grid"]', '.calendar', '.popover-content']
        calendar_found = False
        
        for selector in calendar_selectors:
            if await page.locator(selector).count() > 0:
                calendar_found = True
                print(f"Calendar found with selector: {selector}")
                
                # Check for day names
                day_names = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
                calendar_html = await page.locator(selector).inner_html()
                
                found_days = []
                for day in day_names:
                    if day in calendar_html:
                        found_days.append(day)
                
                if found_days:
                    print(f"Found day names in calendar: {found_days}")
                else:
                    print("No day names found in calendar - they appear to be hidden!")
                
                # Check specifically for header row
                if await page.locator('.rdp-head_row').count() > 0:
                    is_visible = await page.locator('.rdp-head_row').is_visible()
                    print(f"Header row (.rdp-head_row) exists and visible: {is_visible}")
                else:
                    print("Header row (.rdp-head_row) not found")
                
                break
        
        if not calendar_found:
            print("Calendar not found on page")
        
        # Final screenshot
        await page.screenshot(path="calendar_test_final.png", full_page=True)
        print("Final screenshot saved as calendar_test_final.png")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_calendar())