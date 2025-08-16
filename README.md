# AuroraOS - AI Terminal Assistant

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

## Usage

**Note:** If using a virtual environment, make sure to activate it first:
```bash
source venv/bin/activate
```

### Generate a command (without executing):
```bash
./ask.py "list all files in current directory"
# Output: Generated command: ls -la
```

### Generate and execute a command:
```bash
./ask.py "show disk usage" --execute
# Output: Generated command: df -h
# Executing command...
# [command output]
# Done!
```

### More examples:
```bash
./ask.py "find all Python files"
./ask.py "show running processes"
./ask.py "create a directory called test"
./ask.py "compress folder mydata into a zip file" --execute
```

## Safety Note

Always review the generated command before using `--execute` to ensure it's safe and correct.