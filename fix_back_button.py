# -*- coding: utf-8 -*-
"""Script to move user's back button from item detail card to renderInputArea"""
import re

PATH = r'C:\Users\Артем\YandexDisk-turbinist-site\repository\Telegram-Dle-Post\universal_chat\app\widgets\chat\index.html'

with open(PATH, 'r', encoding='utf-8') as f:
    content = f.read()

changes = 0

# -------------------------------------------------------------------
# 1. Remove "← Назад к списку" button from USER AD detail card
# -------------------------------------------------------------------
# Pattern: the button block just before "User: список новостей" comment
old_ad_btn = (
    '                          <button onClick={() => { setMessages([]); setUserAdViewItem(null); }}\n'
    '                            className="w-full bg-gradient-to-r from-gray-100 to-gray-50 text-gray-600 px-3 py-2.5 rounded-xl text-sm font-medium hover:from-gray-200 border border-gray-200 shadow-sm transition-all active:scale-[0.98]">\n'
    '                            ← Назад к списку\n'
    '                          </button>\n'
    '                        </div>\n'
    '                      );\n'
    '                    })()}'
)

new_ad_end = (
    '                        </div>\n'
    '                      );\n'
    '                    })()}'
)

if old_ad_btn in content:
    content = content.replace(old_ad_btn, new_ad_end)
    print('✅ 1. Ads back button removed')
    changes += 1
else:
    print('❌ 1. Ads back button NOT found. Debug:')
    idx = content.find('setUserAdViewItem(null); }}\n')
    if idx > 0:
        print(f'  Found at {idx}, showing context:')
        print(repr(content[idx:idx+400]))

# -------------------------------------------------------------------
# 2. Remove "← Назад к списку" button from USER NEWS detail card
# -------------------------------------------------------------------
old_news_btn = (
    '                          <button onClick={() => { setMessages([]); setUserNewsViewItem(null); }}\n'
    '                            className="w-full bg-gradient-to-r from-gray-100 to-gray-50 text-gray-600 px-3 py-2.5 rounded-xl text-sm font-medium hover:from-gray-200 border border-gray-200 shadow-sm transition-all active:scale-[0.98]">\n'
    '                            ← Назад к списку\n'
    '                          </button>\n'
    '                        </div>\n'
    '                      );\n'
    '                    })()}'
)

new_news_end = (
    '                        </div>\n'
    '                      );\n'
    '                    })()}'
)

if old_news_btn in content:
    content = content.replace(old_news_btn, new_news_end)
    print('✅ 2. News back button removed')
    changes += 1
else:
    print('❌ 2. News back button NOT found')

# -------------------------------------------------------------------
# 3. Add back button to renderInputArea before "Выберите действие из меню ↓"
# -------------------------------------------------------------------
old_menu_block = (
    '        // Главное меню (кроме admin_panel+messages и adminSelected — там контент в осн. layout)\n'
    '        if ((step !== "admin_panel" || adminSection !== "messages") && !adminSelected) {\n'
    '        return (\n'
    '          <div className="flex-1 text-center text-xs text-gray-400 py-2">\n'
    '            Выберите действие из меню ↓\n'
    '          </div>\n'
    '        );\n'
    '        }'
)

new_menu_block = (
    '        // Пользователь смотрит заявку — кнопка назад вместо "Выберите действие из меню ↓"\n'
    '        if (!isAdmin && (userAdViewItem || userNewsViewItem)) {\n'
    '          if (userAdViewItem) {\n'
    '            return (\n'
    '              <div className="flex gap-2">\n'
    '                <button onClick={() => { setMessages([]); setUserAdViewItem(null); }}\n'
    '                  className="flex-1 bg-gray-200 text-gray-600 px-3 py-2 rounded-lg text-sm hover:bg-gray-300">← Назад к списку</button>\n'
    '              </div>\n'
    '            );\n'
    '          }\n'
    '          if (userNewsViewItem) {\n'
    '            return (\n'
    '              <div className="flex gap-2">\n'
    '                <button onClick={() => { setMessages([]); setUserNewsViewItem(null); }}\n'
    '                  className="flex-1 bg-gray-200 text-gray-600 px-3 py-2 rounded-lg text-sm hover:bg-gray-300">← Назад к списку</button>\n'
    '              </div>\n'
    '            );\n'
    '          }\n'
    '        }\n'
    '\n'
    '        // Главное меню (кроме admin_panel+messages и adminSelected — там контент в осн. layout)\n'
    '        if ((step !== "admin_panel" || adminSection !== "messages") && !adminSelected) {\n'
    '        return (\n'
    '          <div className="flex-1 text-center text-xs text-gray-400 py-2">\n'
    '            Выберите действие из меню ↓\n'
    '          </div>\n'
    '        );\n'
    '        }'
)

if old_menu_block in content:
    content = content.replace(old_menu_block, new_menu_block)
    print('✅ 3. Back button added in renderInputArea')
    changes += 1
else:
    print('❌ 3. Menu prompt block NOT found. Debug:')
    idx = content.find('Выберите действие из меню ↓')
    if idx > 0:
        print(f'  Found at {idx}, showing context:')
        start = max(0, idx - 300)
        print(repr(content[start:idx+30]))

# -------------------------------------------------------------------
# Save if changes were made
# -------------------------------------------------------------------
if changes > 0:
    with open(PATH, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'\n✅ Saved! {changes} changes made.')
else:
    print('\n❌ No changes were made!')
