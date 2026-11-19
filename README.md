# Forbidden Memories Workshop

A browser and Windows desktop editor for the USA Yu-Gi-Oh! Forbidden Memories disc. It reads the game's card tables and artwork from your own disc image, lets you edit card data, fusions, opponent drop pools and opponent portraits, creates a new PS1 memory card, and exports a patched raw disc image with a companion CUE file.

## Browser editor

[Open Forbidden Memories Workshop on GitHub Pages](https://sickduck696969.github.io/YGO-FM-Editor/).

Choose **Open disc image** and select your USA SLUS-01411 BIN, IMG or ISO. For a single-track CUE or CCD, select its data file alongside it. The editor reads the game artwork, opponent portraits and databases on your device. To edit an existing memory card independently, choose **Save editor → Open save file**.

In **Fusion lab**, choose **Multiple cards** for either material, select cards by name or artwork, and confirm with **Use selected cards**. Choose one result and apply the recipe to create each unique pairing between the two materials.

Use **Apply card changes** to stage the selected card. In **Rewards & export**, build and download a BPS patch or the patched disc. Raw disc exports have two download links. Keep the BIN and CUE together and open the CUE in DuckStation. Starter decks and edited saves download from their own tabs. Edits live in the current browser tab until downloaded.

To serve the browser version locally, run `python tools/build_pages.py`, then `python -m http.server 8000 --directory dist/pages` and open `http://localhost:8000`. The build downloads a pinned Pyodide runtime and Pillow. GitHub Actions builds and deploys the same static files on pushes to `master`.

## Start the desktop editor

Install Python 3.10 or newer, then open PowerShell in this folder and run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m fm_editor
```

Or double-click **Launch Editor.bat** after installing the dependency. The workspace already includes a virtual environment when developed here.

Open a USA release image (`.img`, `.bin`, `.iso`, `.cue`, or `.ccd`). `.ccd` expects the matching `.img` beside it. The supported raw layouts are 2352-byte PS1 sectors, 2336-byte Mode 2 sectors, and 2048-byte ISO sectors. The editor currently recognizes `SLUS_014.11`; it does not accept CHD/PBP archives or other regional releases.

Choose a workspace from the top navigation. The **Theme** selector includes twelve palettes inspired by TCG boss monsters, from Mirrorjade’s glacial blue to Eldlich’s gold.

## Edit and export

- **Cards:** Edit name, description, ATK, DEF, level, type, attribute, guardian stars, password, starchip cost and artwork. Card lists use the original type, attribute and Guardian Star sprites extracted from the loaded game data, plus a level star marker. Imported artwork is converted to the game's 102×96 texture and both in-game thumbnails; edited names also update the title image baked into the card record.
- **Save Data Editor** opens DuckStation memory cards and single saves. Edit the profile, campaign milestones, trunk, deck and Free Duel opponents, then save a checksummed copy. Open a ROM to load portraits. Toggle opponents individually or use **Unlock all** and **Lock all**. Duel Master K is always available.
- **Card filters** let you combine multiple types, attributes and levels with inclusive ATK and DEF ranges. Selections within a category match any selected value. Apply the menu to update the list or cancel to keep browsing.
- **Fusion Lab** shows live artwork for both materials and the result in play order. Use **Result**, **Material**, or **Everywhere** to search by name or exact card ID (for example, `#1`). Right-click a card in Card Studio to find its recipes, or right-click a recipe to copy it. Click a recipe or navigate with the arrow keys to edit it. Browse all pages, filter results, or select **In starter deck** to find recipes the current deck can make. Use either specific cards or material filters with exceptions. **Skip existing pairs** protects existing recipes during bulk edits. **Undo recipe edit** restores the previous recipe table after an apply, deletion or reset.
- **Duelist Drops:** Select an opponent and rank pool. The opponent portrait and card thumbnails are shown. Double-click a card row to edit its weight, add a card through the visual card picker, balance weights to 2048, and replace that opponent's portrait.
- **Starter Deck & Save:** Build exactly 40 cards from an artwork-backed card library (up to three copies each). Left-click a library card to add it; right-click to remove one copy. Fill remaining deck slots randomly or generate a balanced, monster-heavy or unrestricted random deck. Set a player name and starting starchips, then create a 128 KiB `.mcd` for DuckStation.
- **Rewards & Export** lets you override compatible USA reward hooks and choose 1 to 100 cards per win. The results screen shows the first roll. Extra rolls from the same rank pool go directly into the trunk.

Use **Export BPS patch** to share edits. In a BPS-compatible patcher such as Floating IPS, select the patch and the exact original binary image used in Workshop. If you opened a CUE or CCD, use its BIN or IMG data file. The patch checks the source and resulting image CRCs. For raw discs, point a copy of the original CUE at the patched track name.

Exports default to `Yu-Gi-Oh! - Forbidden Memories.bin` for raw-sector images, or `.iso` for 2048-byte images. Memory card saves use the same base name with `.mcd`. Raw-sector exports also create a matching `.cue`; keep both disc files together and open the `.cue` in DuckStation. It points to the BIN image.

Drop weights are stored as 16-bit values across the game's 39 opponent records. Each pool should total 2048; use **Balance weights to 2048** after edits.

## Notes

The game stores card level and attribute as packed nibbles in `SLUS_014.11`. Card IDs remain the original 1–722. Card effects and new card IDs are not represented by the retail data tables and are outside this editor's card fields.

The ROM table and sector code has an MIT license in `THIRD_PARTY_LICENSE.txt`. The app does not ship a game image or game artwork.
