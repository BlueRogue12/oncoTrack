# Environment Setup with .env File

The pipeline now uses a `.env` file for configuration, making it much easier to manage settings like your Fiji path.

## 🚀 Quick Setup (3 Steps)

### 1. Run the Setup Script

This will create your `.env` file and install dependencies:

```bash
cd ~/code/oncoTrack
./setup_env.sh
```

### 2. Edit .env File (If Needed)

The `.env` file is already created with your Fiji path. To modify:

```bash
nano .env
```

Or edit it in your IDE. It looks like this:

```bash
# OncoTrack Pipeline Configuration

# Path to Fiji executable
FIJI_PATH=/home/username/Fiji/fiji-linux-x64
```

### 3. Run the Pipeline

```bash
./test_vid1_frames.sh
```

That's it! The `.env` file is automatically loaded.

---

## 📝 Manual Setup

If you prefer to set up manually:

### 1. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install packages (including python-dotenv)
pip install -r requirements.txt
```

### 2. Create .env File

```bash
# Copy the example
cp .env.example .env

# Edit with your settings
nano .env
```

### 3. Configure Your Fiji Path

Edit `.env` and set:

```bash
FIJI_PATH=/home/username/Fiji/fiji-linux-x64
```

**For other systems:**
- Linux: `/path/to/fiji/ImageJ-linux64`
- Mac: `/Applications/Fiji.app/Contents/MacOS/ImageJ-macosx`
- Windows WSL: `/mnt/c/path/to/fiji-win64.exe`

---

## 🔧 How It Works

### Python Code

The `src/config.py` module automatically loads `.env`:

```python
from dotenv import load_dotenv
load_dotenv()

# Then uses environment variables
fiji_path: str = os.environ.get("FIJI_PATH", "fiji")
```

### Shell Scripts

Shell scripts (`run_pipeline.sh`, `test_vid1_frames.sh`) automatically load `.env`:

```bash
if [ -f ".env" ]; then
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
fi
```

---

## 📋 Available Configuration Options

You can add these to your `.env` file:

```bash
# Required: Path to Fiji executable
FIJI_PATH=/home/username/Fiji/fiji-linux-x64

# Recommended: Default path to frames directory
# Can be relative (to project root) or absolute
FRAMES_PATH=vid1_frames_1-3

# Optional: Override database path
DB_PATH=data/tracking.db

# Optional: Override output directory
OUTPUT_DIR=output

# Optional: Default log level
LOG_LEVEL=INFO
```

### Team-Friendly Frame Paths

Each team member can configure their own frame location:

**Developer 1** (local project folder):
```bash
FRAMES_PATH=vid1_frames_1-3
```

**Developer 2** (different batch):
```bash
FRAMES_PATH=data/batches/my_cells_batch1
```

**Developer 3** (shared network drive):
```bash
FRAMES_PATH=/mnt/shared/microscope_captures/experiment_2024
```

**Developer 4** (Windows WSL path):
```bash
FRAMES_PATH=/mnt/c/Users/username/Documents/cell_frames
```

---

## ✅ Verify Setup

Run the verification script:

```bash
./verify_setup.sh
```

This checks:
- ✓ Python version
- ✓ Virtual environment
- ✓ Required packages
- ✓ Fiji path from .env
- ✓ Fiji executable accessibility

---

## 🔒 Security Note

The `.env` file is in `.gitignore` and won't be committed to git. This is intentional because:
- It contains local paths specific to your machine
- Different team members may have Fiji installed in different locations

The `.env.example` file IS committed and serves as a template.

---

## 🆘 Troubleshooting

### .env file not loading?

Make sure you're running scripts from the project root:

```bash
cd ~/code/oncoTrack
./test_vid1_frames.sh
```

### FIJI_PATH not working?

1. Check the path is correct:
   ```bash
   ls -la ~/Fiji/fiji-linux-x64
   ```

2. Make sure the file is executable:
   ```bash
   chmod +x ~/Fiji/fiji-linux-x64
   ```

3. Test Fiji directly:
   ```bash
   ~/Fiji/fiji-linux-x64 --version
   ```

### Still getting "FIJI_PATH not set"?

Manually load the .env file:

```bash
export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
echo $FIJI_PATH
```

---

## 🔄 Updating Configuration

To change settings, just edit `.env`:

```bash
nano .env
```

No need to restart anything - the configuration is loaded each time you run the pipeline.

---

## 📚 Related Documentation

- **Full Setup**: See `QUICKSTART.md`
- **Pipeline Details**: See `README_PIPELINE.md`
- **Project Overview**: See `PROJECT_SUMMARY.md`
