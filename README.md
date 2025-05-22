# EOD Status Update Bot 🤖

A Slack bot that helps developers share their end-of-day status updates in a structured and organized way. The bot sends daily reminders at 5 PM in each developer's local timezone and provides an easy-to-use interface for submitting updates.

## Features ✨

- 📅 **Automated Daily Reminders**: Sends reminders at 5 PM in each developer's local timezone
- 📝 **Structured Updates**: Pre-defined fields for updates, next steps, priority, and blockers
- 🔄 **Edit Support**: Edit your status updates after submission
- 🎯 **Project-Specific Updates**: Submit updates for different project channels
- 🤖 **Developer-Only Access**: Restricts access to authorized developers
- ⏰ **Timezone Support**: Handles multiple timezones for distributed teams
- 🧪 **Test Mode**: Test reminders and functionality with `/test-reminders` command

## Prerequisites 📋

- Python 3.8 or higher
- A Slack workspace with admin access
- A Slack app with the following scopes:
  - `chat:write`
  - `commands`
  - `users:read`
  - `usergroups:read` (optional, for developer group support)
  - `channels:read`
  - `groups:read`
  - `im:write`
  - `mpim:write`

## Installation 🚀

1. Clone the repository:

   ```bash
   git clone https://github.com/yourusername/eod-status-update.git
   cd eod-status-update
   ```

2. Create and activate a virtual environment:

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root:

   ```env
   # Required
   SLACK_BOT_TOKEN=xoxb-your-bot-token
   APP_LEVEL_TOKEN=xapp-your-app-level-token
   
   # Optional but recommended
   DEVELOPER_USERGROUP_ID=your-usergroup-id  # For developer group support
   FALLBACK_DEVELOPER_IDS=U123456,U789012    # Comma-separated list of developer IDs
   TEST_CHANNEL=#your-test-channel           # For testing messages
   PORT=3000                                 # Port for the HTTP server
   ```

## Slack App Setup 🔧

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app
2. Under "OAuth & Permissions":
   - Add the required scopes listed in Prerequisites
   - Install the app to your workspace
   - Copy the "Bot User OAuth Token" to `SLACK_BOT_TOKEN` in `.env`
3. Under "Basic Information":
   - Enable Socket Mode
   - Copy the "App-Level Token" to `APP_LEVEL_TOKEN` in `.env`
4. Under "Slash Commands":
   - Create a new command `/eod-status`
   - Create a new command `/test-reminders`
5. Under "User Groups":
   - Create a user group for developers (optional)
   - Copy the group ID to `DEVELOPER_USERGROUP_ID` in `.env`

## Running the Bot

To run the bot, make sure you're in the project root directory and have activated your virtual environment:

```bash
# Activate virtual environment
source venv/bin/activate  # On Unix/macOS
# or
.\venv\Scripts\activate  # On Windows

# Run the bot from the project root
python main.py
```

⚠️ **Important**: Always run the bot using `main.py` from the project root directory. Do not try to run individual Python files directly as they depend on the proper Python package structure.

## Usage Guide 📖

### For Developers

1. **Daily Reminders**:
   - Receive a reminder at 5 PM in your local timezone
   - Click "Yes, let's do it! ✨" to start an update
   - Click "Not today 🙅‍♂️" to skip

2. **Manual Updates**:
   - Use `/eod-status` command to start an update
   - Select a project channel
   - Fill in the update form

3. **Editing Updates**:
   - Click "✏️ Edit Update" on any status message
   - Modify the update in the modal
   - Click "Update" to save changes

### For Admins

1. **Testing**:
   - Use `/test-reminders` to test the reminder system
   - Check the logs for detailed information

2. **Configuration**:
   - Update `.env` file for configuration changes
   - Modify `app/config.py` for message templates and settings

## Project Structure 📁

```plaintext
eod-status-update/
├── main.py                 # Entry point
├── app/
│   ├── __init__.py
│   ├── bot.py             # Bot initialization
│   ├── config.py          # Configuration
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── status.py      # Status update handlers
│   │   ├── reminders.py   # Reminder handlers
│   │   └── commands.py    # Slash command handlers
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── form.py        # Form handling utilities
│   │   ├── timezone.py    # Timezone utilities
│   │   └── developers.py  # Developer management
│   └── models/
│       ├── __init__.py
│       └── status.py      # Status data models
├── requirements.txt
└── .env
```

## Contributing 🤝

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License 📄

This project is licensed under the MIT License - see the LICENSE file for details.

## Support 💬

For support, please:

1. Check the [documentation](docs/)
2. Open an issue in the repository
3. Contact the maintainers
