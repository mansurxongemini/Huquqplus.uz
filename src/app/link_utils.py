def build_group_message_link(group_id: str | int | None, message_id: int | None) -> str | None:
    """
    Build a direct Telegram web link to a message in a supergroup or public channel.
    """
    if not message_id or not group_id:
        return None
    group_id_str = str(group_id)
    if group_id_str.startswith("@"):
        return f"https://t.me/{group_id_str[1:]}/{message_id}"
    if group_id_str.startswith("-100") and group_id_str[4:].isdigit():
        return f"https://t.me/c/{group_id_str[4:]}/{message_id}"
    return None
