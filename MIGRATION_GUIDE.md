# EOD Status Bot - Migration Guide

This guide details the steps required to migrate the EOD Status Bot from a test Slack workspace to your production team workspace.

## Prerequisites

Before starting the migration, ensure you have:
- Access to both the test and production Slack workspaces
- Admin permissions in the production workspace (or ability to install apps)
- The current working codebase from your test environment
- A hosting platform ready for production deployment

## Step 1: Create New Slack App in Production Workspace

1. **Navigate to Slack API Dashboard**
   - Go to [https://api.slack.com/apps](https://api.slack.com/apps)
   - Sign in with your production workspace account

2. **Create New App**
   - Click "Create New App"
   - Choose "From scratch"
   - Enter app name: `EOD Status Bot` (or your preferred name)
   - Select the **production workspace** (not your test workspace)
   - Click "Create App"

## Step 2: Configure App Permissions

1. **Navigate to OAuth & Permissions**
   - In the left sidebar, click "OAuth & Permissions"

2. **Add Required Scopes**
   Under "Bot Token Scopes", add the following permissions:
   - `chat:write` - Send messages to channels and DMs
   - `commands` - Add slash commands
   - `users:read` - Read user information (for timezone data)
   - `usergroups:read` - Read user groups (for developer usergroup)
   - `channels:read` - Read public channels
   - `groups:read` - Read private channels
   - `im:write` - Send direct messages
   - `mpim:write` - Send group direct messages

3. **Save Changes**
   - Click "Save Changes" at the bottom of the page

## Step 3: Enable Socket Mode

1. **Navigate to Socket Mode**
   - In the left sidebar, click "Socket Mode"

2. **Enable Socket Mode**
   - Toggle "Enable Socket Mode" to On

3. **Generate App-Level Token**
   - Click "Generate Token and Secret"
   - Add the `connections:write` scope
   - Click "Generate"
   - **Copy and save this token** - it starts with `xapp-`

## Step 4: Configure Slash Command

1. **Navigate to Slash Commands**
   - In the left sidebar, click "Slash Commands"

2. **Create New Command**
   - Click "Create New Command"
   - Fill in the details:
     - **Command**: `/eod-status`
     - **Short Description**: `Submit your end-of-day status update`
     - **Usage Hint**: `[optional message]`
   - Click "Save"

## Step 5: Set Up Developer Usergroup

1. **In Your Production Slack Workspace**
   - Go to "People & User Groups" in Slack
   - Click "User Groups" tab
   - Click "Create User Group"

2. **Create Developer Group**
   - **Name**: `developers` (or your preferred name)
   - **Handle**: `@developers`
   - **Description**: `Team members who submit EOD status updates`
   - **Members**: Add all team members who should receive status updates
   - Click "Create"

3. **Get Usergroup ID**
   - Click on the newly created usergroup
   - Copy the usergroup ID from the URL (it's a string like `S0123456789`)

## Step 6: Prepare Production Environment Variables

1. **Get Bot Token**
   - Go back to "OAuth & Permissions" in your app settings
   - Click "Install to Workspace"
   - Authorize the app
   - Copy the "Bot User OAuth Token" (starts with `xoxb-`)

2. **Create Production .env File**
   Create a new `.env` file for production:
   ```bash
   SLACK_BOT_TOKEN=xoxb-your-new-bot-token
   APP_LEVEL_TOKEN=xapp-your-new-app-level-token
   DEVELOPER_USERGROUP_ID=your-new-usergroup-id
   PORT=3000
   TEST_CHANNEL=#general
   ```

## Step 7: Deploy to Production Hosting

### Option A: Heroku Deployment
1. **Create Heroku App**
   ```bash
   heroku create your-eod-status-bot
   ```

2. **Set Environment Variables**
   ```bash
   heroku config:set SLACK_BOT_TOKEN=xoxb-your-token
   heroku config:set APP_LEVEL_TOKEN=xapp-your-token
   heroku config:set DEVELOPER_USERGROUP_ID=your-usergroup-id
   heroku config:set TEST_CHANNEL=#general
   ```

3. **Deploy**
   ```bash
   git push heroku main
   ```

### Option B: AWS/DigitalOcean Deployment
1. **Set up your server/container**
2. **Copy the production .env file**
3. **Install dependencies**: `pip install -r requirements.txt`
4. **Run the application**: `python eod-status.py`

### Option C: Docker Deployment
1. **Create Dockerfile** (if not already present)
2. **Build and run container**
   ```bash
   docker build -t eod-status-bot .
   docker run -d --env-file .env eod-status-bot
   ```

## Step 8: Install App to Production Workspace

1. **Navigate to Install App**
   - In your app settings, click "Install App"

2. **Install to Workspace**
   - Click "Install to Workspace"
   - Review the permissions
   - Click "Allow"

3. **Verify Installation**
   - You should see "App installed successfully"
   - Note the "Bot User OAuth Token" for your .env file

## Step 9: Test Production Deployment

1. **Test Slash Command**
   - In your production workspace, try `/eod-status`
   - Verify the bot responds correctly

2. **Test Status Submission**
   - Complete a full status update flow
   - Verify the modal opens and submits correctly
   - Check that messages are posted to the selected channel

3. **Test Scheduling**
   - Wait for 5 PM in your timezone
   - Verify that reminders are sent to developers in the usergroup

4. **Test Error Handling**
   - Try submitting with missing required fields
   - Verify error messages are displayed correctly

## Step 10: Final Configuration

1. **Update Team Documentation**
   - Document the new slash command for your team
   - Explain how to use the bot
   - Set expectations for daily updates

2. **Set Up Monitoring** (Optional)
   - Configure logging to track bot usage
   - Set up alerts for any errors
   - Monitor bot performance

3. **Team Training**
   - Schedule a brief team meeting to introduce the bot
   - Demonstrate the features
   - Answer any questions

## Step 11: Clean Up Test Environment

1. **Uninstall from Test Workspace**
   - Go to your test workspace
   - Navigate to Apps
   - Find your test bot and uninstall it

2. **Archive Test App**
   - In the Slack API dashboard, you can archive the test app
   - Or keep it for future testing purposes

## Troubleshooting Common Issues

### Bot Not Responding
- Verify all environment variables are set correctly
- Check that the app is installed to the workspace
- Ensure Socket Mode is enabled
- Check the production logs for errors

### Permission Errors
- Verify all required scopes are added
- Reinstall the app after adding new scopes
- Check that the bot is invited to relevant channels

### Scheduling Not Working
- Verify the usergroup ID is correct
- Check that users are added to the usergroup
- Ensure the bot has permission to send DMs

### Modal Not Opening
- Check that the trigger_id is valid
- Verify the modal structure is correct
- Check for any JavaScript errors in the logs

## Security Considerations

1. **Environment Variables**
   - Never commit .env files to version control
   - Use secure methods to store production tokens
   - Rotate tokens periodically

2. **Bot Permissions**
   - Only grant the minimum required permissions
   - Regularly review and audit permissions
   - Monitor bot activity for unusual behavior

3. **Access Control**
   - Limit who can access the production environment
   - Use different tokens for different environments
   - Implement proper logging and monitoring

## Support and Maintenance

1. **Regular Updates**
   - Keep dependencies updated
   - Monitor Slack API changes
   - Update the bot as needed

2. **Backup and Recovery**
   - Keep backups of your configuration
   - Document the deployment process
   - Have a rollback plan ready

3. **Team Communication**
   - Establish a process for reporting issues
   - Keep the team informed of any changes
   - Provide training and support as needed

## Conclusion

After completing these steps, your EOD Status Bot should be successfully running in your production workspace. The bot will:

- Send daily reminders at 5 PM in each developer's local timezone
- Allow manual status updates via `/eod-status`
- Collect structured updates with priority, next steps, and timezone information
- Post updates to selected project channels
- Support cross-timezone team collaboration

Remember to test thoroughly in production before relying on the bot for daily operations. If you encounter any issues, refer to the troubleshooting section or check the application logs for detailed error information.
