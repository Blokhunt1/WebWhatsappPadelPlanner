import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta
from playwright.async_api import async_playwright

async def is_slot_available(dt: datetime) -> bool:
    """Check if the slot is available based on user rules."""
    is_weekend = dt.weekday() >= 5
    if is_weekend:
        return True
    
    # Weekdays
    hour = dt.hour
    if hour < 9: # Anytime before 09:00
        return False
    if 9 <= hour < 19: # 09:00 to 17:00 (working hours) + 17:00-19:00 excluded
        return False
    # Anytime from 19:00 onwards
    return True

async def scrape_padel_slots(days: int):
    today = datetime.now()
    dates_to_check = [today + timedelta(days=i) for i in range(days)]
    all_available_slots = {}
    
    # Send all print statements to stderr to prevent polluting stdout JSON
    print(f"Scraping Peakz Padel for {days} days...", file=sys.stderr)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        url = "https://www.peakzpadel.nl/reserveren/court-booking/reservation?location=westerpark"
        await page.goto(url, wait_until='networkidle')
        await page.wait_for_timeout(3000)
        
        for check_date in dates_to_check:
            date_str = check_date.strftime("%Y-%m-%d")
            
            try:
                date_cell = page.locator(f'[data-date="{date_str}"]')
                if await date_cell.count() > 0:
                    await date_cell.first.click()
                else:
                    day_text = str(check_date.day)
                    await page.locator('.b-calendar-grid-body span', has_text=day_text).first.click()
                
                await page.wait_for_timeout(2000)
                
                slots = await page.locator('#my-env-reserve-time-slot-page button.btn-outline-primary:not(.disabled)').all()
                available_for_date = []
                
                for slot in slots:
                    try:
                        time_text = await slot.locator('div').first.inner_text()
                        price_text = await slot.locator('div').last.inner_text()
                        
                        time_text = time_text.strip()
                        price_text = price_text.strip()
                        if price_text == "-":
                            continue
                            
                        # Parse time to check our rules
                        slot_time = datetime.strptime(time_text, "%H:%M").time()
                        slot_dt = datetime.combine(check_date.date(), slot_time)
                        
                        if await is_slot_available(slot_dt):
                            available_for_date.append({
                                'time': time_text,
                                'price': price_text
                            })
                    except Exception:
                        pass
                
                if available_for_date:
                    all_available_slots[date_str] = available_for_date
                    
            except Exception as e:
                print(f"Error checking {date_str}: {e}", file=sys.stderr)
                
        await browser.close()
        
        # Only print the absolute final JSON to stdout so Node.js can parse it cleanly
        print(json.dumps(all_available_slots))

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=4)
    args = parser.parse_args()
    
    try:
        if sys.platform == 'win32':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        asyncio.run(scrape_padel_slots(args.days))
    except (KeyboardInterrupt, SystemExit, RuntimeError):
        pass
