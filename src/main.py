import asyncio
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
import traceback
import os

# Configuration
WHATSAPP_CHAT_NAME = "PadelBoys"  # Replace with exact WhatsApp Chat/Group name
MAX_POLL_OPTIONS = 3

async def is_slot_available(dt: datetime) -> bool:
    """Check if the slot is available based on user rules."""
    is_weekend = dt.weekday() >= 5
    if is_weekend:
        return True
    
    # Weekdays
    hour = dt.hour
    if hour < 9: # Anytime before 09:00 (e.g. 07:00, 08:00)
        return True
    if 9 <= hour < 19: # 09:00 to 17:00 (working hours) + 17:00-19:00 excluded
        return False
    # Anytime from 19:00 onwards
    return True

async def scrape_padel_slots():
    print("Starting Peakz Padel Scraper...")
    today = datetime.now()
    dates_to_check = [today + timedelta(days=i) for i in range(14)]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        # We navigate once to the main location page
        url = "https://www.peakzpadel.nl/reserveren/court-booking/reservation?location=westerpark"
        print("Navigating to Peakz Padel Westerpark...")
        await page.goto(url, wait_until='networkidle')
        
        # Give the Vue app some time to initialize
        await page.wait_for_timeout(3000)
        
        all_available_slots = {}
        
        for check_date in dates_to_check:
            date_str = check_date.strftime("%Y-%m-%d")
            print(f"Checking date: {date_str} - {check_date.strftime('%A')}")
            
            try:
                # Click the date on the calendar
                date_cell = page.locator(f'[data-date="{date_str}"]')
                if await date_cell.count() > 0:
                    await date_cell.first.click()
                else:
                    print(f"  Warning: Could not find calendar cell for {date_str}")
                    # Try clicking by the day text as a fallback
                    day_text = str(check_date.day)
                    await page.locator('.b-calendar-grid-body span', has_text=day_text).first.click()
                
                # Wait for slots to load/refresh
                await page.wait_for_timeout(2000)
                
                # Find all available buttons that have a price (euro sign)
                # The user-identified container is #my-env-reserve-time-slot-page
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
                        try:
                            slot_time = datetime.strptime(time_text, "%H:%M").time()
                            slot_dt = datetime.combine(check_date.date(), slot_time)
                            
                            if await is_slot_available(slot_dt):
                                available_for_date.append({
                                    'time': time_text,
                                    'price': price_text
                                })
                        except ValueError:
                            pass
                            
                    except Exception as e:
                        pass
                
                if available_for_date:
                    all_available_slots[date_str] = available_for_date
                    print(f"  Found {len(available_for_date)} available slots matching criteria.")
                else:
                    print(f"  No available slots matching criteria.")
                    
            except Exception as e:
                print(f"  Error checking {date_str}: {e}")
                print(traceback.format_exc())
                
        await browser.close()
        
        print("\n" + "="*40)
        print("--- SUMMARY OF AVAILABLE SLOTS ---")
        print("="*40)
        if not all_available_slots:
            print("No slots available in the next 14 days matching your criteria.")
        else:
            for date_str, slots in all_available_slots.items():
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                print(f"\n{date_str} ({date_obj.strftime('%A')}):")
                for slot in slots:
                    print(f"  - {slot['time']} for {slot['price']}")
        print("="*40)
        
        # After summarizing, trigger WhatsApp Web
        if all_available_slots:
            await send_whatsapp_polls(all_available_slots)

async def send_whatsapp_polls(slots_data: dict):
    print("\nStarting WhatsApp Web Integration (Node.js agent)...")
    import json
    import subprocess
    import sys
    
    print(f"Targeting chat: '{WHATSAPP_CHAT_NAME}'")
    
    if getattr(sys, 'frozen', False):
        # Running as compiled executable, find src relative to the .exe
        base_dir = os.path.dirname(sys.executable)
        script_dir = os.path.join(base_dir, "src")
    else:
        # Running as python script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
    temp_file = os.path.join(script_dir, "whatsapp_data.json")
    script_path = os.path.join(script_dir, "whatsapp_sender.js")
    
    data = {
        "chatName": WHATSAPP_CHAT_NAME,
        "slots": slots_data
    }
    
    try:
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f)
            
        print("Running WhatsApp Node.js Sender... (Will print a QR code here if not logged in)")
        # We run the command inside the src directory so the Node environment finds its modules
        subprocess.run(["node", script_path, temp_file], cwd=script_dir, check=True)
        
    except FileNotFoundError:
        print("ERROR: Node.js is not installed or not found in PATH.")
        print("Please install Node.js from https://nodejs.org/")
    except subprocess.CalledProcessError as e:
        print(f"WhatsApp sender script failed with exit code: {e.returncode}")
    except Exception as e:
        print(f"Failed to run WhatsApp script: {e}")
        print(traceback.format_exc())
    finally:
        # Cleanup temp JSON
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except:
                pass

if __name__ == "__main__":
    asyncio.run(scrape_padel_slots())
