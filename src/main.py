import asyncio
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
import traceback
import os

# Configuration
WHATSAPP_CHAT_NAME = "My Padel Group"  # Replace with exact WhatsApp Chat/Group name
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
    print("\nStarting WhatsApp Web Integration...")
    print(f"Targeting chat: '{WHATSAPP_CHAT_NAME}'")
    
    # We must construct an absolute path for the user_data_dir to work smoothly within Pyinstaller
    data_dir = os.path.join(os.getcwd(), "whatsapp_profile")
    
    async with async_playwright() as p:
        # Launch persistent context
        # We set headless=False so the user can scan the QR code if needed
        context = await p.chromium.launch_persistent_context(
            user_data_dir=data_dir,
            headless=False,
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        )
        page = await context.new_page()
        
        try:
            print("Navigating to WhatsApp Web...")
            await page.goto("https://web.whatsapp.com/")
            
            print("Waiting for login... (Please scan QR code if prompted)")
            # Wait until the search box is visible, which indicates we are logged in
            # The search box usually has data-tab="3" or a specific title
            search_box = page.locator('div[contenteditable="true"][data-tab="3"]')
            
            try:
                # We wait up to 60 seconds primarily for the user to scan the QR code manually
                await search_box.wait_for(state="visible", timeout=60000)
                print("Successfully logged in to WhatsApp Web!")
            except Exception as e:
                print("Login timeout. Please check your phone or try again.")
                return
                
            print(f"Searching for chat: '{WHATSAPP_CHAT_NAME}'")
            await search_box.fill(WHATSAPP_CHAT_NAME)
            await page.wait_for_timeout(2000)
            
            # Click the chat in the search results
            chat_element = page.locator(f'span[title="{WHATSAPP_CHAT_NAME}"]').first
            if await chat_element.count() > 0:
                await chat_element.click()
                await page.wait_for_timeout(2000)
            else:
                print(f"Chat '{WHATSAPP_CHAT_NAME}' not found. Cannot send polls.")
                return

            for date_str, slots in slots_data.items():
                if not slots:
                    continue
                    
                # Limit to top configured options per day
                slots_to_poll = slots[:MAX_POLL_OPTIONS]
                
                # Format the date for the poll title
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                poll_title = f"Padel Slots {date_obj.strftime('%A %d-%m-%Y')}"
                
                print(f"Creating poll: '{poll_title}'")
                
                # Click the attachment/plus icon
                # WhatsApp recently uses a plus icon on the left of input box
                attach_btn = page.locator('span[data-icon="plus"]').locator('..')
                await attach_btn.click()
                await page.wait_for_timeout(1000)
                
                # Click the Poll option (Poll icon)
                poll_btn = page.locator('span[data-icon="poll"]').locator('..')
                await poll_btn.click()
                await page.wait_for_timeout(1000)
                
                # Inside the Poll creation overlay
                # Question input is the first textbox, options are subsequent textboxes
                textboxes = page.locator('div[role="dialog"] div[contenteditable="true"]')
                await textboxes.first.wait_for(state="visible", timeout=10000)
                
                # Fill title
                await textboxes.nth(0).fill(poll_title)
                
                # Fill options
                for idx, slot in enumerate(slots_to_poll):
                    option_text = f"{slot['time']} - {slot['price']}"
                    await textboxes.nth(idx + 1).fill(option_text)
                    await page.wait_for_timeout(500)
                    
                # Click the Send button inside the dialog
                send_btn = page.locator('div[role="dialog"] span[data-icon="send"]').locator('..')
                await send_btn.click()
                print(f"Poll sent for {date_str}!")
                
                # Wait a bit before creating the next poll
                await page.wait_for_timeout(2000)
                
        except Exception as e:
            print(f"WhatsApp UI error: {e}")
            print(traceback.format_exc())
            
        finally:
            await context.close()

if __name__ == "__main__":
    asyncio.run(scrape_padel_slots())
