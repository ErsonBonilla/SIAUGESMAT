import asyncio
import re
import sys

sys.path.insert(0, "/app")

from app.core.config import settings
from app.services.moodle import MoodleService

CAT = "SIB"


async def check():
    config = settings.get_moodle_config("DISTANCIA")
    ms = MoodleService(token=config["token"], base_url=config["url"], version=config["version"])

    # 1. Get ALL SIB courses from Moodle
    print("=== CURSOS SIBATE EN MOODLE ===")
    all_courses = await ms.get_courses()
    sib_moodle = [c for c in all_courses if c.get("shortname", "").startswith(CAT)]
    print(f"Total SIB en Moodle: {len(sib_moodle)}")
    for c in sib_moodle[:10]:
        print(f"  {c['shortname']:55s} id={c['id']:5d}  visible={c.get('visible', '?')}")

    print(f"\n... y {len(sib_moodle) - 10} mas")

    # 2. Get ALL courses from Moodle (any prefix) to see total
    print("\n=== TOTAL CURSOS EN MOODLE ===")
    print(f"Total cursos en Moodle: {len(all_courses)}")

    # 3. Count by prefix
    from collections import Counter

    prefixes = Counter()
    for c in all_courses:
        sn = c.get("shortname", "")
        m = re.match(r"^([A-Z]{3})", sn)
        if m:
            prefixes[m.group(1)] += 1
    print("\n=== CURSOS POR PREFIJO (top 15) ===")
    for pref, count in prefixes.most_common(15):
        print(f"  {pref}: {count}")

    await ms.close()


asyncio.run(check())
