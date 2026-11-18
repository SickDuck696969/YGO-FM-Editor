"""A scrollable recipe sheet with an artwork cell for each card."""
import tkinter as tk
from tkinter import font, ttk
from PIL import Image, ImageTk


class RecipeSheet(ttk.Frame):
    def __init__(self, parent, cards, artwork, select, context):
        super().__init__(parent)
        self.cards, self.artwork = cards, artwork
        self.select, self.context = select, context
        self.rows = []
        self.selected = None
        self.photos = {}
        self.text_font = font.Font(self, family='Segoe UI', size=10, weight='bold')
        self.detail_font = font.Font(self, family='Segoe UI', size=9)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky='ew')
        for i, title in enumerate(('First material', 'Second material', 'Fusion result')):
            header.columnconfigure(i, weight=1, uniform='recipe')
            ttk.Label(header, text=title, style='SheetHeading.TLabel', padding=(12,5)).grid(row=0, column=i, sticky='ew')
        self.canvas = tk.Canvas(self, takefocus=True, highlightthickness=0, borderwidth=0)
        self.canvas.grid(row=1, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        scroll.grid(row=1, column=1, sticky='ns')
        self.canvas.configure(yscrollcommand=self._scrolled(scroll))
        self.canvas.bind('<Configure>', lambda _: self.draw())
        self.canvas.bind('<Button-1>', self.click)
        self.canvas.bind('<Button-3>', self.popup)
        self.canvas.bind('<Button-2>', self.popup)
        self.canvas.bind('<MouseWheel>', self.wheel)
        self.canvas.bind('<Button-4>', lambda _: self.canvas.yview_scroll(-1, 'units'))
        self.canvas.bind('<Button-5>', lambda _: self.canvas.yview_scroll(1, 'units'))
        for key in ('Up','Down','Prior','Next','Home','End'):
            self.canvas.bind('<'+key+'>', self.navigate)

    def _scrolled(self, scrollbar):
        def moved(first, last):
            scrollbar.set(first, last)
            self.draw()
        return moved

    height = 64

    def set_rows(self, rows):
        self.rows = rows
        self.selected = None
        self.photos.clear()
        self.canvas.yview_moveto(0)
        self.resize()

    def resize(self):
        self.canvas.configure(scrollregion=(0,0,1,len(self.rows)*self.height), yscrollincrement=self.height)
        self.draw()

    def wheel(self, event):
        if event.delta:
            self.canvas.yview_scroll(-1 if event.delta > 0 else 1, 'units')
        return 'break'

    def choose(self, index):
        self.selected = index
        self.draw()
        self.select()

    def click(self, event):
        index = int(self.canvas.canvasy(event.y)//self.height)
        if 0 <= index < len(self.rows):
            self.canvas.focus_set()
            self.choose(index)
            return True
        return False

    def popup(self, event):
        if self.click(event):
            self.context(event)

    def navigate(self, event):
        if not self.rows:
            return 'break'
        step = max(1, self.canvas.winfo_height()//self.height)
        current = self.selected if self.selected is not None else -1
        target = {'Home':0, 'End':len(self.rows)-1, 'Up':current-1,
                  'Down':current+1, 'Prior':current-step, 'Next':current+step}[event.keysym]
        index = max(0, min(target, len(self.rows)-1))
        top = self.canvas.canvasy(0)/self.height
        if index < top or index >= top+step:
            self.canvas.yview_moveto((index if index < top else index-step+1)/len(self.rows))
        self.choose(index)
        return 'break'

    def fit(self, name, width):
        if self.text_font.measure(name) <= width:
            return name
        while name and self.text_font.measure(name+'…') > width:
            name = name[:-1]
        return name+'…'

    def draw(self):
        if not hasattr(self, 'palette'):
            return
        p, c = self.palette, self.canvas
        c.delete('all')
        w, h = c.winfo_width(), self.height
        first = max(0, int(c.canvasy(0)//h))
        if not self.rows:
            c.create_text(16,24,anchor='w',text='No matching recipes',fill=p.text,font=self.detail_font)
        for i in range(first, min(len(self.rows), first+c.winfo_height()//h+2)):
            y = i*h
            selected = self.selected == i
            fg = p.on_accent if selected else p.text
            bg = p.accent if selected else (p.panel if i%2 else p.field)
            c.create_rectangle(0,y,w,y+h,fill=bg,outline='')
            for col, cid in enumerate(self.rows[i]):
                card = self.cards(cid)
                x = int(col*w/3)+12
                if cid not in self.photos:
                    art = self.artwork(cid)
                    self.photos[cid] = ImageTk.PhotoImage(art.resize((48,48),Image.Resampling.LANCZOS)) if art else None
                if self.photos[cid]:
                    c.create_image(x,y+8,image=self.photos[cid],anchor='nw')
                x += 58
                end = int((col+1)*w/3)
                title = self.fit(card.name, end-x-24)
                c.create_text(x,y+23,text=title,fill=fg,anchor='w',font=self.text_font)
                c.create_text(x,y+43,text=f'{card.atk} ATK   {card.def_} DEF',fill=fg,anchor='w',font=self.detail_font)
                if col < 2:
                    c.create_text(end-8,y+h//2,text='+' if col==0 else '→',fill=fg,font=self.text_font)

    def set_palette(self, palette):
        self.palette = palette
        self.canvas.configure(bg=palette.field)
        self.draw()
