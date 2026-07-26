import argparse
import asyncio
import csv
import sys
import time

from app.core.config import settings
from app.services.moodle import MoodleService


async def main():
    parser = argparse.ArgumentParser(description="Bulk set course visibility in Moodle")
    parser.add_argument("--csv", required=True, help="CSV file with 'identifier' column (shortnames)")
    parser.add_argument("--action", required=True, choices=["show", "hide"], help="show (visible=1) or hide (visible=0)")
    parser.add_argument("--modalidad", default="DISTANCIA", help="Modalidad token to use")
    parser.add_argument("--batch", type=int, default=25, help="Batch size for API calls")
    args = parser.parse_args()

    visible = 1 if args.action == "show" else 0
    action_label = "Des-ocultando" if args.action == "show" else "Ocultando"

    shortnames = []
    with open(args.csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sn = row.get("identifier", "").strip()
            if sn:
                shortnames.append(sn)

    if not shortnames:
        print("No shortnames found in CSV")
        return

    print(f"Loaded {len(shortnames)} shortnames from {args.csv}")

    cfg = settings.get_moodle_config(args.modalidad)
    moodle = MoodleService(token=cfg["token"], base_url=cfg["url"], version=cfg["version"])

    print("Resolving course IDs...")
    all_courses = await moodle.get_courses()
    sn_to_id = {c.get("shortname"): int(c["id"]) for c in all_courses if c.get("shortname") and c.get("id")}
    print(f"Got {len(sn_to_id)} courses from Moodle")

    resolved = []
    not_found = []
    for sn in shortnames:
        if sn in sn_to_id:
            resolved.append((sn_to_id[sn], sn))
        else:
            not_found.append(sn)

    print(f"Resolved: {len(resolved)} to {action_label.lower()}, {len(not_found)} not found in Moodle")
    if not_found and len(not_found) <= 10:
        for sn in not_found:
            print(f"  Not found: {sn}")

    updated = 0
    failed = 0
    t0 = time.monotonic()

    for i in range(0, len(resolved), args.batch):
        chunk = resolved[i:i + args.batch]
        params = {}
        for j, (cid, sn) in enumerate(chunk):
            params[f"courses[{j}][id]"] = cid
            params[f"courses[{j}][visible]"] = visible
        try:
            await moodle._request("core_course_update_courses", params, use_post=True)
            updated += len(chunk)
        except Exception as e:
            failed += len(chunk)
            print(f"  Error batch [{i}:{i+len(chunk)}]: {str(e)[:100]}")

        if updated % 250 == 0 and updated > 0:
            elapsed = time.monotonic() - t0
            rate = updated / elapsed if elapsed > 0 else 0
            eta = (len(resolved) - updated - failed) / rate if rate > 0 else 0
            print(f"  Progress: {updated}/{len(resolved)}, ETA {eta:.0f}s")

    elapsed = time.monotonic() - t0
    print(f"DONE: {updated} {action_label.lower()}, {failed} failed, {len(not_found)} not found ({elapsed:.0f}s)")

    await moodle.close()


if __name__ == "__main__":
    asyncio.run(main())
