import httpx, json, asyncio

async def main():
    url = "https://turbinist.ru/api-bot-bridge.php"
    token = "YzJkZDg4NWMtOGNiZi00OWYyLWE2YmYtM2RlMmU2YzgzMmI2MmMzNGI1NWEtMDFjYi00NzBlLWJmNDAtMzMzZThmNzYwNzQ2"

    async with httpx.AsyncClient(timeout=15, verify=False) as client:
        async def req(action, params):
            r = await client.post(url, json={"action": action, "params": params},
                headers={"Authorization": f"Bearer {token}"})
            try:
                return r.json()
            except:
                print(f"Status: {r.status_code}, Raw: {r.text[:500]}")
                return None

        # 1. Проверяем gateway_invoices для user 286601
        print("=== gateway_invoices for user 286601 (changegroup) ===")
        d = await req("load_table", ["dle_webcash_gateway_invoices", "id,created,checkout_store", "user_id=286601 AND area_alias='changegroup'", 1, 0, 10, "id", "DESC"])
        if d and d.get("data"):
            import re
            for inv in d["data"]:
                print(f"\nID={inv['id']}, created={inv['created']}")
                store = inv.get("checkout_store", "")
                # Печатаем всю строку checkout_store (первые 1500 символов)
                print(f"  store_preview={store[:1500]}")
                m = re.search(r'new_time_limit["\']?;i:(\d+);', store)
                if m:
                    print(f"  new_time_limit={m.group(1)}")
                    # Конвертируем в дату
                    import time
                    print(f"  new_time_limit_date={time.strftime('%Y-%m-%d %H:%M:%S', time.gmtime(int(m.group(1))))}")
                m2 = re.search(r'target_group_id["\']?;i:(\d+);', store)
                if m2:
                    print(f"  target_group_id={m2.group(1)}")
        else:
            print("Нет данных или ошибка")
            if d: print(json.dumps(d, indent=2, ensure_ascii=False)[:1000])

        # 2. Проверяем dle_users — какие поля есть
        print("\n=== take_user_by_id(286601) ===")
        d = await req("take_user_by_id", [286601])
        if d and d.get("data"):
            user = d["data"]
            for key in ["user_group", "time_limit", "expire", "name", "email"]:
                print(f"  {key}: {user.get(key, 'НЕТ')}")

        # 3. Проверяем profile API
        print("\n=== Проверка /api/my/stats ===")
        async with httpx.AsyncClient() as c2:
            r = await c2.get("http://localhost:8080/api/my/stats?dle_user_id=286601")
            if r.status_code == 200:
                print(json.dumps(r.json(), indent=2, ensure_ascii=False))

asyncio.run(main())
