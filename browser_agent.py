"""
Browser Agent — HTTP-сервер для управления браузером внутри контейнера.

Запуск:  python browser_agent.py
Порт:    8081 (внутри контейнера)
Доступ:  docker exec uc_app curl "http://localhost:8081/..."
"""
import sys
import uvicorn
from fastapi import FastAPI
from app.services.browser_controller import (
    get_page, click_button, type_text, press_enter,
    take_screenshot, get_text, execute_js, reset_browser,
)

# Создаём отдельное FastAPI-приложение (НЕ трогаем main.py!)
agent = FastAPI(
    title="Browser Agent",
    description="Управление headless Chromium для чат-виджета",
    version="1.0.0",
)


@agent.get("/open")
async def api_open():
    """Открыть виджет (сбросить и загрузить заново)."""
    await reset_browser()
    await get_page()
    path = await take_screenshot()
    return {"status": "ok", "screenshot": path}


@agent.get("/click")
async def api_click(label: str):
    """Кликнуть по кнопке с текстом label."""
    return await click_button(label)


@agent.get("/type")
async def api_type(text: str, index: int = 0):
    """Ввести текст в поле ввода (index: 0=первое, 1=второе...)."""
    return await type_text(text, index)


@agent.get("/enter")
async def api_enter():
    """Нажать Enter."""
    return await press_enter()


@agent.get("/js")
async def api_js(code: str):
    """
    Выполнить JavaScript в контексте страницы.
    Только для разработчика — порт 8081 не exposed наружу.
    Пример: /js?code=document.title
    """
    return await execute_js(code)


@agent.get("/screenshot")
async def api_screenshot():
    """Только скриншот текущего состояния."""
    path = await take_screenshot()
    return {"status": "ok", "screenshot": path}


@agent.get("/text")
async def api_text():
    """Прочитать весь текст со страницы."""
    return await get_text()


@agent.get("/wait")
async def api_wait(ms: int = 2000):
    """Подождать N миллисекунд (для загрузки React после входа)."""
    import asyncio
    await asyncio.sleep(ms / 1000)
    return {"status": "ok", "waited_ms": ms}


@agent.get("/reset")
async def api_reset():
    """Сбросить браузер (закрыть и открыть заново)."""
    return await reset_browser()


@agent.get("/analyze")
async def api_analyze():
    """
    Извлечь визуальные параметры страницы:
    размеры, цвета, шрифты, отступы, контраст.
    Работает даже если Claude не видит скриншот.
    """
    from app.services.browser_controller import get_page
    page = await get_page()
    report = await page.evaluate("""() => {
        const result = {
            viewport: { width: window.innerWidth, height: window.innerHeight },
            body: { bg: '', color: '', fontFamily: '', fontSize: '' },
            buttons: [],
            inputs: [],
            texts: [],
            warnings: []
        };

        // Общие стили body
        const bs = getComputedStyle(document.body);
        result.body.bg = bs.backgroundColor;
        result.body.color = bs.color;
        result.body.fontFamily = bs.fontFamily;
        result.body.fontSize = bs.fontSize;

        // Все кнопки
        document.querySelectorAll('button, [role="button"]').forEach((btn, i) => {
            const s = getComputedStyle(btn);
            const rect = btn.getBoundingClientRect();
            const text = btn.textContent.trim().substring(0, 40);
            result.buttons.push({
                text: text,
                x: Math.round(rect.x), y: Math.round(rect.y),
                w: Math.round(rect.width), h: Math.round(rect.height),
                bg: s.backgroundColor, color: s.color,
                fontSize: s.fontSize, borderRadius: s.borderRadius,
                padding: s.padding, margin: s.margin,
                display: s.display, visibility: s.visibility
            });
        });

        // Поля ввода
        document.querySelectorAll('input, textarea').forEach((inp, i) => {
            const s = getComputedStyle(inp);
            const rect = inp.getBoundingClientRect();
            result.inputs.push({
                type: inp.type || 'text',
                placeholder: (inp.placeholder || '').substring(0, 30),
                x: Math.round(rect.x), y: Math.round(rect.y),
                w: Math.round(rect.width), h: Math.round(rect.height),
                bg: s.backgroundColor, color: s.color,
                fontSize: s.fontSize, borderRadius: s.borderRadius,
                border: s.border
            });
        });

        // Все текстовые блоки (крупные)
        document.querySelectorAll('p, h1, h2, h3, h4, h5, h6, span, div').forEach(el => {
            const text = el.textContent.trim();
            if (text.length > 10 && text.length < 200 && el.children.length === 0) {
                const s = getComputedStyle(el);
                result.texts.push({
                    text: text.substring(0, 80),
                    fontSize: s.fontSize,
                    color: s.color,
                    fontWeight: s.fontWeight,
                    lineHeight: s.lineHeight
                });
            }
        });
        // Только первые 15 текстов
        result.texts = result.texts.slice(0, 15);

        // Проверка контрастности (упрощённо)
        function getLuminance(rgb) {
            const m = rgb.match(/\\d+/g);
            if (!m) return 0;
            const [r, g, b] = m.map(v => v / 255).map(v =>
                v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)
            );
            return 0.2126 * r + 0.7152 * g + 0.0722 * b;
        }
        function contrastRatio(c1, c2) {
            const l1 = getLuminance(c1);
            const l2 = getLuminance(c2);
            const lighter = Math.max(l1, l2);
            const darker = Math.min(l1, l2);
            return ((lighter + 0.05) / (darker + 0.05)).toFixed(2);
        }

        result.buttons.forEach(btn => {
            if (btn.bg && btn.bg !== 'rgba(0, 0, 0, 0)' && btn.color) {
                const ratio = contrastRatio(btn.bg, btn.color);
                if (parseFloat(ratio) < 4.5) {
                    result.warnings.push(
                        'НИЗКИЙ КОНТРАСТ: кнопка «' + btn.text + '» (' + btn.bg + ' / ' + btn.color +
                        ') = ' + ratio + ':1 (минимум 4.5:1)'
                    );
                }
            }
        });

        // Мелкие кнопки
        result.buttons.forEach(btn => {
            if (btn.w > 0 && btn.h > 0 && (btn.w < 44 || btn.h < 44)) {
                result.warnings.push(
                    'МАЛЕНЬКАЯ КНОПКА: «' + btn.text + '» ' + btn.w + '×' + btn.h +
                    'px (минимум 44×44px для пальца)'
                );
            }
        });

        return result;
    }""")
    return {"status": "ok", "analysis": report}


@agent.get("/layout")
async def api_layout():
    """
    SVG-отрисовка страницы с полной детализацией:
    - Все цветные контейнеры и фоны (шапка, облачка, панели)
    - Кнопки, поля ввода, текст
    - Аватарки и изображения
    SVG = текст, Claude «видит» страницу!
    """
    import os, uuid
    from app.services.browser_controller import get_page

    page = await get_page()
    # Ждём ещё 1 сек для полной отрисовки React
    await page.wait_for_timeout(1000)

    elements = await page.evaluate("""() => {
        const els = [];
        const bodyBg = getComputedStyle(document.body).backgroundColor;

        // --- 1. ВСЕ КОНТЕЙНЕРЫ С ФОНОМ (шапка, облачка, панели) ---
        document.querySelectorAll('div, header, nav, section, main, aside').forEach(el => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            const bg = s.backgroundColor;
            // Пропускаем прозрачные и совпадающие с body
            if (r.width > 30 && r.height > 10 && r.y < 3000 &&
                bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent' && bg !== bodyBg) {
                els.push({
                    type:'container', text:'', x:r.x, y:r.y, w:r.width, h:r.height,
                    bg:bg, radius:s.borderRadius, shadow:s.boxShadow
                });
            }
        });

        // --- 2. ИЗОБРАЖЕНИЯ (аватарки, иконки) ---
        document.querySelectorAll('img, svg').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width > 8 && r.height > 8 && r.y < 3000) {
                els.push({
                    type:'image', text: el.alt || el.getAttribute('aria-label') || 'img',
                    x:r.x, y:r.y, w:r.width, h:r.height,
                    bg:getComputedStyle(el).backgroundColor, src:(el.src||'').substring(0,60)
                });
            }
        });

        // --- 3. КНОПКИ ---
        document.querySelectorAll('button, [role="button"]').forEach(el => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            if (r.width > 0 && r.height > 0 && r.y < 3000) {
                els.push({type:'button', text:el.textContent.trim().substring(0,30),
                    x:r.x, y:r.y, w:r.width, h:r.height,
                    bg:s.backgroundColor, color:s.color,
                    fontSize:s.fontSize, borderRadius:s.borderRadius});
            }
        });

        // --- 4. ПОЛЯ ВВОДА ---
        document.querySelectorAll('input, textarea').forEach(el => {
            const r = el.getBoundingClientRect();
            const s = getComputedStyle(el);
            if (r.width > 0 && r.height > 0 && r.y < 3000) {
                els.push({type:'input', text:el.placeholder||'',
                    x:r.x, y:r.y, w:r.width, h:r.height,
                    bg:s.backgroundColor, color:s.color,
                    fontSize:s.fontSize});
            }
        });

        // --- 5. ТЕКСТОВЫЕ БЛОКИ (листовые узлы с текстом) ---
        document.querySelectorAll('p, h1, h2, h3, h4, span, div').forEach(el => {
            const text = el.textContent.trim();
            if (text.length > 3 && text.length < 200 && el.children.length === 0) {
                const r = el.getBoundingClientRect();
                const s = getComputedStyle(el);
                if (r.width > 10 && r.y > 0 && r.y < 2500) {
                    els.push({type:'text', text:text.substring(0,120),
                        x:r.x, y:r.y, w:r.width, h:r.height,
                        color:s.color, fontSize:s.fontSize, fontWeight:s.fontWeight});
                }
            }
        });

        return {bodyBg: bodyBg, elements: els.slice(0, 80)};
    }""")

    w, h = 420, 700
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n  <!-- Фон -->\n'
    svg += f'  <rect width="{w}" height="{h}" fill="{elements["bodyBg"]}"/>\n'

    # Закрашиваем контейнеры ПЕРВЫМИ (подложка)
    for el in elements['elements']:
        if el['type'] != 'container':
            continue
        x, y, ew, eh = el['x'], el['y'], el['w'], el['h']
        bg = el.get('bg','#eee')
        rx = el.get('radius','0px').replace('px','')
        try: rx = int(float(rx))
        except: rx = 0
        svg += f'  <rect x="{x:.0f}" y="{y:.0f}" width="{ew:.0f}" height="{eh:.0f}" rx="{rx}" fill="{bg}" opacity="0.95"/>\n'

    # Затем изображения
    for el in elements['elements']:
        if el['type'] != 'image':
            continue
        x, y, ew, eh = el['x'], el['y'], el['w'], el['h']
        label = el.get('text','')[:15]
        svg += f'  <rect x="{x:.0f}" y="{y:.0f}" width="{ew:.0f}" height="{eh:.0f}" rx="{min(ew,eh)/2:.0f}" fill="#cbd5e1" stroke="#94a3b8" stroke-width="1"/>\n'
        if label:
            svg += f'  <text x="{x+ew/2:.0f}" y="{y+eh/2+4:.0f}" text-anchor="middle" font-size="8" fill="#64748b" font-family="Arial,sans-serif">{label}</text>\n'

    # Затем кнопки
    for el in elements['elements']:
        if el['type'] != 'button':
            continue
        x, y, ew, eh = el['x'], el['y'], el['w'], el['h']
        text = el['text'].replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')[:40]
        fs = el.get('fontSize','14px')
        fw = el.get('fontWeight','normal')
        try: fsn = int(float(fs.replace('px','')))
        except: fsn = 14
        bg = el.get('bg','#ddd'); color = el.get('color','#000')
        rx = el.get('borderRadius','4px').replace('px','')
        try: rx = int(float(rx))
        except: rx = 4
        svg += f'  <rect x="{x:.0f}" y="{y:.0f}" width="{ew:.0f}" height="{eh:.0f}" rx="{rx}" fill="{bg}" stroke="rgba(0,0,0,0.1)" stroke-width="1"/>\n'
        svg += f'  <text x="{x+ew/2:.0f}" y="{y+eh/2+fsn/3:.0f}" text-anchor="middle" font-size="{fs}" fill="{color}" font-weight="{fw}" font-family="Arial,sans-serif">{text}</text>\n'

    # Затем поля ввода
    for el in elements['elements']:
        if el['type'] != 'input':
            continue
        x, y, ew, eh = el['x'], el['y'], el['w'], el['h']
        text = el['text'].replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')[:30]
        fs = el.get('fontSize','14px')
        try: fsn = int(float(fs.replace('px','')))
        except: fsn = 14
        bg = el.get('bg','#fff'); color = el.get('color','#000')
        svg += f'  <rect x="{x:.0f}" y="{y:.0f}" width="{ew:.0f}" height="{eh:.0f}" rx="6" fill="{bg}" stroke="#d1d5db" stroke-width="1"/>\n'
        if text:
            svg += f'  <text x="{x+8:.0f}" y="{y+eh/2+fsn/3:.0f}" font-size="{fs}" fill="{color}" font-family="Arial,sans-serif" opacity="0.5">{text}</text>\n'

    # Сверху текст
    for el in elements['elements']:
        if el['type'] != 'text':
            continue
        x, y, ew, eh = el['x'], el['y'], el['w'], el['h']
        text = el['text'].replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')[:120]
        fs = el.get('fontSize','14px')
        fw = el.get('fontWeight','normal')
        try: fsn = int(float(fs.replace('px','')))
        except: fsn = 14
        color = el.get('color','#000')
        # Разбиваем длинный текст на строки
        lines = [text[i:i+50] for i in range(0, len(text), 50)]
        for li, line in enumerate(lines):
            svg += f'  <text x="{x:.0f}" y="{y+fsn+li*(fsn+2):.0f}" font-size="{fs}" fill="{color}" font-weight="{fw}" font-family="Arial,sans-serif">{line}</text>\n'

    svg += '</svg>'

    sdir = '/app/screenshots'
    os.makedirs(sdir, exist_ok=True)
    fname = f'layout_{uuid.uuid4().hex[:8]}.svg'
    fpath = os.path.join(sdir, fname)
    with open(fpath, 'w', encoding='utf-8') as f:
        f.write(svg)

    return {"status": "ok", "layout": fpath, "svg_size": len(svg), "elements": len(elements['elements'])}


if __name__ == "__main__":
    # Создаём папку для скриншотов при старте
    import os
    os.makedirs("/app/screenshots", exist_ok=True)

    print("🚀 Browser Agent запущен на порту 8081")
    uvicorn.run(agent, host="0.0.0.0", port=8081, log_level="warning")
