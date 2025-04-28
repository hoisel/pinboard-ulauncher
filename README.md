# Pinboard Ulauncher Extension

A Ulauncher extension to interact with your [Pinboard.in](https://pinboard.in) bookmarks.

## Features

- Search your Pinboard bookmarks
- Browse and filter by tags
- View recent bookmarks
- Add new bookmarks (placeholder functionality)

## Requirements

- [Ulauncher](https://ulauncher.io/) 5.0+
- Python 3.6+
- A Pinboard.in account with API token

## Installation

1. Open Ulauncher preferences
2. Go to "Extensions" tab
3. Click "Add extension"
4. Paste this repository URL: `https://github.com/your-username/pinboard-ulauncher`

## Usage

1. Configure your Pinboard API token in the extension preferences
   - You can find your API token at https://pinboard.in/settings/password
   - It should be in the format `username:HEXADECIMALTOKEN`

2. Type the keyword (default: `pb`) in Ulauncher to activate the extension
   - Main menu will show available actions
   - Type additional text to search your bookmarks
   - Use `#` prefix to browse and select tags (e.g., `pb #javascript`)

## Commands

- `pb` - Show main menu
- `pb [query]` - Search bookmarks containing query
- `pb #[tag]` - Browse and select tags

## License

MIT 