# Mintkey

Mintkey is a minimal Mac app that automatically types text into any window — with AI built in.

Whether you need to type out a long response, paste text into a form, or generate something with AI and have it typed out for you, Mintkey handles it cleanly and quietly in the background.

---

## Features

- **Auto Typer** — paste any text and Mintkey types it into your focused window at a speed you control
- **AI Chat** — chat with an AI model and type the response directly into any app
- **Mistake simulation** — adds realistic typos and corrections so it looks human
- **Multiple AI models** — switch between Mistral, GLM, MiniMax and more
- **Debug terminal** — see exactly what's happening behind the scenes with `/terminal`
- **Clean UI** — minimal pink design that stays out of your way

---

## Tips

- Set a 10 second delay so you have time to click into your target window before typing starts
- A mistake rate of 0.05 looks very natural without being obvious
- Use AI Chat to generate a response, then hit Type Response to have it typed out automatically
- Type `/terminal` in the AI chat input to open the debug window
- Your API key lives in a `.env` file on your Desktop — never share it or push it to GitHub
- If the app won't type, go to System Settings > Privacy & Security > Accessibility and make sure Mintkey is listed and enabled

---

## Requirements

- macOS
- An NVIDIA NIM API key from [build.nvidia.com](https://build.nvidia.com)
- A `.env` file on your Desktop with `NIM_API_KEY=your-key-here`

---

## Download

[Download the latest version](https://github.com/Kamiko-Weeb/MintKey/raw/main/Mintkey.dmg)

---

Made with love · Mintkey
