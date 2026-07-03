# Fella

A local AI companion that lives in your KDE system tray. Fella chats with
you through a locally-hosted LLM (via [Ollama](https://ollama.com)), reads
your hardware read-only so it actually knows your machine, and can run a
small set of vetted repair "recipes" (restart audio, free disk space,
refresh mirrors, etc.) — but only after you click a button to approve it.
Nothing leaves your computer.

Fella currently assumes an Arch-based system (developed against Garuda
Linux / KDE Plasma) since its recipes and system prompt use `pacman`.

## Requirements

- Linux with a KDE Plasma (or other system-tray-capable) desktop
- Python 3.10+
- [Ollama](https://ollama.com) installed and able to run locally
- An Ollama model pulled, e.g. `qwen2.5:7b-instruct`

## Setup

1. Install Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Install and start Ollama, then pull a model:

   ```bash
   sudo systemctl enable --now ollama
   ollama pull qwen2.5:7b-instruct
   ```

3. Run Fella:

   ```bash
   python -m fella.main
   ```

   A face icon will appear in your system tray. Click it to open the chat
   window.

## Notes

- Fella's memory (your name, chat log) is stored locally at
  `~/.local/share/fella/` as a plain-text `profile.txt` and a SQLite
  `memory.db`. You can open, edit, or delete either at any time — there's
  a "Open my memory file" option in the tray menu.
- Repair recipes live in `recipes/*.yaml`. Each one is preview → optional
  snapshot (via `snapper`, if installed) → run → verify, and nothing runs
  without you clicking the action button in chat.
- The AI never invents raw shell commands — it can only reference recipes
  by id; the actual commands are fixed in the YAML files.
