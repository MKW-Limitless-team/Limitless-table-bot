HELP_MESSAGE = """For more details about a command, use /help command:<name>

Main commands:
- `sw`: start a new table
- `vr`: verify a room
- `wp`: render the current table image
- `mergeroom`: merge another room onto the table

Status commands:
- `url`
- `rr`
- `commands`
- `teams`
- `races`
- `ap`
- `tt`

Edit commands:
- `changetag`
- `edittag`
- `teampen`
- `sub`
- `removerace`
- `insertrace`
- `editrace`
- `cp`
- `edit`
- `gpedit`
- `changename`
- `undo`
- `redo`
- `undoall`
- `redoall`
"""

HELP_MAP = {
    "sw": "Start a new table from a room code or player lookup.",
    "vr": "Show the players currently in a room.",
    "wp": "Render the current table image from saved state.",
    "mergeroom": "Attach another room to the current table metadata.",
    "rr": "Show race results for a specific race.",
    "url": "Show the Limitless race-results URL for tracked rooms.",
    "tt": "Get Lorenzi-compatible table text.",
    "ap": "List all players on the current table.",
    "races": "List all tracked races.",
    "teams": "List team tags and members.",
    "commands": "List applied table-edit commands.",
}
