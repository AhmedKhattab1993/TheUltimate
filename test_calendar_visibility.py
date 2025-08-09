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
        
        # Wait for the page to load
        await page.wait_for_timeout(2000)
        
        # Click on the date button to open calendar
        print("Opening calendar...")
        await page.click('button:has-text("July 10th, 2025")')
        await page.wait_for_timeout(1000)
        
        # Check table header visibility
        print("\nChecking table headers...")
        
        # Find all thead elements
        thead_elements = await page.locator('thead').all()
        print(f"Found {len(thead_elements)} thead elements")
        
        for i, thead in enumerate(thead_elements):
            is_visible = await thead.is_visible()
            display = await thead.evaluate('el => window.getComputedStyle(el).display')
            print(f"  thead {i}: visible={is_visible}, display={display}")
        
        # Find elements containing day names
        day_selectors = ['th', 'td', 'div']
        day_names = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa']
        
        print("\nChecking elements with day names...")
        for selector in day_selectors:
            elements = await page.locator(selector).all()
            for elem in elements:
                text = await elem.text_content()
                if text and text.strip() in day_names:
                    is_visible = await elem.is_visible()
                    display = await elem.evaluate('el => window.getComputedStyle(el).display')
                    parent_display = await elem.evaluate('el => el.parentElement ? window.getComputedStyle(el.parentElement).display : "n/a"')
                    print(f"  {selector} with '{text}': visible={is_visible}, display={display}, parent_display={parent_display}")
        
        # Check for specific classes
        print("\nChecking specific classes...")
        classes_to_check = ['.rdp-weekdays', '.rdp-weekday', '.rdp-head_row']
        
        for class_name in classes_to_check:
            count = await page.locator(class_name).count()
            if count > 0:
                elem = page.locator(class_name).first
                is_visible = await elem.is_visible()
                display = await elem.evaluate('el => window.getComputedStyle(el).display')
                print(f"  {class_name}: count={count}, visible={is_visible}, display={display}")
            else:
                print(f"  {class_name}: not found")
        
        # Take screenshot
        await page.screenshot(path="calendar_visibility_test.png", full_page=True)
        print("\nScreenshot saved as calendar_visibility_test.png")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_calendar())