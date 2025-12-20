#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

PROJECT_NAME="swimming-game"

echo "=========================================="
echo "🏊 SWIMMING GAME BOOTSTRAPPER 🏊"
echo "=========================================="

# 1. Check for Node/NPM
if ! command -v npm &> /dev/null; then
    echo "❌ Error: npm is not installed. Please install Node.js."
    exit 1
fi

# 2. Scaffold Angular Project
echo "🛠  Creating Angular Project: $PROJECT_NAME..."
# --ssr false: No server-side rendering (games don't need it)
# --routing false: Single page, no router needed
# --style css: Standard CSS
# --skip-git: We will init git at the end
npx -y @angular/cli@latest new $PROJECT_NAME --style css --ssr false --routing false --skip-git --skip-install

cd $PROJECT_NAME

# 3. Install Dependencies (We skipped install above to speed up scaffold, now we do it)
echo "📦 Installing dependencies..."
npm install

# 4. Generate Game Component
echo "🧩 Generating Swimming Component..."
npx ng generate component swimming-game --skip-tests