# End of Day Status Bot

A Slack bot that reminds developers to submit their end-of-day status updates.

## Setup

1. Create a virtual environment:
```
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:
```
pip install -r requirements.txt
```

3. Create a `.env` file in the root directory with the following variables:
```
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here
DEVELOPER_USERGROUP_ID=your-usergroup-id-here
PORT=3000
TEST_CHANNEL=#channel-for-test-messages
```

4. Configure Slack Event Subscriptions:
   - Go to your Slack App configuration page
   - Under "Event Subscriptions", enable events and add your URL (e.g., https://your-domain.com/slack/events)
   - Subscribe to bot events like `message.channels`, `team_join`, etc.
   - In the Events API setup, Slack will send a challenge parameter that the application will automatically respond to

5. Run the application:
```
python eod-status.py
```

## Features

- Automatic reminders at the end of the workday
- Easy status submission via Slack modal
- Option to include technical details
- Multiple project channel selection 