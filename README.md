# Forbidden Memories Workshop

A Windows desktop editor for the USA Yu-Gi-Oh! Forbidden Memories disc. It reads the game's card tables and artwork from your own disc image, lets you edit card data, fusions, opponent drop pools and opponent portraits, creates a new PS1 memory card, and exports a patched raw disc image with a companion CUE file.

## Start

Install Python 3.10 or newer, then open PowerShell in this folder and run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m fm_editor
```

Or double-click **Launch Editor.bat** after installing the dependency. The workspace already includes a virtual environment when developed here.

Open a USA release image (`.img`, `.bin`, `.iso`, `.cue`, or `.ccd`). `.ccd` expects the matching `.img` beside it. The supported raw layouts are 2352-byte PS1 sectors, 2336-byte Mode 2 sectors, and 2048-byte ISO sectors. The editor currently recognizes `SLUS_014.11`; it does not accept CHD/PBP archives or other regional releases.

## Edit and export

- **Cards:** Edit name, description, ATK, DEF, level, type, attribute, guardian stars, password, starchip cost and artwork. Card lists use the original type, attribute and Guardian Star sprites extracted from the loaded game data, plus a level star marker. Imported artwork is converted to the game's 102×96 texture and both in-game thumbnails; edited names also update the title image baked into the card record.
- **Save Data Editor:** Open a DuckStation `.mcd` card or an exported `.mcs` save, edit the player profile, tournament completion, trunk counts and individual deck slots, then save a checksummed copy.
- **Fusion Lab:** Add/update and delete recipes using card artwork and names. Either material can target one card or match cards by type, level and attribute together; excluded cards are omitted from that material. Filtered selections expand into unique card pairs and are rejected without a partial edit if they exceed the game table.
- **Duelist Drops:** Select an opponent and rank pool. The opponent portrait and card thumbnails are shown. Double-click a card row to edit its weight, add a card through the visual card picker, balance weights to 2048, and replace that opponent's portrait.
- **Starter Deck & Save:** Build exactly 40 cards from an artwork-backed card library (up to three copies each). Left-click a library card to add it; right-click to remove one copy. Fill remaining deck slots randomly or generate a balanced, monster-heavy or unrestricted random deck. Set a player name and starting starchips, then create a 128 KiB `.mcd` for DuckStation.
- **Rewards & Export:** Set 1–100 cards dropped after each duel when the executable matches the supported retail reward layout. Custom mod reward code is preserved to avoid victory-screen hangs. Export writes a new patched image, verifies the edited files, and leaves the original image intact.

Exports default to `Yu-Gi-Oh! - Forbidden Memories.bin` for raw-sector images, or `.iso` for 2048-byte images. Memory card saves use the same base name with `.mcd`. Raw-sector exports also create a matching `.cue`; keep both disc files together and open the `.cue` in DuckStation. It points to the BIN image.

Drop weights are stored as 16-bit values across the game's 39 opponent records. Each pool should total 2048; use **Balance weights to 2048** after edits.

## Notes

The editor can identify the known stock North American `SLUS_014.11` executable by SHA-256 `84a54ed74f3d0edd6d81380839f7e4ef5bfb21ecea18be9a062bd6bfa5a45c88`. This checks the executable, not every file on the disc. The game stores card level and attribute as packed nibbles in `SLUS_014.11`. Card IDs remain the original 1–722. Card effects and new card IDs are not represented by the retail data tables and are outside this editor's card fields.

The ROM table and sector code has an MIT license in `THIRD_PARTY_LICENSE.txt`. The app does not ship a game image or game artwork.
