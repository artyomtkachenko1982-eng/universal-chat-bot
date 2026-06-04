import urllib.request, urllib.parse, time

def call(endpoint):
    url = 'http://localhost:8081' + endpoint
    try:
        r = urllib.request.urlopen(url, timeout=10)
        return r.read().decode()[:300]
    except Exception as e:
        return f"ERROR: {e}"

# Шаг 1: Открываем виджет
print("1. OPEN:", call('/open'))

# Шаг 2: Ждем загрузки
print("2. WAIT:", call('/wait?ms=2000'))

# Шаг 3: Впрыскиваем fetch-перехватчик
with open('/app/inject_admin.js', 'r') as f:
    js = f.read()
print("3. INJECT:", call('/js?code=' + urllib.request.quote(js)))

# Шаг 4: Вводим логин
print("4. TYPE login:", call('/type?text=dummy&index=0'))

# Шаг 5: Вводим пароль
print("5. TYPE pass:", call('/type?text=dummy&index=1'))

# Шаг 6: Кликаем «Войти»
print("6. CLICK:", call('/click?label=' + urllib.request.quote('Войти')))

# Шаг 7: Ждем React
print("7. WAIT:", call('/wait?ms=3000'))

# Шаг 8: Проверяем текст страницы
print("8. TEXT:", call('/text'))
