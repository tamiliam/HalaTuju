"""Quick test to verify job loading works correctly."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.description import get_jobs_for_course, _JOBS_DATA

print(f"Total courses with jobs: {len(_JOBS_DATA)}")
print()

# Test a few courses
test_courses = ["POLY-DIP-001", "POLY-DIP-007", "KKOM-DIP-001", "IJTM-DIP-010"]

for cid in test_courses:
    jobs = get_jobs_for_course(cid)
    print(f"{cid}: {len(jobs)} jobs")
    for job in jobs[:3]:  # Show first 3
        if isinstance(job, dict):
            print(f"  - {job.get('title')} -> {job.get('url', 'NO URL')[:50]}...")
        else:
            print(f"  - {job}")
    print()
