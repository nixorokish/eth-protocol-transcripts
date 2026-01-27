# notifications.py - Send notifications for critical errors
import os
import subprocess
import platform
from pathlib import Path

def send_notification(title, message, error_level="error"):
    """Send a notification using the best available method
    
    Args:
        title: Notification title
        message: Notification message
        error_level: "error", "warning", or "info"
    """
    system = platform.system()
    
    # macOS - use osascript for native notifications
    if system == "Darwin":
        try:
            # Escape special characters for AppleScript
            title_escaped = title.replace('"', '\\"').replace('\\', '\\\\')
            message_escaped = message.replace('"', '\\"').replace('\\', '\\\\')
            
            # Use different notification sounds based on error level
            sound = "Basso" if error_level == "error" else "Ping"
            
            applescript = f'''
            display notification "{message_escaped}" with title "{title_escaped}" sound name "{sound}"
            '''
            
            subprocess.run(
                ['osascript', '-e', applescript],
                check=False,
                timeout=5,
                capture_output=True
            )
            return True
        except Exception:
            pass
    
    # Linux - use notify-send if available
    elif system == "Linux":
        try:
            urgency = "critical" if error_level == "error" else "normal"
            subprocess.run(
                ['notify-send', '-u', urgency, title, message],
                check=False,
                timeout=5,
                capture_output=True
            )
            return True
        except Exception:
            pass
    
    # Fallback: Write to a notification log file
    try:
        log_file = Path("logs") / "notifications.log"
        log_file.parent.mkdir(exist_ok=True)
        with open(log_file, 'a') as f:
            from datetime import datetime
            f.write(f"{datetime.now().isoformat()} - [{error_level.upper()}] {title}: {message}\n")
        return True
    except Exception:
        pass
    
    return False

def notify_github_token_expired():
    """Send notification about expired GitHub token"""
    title = "🚨 Transcripts Script: GitHub Token Expired"
    message = "Your GitHub token has expired. Please update GITHUB_TOKEN in .env file"
    send_notification(title, message, error_level="error")

def notify_critical_error(error_message):
    """Send notification about critical error"""
    title = "🚨 Transcripts Script: Critical Error"
    message = error_message[:200]  # Limit message length
    send_notification(title, message, error_level="error")

def notify_processing_complete(processed_count, skipped_count):
    """Send notification about successful processing"""
    title = "✓ Transcripts Script: Processing Complete"
    message = f"Processed {processed_count} meetings, skipped {skipped_count}"
    send_notification(title, message, error_level="info")

