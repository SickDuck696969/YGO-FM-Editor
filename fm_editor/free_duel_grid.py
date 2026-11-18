import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from core.card_data import OPPONENT_NAMES
from .appearance import THEMES
from .save_data import FREE_DUEL_UNLOCK_FLAG_BASE


class FreeDuelGrid(ttk.Frame):
    SIDE = 96
    HEIGHT = 130

    def __init__(self, parent, photos):
        super().__init__(parent, padding=6)
        self.palette = next(iter(THEMES.values()))
        self.values = {}
        self.images = {}
        self.loaded = False
        self.columns = 1
        self.focused = 1
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        bar = ttk.Frame(self)
        bar.grid(row=0, column=0, sticky='ew', pady=(0, 6))
        self.bulk_buttons = []
        for label, value in [('Unlock all', True), ('Lock all', False)]:
            button = ttk.Button(bar, text=label, command=lambda v=value: self.select_all(v))
            button.pack(side='left', padx=3)
            button.state(['disabled'])
            self.bulk_buttons.append(button)
        self.count = ttk.Label(bar)
        self.count.pack(side='left', padx=8)
        self.canvas = tk.Canvas(self, background='#182230', highlightthickness=0, takefocus=True)
        self.canvas.grid(row=1, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        scroll.grid(row=1, column=1, sticky='ns')
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.bind('<Configure>', self.resize)
        self.canvas.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(-int(e.delta/120), 'units'))
        self.canvas.bind('<Button-1>', self.click)
        for key in ('Left', 'Right', 'Up', 'Down', 'space', 'Return'):
            self.canvas.bind('<'+key+'>', self.key)
        self.canvas.bind('<FocusIn>', lambda _: self.draw())
        self.canvas.bind('<FocusOut>', lambda _: self.draw())
        for i in range(1, 39):
            var = tk.BooleanVar(self)
            self.values[i] = var
            var.trace_add('write', lambda *_, n=i: self.paint_status(n))
        self.refresh_images(photos)

    def set_palette(self, palette):
        self.palette = palette
        self.canvas.configure(background=palette.field)
        self.draw()

    def refresh_images(self, photos):
        self.images = {i: ImageTk.PhotoImage(ImageTk.getimage(photo).resize(
            (self.SIDE, self.SIDE), Image.Resampling.NEAREST)) for i, photo in photos.items()}
        self.draw()

    def resize(self, event):
        cols = max(1, min(39, event.width // self.SIDE))
        if cols != self.columns:
            self.columns = cols
            self.draw()

    def draw(self):
        c = self.canvas
        c.delete('all')
        for i, name in enumerate(OPPONENT_NAMES, 1):
            row, col = divmod(i-1, self.columns)
            x, y = col*self.SIDE, row*self.HEIGHT
            if i in self.images:
                c.create_image(x, y, anchor='nw', image=self.images[i])
            else:
                c.create_text(x+48, y+48, text=' '.join(w[0] for w in name.split()), fill=self.palette.text)
            c.create_rectangle(x, y+96, x+95, y+129, width=0, tags=f'bar{i}')
            c.create_text(x+48, y+113, text=name, tags=f'name{i}', width=93, justify='center', fill='white',
                          font=('Segoe UI', 8))
            c.create_rectangle(x+1, y+1, x+24, y+21, tags=f'mark{i}', width=0)
            c.create_text(x+12, y+11, tags=f'check{i}', fill='white', font=('Segoe UI', 10, 'bold'))
            self.paint_status(i, update_count=False)
            if i == self.focused and self.focus_get() == c:
                c.create_rectangle(x+1, y+1, x+94, y+128, outline=self.palette.text, width=2)
        c.configure(scrollregion=(0, 0, self.columns*self.SIDE,
                                  ((39+self.columns-1)//self.columns)*self.HEIGHT))
        self.update_count()

    def paint_status(self, i, update_count=True):
        unlocked = i == 39 or self.values[i].get()
        color = self.palette.accent if unlocked else self.palette.surface
        fg = self.palette.on_accent if unlocked else self.palette.text
        self.canvas.itemconfigure(f'name{i}', fill=fg)
        self.canvas.itemconfigure(f'bar{i}', fill=color)
        self.canvas.itemconfigure(f'mark{i}', fill=color)
        self.canvas.itemconfigure(f'check{i}', text='✓' if unlocked else '–', fill=fg)
        if update_count:
            self.update_count()

    def update_count(self):
        text = f'{sum(v.get() for v in self.values.values())} / 38 unlocked · Duel Master K always available'
        if not self.images:
            text += ' · Open a ROM for portraits'
        self.count.configure(text=text)

    def toggle(self):
        if self.loaded and self.focused in self.values:
            var = self.values[self.focused]
            var.set(not var.get())

    def click(self, event):
        row = int(self.canvas.canvasy(event.y)) // self.HEIGHT
        col = event.x // self.SIDE
        opponent = row*self.columns + col + 1
        if col < self.columns and 1 <= opponent <= 39:
            self.canvas.focus_set()
            self.focused = opponent
            self.toggle()
            self.draw()

    def key(self, event):
        if event.keysym in ('Return', 'space'):
            self.toggle()
        else:
            step = {'Left': -1, 'Right': 1, 'Up': -self.columns, 'Down': self.columns}
            self.focused = min(39, max(1, self.focused + step[event.keysym]))
            top = ((self.focused-1)//self.columns)*self.HEIGHT
            visible = self.canvas.canvasy(0)
            height = self.canvas.winfo_height()
            if top < visible or top+self.HEIGHT > visible+height:
                total = ((39+self.columns-1)//self.columns)*self.HEIGHT
                self.canvas.yview_moveto((top if top < visible else top+self.HEIGHT-height)/total)
            self.draw()
        return 'break'

    def select_all(self, unlocked):
        for var in self.values.values():
            var.set(unlocked)

    def load(self, doc):
        self.loaded = True
        for opponent, var in self.values.items():
            var.set(doc.campaign_flag(FREE_DUEL_UNLOCK_FLAG_BASE + opponent))
        for button in self.bulk_buttons:
            button.state(['!disabled'])

    def apply(self, doc):
        for opponent, var in self.values.items():
            doc.set_campaign_flag(FREE_DUEL_UNLOCK_FLAG_BASE + opponent, var.get())
