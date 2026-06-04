# -*- coding: utf-8 -*-
"""Copy inside docker: docker cp fix_back_button_docker.py uc_app:/app/ && docker exec uc_app python3 /app/fix_back_button_docker.py"""
import sys, re

PATH = '/app/app/widgets/chat/index.html'

with open(PATH, 'r', encoding='utf-8') as f:
    lines = f.readlines()

print(f"File has {len(lines)} lines", flush=True)

# Find the exact lines for each edit by line content
remove_ranges = []
for i, line in enumerate(lines):
    stripped = line.strip()
    # Ads back button - line has setUserAdViewItem
    if 'setUserAdViewItem' in stripped and 'onClick' in stripped:
        # Remove this button block: button + </div> + ); + })()}
        # From this line, we need to remove button + following 4 lines
        # The button is on line i, the </div> is on i+3, ); on i+4, })() on i+5
        # Actually looking at the structure:
        # i:   <button onClick...
        # i+1: className=...
        # i+2: ← Назад к списку
        # i+3: </button>
        # i+4: </div>
        # i+5:   );
        # i+6:   })()}
        # We want to keep from </div> onwards, removing lines i through i+3
        print(f"Found ads button at line {i+1}: {stripped[:50]}", flush=True)
        remove_ranges.append((i, i+4))  # remove lines i through i+3 (button block)

    # News back button
    if 'setUserNewsViewItem' in stripped and 'onClick' in stripped:
        print(f"Found news button at line {i+1}: {stripped[:50]}", flush=True)
        remove_ranges.append((i, i+4))

# Remove in reverse order to preserve line numbers
remove_ranges.sort(key=lambda x: x[0], reverse=True)
for start, end in remove_ranges:
    del lines[start:end]

# Now find and replace the menu prompt block
# Join lines back to search
content = ''.join(lines)

# Look for the menu prompt pattern
old = '        // Главное меню (кроме admin_panel+messages и adminSelected — там контент в осн. layout)'
if old in content:
    idx = content.find(old)
    # Find the end of this block - it ends with two closing braces and newlines
    end_idx = content.find('        }', idx)
    # The block ends with:
    #         return (
    #           <div ...
    #             Выберите действие из меню ↓
    #           </div>
    #         );
    #         }
    # Find the closing } that ends this if block
    # After the first `}`, find the next `}\n`
    rest = content[end_idx:]
    # The pattern is `        }\n` followed by newline then next code
    # Let me just find the correct } by counting
    # Actually this is at the end of the function, so let me find the entire block more carefully

    search_from = idx
    # Find the exact block
    block_end = content.find('\n        }', search_from)
    if block_end > 0:
        block_end = content.find('\n', block_end + 1)  # skip past the }
        if block_end < 0:
            block_end = len(content)

        old_block = content[idx:block_end]
        print(f"\nFound menu prompt at line offset {idx}", flush=True)
        print(f"Block length: {len(old_block)}", flush=True)
        print(f"Block starts with: {repr(old_block[:50])}", flush=True)
        print(f"Block ends with: {repr(old_block[-50:])}", flush=True)

        new_block = (
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

        content = content[:idx] + new_block + content[block_end:]
        print("Menu prompt replaced successfully", flush=True)

with open(PATH, 'w', encoding='utf-8') as f:
    f.write(content)

print("\nDone! File updated.", flush=True)
