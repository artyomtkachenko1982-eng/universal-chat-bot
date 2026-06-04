#!/bin/bash
cd /opt/chat
git pull origin main
docker restart uc_app
echo "✅ Готово!"
