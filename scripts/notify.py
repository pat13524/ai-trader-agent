import os
import sys
from dotenv import load_dotenv

load_dotenv()

def send_digest(journal_path):
    """Send today's journal as an email digest."""
    try:
        with open(journal_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Journal file not found: {journal_path}")
        return

    # Print to console for now — replace with email service later
    print("=" * 50)
    print("TRADING AGENT DAILY DIGEST")
    print("=" * 50)
    print(content)
    print("=" * 50)
    print(f"Digest generated from: {journal_path}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        send_digest(sys.argv[1])
    else:
        print("Usage: python scripts/notify.py journal/YYYY-MM-DD.md")