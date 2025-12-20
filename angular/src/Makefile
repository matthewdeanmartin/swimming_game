# Makefile for Swimming Game

# Configuration
PROJECT_NAME := swimming-game
OUTPUT_DIR := dist/$(PROJECT_NAME)/browser
NODE_MODULES := node_modules

# Default target
.PHONY: all
all: init build

# 1. Initialization: Install dependencies
.PHONY: init
init:
	@echo "Installing dependencies..."
	npm ci

# 2. Local Development: Run the dev server
.PHONY: start
start:
	@echo "Starting local development server..."
	npm start

# 3. Compile/Build: Standard production build
.PHONY: build
build:
	@echo "Building project..."
	npm run build

# 4. GitHub Pages Build: Builds with the correct base-href
# Usage: make build-gh REPO_NAME=your-repo-name
.PHONY: build-gh
build-gh:
ifndef REPO_NAME
	$(error REPO_NAME is undefined. Usage: make build-gh REPO_NAME=your-repo-name)
endif
	@echo "Building for GitHub Pages (Repo: $(REPO_NAME))..."
	# Angular requires the base-href to match the repository name for GH Pages
	npx ng build --configuration production --base-href /$(REPO_NAME)/

# 5. Clean: Remove dist folder and cache
.PHONY: clean
clean:
	@echo "Cleaning build artifacts..."
	rm -rf dist
	rm -rf .angular

# 6. Test: Run unit tests
.PHONY: test
test:
	npm test