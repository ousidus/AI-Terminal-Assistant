# AI Terminal Assistant

A natural language command generator using Google's Gemini AI.

## Setup

### Option 1: Using Virtual Environment (Recommended)
1. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Option 2: Using pipx (Alternative)
1. **Install pipx if you don't have it:**
   ```bash
   brew install pipx
   ```

2. **Install each dependency separately:**
   ```bash
   pipx install google-generativeai
   pip3 install requests --user
   ```

**Note:** pipx is mainly for applications, not libraries, so this might not work perfectly.

### Option 3: System-wide install (Not recommended)
```bash
pip3 install -r requirements.txt --break-system-packages
```

2. **Get your Gemini API key:**
   - Go to [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Create a new API key
   - Copy the key

3. **Set up your environment variable:**
   ```bash
   # Add to your ~/.bashrc, ~/.zshrc, or ~/.profile
   export GEMINI_API_KEY="your_api_key_here"
   
   # Or set it temporarily for this session
   export GEMINI_API_KEY="your_api_key_here"
   ```

4. **Make the script executable:**
   ```bash
   chmod +x ask.py
   ```

## 🚀 Features

- 🤖 **RAG-Enhanced AI**: Uses vector similarity search to find relevant commands from knowledge base
- 🔒 **Safety Sandbox**: Automatic sandbox execution for risky commands with Docker isolation
- 📜 **Query History**: Tracks all queries and execution results
- 🎯 **Dry Run Mode**: Preview commands before execution
- 🧠 **Learning System**: Continuously learns from new commands
- ⚡ **Multiple Execution Modes**: Normal, sandbox, or dry-run
- 🎨 **Beautiful CLI**: Rich colors, panels, and progress indicators

## 📖 Usage

**Note:** If using a virtual environment, activate it first:
```bash
source venv/bin/activate
```

### 🔍 Basic Command Generation
```bash
# Generate command (no execution)
./ask.py "list all files in current directory"

# Show similar commands from knowledge base
./ask.py "find large files" --show-similar
```

### ⚡ Execution Modes
```bash
# Execute immediately (with confirmation)
./ask.py "show disk usage" --execute

# Dry run mode (preview only)
./ask.py "delete all temp files" --dry-run

# Force sandbox execution (safe)
./ask.py "install packages" --sandbox
```

### 📜 History Management
```bash
# View recent queries
./ask.py history

# Limit history results
./ask.py history --limit 5
```

### 🧠 Knowledge Base
```bash
# Search similar commands
./ask.py search "file operations"

# Add command to knowledge base
./ask.py learn "show memory usage" "free -h" --description "Display memory usage" --safety 1

# Clean up sandbox resources
./ask.py cleanup
```

### 🎯 Advanced Examples
```bash
# Risky command with automatic sandbox
./ask.py "remove all log files" --execute
# ⚠️ Automatically detects risk and uses sandbox

# Learning from interaction
./ask.py "backup my documents" --execute
# 🧠 Adds successful commands to knowledge base

# Multiple options
./ask.py "compress large directory" --dry-run --show-similar
# 🔍 Shows similar commands + preview without execution
```

## 🔒 Safety Features

- **Automatic Risk Detection**: Commands are analyzed for danger level (1-5)
- **Sandbox Execution**: High-risk commands run in isolated Docker containers
- **Confirmation Prompts**: Always asks before executing commands
- **Process Limits**: CPU and memory restrictions in sandbox mode
- **Read-only Filesystem**: Sandbox prevents system modifications

### Safety Levels:
- 🟢 **Level 1-2**: Safe commands (ls, cat, etc.)
- 🟡 **Level 3**: Moderate risk (sudo, file moves)
- 🟠 **Level 4**: High risk (kill processes, chmod 777)
- 🔴 **Level 5**: Extremely dangerous (rm -rf, disk formatting)