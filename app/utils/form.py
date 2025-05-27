import json
import logging

logger = logging.getLogger(__name__)

def get_form_data(view_state):
    """
    Safely extract form data from the view state, handling empty and optional fields.
    """
    try:
        # Required fields with safe gets
        update_text = view_state["update_block"]["update_text"]["value"]
        next_steps = view_state["next_steps_block"]["next_steps_text"]["value"]
        
        # Priority with safe fallback
        priority_block = view_state["priority_block"]["priority_select"]
        priority = "medium"  # default
        if priority_block.get("selected_option"):
            priority = priority_block["selected_option"]["value"]

        # Optional fields with safe gets
        technical_details = None
        if "technical_details_block" in view_state:
            tech_block = view_state["technical_details_block"].get("technical_details_text", {})
            if tech_block and isinstance(tech_block, dict):
                technical_details = tech_block.get("value")

        blockers = None
        if "blockers_block" in view_state:
            blockers_block = view_state["blockers_block"].get("blockers_select", {})
            if blockers_block and isinstance(blockers_block, dict):
                selected_option = blockers_block.get("selected_option")
                if selected_option and isinstance(selected_option, dict):
                    blockers = selected_option.get("value")

        blockers_details = None
        if "blockers_details_block" in view_state:
            blockers_details_block = view_state["blockers_details_block"].get("blockers_details_text", {})
            if blockers_details_block and isinstance(blockers_details_block, dict):
                blockers_details = blockers_details_block.get("value")

        return {
            "update_text": update_text,
            "next_steps": next_steps,
            "priority": priority,
            "technical_details": technical_details,
            "blockers": blockers,
            "blockers_details": blockers_details
        }
    except Exception as e:
        logger.error(f"Error extracting form data: {e}")
        logger.error(f"View state: {view_state}")
        raise

def build_status_modal(channel_id, form_data=None):
    """
    Build the status modal with optional pre-filled data.
    form_data is only provided when editing an existing status.
    """
    # Helper function to safely get string values
    def get_string_value(key, default=""):
        if not form_data:
            return default
        value = form_data.get(key)
        return str(value) if value is not None else default

    blocks = [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"Updating status for <#{channel_id}>"}
        },
        {
            "type": "input",
            "block_id": "update_block",
            "label": {"type": "plain_text", "text": "What's your update?"},
            "element": {
                "type": "plain_text_input",
                "multiline": True,
                "action_id": "update_text",
                "initial_value": get_string_value("update_text")
            }
        }
    ]

    # Add existing files section if editing
    if form_data and form_data.get("media_files"):
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "📎 *Currently attached files:*\nThese files will be kept unless you remove them in your edit."
            }
        })
        for file_id in form_data["media_files"]:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"• File ID: `{file_id}` (will be preserved)"
                    }
                ]
            })

    # Add file upload section
    blocks.append({
        "type": "input",
        "block_id": "media_block",
        "optional": True,
        "label": {"type": "plain_text", "text": "📎 Add New Media (optional)"},
        "element": {
            "type": "file_input",
            "action_id": "media_upload",
            "filetypes": ["png", "jpg", "jpeg", "gif", "pdf"],
            "max_files": 3
        },
        "hint": {
            "type": "plain_text",
            "text": "You can upload up to 3 new files (images or PDFs). Max 10MB per file. Existing files will be kept unless removed."
        }
    })

    # Add the rest of the blocks
    blocks.extend([
        {
            "type": "input",
            "block_id": "next_steps_block",
            "label": {"type": "plain_text", "text": "Next Steps"},
            "element": {
                "type": "plain_text_input",
                "multiline": True,
                "action_id": "next_steps_text",
                "initial_value": get_string_value("next_steps"),
                "placeholder": {"type": "plain_text", "text": "What needs to be done next?"}
            }
        },
        {
            "type": "input",
            "block_id": "priority_block",
            "label": {"type": "plain_text", "text": "Priority"},
            "element": {
                "type": "static_select",
                "placeholder": {"type": "plain_text", "text": "Select priority"},
                "options": [
                    {"text": {"type": "plain_text", "text": "High"}, "value": "high"},
                    {"text": {"type": "plain_text", "text": "Medium"}, "value": "medium"},
                    {"text": {"type": "plain_text", "text": "Low"}, "value": "low"}
                ],
                "action_id": "priority_select",
                "initial_option": {
                    "text": {"type": "plain_text", "text": get_string_value("priority", "medium").title()},
                    "value": get_string_value("priority", "medium")
                }
            }
        },
        {
            "type": "input",
            "block_id": "technical_details_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "🤓 Dev Notes (optional)"},
            "element": {
                "type": "plain_text_input",
                "multiline": True,
                "action_id": "technical_details_text",
                "initial_value": get_string_value("technical_details")
            }
        },
        {
            "type": "input",
            "block_id": "blockers_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "🚫 Blockers? (optional)"},
            "element": {
                "type": "static_select",
                "placeholder": {"type": "plain_text", "text": "Select an option"},
                "options": [
                    {"text": {"type": "plain_text", "text": "Yes"}, "value": "yes"},
                    {"text": {"type": "plain_text", "text": "No"}, "value": "no"}
                ],
                "action_id": "blockers_select",
                "initial_option": {
                    "text": {"type": "plain_text", "text": "Yes" if get_string_value("blockers") == "yes" else "No"},
                    "value": get_string_value("blockers", "no")
                }
            }
        },
        {
            "type": "input",
            "block_id": "blockers_details_block",
            "optional": True,
            "label": {"type": "plain_text", "text": "Blockers Details (optional)"},
            "element": {
                "type": "plain_text_input",
                "multiline": True,
                "action_id": "blockers_details_text",
                "initial_value": get_string_value("blockers_details")
            }
        }
    ])

    return {
        "type": "modal",
        "callback_id": "status_submission_edit" if form_data else "status_submission",
        "private_metadata": json.dumps({
            "channel_id": channel_id,
            "message_ts": form_data.get("message_ts") if form_data else None,
            "media_files": form_data.get("media_files", []) if form_data else []
        }),
        "title": {"type": "plain_text", "text": "Edit Status Update" if form_data else "Project Status Update"},
        "blocks": blocks,
        "submit": {"type": "plain_text", "text": "Update" if form_data else "Submit"}
    } 