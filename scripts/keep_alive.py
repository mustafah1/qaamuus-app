#!/usr/bin/env python3
import requests
import time
import sys
from datetime import datetime

# Configuration
SITE_URL = "https://qaamuus-7uin.onrender.com"
LOG_FILE = "keep_alive.log"
PING_INTERVAL = 600  # 10 minutes in seconds

def log_message(message):
    """Log message with timestamp to both console and log file"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"{timestamp} - {message}"
    print(log_line)
    with open(LOG_FILE, 'a') as f:
        f.write(log_line + '\n')

def ping_site():
    """Ping the website and log the result"""
    try:
        response = requests.get(SITE_URL, timeout=10)
        log_message(f"Ping successful - Status: {response.status_code}")
        return True
    except requests.exceptions.RequestException as e:
        log_message(f"Ping failed: {str(e)}")
        return False

def main():
    log_message(f"Starting keep-alive service for {SITE_URL}")
    log_message(f"Logging to: {LOG_FILE}")
    
    try:
        while True:
            ping_site()
            time.sleep(PING_INTERVAL)
    except KeyboardInterrupt:
        log_message("Service stopped by user")
    except Exception as e:
        log_message(f"Service crashed: {str(e)}")
        raise

if __name__ == "__main__":
    main()
