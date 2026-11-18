"""Shared multi-select filter for card browsers and fusion materials."""
from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk

from core.card_data import CARD_TYPES

ATTRIBUTES = ['Light', 'Dark', 'Earth', 'Water', 'Fire', 'Wind', 'Magic', 'Trap']
GROUPS = (('Type', CARD_TYPES), ('Attribute', ATTRIBUTES), ('Level', tuple(map(str, range(13)))))


@dataclass(frozen=True)
class Criteria:
    types: frozenset = frozenset()
    attributes: frozenset = frozenset()
    levels: frozenset = frozenset()
    atk_min: int = 0
    atk_max: int = 5110
    def_min: int = 0
    def_max: int = 5110

    def matches(self, card):
        if card is None:
            return self == Criteria()
        return ((not self.types or card.type_id in self.types)
                and (not self.attributes or card.attribute in self.attributes)
                and (not self.levels or card.level in self.levels)
                and self.atk_min <= card.atk <= self.atk_max
                and self.def_min <= card.def_ <= self.def_max)

    def labels(self):
        parts = []
        for (name, options), selected in zip(GROUPS, (self.types, self.attributes, self.levels)):
            if selected:
                values = ', '.join(options[i] for i in sorted(selected))
                parts.append(f'{name}: {values}')
        for name, low, high in [('ATK', self.atk_min, self.atk_max), ('DEF', self.def_min, self.def_max)]:
            if (low, high) != (0, 5110):
                parts.append(f'{name} {low}–{high}')
        return parts


class FilterButton(ttk.Button):
    def __init__(self, parent, cards, on_apply, label='Filters'):
        super().__init__(parent, text=label, command=self.open)
        self.label = label
        self.criteria = Criteria()
        self.cards = cards
        self.on_apply = on_apply

    def reset(self):
        self.criteria = Criteria()
        self.configure(text=self.label)

    def open(self):
        win = tk.Toplevel(self)
        win.title(self.label)
        win.transient(self.winfo_toplevel())
        win.grab_set()
        pane = ttk.Frame(win, padding=14)
        pane.pack(fill='both', expand=True)
        ttk.Label(pane, text='Choose any values within a group. Cards must match every active group.').pack(anchor='w')
        tabs = ttk.Notebook(pane)
        tabs.pack(fill='both', expand=True, pady=8)
        groups = []
        for (name, options), active in zip(GROUPS, (self.criteria.types, self.criteria.attributes, self.criteria.levels)):
            tab = ttk.Frame(tabs, padding=8)
            tabs.add(tab, text=name)
            group = []
            for i, option in enumerate(options):
                value = tk.BooleanVar(win, value=i in active)
                ttk.Checkbutton(tab, text=option, variable=value).grid(row=i//4, column=i%4, sticky='w', padx=5, pady=4)
                group.append(value)
            groups.append(group)
        stats = ttk.Frame(tabs, padding=12)
        tabs.add(stats, text='ATK / DEF')
        ranges = []
        for col, title in enumerate(('Stat', 'Minimum', 'Maximum')):
            ttk.Label(stats, text=title).grid(row=0, column=col, sticky='w')
        for row, (title, low, high) in enumerate((('ATK', self.criteria.atk_min, self.criteria.atk_max),
                                                 ('DEF', self.criteria.def_min, self.criteria.def_max)), 1):
            ttk.Label(stats, text=title).grid(row=row, column=0, sticky='w')
            for col, initial in enumerate((low, high), 1):
                var = tk.StringVar(win, value=str(initial))
                ttk.Entry(stats, width=10, textvariable=var).grid(row=row, column=col, padx=4, pady=4)
                ranges.append(var)
        footer = ttk.Frame(pane)
        footer.pack(fill='x')
        status = ttk.Label(footer)
        status.pack(side='left')

        def read():
            numbers = [int(v.get().strip() or default) for v, default in zip(ranges, (0, 5110, 0, 5110))]
            if not (0 <= numbers[0] <= numbers[1] <= 5110 and 0 <= numbers[2] <= numbers[3] <= 5110):
                raise ValueError
            return Criteria(*(frozenset(i for i, var in enumerate(group) if var.get()) for group in groups), *numbers)

        def preview(*_):
            try:
                criteria = read()
            except ValueError:
                status.configure(text='Use whole numbers from 0 to 5110, minimum first.')
                apply_button.state(['disabled'])
                return
            status.configure(text=f'{sum(criteria.matches(c) for c in self.cards())} matching cards')
            apply_button.state(['!disabled'])

        def apply():
            self.criteria = read()
            n = len(self.criteria.labels())
            self.configure(text=f'{self.label} ({n})' if n else self.label)
            win.destroy()
            self.on_apply()

        def clear():
            for group in groups:
                for var in group:
                    var.set(False)
            for var, default in zip(ranges, (0, 5110, 0, 5110)):
                var.set(str(default))

        apply_button = ttk.Button(footer, text='Apply', command=apply)
        apply_button.pack(side='right')
        ttk.Button(footer, text='Cancel', command=win.destroy).pack(side='right', padx=4)
        ttk.Button(footer, text='Clear', command=clear).pack(side='right')
        for group in [*groups, ranges]:
            for var in group:
                var.trace_add('write', preview)
        win.bind('<Escape>', lambda _: win.destroy())
        preview()
