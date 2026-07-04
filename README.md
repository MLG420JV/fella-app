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

## Installing apps

You can also ask Fella to install a known app, e.g. "install steam" or
"can you set up discord". Fella only installs from a fixed catalog in
`fella/apps.py` — it never runs a package manager with raw text you typed,
so there's no way to slip in an arbitrary package name. An install goes
through the same preview → snapshot → execute → verify flow as repair
recipes, with a confirm button.

Currently cataloged: Steam, Discord, Spotify, VS Code, GIMP, Blender,
OBS Studio, VLC, Telegram, Lutris, Heroic Games Launcher, Timeshift,
Chromium, Firefox, Slack. Spotify, Heroic, and Slack come from
`chaotic-aur`, so that repo needs to be enabled (it is by default on
Garuda).

If you ask for something outside that catalog, Fella falls back to
searching Flathub — the same app store behind KDE Discover — and offers
the closest match through `flatpak install`, still gated by the same
confirm button. Requires `flatpak` with the `flathub` remote configured
(`flatpak remote-add flathub https://flathub.org/repo/flathub.flatpakrepo`
if it isn't already — Garuda ships this by default).

## The chat window

Fella shows its face at the top of the chat window and reacts as you talk:
idle by default, thinking while it's generating a reply, asking when it's
offering you a recipe/install button, and a brief happy reaction once a
reply lands with nothing to confirm. Messages render as chat bubbles
(yours on the right, Fella's on the left).

## Notes

- Fella's memory (your name, chat log) is stored locally at
  `~/.local/share/fella/` as a plain-text `profile.txt` and a SQLite
  `memory.db`. You can open, edit, or delete either at any time — there's
  a "Open my memory file" option in the tray menu.
- Repair recipes live in `recipes/*.yaml`. Each one is preview → optional
  snapshot (via `snapper`, if installed) → run → verify, and nothing runs
  without you clicking the action button in chat.
- The AI never invents raw shell commands — it can only reference recipes
  or cataloged app installs by id; the actual commands are fixed in code
  or YAML, never built from what you typed.
