"""
Seed script — populates the system with sample transcripts for demo purposes.

Usage: python -m scripts.seed_data
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests

API_BASE = os.getenv("API_BASE_URL", "http://api:8000/api/v1")
FIXTURES_DIR = Path(__file__).parent.parent / "tests" / "fixtures" / "sample_transcripts"


SAMPLE_TRANSCRIPTS = [
    {
        "title": "Weekly Standup - June 5, 2026",
        "file": "standup.txt",
        "participants": ["John Doe", "Sarah Chen"],
    },
    {
        "title": "Notification System Design Review",
        "file": "technical_review.txt",
        "participants": ["Alex Rivera", "Priya Sharma", "David Park"],
    },
    {
        "title": "Water Cooler Chat",
        "file": "casual_chat.txt",
        "participants": ["Sarah Chen", "Unknown Colleague"],
    },
]


def seed():
    """Post sample transcripts to the API."""
    print(f"\n🌱 Seeding Memory Wiki with sample transcripts...")
    print(f"   API: {API_BASE}\n")

    for sample in SAMPLE_TRANSCRIPTS:
        filepath = FIXTURES_DIR / sample["file"]

        if not filepath.exists():
            print(f"   ⚠️  Skipping {sample['file']} (file not found)")
            continue

        content = filepath.read_text(encoding="utf-8")

        payload = {
            "title": sample["title"],
            "content": content,
            "participants": sample["participants"],
        }

        try:
            response = requests.post(f"{API_BASE}/transcripts", json=payload)
            if response.status_code == 202:
                data = response.json()
                print(f"   ✅ {sample['title']}")
                print(f"      ID: {data['id']}")
                print(f"      Status: {data['status']}")
            else:
                print(f"   ❌ {sample['title']}: {response.status_code} - {response.text}")
        except requests.ConnectionError:
            print(f"   ❌ Cannot connect to API at {API_BASE}")
            print(f"      Make sure the server is running: docker-compose up")
            sys.exit(1)

    print(f"\n✨ Done! Memories will be generated in the background.")
    print(f"   Check status: GET http://localhost:8000/api/v1/transcripts")
    print(f"   View memories: GET http://localhost:8000/api/v1/memories/tree?path=/\n")


if __name__ == "__main__":
    seed()
