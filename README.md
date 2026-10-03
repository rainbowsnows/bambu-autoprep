# Bambu AutoPrep Marketplace

This repository is structured as a ChatGPT/Codex plugin marketplace.

## What it does

Bambu AutoPrep is intended to:
- inspect a user-supplied printable model;
- choose conservative Bambu Studio settings;
- use the installed Bambu Studio profiles as the source of truth;
- export a ready 3MF through its MCP tool;
- return a preview image and concise print guide.

It does **not** automatically start the physical printer.

## Repository layout

- `.agents/plugins/marketplace.json` — marketplace catalog
- `plugins/bambu-autoprep/plugin.json` — portable Agent Plugins manifest
- `plugins/bambu-autoprep/skills/bambu-autoprep/SKILL.md` — workflow skill
- `plugins/bambu-autoprep/mcp/` — local Bambu Studio MCP implementation

## Final setup required in ChatGPT Work

The included Bambu MCP implementation needs to be registered as a ChatGPT MCP connection
before the plugin can call it from ChatGPT.

Current OpenAI guidance for an MCP-backed plugin is:

1. Enable ChatGPT Developer mode.
2. Run/deploy the MCP endpoint so ChatGPT Desktop can reach it.
3. Add the MCP connection in ChatGPT Plugins.
4. Copy the resulting technical app ID (`plugin_asdk_app...`).
5. In Work mode, use `@plugin-creator` to wire that app ID into this plugin.
6. Commit the generated `.app.json`/manifest update to this repository.
7. Push to GitHub.

## Importing the marketplace

For supported workspace GitHub marketplace import, use the repository URL itself:

`https://github.com/<owner>/<repo>`

Do not append the branch, folder, or marketplace JSON filename.

The selected repository contains `.agents/plugins/marketplace.json` at its root.
