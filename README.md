# Pinboard Ulauncher Extension

A Ulauncher extension to interact with your [Pinboard.in](https://pinboard.in) bookmarks.

## Features

- Search your Pinboard bookmarks
- Browse and filter by tags (with multi-tag selection)
- View recent bookmarks
- Add new bookmarks (placeholder functionality)
- Sort bookmarks by date or title
- Sort tags by count or alphabetically
- Configurable cache duration to reduce API calls
- Customizable number of results

## Requirements

- [Ulauncher](https://ulauncher.io/) 5.0+
- Python 3.6+
- A Pinboard.in account with API token

## Installation

1. Open Ulauncher preferences
2. Go to "Extensions" tab
3. Click "Add extension"
4. Paste this repository URL: `https://github.com/hoisel/pinboard-ulauncher`

## Usage

1. Configure your Pinboard API token in the extension preferences
   - You can find your API token at https://pinboard.in/settings/password
   - It should be in the format `username:HEXADECIMALTOKEN`

2. Type the keyword (default: `pb`) in Ulauncher to activate the extension
   - Main menu will show available actions
   - Type additional text to search your bookmarks
   - Use `#` prefix to browse and select tags (e.g., `pb #javascript`)

## Commands

- `pb` - Show main menu with options to:
  - Search bookmarks
  - Browse tags
  - Browse recent bookmarks
  - Add new bookmark
- `pb [query]` - Search bookmarks containing query
- `pb #[tag]` - Browse and select tags
  - Click on tags to toggle selection
  - Selected tags will be used to filter bookmarks in search

## Configuration Options

- **Pinboard Token**: Your Pinboard API token
- **Maximum Results**: Number of results to display (5-200)
- **Cache Duration**: How long to cache data from Pinboard (1 min - 1 hour)
- **Sort Bookmarks**: Sort by most recent or alphabetically by title
- **Sort Tags**: Sort by count (most used first) or alphabetically
- **Recent Bookmarks Count**: Number of recent bookmarks to display (5-100)

## License

MIT 