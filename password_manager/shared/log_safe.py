"""
Neutralise line breaks in values that go into log messages.

A username, provider name, header or request field written into a log line
unescaped can contain CR/LF and forge extra log entries (CWE-117). Wrap such
values, or the whole formatted message, in ``log_safe()``:

    logger.info("Created vault for %s", log_safe(user.username))
    logger.info(log_safe(f"Created vault for {user.username}"))

Line breaks are escaped (``\\n``), not dropped, so the log still shows that
the value contained one.
"""

# Unicode line boundaries that log viewers may also render as a new line.
_OTHER_LINE_BREAKS = {
    "\x0b": "\\x0b",
    "\x0c": "\\x0c",
    "\x1c": "\\x1c",
    "\x1d": "\\x1d",
    "\x1e": "\\x1e",
    "\x85": "\\x85",
    "\u2028": "\\u2028",
    "\u2029": "\\u2029",
}
_OTHER_LINE_BREAKS_TABLE = str.maketrans(_OTHER_LINE_BREAKS)


def log_safe(value) -> str:
    """Return ``str(value)`` with every line break escaped."""
    text = str(value).translate(_OTHER_LINE_BREAKS_TABLE)
    # Keep "\n" as the last replacement: it is the step static analysers
    # (CodeQL py/log-injection) recognise as the line-break sanitiser.
    return text.replace("\r", "\\r").replace("\n", "\\n")
