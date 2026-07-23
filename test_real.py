import asyncio, uuid
from app.services.moodle import MoodleService
from app.core.config import settings

async def test():
    cfg = settings.get_moodle_config("DISTANCIA")
    ms = MoodleService(token=cfg["token"], base_url=cfg["url"], version=cfg["version"])
    uid = uuid.uuid4().hex[:6]
    cat_idn = f"TEST_CAT_{uid}"
    sn = f"TEST_CURSO_{uid}"
    username = f"testuser_{uid}"
    results = []

    # 1. Crear categoria
    try:
        await ms.create_categories([{"name": f"CAT PRUEBA {uid}", "idnumber": cat_idn, "parent": 0}])
        cats = await ms.get_categories(idnumber=cat_idn)
        results.append(("Crear categoria", "OK" if cats else "FAIL"))
    except Exception as e:
        results.append(("Crear categoria", f"FAIL: {e}"))

    # 2. Crear curso
    try:
        r = await ms.create_courses([{"shortname": sn, "fullname": f"CURSO PRUEBA {uid}", "categoryidnumber": cat_idn, "format": "onetopic", "visible": 1}])
        results.append(("Crear curso", f"OK (id={r[0]['id']})" if r else "FAIL"))
    except Exception as e:
        results.append(("Crear curso", f"FAIL: {e}"))

    # 3. Crear usuario
    try:
        await ms.create_users([{"username": username, "firstname": "Test", "lastname": uid, "email": f"{username}@test.com", "createpassword": True}])
        users = await ms.get_users("username", [username])
        results.append(("Crear usuario", f"OK (id={users[0]['id']})" if users else "FAIL"))
    except Exception as e:
        results.append(("Crear usuario", f"FAIL: {e}"))

    # 4. Eliminar curso
    try:
        await ms.delete_courses([sn])
        courses = await ms.get_courses(shortname=sn)
        results.append(("Eliminar curso", "OK" if not courses else "FAIL"))
    except Exception as e:
        results.append(("Eliminar curso", f"FAIL: {e}"))

    # 5. Eliminar usuario
    try:
        await ms.delete_users([username])
        users = await ms.get_users("username", [username])
        results.append(("Eliminar usuario", "OK" if not users else "FAIL"))
    except Exception as e:
        results.append(("Eliminar usuario", f"FAIL: {e}"))

    # 6. Eliminar categoria
    try:
        cats = await ms.get_categories(idnumber=cat_idn)
        if cats:
            await ms.delete_category(int(cats[0]["id"]), recursive=True)
            cats2 = await ms.get_categories(idnumber=cat_idn)
            results.append(("Eliminar categoria", "OK" if not cats2 else "FAIL"))
    except Exception as e:
        results.append(("Eliminar categoria", f"FAIL: {e}"))

    await ms.close()
    print(f"\n=== RESULTADOS ({uid}) ===")
    for op, res in results:
        print(f"  {res:35s} {op}")


asyncio.run(test())
