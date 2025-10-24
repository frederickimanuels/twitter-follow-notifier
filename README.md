X (Twitter) Following Scraper Bot
This is a Python bot that monitors the "following" list of specified X (formerly Twitter) users. It periodically scrapes their lists, detects when they follow new accounts, and sends an alert to a Discord webhook.

The bot is designed to be robust against X.com's partial list loading. It maintains a historical, append-only database (as a CSV file) of all accounts a user has ever been seen following, ensuring it only alerts on truly new follows.

Features
New Follow Detection: Monitors one or more users and alerts when they follow a new account.

Discord Integration: Sends formatted alerts to a Discord webhook for instant notifications.

Robust Error Reporting: Alerts the same Discord webhook if the bot crashes, (e.g., due to an invalid auth_token).

Historical Data: Intelligently saves all discovered follows to disk, so it doesn't lose track of data or send false alerts, even when X.com only shows a partial list.

Headless & Server-Ready: Runs in a headless Chrome browser, perfect for deploying on a 24/7 Linux server.

Cookie-Based Auth: Uses an auth_token cookie for authentication, which is more secure than storing a password.

Requirements
System
Python 3.x

Google Chrome (The browser itself)

Python Libraries
selenium

webdriver-manager

pandas

requests

Setup & Installation

1. (On Server) Install Dependencies
   On a headless Ubuntu server, you must install Python, pip, and Google Chrome:

# Update package lists

```bash
sudo apt update && sudo apt upgrade -y
```

# Install Python & venv

```bash
sudo apt install python3 python3-pip python3-venv -y
```

# Install Google Chrome

```bash
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo dpkg -i google-chrome-stable_current_amd64.deb
```

# Fix any missing dependencies (if the above command failed)

```bash
sudo apt-get install -f -y
```

2. Clone & Set Up Project
   Clone or copy this project's files to your server.

# Clone the repository (if you're using git)

```bash
git clone <your-repo-url>
cd <your-project-directory>
```

# 1. Create a Python virtual environment

```bash
python3 -m venv venv
```

# 2. Activate the environment

```bash
source venv/bin/activate
```

# 3. Install the required Python libraries

```bash
pip install selenium webdriver-manager pandas requests
```

Configuration
You must create a config.py file in the same directory as scraper.py.
You can copy and rename config.pyexample to config.py.

How to get your auth_token
Go to https://x.com in your browser (e.g., Chrome) and log in.

Open Developer Tools (F12 or Right-Click > Inspect).

Go to the Application tab.

On the left, expand Cookies and click on https://x.com.

Find the cookie named auth_token and copy its Value.

Paste this value into the AUTH_TOKEN_COOKIE variable in config.py.

⚠️ Warning: Treat your auth_token like a password. Do not share it or commit it to a public repository.

Running the Bot
Local Test
You can run the bot directly for testing:

Bash

# Make sure your environment is active

```bash
source venv/bin/activate
```

# Run the script

```bash
python scraper.py
```

To run the bot 24/7, you must use a tool that keeps it running after you disconnect from your SSH session. tmux is highly recommended.

Disclaimer
Scraping X.com (Twitter) is against their Terms of Service. Use this tool at your own risk.

This bot relies on X.com's front-end HTML, which changes frequently. If the bot stops finding users, the XPATH selector in the get_following_list function within scraper.py will likely need to be updated.
