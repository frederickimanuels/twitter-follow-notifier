import os
import time
import requests
import pandas as pd
import random
from datetime import datetime
import config  # Imports our config.py file

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# --- Custom Exceptions ---
class AuthException(Exception):
    """Custom exception for authentication failures."""
    pass

def setup_driver():
    """Sets up the Selenium Chrome WebDriver."""
    print("Setting up WebDriver...")
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Run without opening a browser window
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    # Use webdriver-manager to automatically install and manage the driver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    print("WebDriver setup complete.")
    return driver

def load_and_authenticate(driver, auth_token):
    """
    Loads the X (Twitter) homepage and injects the authentication cookie.
    Raises AuthException if login fails.
    """
    print("Loading X.com and authenticating...")
    driver.get("https://x.com/") 
    time.sleep(2) # Give it a sec to settle

    # Add the authentication cookie for the .x.com domain
    driver.add_cookie({
        'name': 'auth_token',
        'value': auth_token,
        'domain': '.x.com',
        'path': '/',
        'secure': True,
        'httpOnly': True
    })
    
    print("Cookie added. Refreshing page...")
    driver.refresh()
    time.sleep(5) # Wait for the page to load (5 seconds)
    
    # Check if login was successful
    if "Home" in driver.title:
        print("Authentication successful!")
    else:
        print(f"Authentication failed. Page title is: {driver.title}")
        raise AuthException("Authentication failed. Page title did not contain 'Home'. Please check your auth_token.")

    return driver

def get_following_list(driver, username):
    """
    Scrapes the complete 'following' list for a given username.
    Returns a set of usernames (@handles).
    """
    print(f"\nAttempting to scrape 'following' list for: {username}")
    following_url = f"https://x.com/{username}/following"
    driver.get(following_url)
    
    # Wait for the page to load and the main content to be visible
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="UserCell"]'))
        )
        print("Page loaded. Starting scroll...")
    except Exception as e:
        print(f"Could not load following page for {username}. Maybe a private/suspended account? Error: {e}")
        return set() # Return an empty set

    following_set = set()
    last_height = driver.execute_script("return document.body.scrollHeight")
    scroll_attempts = 0
    max_scroll_attempts = 3

    while True:
        # Find all user cells currently visible
        try:
            # This XPATH finds the @handle within a UserCell, which is more reliable
            user_elements = driver.find_elements(By.XPATH, "//span[starts-with(text(), '@')]")
            if not user_elements and not following_set:
                 print("No user elements found on initial load. Waiting...")
                 time.sleep(2)
                 
            for el in user_elements:
                handle = el.text
                if handle.startswith('@'):
                    following_set.add(handle)

        except Exception as e:
            print(f"Error finding user elements: {e}")

        # Scroll down to the bottom
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        
        # Wait for new content to load
        time.sleep(random.randint(5, 8)) # Randomized wait

        # Check if we've reached the bottom
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            scroll_attempts += 1
            if scroll_attempts >= max_scroll_attempts:
                print("Reached the bottom of the list (or page stuck).")
                break
            else:
                 print(f"Scroll height unchanged, trying again... ({scroll_attempts}/{max_scroll_attempts})")
                 time.sleep(5) # Extra wait
        else:
            last_height = new_height
            scroll_attempts = 0 # Reset attempt counter
            
    print(f"Scrape complete for {username}. Found {len(following_set)} following.")
    return following_set

def get_profile_details(driver, username):
    """
    Visits a user's profile page and scrapes their details.
    Returns a dictionary.
    """
    if not username:
        return None
        
    username_clean = username.lstrip('@')
    print(f"Scraping profile details for @{username_clean}...")
    driver.get(f"https://x.com/{username_clean}")
    
    # Default values
    details = {
        "description": "No description found.",
        "join_date": "Join date not found.",
        "following_count": "N/A Following",
        "followers_count": "N/A Followers"
    }

    try:
        # 1. Wait for the main profile header to load (we'll use the 'following' link)
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'a[href$="/following"]'))
        )
        
        # 2. Scrape Description
        try:
            desc_el = driver.find_element(By.CSS_SELECTOR, '[data-testid="UserDescription"]')
            details["description"] = desc_el.text if desc_el.text else "No description found."
        except Exception:
            pass # Keep default

        # 3. Scrape Join Date
        try:
            join_el = driver.find_element(By.CSS_SELECTOR, '[data-testid="UserJoinDate"]')
            # Clean the emoji and "Joined " text
            details["join_date"] = join_el.text.replace('🗓️', '').replace('Joined ', '').strip()
        except Exception:
            pass # Keep default

        # 4. Scrape Following Count
        try:
            # Selects the <span> inside the <a> link that ends with '/following'
            following_el = driver.find_element(By.CSS_SELECTOR, 'a[href$="/following"] span')
            details["following_count"] = following_el.text
        except Exception:
            pass # Keep default

        # 5. Scrape Followers Count
        try:
            # Selects the <span> inside the <a> link that ends with '/followers'
            followers_el = driver.find_element(By.CSS_SELECTOR, 'a[href$="/verified_followers"] span')
            details["followers_count"] = followers_el.text
        except Exception:
            pass # Keep default
            
        return details
        
    except TimeoutException:
        print(f"Could not load profile for @{username_clean} (Timeout).")
        return details # Return default details
    except Exception as e:
        print(f"Error scraping profile for {username}: {e}")
        return details # Return default details

def send_discord_alert(driver, tracked_username, new_follows_list):
    """
    Sends a formatted alert to the Discord webhook, including full profile details.
    """
    if not config.DISCORD_WEBHOOK_URL or "YOUR_DISCORD_WEBHOOK_URL" in config.DISCORD_WEBHOOK_URL:
        print("Discord webhook URL not set. Skipping alert.")
        return

    print(f"Building detailed Discord alert for {tracked_username}...")
    
    message_parts = []
    message_parts.append(f"**🚨 New Follows Detected for @{tracked_username}**\n")

    payload = {
        "content": "".join(message_parts)
    }

    try:
        response = requests.post(config.DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print("Discord alert sent successfully.")
        else:
            print(f"Error sending Discord alert: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Exception while sending Discord alert: {e}")

    message_parts = []

    for new_user in new_follows_list:
        # Scrape the profile details for each new follow
        details = get_profile_details(driver, new_user)
        
        if not details:
            message_parts.append(f"**{new_user}**\n> Error scraping profile.\n")
            continue
        
        # Format the description with Discord's "quote" formatting
        # formatted_description = "\n> ".join(details['description'].split('\n'))
        
        # Add this user's details to the message
        message_parts.append(f"[**{new_user}**](https://x.com/{new_user[1:]})")
        # Add the new stats line
        message_parts.append(f"> **{details['following_count']} Following** | **{details['followers_count']} Followers** | **Joined {details['join_date']}**\n")
        # # Add the description
        # message_parts.append(f"> {formatted_description}\n")
        
        # CRITICAL: Wait a bit before scraping the next profile
        time.sleep(random.randint(2, 5)) 

        # Combine all parts into one message
        final_message = "\n".join(message_parts)

        # Handle Discord's 2000-character limit
        if len(final_message) > 2000:
            print("Message too long for Discord. Truncating.")
            final_message = final_message[:1950] + "\n... (message truncated)"

        payload = {
            "content": final_message
        }

        try:
            response = requests.post(config.DISCORD_WEBHOOK_URL, json=payload)
            if response.status_code == 204:
                print("Discord alert sent successfully.")
            else:
                print(f"Error sending Discord alert: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"Exception while sending Discord alert: {e}")
            
        message_parts = []

def send_error_alert(error_message):
    """Sends a formatted ERROR alert to the Discord webhook."""
    if not config.DISCORD_WEBHOOK_URL or "YOUR_DISCORD_WEBHOOK_URL" in config.DISCORD_WEBHOOK_URL:
        print("Discord webhook URL not set. Skipping error alert.")
        return

    print(f"Sending Discord ERROR alert...")
    
    # We use a code block (```) for clean error formatting in Discord
    payload = {
        "content": f"**❌ SCRAPER BOT FAILED**\n```\n{error_message}\n```"
    }

    try:
        response = requests.post(config.DISCORD_WEBHOOK_URL, json=payload)
        if response.status_code == 204:
            print("Discord error alert sent.")
        else:
            print(f"Error sending Discord error alert: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Exception while sending Discord error alert: {e}")

def check_for_new_follows(username, current_following_set):
    """
    Loads the historical list, compares it to the current (partial) list,
    saves the *combined* list, and returns only the new follows.
    """
    print(f"Checking for new follows for {username}...")
    
    # Ensure the data directory exists
    os.makedirs(config.DATA_DIR, exist_ok=True)
    
    # Define the file path for this user
    file_path = os.path.join(config.DATA_DIR, f"{username}_following.csv")
    
    historical_set = set()
    new_follows = set()

    # 1. Load the OLD (historical) list if it exists
    if os.path.exists(file_path):
        try:
            old_df = pd.read_csv(file_path)
            historical_set = set(old_df['username'])
            print(f"Loaded {len(historical_set)} users from historical data.")
        except Exception as e:
            print(f"Could not read {file_path}. Starting fresh. Error: {e}")
    else:
        print(f"No historical data found for {username}. Creating baseline.")

    # 2. Compare the CURRENT scrape against the HISTORICAL set
    # This correctly finds only users we have *never* seen before.
    new_follows = current_following_set - historical_set

    # 3. *** THIS IS THE KEY CHANGE ***
    # We create a new *combined* set of all historical users
    # plus any users found in the current scrape.
    combined_set = historical_set.union(current_following_set)

    # 4. Save the new, LARGER *combined_set* back to the file.
    # This ensures our list only ever grows and we never lose data.
    try:
        combined_df = pd.DataFrame(list(combined_set), columns=['username'])
        combined_df.to_csv(file_path, index=False)
        
        if len(combined_set) > len(historical_set):
            print(f"Updated historical data. Total known following: {len(combined_set)}")
        else:
            print(f"Historical data is up to date ({len(combined_set)} users).")
            
    except Exception as e:
        print(f"Error saving data to {file_path}: {e}")

    # 5. Return *only* the new follows for alerting.
    return list(new_follows)

def main():
    """Main function to run the scraper."""
    driver = None
    try:
        driver = setup_driver()
        # 1. CRITICAL BLOCK: Authenticate
        load_and_authenticate(driver, config.AUTH_TOKEN_COOKIE)

        # --- Main operational loop ---
        print("\n--- Scraper Bot Started ---")
        while True:
            print(f"\n--- New check cycle starting at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")
            
            for user in config.USERS_TO_TRACK:
                try: 
                    # 2. USER-LEVEL BLOCK: Scrape and check
                    
                    # 2a. Scrape the user's following list
                    following_list_set = get_following_list(driver, user)
                    
                    if not following_list_set:
                        print(f"Skipping {user}, list was empty (or page failed to load).")
                        continue

                    # 2b. Check for differences
                    new_follows = check_for_new_follows(user, following_list_set)

                    # 2c. Alert if there are new follows
                    if new_follows:
                        print(f"!!! FOUND {len(new_follows)} NEW FOLLOWS for {user}: {new_follows} !!!")
                        send_discord_alert(driver, user, new_follows)
                    else:
                        print(f"No new follows detected for {user}.")
                
                except Exception as e:
                    # Catch errors for a *single user* and continue
                    print(f"An error occurred while processing {user}: {e}")
                    send_error_alert(f"Failed to process user @{user}.\nError: {e}\nContinuing to next user.")
                
                finally:
                    # Random delay between users
                    delay = random.randint(30, 60)
                    print(f"Waiting {delay} seconds before next user...")
                    time.sleep(delay)
            
            # 4. Wait for the next cycle
            print(f"\nCycle complete. Sleeping for {config.SCRAPE_INTERVAL} seconds...")
            time.sleep(config.SCRAPE_INTERVAL)

    except AuthException as auth_err:
        # Catch our specific cookie/auth error
        print(f"CRITICAL: {auth_err}")
        send_error_alert(f"CRITICAL: Authentication failed. Bot is shutting down. Please update auth_token.\nError: {auth_err}")
    
    except KeyboardInterrupt:
        print("\nManual interruption detected. Shutting down.")
        send_error_alert("Bot was manually shut down (KeyboardInterrupt).")

    except Exception as e:
        # Catch any other unexpected critical error
        print(f"An critical UNHANDLED error occurred in main: {e}")
        send_error_alert(f"CRITICAL: An unhandled error occurred, bot is shutting down.\nError: {e}")

    finally:
        # This always runs, ensuring the browser closes
        if driver:
            print("Closing WebDriver.")
            driver.quit()

if __name__ == "__main__":
    main()