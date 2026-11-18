"""Browser-facing operations for the same USA game and save formats as the desktop editor."""
import base64
import copy
import io
import json
import re
import struct
from pathlib import Path

from PIL import Image
from core.card_data import CARD_NAMES, CARD_TYPES, GUARDIAN_STARS, OPPONENT_NAMES
from core.card_graphics import CardGraphicsDatabase, bgr555_to_rgb
from core.card_list_icons import extract_card_list_icons
from core.cards import CardDatabase
from core.duel_rewards import reward_layout, set_reward_count
from core.fusions import FusionDatabase
from core.legacy_frame_patch import remove_legacy_frame_color_patch
from fm_editor import portraits
from fm_editor.disc import Disc
from fm_editor.memory_card import create_card
from fm_editor.save_data import CAMPAIGN_CHECKPOINTS, FREE_DUEL_UNLOCK_FLAG_BASE, SaveDataDocument

ATTRIBUTES = ["Light", "Dark", "Earth", "Water", "Fire", "Wind", "Magic", "Trap"]
FIELDS = "name atk def_ type_id attribute level gs1 gs2 star_cost password description".split()
EXE = "SLUS_014.11"
WA = "DATA/WA_MRG.MRG"
game = None
save = None


def png(im):
    if im is None:
        return ""
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def card_record(c):
    return {"id": c.card_id, **{k: getattr(c, k) for k in FIELDS}}


def metadata():
    return dict(types=CARD_TYPES, stars=GUARDIAN_STARS, attributes=ATTRIBUTES,
                names=CARD_NAMES, opponents=OPPONENT_NAMES,
                milestones={key: val["label"] for key, val in CAMPAIGN_CHECKPOINTS.items()})


class Game:
    def __init__(self, path):
        self.disc = Disc(path)
        self.exe = self.disc.extract_file(EXE)
        self.wa = self.disc.extract_file(WA)
        self.cards = CardDatabase()
        self.cards.load_from_exe_and_wa(self.exe, self.wa)
        self.original = copy.deepcopy(self.cards.cards)
        self.art = CardGraphicsDatabase()
        self.art.set_wa_data(self.wa)
        self.fusions = FusionDatabase()
        self.fusions.load_from_wa(self.wa)
        self.fusions_changed = False
        self.drop_edits = {}
        self.portrait_edits = {}

    def atlas(self):
        atlas = Image.new("RGB", (16 * 40, 46 * 32))
        for i in range(722):
            offset = i * 2048
            tile = Image.frombytes("P", (40, 32), self.wa[offset:offset + 1280])
            words = struct.unpack_from("<64H", self.wa, offset + 1280)
            tile.putpalette(bytes(channel for word in words for channel in bgr555_to_rgb(word)) * 4)
            atlas.paste(tile.convert("RGB"), (i % 16 * 40, i // 16 * 32))
        return png(atlas)

    def recipes(self):
        return [[a, b, r] for (a, b), r in self.fusions.fusions.items()]

    def snapshot(self):
        return dict(cards=[card_record(c) for c in self.cards.cards.values()], atlas=self.atlas(),
                    portraits=[png(portraits.read(self.wa, i + 1)) for i in range(len(OPPONENT_NAMES))],
                    icons={k: [png(i) for i in icons] for k, icons in extract_card_list_icons(self.wa).items()},
                    recipes=self.recipes(), reward=reward_layout(self.exe), layout=self.disc.detected)

    def drops(self, opponent, rank):
        if not 0 <= opponent < len(OPPONENT_NAMES) or not 0 <= rank < 3:
            raise ValueError("Choose a duelist and rank.")
        offset = 0xE9B000 + opponent * 0x1800 + (rank + 1) * 1460
        return self.drop_edits.get((opponent, rank), list(struct.unpack_from("<722H", self.wa, offset)))

    def recipe_edit(self, a_ids, b_ids, result):
        trial = FusionDatabase()
        trial.fusions = self.fusions.fusions.copy()
        pairs = {tuple(sorted((a, b))) for a in a_ids for b in b_ids}
        if not pairs:
            raise ValueError("Each material must match at least one card.")
        for pair in pairs:
            if result is None:
                trial.fusions.pop(pair, None)
            else:
                trial.fusions[pair] = result
        if trial.fusions == self.fusions.fusions:
            return self.recipes()
        if not trial.compact():
            raise ValueError("These recipes exceed the game's fusion table capacity. Narrow the materials.")
        self.fusions = trial
        self.fusions_changed = True
        return self.recipes()

    def export(self, count, progress):
        exe, wa = bytearray(self.exe), bytearray(self.wa)
        remove_legacy_frame_color_patch(exe)
        if any(vars(c) != vars(self.original[i]) for i, c in self.cards.cards.items()):
            self.cards.save_to_exe_and_wa(exe, wa)
            verified = CardDatabase()
            verified.load_from_exe_and_wa(exe, wa)
            for i, c in self.cards.cards.items():
                for field in FIELDS:
                    if getattr(c, field) != getattr(verified.cards[i], field):
                        raise ValueError(f"Card {i}: the game cannot encode the edited {field}.")
        self.art.apply_to_wa(wa, self.cards.cards, self.original)
        if self.fusions_changed:
            self.fusions.save_to_wa(wa)
        for (op, rank), weights in self.drop_edits.items():
            struct.pack_into("<722H", wa, 0xE9B000 + op * 0x1800 + (rank + 1) * 1460, *weights)
        for op, im in self.portrait_edits.items():
            portraits.write(wa, op + 1, im)
        kind, installed = reward_layout(self.exe)
        if count is not None or kind == "installed":
            set_reward_count(self.exe, exe, installed if count is None else count)
        return self.disc.export("export.bps", {EXE: exe, WA: wa}, progress, patch=True)


def save_state():
    return dict(player=save.player_name(), chips=save.starchips(), record=save.duel_record(),
                deck=save.deck(), trunk=[save.card_quantity(i) for i in range(1, 723)],
                milestones={k: save.campaign_checkpoint(k) for k in CAMPAIGN_CHECKPOINTS},
                unlocked=[save.campaign_flag(FREE_DUEL_UNLOCK_FLAG_BASE+i) for i in range(1, 39)])


def handle(op, args, progress=lambda p, text: None):
    global game, save
    if op == "metadata":
        return metadata()
    if op == "disc":
        candidate = Game(args["path"])
        state = candidate.snapshot()
        game = candidate
        return state
    if op == "save":
        save = SaveDataDocument.open(args["path"])
        return save_state()
    if op == "saveExport":
        doc = copy.deepcopy(save)
        if args["player"] != doc.player_name():
            doc.set_player_name(args["player"])
        doc.set_starchips(args["chips"])
        doc.set_duel_record(*args["record"])
        if args["deck"] != [cid for cid in doc.deck() if cid]:
            doc.set_deck(args["deck"] + [0] * (40-len(args["deck"])))
        for i, value in enumerate(args["trunk"], 1):
            doc.set_card_quantity(i, value)
        for key, enabled in args["milestones"].items():
            if enabled != save.campaign_checkpoint(key):
                doc.set_campaign_checkpoint(key, enabled)
        for i, enabled in enumerate(args["unlocked"], 1):
            doc.set_campaign_flag(FREE_DUEL_UNLOCK_FLAG_BASE+i, enabled)
        Path("export.save").write_bytes(doc.to_bytes())
        return
    if op == "newSave":
        Path("export.save").write_bytes(create_card(game.exe, args["deck"], args["player"], args["chips"]))
        return
    if op == "art":
        return png(game.art.get_card_art(args["id"]))
    if op in ("artEdit", "portraitEdit"):
        with Image.open(args["path"]) as source:
            source.thumbnail((512, 512))
            im = source.convert("RGB")
        if op == "artEdit":
            game.art.set_custom_art(args["id"], im)
            return png(game.art.get_card_art(args["id"]))
        game.portrait_edits[args["id"]] = im
        return png(im)
    if op == "card":
        data = args["card"]
        c = copy.copy(game.cards.cards[data["id"]])
        for key in FIELDS:
            setattr(c, key, data[key])
        if not c.name.strip() or len(c.name) > 36 or not re.fullmatch("[0-9a-fA-F]{8}", c.password):
            raise ValueError("Enter a name (1–36 characters) and an eight-digit hexadecimal password.")
        for key, high in (("type_id", 23), ("attribute", 7), ("level", 12), ("gs1", 10),
                          ("gs2", 10), ("star_cost", 999999), ("atk", 5110), ("def_", 5110)):
            if type(getattr(c, key)) is not int or not 0 <= getattr(c, key) <= high:
                raise ValueError(f"{key} must be a whole number between 0 and {high}.")
        if c.atk % 10 or c.def_ % 10:
            raise ValueError("ATK and DEF must be multiples of ten.")
        c.password = c.password.lower()
        game.cards.cards[c.card_id] = c
        return card_record(c)
    if op == "resetCards":
        game.cards.cards = copy.deepcopy(game.original)
        game.art = CardGraphicsDatabase()
        game.art.set_wa_data(game.wa)
        return [card_record(c) for c in game.cards.cards.values()]
    if op == "recipe":
        return game.recipe_edit(args["a"], args["b"], args["result"])
    if op == "resetRecipes":
        game.fusions = FusionDatabase()
        game.fusions.load_from_wa(game.wa)
        game.fusions_changed = False
        return game.recipes()
    if op == "drops":
        return game.drops(args["opponent"], args["rank"])
    if op == "setDrops":
        weights = args["weights"]
        if len(weights) != 722 or any(type(w) is not int or not 0 <= w <= 65535 for w in weights):
            raise ValueError("Invalid drop weights.")
        game.drop_edits[args["opponent"], args["rank"]] = weights
        return weights
    if op == "resetDrops":
        game.drop_edits.clear()
        game.portrait_edits.clear()
        return [png(portraits.read(game.wa, i + 1)) for i in range(len(OPPONENT_NAMES))]
    if op == "export":
        return game.export(args["count"], progress)
    raise ValueError("Unknown editor operation.")
