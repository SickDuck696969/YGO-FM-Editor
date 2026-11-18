from typing import NamedTuple
from tkinter import ttk


class Palette(NamedTuple):
    base: str
    panel: str
    surface: str
    field: str
    text: str
    accent: str
    on_accent: str


THEMES = {
    'Mirrorjade the Iceblade Dragon': Palette('#14213a','#203453','#314767','#14263e','#edf7ff','#8ce2f5','#14213a'),
    'Tearlaments Rulkallos': Palette('#102b33','#163a44','#24505b','#102f39','#ebfaf7','#83e3c9','#102b33'),
    'Baronne de Fleur': Palette('#ede5e1','#fff9f4','#edddd9','#fffdf9','#392733','#843959','#ffffff'),
    'Kashtira Arise-Heart': Palette('#271421','#391e30','#593347','#2a1724','#fff0ed','#ff927e','#291421'),
    'Borreload Savage Dragon': Palette('#191a28','#292a3d','#38394e','#1c1e2d','#f4f0ff','#c0a3ff','#241d36'),
    'Eldlich the Golden Lord': Palette('#201d16','#322c20','#484030','#272218','#fff4db','#edc366','#291e0a'),
    'Cyber Dragon Infinity': Palette('#191c20','#282e36','#393f47','#1d2127','#fff6ec','#ff9d55','#28190d'),
    'Thunder Dragon Colossus': Palette('#242312','#35351f','#48492c','#282918','#fffbdd','#e7ec48','#272914'),
    'El Shaddoll Construct': Palette('#ece7f1','#faf6ff','#e5dced','#f4eff9','#382c42','#633e83','#fffaff'),
    'Dingirsu, the Orcust of the Evening Star': Palette('#101f2b','#1e303b','#314552','#17262f','#ebf5f6','#e6ba85','#271d10'),
    'Invoked Mechaba': Palette('#dfe6e4','#f6faf7','#d5e1dc','#ffffff','#22382e','#326556','#ffffff'),
    'ABC-Dragon Buster': Palette('#152419','#23362a','#374d3c','#1b2c20','#f2faec','#a9de76','#192611'),
}


def apply_theme(root, p):
    style = ttk.Style(root)
    root.configure(bg=p.base)
    style.configure('.', background=p.panel, foreground=p.text, fieldbackground=p.field,
                    bordercolor=p.surface, lightcolor=p.surface, darkcolor=p.surface,
                    focuscolor=p.accent, troughcolor=p.field, font=('Segoe UI', 10))
    style.configure('TFrame', background=p.panel)
    style.configure('TLabel', background=p.panel, foreground=p.text)
    style.configure('TLabelframe', background=p.panel, bordercolor=p.surface, relief='solid')
    style.configure('TLabelframe.Label', background=p.panel, foreground=p.text, font=('Segoe UI', 10, 'bold'))
    style.configure('TButton', background=p.surface, foreground=p.text, padding=(7,4), relief='flat')
    style.map('TButton', background=[('active',p.accent)], foreground=[('active',p.on_accent)])
    for widget in ('TEntry','TCombobox','TSpinbox'):
        style.configure(widget, fieldbackground=p.field, foreground=p.text, arrowcolor=p.text,
                        background=p.surface, insertcolor=p.text)
        style.map(widget, fieldbackground=[('readonly',p.field),('disabled',p.surface)],
                  foreground=[('readonly',p.text),('disabled',p.text)],
                  selectbackground=[('readonly',p.field)], selectforeground=[('readonly',p.text)])
    style.configure('TCheckbutton', indicatorbackground=p.field, indicatorforeground=p.text)
    style.map('TCheckbutton', background=[('active',p.surface)], foreground=[('active',p.text)],
              indicatorbackground=[('selected',p.accent)], indicatorforeground=[('selected',p.on_accent)])
    style.configure('TRadiobutton',background=p.panel,foreground=p.text,indicatorbackground=p.field)
    style.map('TRadiobutton',background=[('active',p.surface)],foreground=[('active',p.text)],
              indicatorbackground=[('selected',p.accent)],indicatorforeground=[('selected',p.on_accent)])
    style.configure('Treeview', background=p.field, foreground=p.text, fieldbackground=p.field, rowheight=50)
    style.map('Treeview', background=[('selected',p.accent)], foreground=[('selected',p.on_accent)])
    style.configure('Treeview.Heading', background=p.surface, foreground=p.text)
    style.map('Treeview.Heading', background=[('active',p.surface)])
    style.configure('TNotebook', background=p.base)
    style.configure('TNotebook.Tab', background=p.surface, foreground=p.text, padding=(10,5))
    style.map('TNotebook.Tab', background=[('selected',p.accent)], foreground=[('selected',p.on_accent)])
    style.configure('Chrome.TFrame', background=p.base)
    style.configure('Chrome.TLabel', background=p.base, foreground=p.text)
    style.configure('Title.Chrome.TLabel', font=('Georgia', 22, 'bold'))
    style.configure('Status.Chrome.TLabel', font=('Segoe UI', 9))
    style.configure('Tab.TButton', background=p.base, foreground=p.text, relief='flat', padding=(10,7))
    style.configure('Active.Tab.TButton', background=p.accent, foreground=p.on_accent, font=('Segoe UI',10,'bold'))
    style.configure('Primary.TButton', background=p.accent, foreground=p.on_accent, padding=(12,6))
    style.configure('SheetHeading.TLabel', background=p.surface, foreground=p.text, font=('Segoe UI',10,'bold'))
    # A combobox keeps its Tk listbox after the first time it is opened.
    # Update existing lists as well as the defaults for future dialogs.
    stack = [root]
    while stack:
        widget = stack.pop()
        stack.extend(widget.winfo_children())
        if isinstance(widget, ttk.Combobox):
            popup_list = f'{widget}.popdown.f.l'
            if root.tk.call('winfo','exists',popup_list):
                root.tk.call(popup_list,'configure','-background',p.field,'-foreground',p.text,
                             '-selectbackground',p.accent,'-selectforeground',p.on_accent)
    for option, value in [('background',p.field),('foreground',p.text),
                          ('selectBackground',p.accent),('selectForeground',p.on_accent)]:
        root.option_add('*TCombobox*Listbox.'+option,value)
