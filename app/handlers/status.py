import json
import logging
from app.utils.form import get_form_data, build_status_modal
from app.utils.timezone import get_user_timezone, get_user_local_time
from app.utils.developers import get_relevant_project_channels

logger = logging.getLogger(__name__)

def register_status_handlers(app):
    """Register all status update related handlers."""
    
    @app.action("initial_update_choice")
    async def handle_initial_choice(ack, body, client, logger):
        """Handle the initial Yes/No choice for status updates."""
        try:
            await ack()
            user_id = body["user"]["id"]
            choice = body["actions"][0]["selected_option"]["value"]
            logger.info(f"Initial choice from user {user_id}: {choice}")

            if choice == "yes_update":
                project_channels = await get_relevant_project_channels(client)
                if project_channels:
                    channel_options = [
                        {"text": {"type": "plain_text", "text": channel["name"]}, "value": channel["id"]} 
                        for channel in project_channels
                    ]
                    await client.chat_postMessage(
                        channel=user_id,
                        text="Which project channel would you like to update?",
                        blocks=[
                            {
                                "type": "section",
                                "text": {"type": "mrkdwn", "text": "🎯 *Select the project channel you want to update:*"},
                                "accessory": {
                                    "type": "static_select",
                                    "placeholder": {"type": "plain_text", "text": "Choose a channel 📝"},
                                    "options": channel_options,
                                    "action_id": "select_project_channel"
                                }
                            }
                        ]
                    )
                else:
                    await client.chat_postMessage(
                        channel=user_id,
                        text="😕 It seems there are no project channels available to update right now."
                    )
            elif choice == "no_update":
                await client.chat_postMessage(
                    channel=user_id,
                    text="👋 No worries! Have a productive day! 💪"
                )
        except Exception as e:
            logger.error(f"Error in initial choice handler: {e}")
            logger.error(f"Request body: {json.dumps(body, indent=2)}")
            try:
                await client.chat_postEphemeral(
                    channel=user_id,
                    user=user_id,
                    text="😅 Oops! Something went wrong while processing your choice. Please try again!"
                )
            except Exception as e2:
                logger.error(f"Error sending error message: {e2}")

    @app.action("select_project_channel")
    async def handle_project_selection(ack, body, client, logger):
        """Handle project channel selection."""
        try:
            await ack()
            user_id = body["user"]["id"]
            channel_id = body["actions"][0]["selected_option"]["value"]
            logger.info(f"Project selection from user {user_id}: channel {channel_id}")
            
            # Build and open the status modal
            modal = build_status_modal(channel_id)
            await client.views_open(
                trigger_id=body["trigger_id"],
                view=modal
            )
        except Exception as e:
            logger.error(f"Error in project selection handler: {e}")
            logger.error(f"Request body: {json.dumps(body, indent=2)}")
            try:
                await client.chat_postEphemeral(
                    channel=user_id,
                    user=user_id,
                    text="😅 Sorry, there was an error opening the status form. Please try again."
                )
            except Exception as e2:
                logger.error(f"Error sending error message: {e2}")

    @app.view("status_submission")
    async def handle_status_submission(ack, body, view, client, logger):
        """Handle new status submission."""
        try:
            await ack()
            metadata = json.loads(view["private_metadata"])
            channel_id = metadata["channel_id"]
            user_id = body["user"]["id"]
            logger.info(f"Status submission from user {user_id} for channel {channel_id}")
            
            # Get form data
            form_data = get_form_data(view["state"]["values"])
            
            # Get user's timezone
            user_tz = await get_user_timezone(client, user_id)
            current_time = get_user_local_time(user_tz)
            
            # Build the message
            priority_emoji = {
                "high": "🔴",
                "medium": "🟡",
                "low": "🟢"
            }.get(form_data["priority"], "🟡")

            message = (
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 *Status Update from <@{user_id}>*\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🕒 *Local Time:* {current_time.strftime('%I:%M %p')} ({user_tz})\n"
                f"🎯 *Priority:* {priority_emoji} {form_data['priority'].upper()}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📝 *Update:*\n{form_data['update_text']}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏭️ *Next Steps:*\n{form_data['next_steps']}\n"
            )

            if form_data.get("technical_details"):
                message += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                message += f"🤓 *Dev Notes:*\n{form_data['technical_details']}\n"

            if form_data.get("blockers") == "yes":
                message += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                message += f"🚫 *Blockers:*\n{form_data.get('blockers_details', 'No details provided')}\n"

            # Handle media files
            media_blocks = []
            if "media_block" in view["state"]["values"]:
                media_files = view["state"]["values"]["media_block"]["media_upload"]["files"]
                if media_files:
                    message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    message += "📎 *Attached Media:*\n"
                    
                    for file in media_files:
                        file_id = file["id"]
                        file_info = await client.files_info(file=file_id)
                        if file_info["ok"]:
                            file_data = file_info["file"]
                            file_url = file_data["url_private"]
                            file_name = file_data["name"]
                            file_type = file_data["filetype"]
                            
                            # Add file to message
                            message += f"• {file_name}\n"
                            
                            # Add file block if it's an image
                            if file_type in ["png", "jpg", "jpeg", "gif"]:
                                media_blocks.append({
                                    "type": "image",
                                    "image_url": file_url,
                                    "alt_text": file_name
                                })
                            else:
                                # For non-image files, add a link
                                media_blocks.append({
                                    "type": "section",
                                    "text": {
                                        "type": "mrkdwn",
                                        "text": f"📄 <{file_url}|{file_name}>"
                                    }
                                })

            # Post the message with media blocks
            blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": message}
                }
            ]
            
            # Add media blocks if any
            blocks.extend(media_blocks)
            
            # Add edit button
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✏️ Edit Update", "emoji": True},
                        "style": "primary",
                        "action_id": "edit_status_update",
                        "value": json.dumps({
                            "channel_id": channel_id,
                            "form_data": form_data,
                            "message_ts": None,
                            "media_files": [f["id"] for f in media_files] if "media_block" in view["state"]["values"] else []
                        })
                    }
                ]
            })

            # Post the message
            response = await client.chat_postMessage(
                channel=channel_id,
                text=message,
                blocks=blocks
            )

            # Update the button with message timestamp
            if response["ok"]:
                message_ts = response["ts"]
                blocks[-1]["elements"][0]["value"] = json.dumps({
                    "channel_id": channel_id,
                    "form_data": form_data,
                    "message_ts": message_ts,
                    "media_files": [f["id"] for f in media_files] if "media_block" in view["state"]["values"] else []
                })
                
                await client.chat_update(
                    channel=channel_id,
                    ts=message_ts,
                    text=message,
                    blocks=blocks
                )

            # Ask about another update
            await client.chat_postMessage(
                channel=user_id,
                text="Do you have another project you'd like to provide an update for?",
                blocks=[
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": "🔄 *Want to update another project?*"},
                        "accessory": {
                            "type": "static_select",
                            "placeholder": {"type": "plain_text", "text": "Make your choice ✨"},
                            "options": [
                                {"text": {"type": "plain_text", "text": "Yes, one more! 🚀"}, "value": "yes_another"},
                                {"text": {"type": "plain_text", "text": "That's all! 🎉"}, "value": "no_another"}
                            ],
                            "action_id": "another_update_choice"
                        }
                    }
                ]
            )
        except Exception as e:
            logger.error(f"Error in status submission handler: {e}")
            logger.error(f"View state: {json.dumps(view['state']['values'], indent=2)}")
            try:
                await client.chat_postEphemeral(
                    channel=user_id,
                    user=user_id,
                    text="😅 Oops! Something went wrong while posting your update. Please try again!"
                )
            except Exception as e2:
                logger.error(f"Error sending error message: {e2}")

    @app.action("edit_status_update")
    async def handle_edit_status(ack, body, client, logger):
        """Handle edit button click."""
        try:
            await ack()
            user_id = body["user"]["id"]
            value_data = json.loads(body["actions"][0]["value"])
            channel_id = value_data["channel_id"]
            form_data = value_data["form_data"]
            message_ts = value_data.get("message_ts")
            media_files = value_data.get("media_files", [])  # Get media files from the button value
            
            if not message_ts:
                logger.error("Missing message timestamp in edit button value")
                await client.chat_postEphemeral(
                    channel=channel_id,
                    user=user_id,
                    text="😅 Sorry, there was an error opening the edit form. The message timestamp is missing."
                )
                return
                
            logger.info(f"Edit status triggered by user {user_id} for message {message_ts}")
            logger.info(f"Media files to preserve: {media_files}")
            
            # Add message_ts and media_files to form_data
            form_data["message_ts"] = message_ts
            form_data["media_files"] = media_files  # Add media files to form data
            
            # Build and open the edit modal
            modal = build_status_modal(channel_id, form_data)
            await client.views_open(
                trigger_id=body["trigger_id"],
                view=modal
            )
        except Exception as e:
            logger.error(f"Error in edit status handler: {e}")
            logger.error(f"Request body: {json.dumps(body, indent=2)}")
            try:
                await client.chat_postEphemeral(
                    channel=user_id,
                    user=user_id,
                    text="😅 Sorry, there was an error opening the edit form. Please try again."
                )
            except Exception as e2:
                logger.error(f"Error sending error message: {e2}")

    @app.view("status_submission_edit")
    async def handle_status_edit_submission(ack, body, view, client, logger):
        """Handle edited status submission."""
        try:
            await ack()
            metadata = json.loads(view["private_metadata"])
            channel_id = metadata["channel_id"]
            message_ts = metadata.get("message_ts")
            user_id = body["user"]["id"]
            existing_media_files = metadata.get("media_files", [])
            
            logger.info(f"Edit submission - Existing media files: {existing_media_files}")
            
            if not message_ts:
                logger.error("Missing message timestamp in edit submission")
                await client.chat_postEphemeral(
                    channel=channel_id,
                    user=user_id,
                    text="😅 Sorry, there was an error updating your status. The message timestamp is missing."
                )
                return
                
            logger.info(f"Edit submission from user {user_id} for message {message_ts}")
            
            # Get form data
            form_data = get_form_data(view["state"]["values"])
            
            # Get user's timezone
            user_tz = await get_user_timezone(client, user_id)
            current_time = get_user_local_time(user_tz)
            
            # Build the message
            priority_emoji = {
                "high": "🔴",
                "medium": "🟡",
                "low": "🟢"
            }.get(form_data["priority"], "🟡")

            message = (
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 *Status Update from <@{user_id}>* (edited)\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🕒 *Local Time:* {current_time.strftime('%I:%M %p')} ({user_tz})\n"
                f"🎯 *Priority:* {priority_emoji} {form_data['priority'].upper()}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📝 *Update:*\n{form_data['update_text']}\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"⏭️ *Next Steps:*\n{form_data['next_steps']}\n"
            )

            if form_data.get("technical_details"):
                message += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                message += f"🤓 *Dev Notes:*\n{form_data['technical_details']}\n"

            if form_data.get("blockers") == "yes":
                message += f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                message += f"🚫 *Blockers:*\n{form_data.get('blockers_details', 'No details provided')}\n"

            # Handle media files
            media_blocks = []
            media_files = []

            # First, handle existing media files that weren't removed
            if "media_block" in view["state"]["values"]:
                current_files = view["state"]["values"]["media_block"]["media_upload"]["files"]
                current_file_ids = [f["id"] for f in current_files]
                
                # Keep only the existing files that are still present
                for file_id in existing_media_files:
                    if file_id in current_file_ids:
                        try:
                            file_info = await client.files_info(file=file_id)
                            if file_info["ok"]:
                                file_data = file_info["file"]
                                file_url = file_data["url_private"]
                                file_name = file_data["name"]
                                file_type = file_data["filetype"]
                                
                                # Add file to message
                                message += f"• {file_name}\n"
                                
                                # Add file block if it's an image
                                if file_type in ["png", "jpg", "jpeg", "gif"]:
                                    media_blocks.append({
                                        "type": "image",
                                        "image_url": file_url,
                                        "alt_text": file_name
                                    })
                                else:
                                    # For non-image files, add a link
                                    media_blocks.append({
                                        "type": "section",
                                        "text": {
                                            "type": "mrkdwn",
                                            "text": f"📄 <{file_url}|{file_name}>"
                                        }
                                    })
                                media_files.append({"id": file_id})
                        except Exception as e:
                            logger.error(f"Error processing existing file {file_id}: {e}")

            # Then, handle new media files
            if "media_block" in view["state"]["values"]:
                new_files = view["state"]["values"]["media_block"]["media_upload"]["files"]
                if new_files:
                    for file in new_files:
                        file_id = file["id"]
                        if file_id not in existing_media_files:  # Only process new files
                            try:
                                file_info = await client.files_info(file=file_id)
                                if file_info["ok"]:
                                    file_data = file_info["file"]
                                    file_url = file_data["url_private"]
                                    file_name = file_data["name"]
                                    file_type = file_data["filetype"]
                                    
                                    # Add file to message
                                    message += f"• {file_name}\n"
                                    
                                    # Add file block if it's an image
                                    if file_type in ["png", "jpg", "jpeg", "gif"]:
                                        media_blocks.append({
                                            "type": "image",
                                            "image_url": file_url,
                                            "alt_text": file_name
                                        })
                                    else:
                                        # For non-image files, add a link
                                        media_blocks.append({
                                            "type": "section",
                                            "text": {
                                                "type": "mrkdwn",
                                                "text": f"📄 <{file_url}|{file_name}>"
                                            }
                                        })
                                    media_files.append({"id": file_id})
                            except Exception as e:
                                logger.error(f"Error processing new file {file_id}: {e}")

            # Build blocks for the message
            blocks = [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": message}
                }
            ]
            
            # Add media blocks if any
            if media_blocks:
                message += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                message += "📎 *Attached Media:*\n"
                blocks.extend(media_blocks)
            
            # Add edit button
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✏️ Edit Update", "emoji": True},
                        "style": "primary",
                        "action_id": "edit_status_update",
                        "value": json.dumps({
                            "channel_id": channel_id,
                            "form_data": form_data,
                            "message_ts": message_ts,
                            "media_files": [f["id"] for f in media_files]  # Include all media files
                        })
                    }
                ]
            })

            # Update the message
            await client.chat_update(
                channel=channel_id,
                ts=message_ts,
                text=message,
                blocks=blocks
            )

            # Notify the user
            await client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="✅ Your status update has been edited!"
            )
        except Exception as e:
            logger.error(f"Error in edit submission handler: {e}")
            logger.error(f"View state: {json.dumps(view['state']['values'], indent=2)}")
            try:
                await client.chat_postEphemeral(
                    channel=user_id,
                    user=user_id,
                    text="😅 Sorry, there was an error updating your status. Please try again."
                )
            except Exception as e2:
                logger.error(f"Error sending error message: {e2}")

    @app.action("another_update_choice")
    async def handle_another_update(ack, body, client, logger):
        """Handle choice for additional updates."""
        try:
            await ack()
            user_id = body["user"]["id"]
            choice = body["actions"][0]["selected_option"]["value"]
            logger.info(f"Another update choice from user {user_id}: {choice}")

            if choice == "yes_another":
                project_channels = await get_relevant_project_channels(client)
                if project_channels:
                    channel_options = [
                        {"text": {"type": "plain_text", "text": channel["name"]}, "value": channel["id"]} 
                        for channel in project_channels
                    ]
                    await client.chat_postMessage(
                        channel=user_id,
                        text="Which project channel would you like to update?",
                        blocks=[
                            {
                                "type": "section",
                                "text": {"type": "mrkdwn", "text": "🔄 *Select another project channel to update:*"},
                                "accessory": {
                                    "type": "static_select",
                                    "placeholder": {"type": "plain_text", "text": "Choose a channel 📝"},
                                    "options": channel_options,
                                    "action_id": "select_project_channel"
                                }
                            }
                        ]
                    )
                else:
                    await client.chat_postMessage(
                        channel=user_id,
                        text="😕 It seems there are no more project channels available to update."
                    )
            elif choice == "no_another":
                await client.chat_postMessage(
                    channel=user_id,
                    text="🎉 Awesome! Thanks for all your updates! Keep up the great work! 💪"
                )
        except Exception as e:
            logger.error(f"Error in another update choice handler: {e}")
            logger.error(f"Request body: {json.dumps(body, indent=2)}")
            try:
                await client.chat_postEphemeral(
                    channel=user_id,
                    user=user_id,
                    text="😅 Oops! Something went wrong while processing your choice. Please try again!"
                )
            except Exception as e2:
                logger.error(f"Error sending error message: {e2}") 