# Git Workflow & What to Commit

## What's Committed (Tracked by Git)

✅ **Source Code**
- `src/` - Python pipeline code
- `fiji_scripts/` - Fiji/TrackMate Jython scripts
- `tools/` - Frame capture GUI
- `tests/` - Unit tests

✅ **Configuration Templates**
- `.env.example` - Configuration template (NOT `.env`)
- `requirements.txt` - All Python dependencies (pipeline + frame capture)

✅ **Documentation**
- `README.md` - Main documentation
- `QUICKSTART.md` - Quick start guide
- `CAPTURE_WORKFLOW.md` - Frame capture workflow
- `TEAM_SETUP.md` - Team onboarding
- All other `*.md` files

✅ **Scripts**
- `run_test.sh` - Test runner
- `setup_env.sh` - Environment setup
- `verify_setup.sh` - Setup verification

✅ **Sample Data** (Optional)
- `vid1_frames_1-3/` - Sample cell images for testing
- `data/batches/` - Additional test batches (if you create them)

✅ **Git Configuration**
- `.gitignore` - What to ignore
- `.editorconfig` - Editor settings (if present)

---

## What's NOT Committed (Gitignored)

❌ **Generated Data** (Each developer generates their own)
- `data/` - All database and TrackMate outputs
  - `data/tracking.db` - SQLite database
  - `data/trackmate_runs/` - TrackMate XML/CSV outputs
- `output/` - All pipeline outputs
  - `output/exports/` - CSV exports
  - `output/visualizations/` - PNG visualizations
- `captures/` - Screenshot captures (local development)

❌ **Personal Configuration**
- `.env` - Your personal paths and settings

❌ **Python Runtime**
- `venv/` - Virtual environment
- `__pycache__/` - Python bytecode
- `*.pyc`, `*.pyo` - Compiled Python files

❌ **IDE Settings** (Personal preferences)
- `.vscode/` - VS Code settings
- `.idea/` - PyCharm settings
- `.cursor/` - Cursor settings

❌ **OS Files**
- `.DS_Store` - macOS metadata
- `Thumbs.db` - Windows thumbnails
- `*.Zone.Identifier` - Windows security zones

❌ **Logs**
- `*.log` - All log files

---

## Why This Separation?

### Committed = Shared
Code, documentation, and configuration templates are shared with the team.

### Gitignored = Personal
Generated data, personal settings, and runtime files are unique to each developer.

---

## Branching Strategy

### Branch Structure

```
main (production - stable, tested)
  ↑
  │ PR: dev → main (after testing)
  │
dev (integration - active development)
  ↑
  │ PR: feature/* → dev
  │ PR: bugfix/* → dev
  │
  ├── feature/add-tracking-algorithm
  ├── feature/improve-visualization
  └── bugfix/fix-stitching-logic

Special case:
main
  ↑
  │ PR: hotfix/* → main (emergency only!)
  │
hotfix/critical-fix
  │
  └── Then: main → dev (sync hotfix back)
```

**Branches:**
- `main` - Production-ready code (stable, tested)
- `dev` - Integration branch (active development)
- `feature/*` - New features (branched from `dev`)
- `bugfix/*` - Bug fixes (branched from `dev`)
- `hotfix/*` - Emergency fixes (branched from `main`)

### Starting a New Feature/Bugfix

**Always branch from `dev`:**

```bash
# 1. Switch to dev branch
git checkout dev

# 2. Pull latest changes from remote
git pull origin dev

# 3. Create your new working branch
git checkout -b feature/cell-division-detection

# 4. Merge latest dev into your branch (ensures you're up to date)
git merge dev
```

**Branch naming conventions:**
- `feature/descriptive-name` - New features
- `bugfix/issue-description` - Bug fixes
- `hotfix/critical-fix` - Emergency production fixes

**Examples:**
```bash
# New feature
git checkout dev
git pull origin dev
git checkout -b feature/export-to-excel
git merge dev

# Bug fix
git checkout dev
git pull origin dev
git checkout -b bugfix/fix-csv-export
git merge dev

# Hotfix (from main, not dev!)
git checkout main
git pull origin main
git checkout -b hotfix/database-corruption
git merge main
```

### Working on Your Branch

```bash
# Make changes to files
nano src/main.py

# Check what changed
git status
git diff

# Stage and commit
git add src/main.py
git commit -m "Add cell division detection algorithm"

# Push your branch to remote
git push -u origin feature/cell-division-detection
```

### Creating a Pull Request (PR)

**Standard workflow (feature/bugfix → dev):**

1. **Push your branch:**
   ```bash
   git push -u origin feature/cell-division-detection
   ```

2. **Create PR on GitHub/GitLab:**
   - Source: `feature/cell-division-detection`
   - Target: `dev`
   - Title: "Add cell division detection"
   - Description: What changed and why

3. **Team reviews PR**

4. **After approval, merge to `dev`**

5. **Delete your feature branch** (after merge)

**Promoting dev to main:**

1. **Test thoroughly on `dev`**

2. **Create PR:**
   - Source: `dev`
   - Target: `main`
   - Title: "Release v1.2.0"
   - Description: List of features/fixes

3. **After approval, merge to `main`**

4. **Tag the release:**
   ```bash
   git checkout main
   git pull origin main
   git tag -a v1.2.0 -m "Release version 1.2.0"
   git push origin v1.2.0
   ```

### Hotfix Workflow (Emergency Fixes)

**ONLY for critical production issues:**

```bash
# 1. Branch from main (not dev!)
git checkout main
git pull origin main
git checkout -b hotfix/critical-database-fix

# 2. Fix the issue
nano src/store.py

# 3. Test the fix
./run_test.sh --clean --visualize

# 4. Commit
git add src/store.py
git commit -m "Hotfix: Prevent database corruption on concurrent writes"

# 5. Push hotfix branch
git push -u origin hotfix/critical-database-fix

# 6. Create PR: hotfix/critical-database-fix → main
#    (Must be tested even though it's urgent!)

# 7. After merge to main, also merge to dev
git checkout dev
git pull origin dev
git merge main
git push origin dev
```

**Important:** Hotfixes must be merged to BOTH `main` AND `dev` to keep them in sync.

### Keeping Your Branch Up to Date

If `dev` has new changes while you're working:

```bash
# On your feature branch
git checkout feature/cell-division-detection

# Pull latest dev
git fetch origin dev

# Merge dev into your branch
git merge origin/dev

# Resolve any conflicts if needed
# Then push
git push
```

### Summary: PR Flow

**Normal Development:**
```
1. Create branch from dev
   git checkout dev
   git pull origin dev
   git checkout -b feature/my-feature
   git merge dev

2. Work and commit
   git add .
   git commit -m "Add feature"
   git push -u origin feature/my-feature

3. Create PR: feature/my-feature → dev
   (Team reviews and approves)

4. Merge to dev
   (Feature branch can be deleted)

5. Test on dev
   (Run full test suite)

6. When stable, create PR: dev → main
   (Final review and approval)

7. Merge to main and tag
   git checkout main
   git pull origin main
   git tag -a v1.2.0 -m "Release 1.2.0"
   git push origin v1.2.0
```

**Hotfix (Emergency):**
```
1. Create hotfix branch from main
   git checkout main
   git pull origin main
   git checkout -b hotfix/critical-fix
   git merge main

2. Fix and test on hotfix branch
   (Must test even though urgent!)

3. Create PR: hotfix/critical-fix → main
   (Quick review and approval)

4. Merge to main
   (Production is now fixed)

5. Sync hotfix back to dev
   git checkout dev
   git pull origin dev
   git merge main
   git push origin dev
   (Ensures dev has the hotfix too)
```

**Golden Rules:**
1. ✅ Always branch from `dev` for features/bugfixes
2. ✅ Always PR to `dev` first (never directly to `main`)
3. ✅ Only merge `dev` → `main` when stable and tested
4. ✅ Hotfixes branch from `main`, merge to `main`, then merge `main` → `dev`
5. ✅ Test hotfixes on the branch before merging (even if urgent!)

---

## Common Git Commands

### First Time Setup
```bash
# Clone the repo
git clone <repo-url>
cd oncoTrack

# Create your personal .env
cp .env.example .env
nano .env  # Add your paths

# Install dependencies
./setup_env.sh
```

### Daily Development
```bash
# Check what changed
git status

# See your changes
git diff

# 1.) Stage changes
git add src/main.py
git add README.md
git add *     # Adds all changed files

# 2.) Commit
git commit -m "Fix: Update tracking parameters"

# 3.) Push to remote
git push
```

### Before Committing
```bash
# Verify you're not committing generated data
git status

# Should NOT see:
#   - data/tracking.db
#   - output/
#   - captures/
#   - .env

# Should see:
#   - Modified .py files
#   - Modified .md files
#   - Modified .sh scripts
```

---

## Team Collaboration

### When Someone Joins the Team

**They get from git:**
- ✅ All source code
- ✅ Documentation
- ✅ Sample data (`vid1_frames_1-3/`)
- ✅ Configuration template (`.env.example`)

**They create locally:**
- 🔧 Their own `.env` with their Fiji path
- 🔧 Their own `venv/` virtual environment
- 🔧 Their own `data/tracking.db` when they run the pipeline
- 🔧 Their own `captures/` when they use frame capture

**Result:** Everyone has the same code, but personalized configuration and data.

---

## Sharing Results

### Option 1: Share Database
```bash
# Export your database
cp data/tracking.db ~/shared/tracking_$(date +%Y%m%d).db
```

### Option 2: Share CSV Exports
```bash
# Run with export
./run_test.sh --batch vid1_frames_1-3 --export

# Share the CSVs
cp output/exports/*.csv ~/shared/
```

### Option 3: Share Visualization
```bash
# Generate visualization
./run_test.sh --batch vid1_frames_1-3 --visualize

# Share the image
cp output/visualizations/tracks.png ~/shared/
```

### Option 4: Commit New Sample Data
```bash
# Create a new batch directory
mkdir -p data/batches/experiment_001
cp ~/my_captures/*.png data/batches/experiment_001/

# Commit it (data/batches/ is NOT gitignored)
git add data/batches/experiment_001/
git commit -m "Add experiment 001 sample data"
git push

# Now your team can test with the same data!
```

---

## Checking Gitignore

### Verify a file is ignored
```bash
git check-ignore -v data/tracking.db
# Output: .gitignore:16:data/	data/tracking.db
```

### List all ignored files
```bash
git status --ignored
```

### Test before committing
```bash
# Dry run - see what would be committed
git add --dry-run .

# Or use git status
git status
```

---

## Summary

| Category | Committed? | Why |
|----------|-----------|-----|
| Source code (`src/`, `fiji_scripts/`) | ✅ Yes | Shared with team |
| Documentation (`*.md`) | ✅ Yes | Shared with team |
| Configuration template (`.env.example`) | ✅ Yes | Template for team |
| Personal config (`.env`) | ❌ No | Each person's paths are different |
| Sample data (`vid1_frames_1-3/`) | ✅ Yes | For testing |
| Generated data (`data/`, `output/`) | ❌ No | Each person generates their own |
| Captures (`captures/`) | ❌ No | Personal workspace |
| Virtual env (`venv/`) | ❌ No | Each person creates their own |

**Golden Rule:** Commit code and docs, not data and personal settings! 🎯

---

## Quick Reference

### Starting New Work

```bash
# Feature
git checkout dev && git pull origin dev
git checkout -b feature/my-feature && git merge dev

# Bugfix
git checkout dev && git pull origin dev
git checkout -b bugfix/fix-issue && git merge dev

# Hotfix
git checkout main && git pull origin main
git checkout -b hotfix/urgent-fix && git merge main
```

### Daily Workflow

```bash
# Check status
git status

# Stage changes
git add src/main.py

# Commit
git commit -m "Add feature X"

# Push
git push
```

### Creating PR

```bash
# Push your branch
git push -u origin feature/my-feature

# Then create PR on GitHub/GitLab:
# feature/my-feature → dev
```

### After PR is Merged

```bash
# Switch back to dev
git checkout dev

# Pull latest (includes your merged changes)
git pull origin dev

# Delete your local feature branch
git branch -d feature/my-feature

# Delete remote feature branch
git push origin --delete feature/my-feature
```

### Branch Targets

| Branch Type | Branch From | PR Target | Notes |
|-------------|-------------|-----------|-------|
| `feature/*` | `dev` | `dev` | New features |
| `bugfix/*` | `dev` | `dev` | Bug fixes |
| `hotfix/*` | `main` | `main` | Then merge `main` → `dev` |
| `dev` | - | `main` | Only when stable & tested |

### Emergency Commands

```bash
# Undo last commit (keep changes)
git reset --soft HEAD~1

# Discard all local changes
git reset --hard HEAD

# See commit history
git log --oneline --graph --all

# See what changed in a commit
git show <commit-hash>

# Stash changes temporarily
git stash
git stash pop
```
