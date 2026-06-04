# -*- coding: utf-8 -*-
"""Step 1.1: Add userChats state and fake chats"""
import sys

PATH = '/app/app/widgets/chat/index.html'

with open(PATH, 'r') as f:
    content = f.read()

changes = 0

# 1. Add new useState lines after chatInput state
old_state = "const [chatInput, setChatInput] = useState(\"\");              // текст нового сообщения\n\n      // 🏠 Комнаты"
new_state = """const [chatInput, setChatInput] = useState("");              // текст нового сообщения
      const [userChats, setUserChats] = useState([]);       // список чатов юзера (реал + фейки)
      const [activeChatId, setActiveChatId] = useState(null); // какой чат открыт

      // 🏠 Комнаты"""

if old_state in content:
    content = content.replace(old_state, new_state)
    print("OK added userChats/activeChatId states")
    changes += 1
else:
    print("FAIL state block not found")

# 2. Add fake chats data - find a good place. Let's add right after the isAdmin line
old_isadmin = "const isAdmin = user && user.id === ADMIN_ID;\n\n      // 🟢 Онлайн-статус"
new_isadmin = """const isAdmin = user && user.id === ADMIN_ID;

      // 🎭 Фейковые чаты для демонстрации списка (юзер-юзер)
      const FAKE_CHATS = [
        {
          id: "fake_anna", name: "Анна Смирнова", avatar: "А", unread: 1, online: true,
          avatarBg: "linear-gradient(135deg,#ec4899,#f472b6)",
          lastMessage: "Привет! Ты уже обновил дизайн?",
          lastTime: "14:32", status: "active",
          messages: [
            { id: 1, sender: "them", text: "Привет! Как там с заявкой?", time: "14:20", timeAgo: "14:20" },
            { id: 2, sender: "me", text: "Почти готово, завтра сдам 👍", time: "14:22", timeAgo: "14:22" },
            { id: 3, sender: "them", text: "Привет! Ты уже обновил дизайн?", time: "14:32", timeAgo: "14:32" },
          ]
        },
        {
          id: "fake_ivan", name: "Иван Петров", avatar: "И", unread: 0, online: false,
          avatarBg: "linear-gradient(135deg,#059669,#10b981)",
          lastMessage: "Спасибо за помощь!",
          lastTime: "вчера", status: "active",
          messages: [
            { id: 1, sender: "me", text: "Иван, привет! Подскажи по проекту?", time: "вчера 10:00", timeAgo: "вчера" },
            { id: 2, sender: "them", text: "Да, конечно, спрашивай", time: "вчера 10:05", timeAgo: "вчера" },
            { id: 3, sender: "me", text: "Как там интеграция прошла?", time: "вчера 10:10", timeAgo: "вчера" },
            { id: 4, sender: "them", text: "Спасибо за помощь!", time: "вчера 12:00", timeAgo: "вчера" },
          ]
        },
      ];

      // 🟢 Онлайн-статус"""

if old_isadmin in content:
    content = content.replace(old_isadmin, new_isadmin)
    print("OK added FAKE_CHATS")
    changes += 1
else:
    print("FAIL isAdmin block not found")

if changes:
    with open(PATH, 'w') as f:
        f.write(content)

print("DONE changes=%d" % changes)
