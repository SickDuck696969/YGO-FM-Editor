import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import struct, threading, queue, string, copy, traceback, random, hashlib, math
from PIL import Image, ImageTk, ImageDraw
from core.cards import CardDatabase, SLUS_STATS_OFFSET
from core.card_graphics import CardGraphicsDatabase
from core.fusions import FusionDatabase
from core.card_data import OPPONENT_NAMES, CARD_TYPES, GUARDIAN_STARS, CARD_NAMES
from core.legacy_frame_patch import remove_legacy_frame_color_patch
from core.card_list_icons import extract_card_list_icons
from .disc import Disc
from .memory_card import create_card
from .save_data import SaveDataDocument, SaveDataError, CAMPAIGN_CHECKPOINTS
from .free_duel_grid import FreeDuelGrid
from core.duel_rewards import reward_layout, set_reward_count
from . import portraits
from .appearance import THEMES, apply_theme
from .recipe_sheet import RecipeSheet
from .card_filters import ATTRIBUTES, FilterButton

CARD_TYPE_FRAME_COLORS={20:'#2b9a72',21:'#bb4b83',22:'#557db5',23:'#2b9a72'}
DUELISTS=OPPONENT_NAMES
OUTPUT_BASENAME='Yu-Gi-Oh! - Forbidden Memories'
class App(tk.Tk):
 def __init__(self):
  super().__init__();self.title('Forbidden Memories Workshop');self.geometry('1440x900');self.minsize(1180,780);self.configure(bg='#111827');self.disc=None;self.exe=None;self.wa=None;self.card_list_icons={};self.dirty=False;self.cards=CardDatabase();self.art=CardGraphicsDatabase();self.fusions=FusionDatabase();self.current=1;self.v={};self.events=queue.Queue();self.after(100,self.poll_events);self.protocol('WM_DELETE_WINDOW',self.close_app)
  ttk.Style(self).theme_use('clam')
  self.color_scheme = tk.StringVar(value=next(iter(THEMES)))
  self.apply_color_scheme()
  shell = ttk.Frame(self, style='Chrome.TFrame', padding=(14, 0))
  shell.pack(fill='both', expand=True)
  shell.columnconfigure(0, weight=1)
  shell.rowconfigure(2, weight=1)
  mast = ttk.Frame(shell, style='Chrome.TFrame', padding=(4, 8))
  mast.grid(row=0, column=0, sticky='ew')
  self.banner_art = ttk.Label(mast, style='Chrome.TLabel')
  self.banner_art.pack(side='left')
  ttk.Label(mast, text='Forbidden Memories', style='Title.Chrome.TLabel').pack(side='left', padx=(8,16))
  self.open_btn = ttk.Button(mast, text='Open ROM image…', style='Primary.TButton', command=self.open)
  self.open_btn.pack(side='right', padx=(12,0))
  theme = ttk.Combobox(mast, textvariable=self.color_scheme, values=list(THEMES), state='readonly', width=39)
  theme.pack(side='right')
  theme.bind('<<ComboboxSelected>>', lambda _: self.apply_color_scheme())
  ttk.Label(mast, text='Theme', style='Chrome.TLabel').pack(side='right', padx=6)
  nav = ttk.Frame(shell, style='Chrome.TFrame')
  nav.grid(row=1, column=0, sticky='ew')
  self.page_frames, self.page_nav_buttons = {}, {}
  sections = [('cards','Card Studio'),('fusion','Fusion Lab'),('drops','Duelist Drops'),
              ('starter','Starter Deck & Save'),('savedata','Save Data Editor'),('export','Rewards & Export')]
  for col, (key,title) in enumerate(sections):
   nav.columnconfigure(col, weight=1, uniform='tools')
   button = ttk.Button(nav, text=title, style='Tab.TButton', command=lambda k=key:self.show_page(k))
   button.grid(row=0, column=col, sticky='ew', padx=(0,2))
   self.page_nav_buttons[key] = button
  self.nb = ttk.Frame(shell)
  self.nb.grid(row=2,column=0,sticky='nsew')
  self.nb.columnconfigure(0,weight=1)
  self.nb.rowconfigure(0,weight=1)
  self.status = ttk.Label(shell, text='Open a USA Forbidden Memories image', style='Status.Chrome.TLabel', padding=(6,4))
  self.status.grid(row=3,column=0,sticky='ew')
  self.cards_page=ttk.Frame(self.nb,padding=12);self.cards_page.grid(row=0,column=0,sticky='nsew');self.page_frames['cards']=self.cards_page;self.card_ui()
  self.fusion_page=ttk.Frame(self.nb,padding=12);self.fusion_page.grid(row=0,column=0,sticky='nsew');self.page_frames['fusion']=self.fusion_page;self.fusion_ui()
  self.drop_page=ttk.Frame(self.nb,padding=12);self.drop_page.grid(row=0,column=0,sticky='nsew');self.page_frames['drops']=self.drop_page;self.drop_ui()
  self.save_page=ttk.Frame(self.nb,padding=12);self.save_page.grid(row=0,column=0,sticky='nsew');self.page_frames['starter']=self.save_page;self.save_ui()
  self.savedata_page=ttk.Frame(self.nb,padding=12);self.savedata_page.grid(row=0,column=0,sticky='nsew');self.page_frames['savedata']=self.savedata_page;self.savedata_ui()
  self.build_page=ttk.Frame(self.nb,padding=22);self.build_page.grid(row=0,column=0,sticky='nsew');self.page_frames['export']=self.build_page;self.build_ui();self.stabilize_list_sizes();self.apply_color_scheme();self.show_page('cards')
 def show_page(self,key):
  page=self.page_frames.get(key)
  if page is None:return
  if key=="fusion":self.load_fusions()
  page.tkraise()
  for name,button in self.page_nav_buttons.items():
   button.configure(style='Active.Tab.TButton' if name==key else 'Tab.TButton')
 def apply_color_scheme(self):
  palette = THEMES[self.color_scheme.get()]
  apply_theme(self, palette)
  if hasattr(self, 'desc'):
   self.desc.configure(bg=palette.field, fg=palette.text, insertbackground=palette.text,
                       selectbackground=palette.accent, selectforeground=palette.on_accent)
  if hasattr(self, 'ft'):
   self.ft.set_palette(palette)
  if hasattr(self, 'free_duel_grid'):
   self.free_duel_grid.set_palette(palette)
 def refresh_banner_art(self):
  images = [self.art.get_card_art(i) for i in (1,35,62)]
  if not all(images):return
  strip = Image.new('RGB', (88,42))
  for i, art in enumerate(images):
   art = art.convert('RGB')
   side = min(art.size)
   x, y = (art.width-side)//2, (art.height-side)//2
   strip.paste(art.crop((x,y,x+side,y+side)).resize((42,42),Image.Resampling.LANCZOS),(i*23,0))
  self.banner_photo = ImageTk.PhotoImage(strip)
  self.banner_art.configure(image=self.banner_photo)
 def stabilize_list_sizes(self):
  # ttk recomputes Treeview's requested width from its stretched columns
  # after style changes. Give each grid cell its own geometry request so a
  # palette change cannot feed the displayed width back into the layout.
  pending = [self.nb]
  while pending:
   widget = pending.pop()
   pending.extend(widget.winfo_children())
   if isinstance(widget, ttk.Treeview) and widget.winfo_manager() == 'grid':
    cell = widget.grid_info()
    widget.grid_forget()
    viewport = ttk.Frame(widget.master, width=widget.winfo_reqwidth(), height=widget.winfo_reqheight())
    viewport.grid(**cell)
    widget.place(in_=viewport, x=0, y=0, relwidth=1, relheight=1)
    widget.lift(viewport)
 def filter_button(self, parent, refresh, label="Filters"):
  return FilterButton(parent, lambda: self.cards.cards.values(), refresh, label)
 def card_ui(self):
  p=self.cards_page;p.columnconfigure(0,weight=4,minsize=360);p.columnconfigure(1,weight=6,minsize=600);p.rowconfigure(1,weight=1);self.query=tk.StringVar();self.card_sort=tk.StringVar(value='Name');tools=ttk.Frame(p);tools.grid(row=0,column=0,sticky='ew');tools.columnconfigure(0,weight=1);q=ttk.Entry(tools,textvariable=self.query);q.grid(row=0,column=0,sticky='ew');q.bind('<KeyRelease>',lambda e:self.fill());self.card_filter=self.filter_button(tools,self.fill);self.card_filter.grid(row=0,column=1,padx=4);ttk.Combobox(tools,textvariable=self.card_sort,values=['Name','Card ID','ATK','DEF','Level'],state='readonly',width=10).grid(row=0,column=2,padx=4);self.card_sort.trace_add('write',lambda *_:self.fill());ttk.Button(tools,text='Reset filters',command=self.reset_card_filters).grid(row=0,column=3)
  card_list=ttk.Frame(p);card_list.grid(row=1,column=0,sticky='nsew',pady=8);card_list.columnconfigure(0,weight=1);card_list.rowconfigure(0,weight=1);self.tree=ttk.Treeview(card_list,show='tree');self.tree.heading('#0',text='CARD · TYPE · ATTRIBUTE · GUARDIAN · LEVEL · ATK / DEF');self.tree.column('#0',width=360);self.tree.grid(row=0,column=0,sticky='nsew');card_scroll=ttk.Scrollbar(card_list,orient='vertical',command=self.tree.yview);card_scroll.grid(row=0,column=1,sticky='ns');self.tree.configure(yscrollcommand=card_scroll.set);self.tree.bind('<<TreeviewSelect>>',self.select);self.tree.bind('<Button-3>',self.card_context_menu);self.tree.bind('<Button-2>',self.card_context_menu)
  ttk.Label(p,text='Game icons: type · attribute · guardian stars 1 and 2 · level star',font=('Segoe UI',9)).grid(row=2,column=0,sticky='w')
  editor=ttk.Frame(p);editor.grid(row=0,column=1,rowspan=2,sticky='nsew',padx=(14,0));editor.columnconfigure(0,weight=0,minsize=280);editor.columnconfigure(1,weight=1,minsize=300);editor.rowconfigure(0,weight=1)
  preview=ttk.LabelFrame(editor,text='CARD PREVIEW',padding=10);preview.grid(row=0,column=0,sticky='n',padx=(0,14),pady=4);self.pic=ttk.Label(preview,text='Open a ROM to view a card',anchor='center');self.pic.pack(pady=(0,8));ttk.Button(preview,text='Change artwork…',command=self.art_import).pack(fill='x',pady=3);ttk.Button(preview,text='Reset selected card',command=self.reset_card).pack(fill='x',pady=3)
  fields = ttk.Frame(editor, padding=(4,4))
  fields.grid(row=0,column=1,sticky='nsew')
  fields.columnconfigure(0,weight=1)
  ttk.Label(fields,text='Card name').grid(row=0,column=0,sticky='w')
  self.v['name'] = tk.StringVar()
  ttk.Entry(fields,textvariable=self.v['name'],font=('Segoe UI',13,'bold')).grid(row=1,column=0,sticky='ew',pady=(2,12))
  tabs = ttk.Notebook(fields)
  tabs.grid(row=2,column=0,sticky='ew')
  combat = ttk.Frame(tabs,padding=10)
  detail = ttk.Frame(tabs,padding=10)
  tabs.add(combat,text='Battle data')
  tabs.add(detail,text='Card text & shop')
  for group in (combat,detail):
   for col in range(2):group.columnconfigure(col,weight=1,uniform='field')
  for index,(key,label,choices) in enumerate((
      ('atk','ATK',None), ('def_','DEF',None), ('type_id','Type',CARD_TYPES),
      ('attribute','Attribute',ATTRIBUTES), ('gs1','Guardian star 1',GUARDIAN_STARS),
      ('gs2','Guardian star 2',GUARDIAN_STARS), ('level','Level',None),
      ('password','Password',None), ('star_cost','Starchip cost',None))):
   group = combat if index<7 else detail
   row,col = divmod(index if index<7 else index-7,2)
   var = self.v[key] = tk.StringVar()
   ttk.Label(group,text=label).grid(row=row*2,column=col,sticky='w',padx=3)
   if choices:
    widget=ttk.Combobox(group,textvariable=var,values=choices,state='readonly',width=12)
   elif key=='level':
    widget=ttk.Spinbox(group,textvariable=var,from_=0,to=12,width=5)
   else:
    widget=ttk.Entry(group,textvariable=var,width=12)
   widget.grid(row=row*2+1,column=col,sticky='ew',padx=3,pady=(2,9))
  ttk.Label(detail,text='Description').grid(row=2,column=0,sticky='w')
  self.desc = tk.Text(detail,height=7,width=20,wrap='word',font=('Segoe UI',10),relief='flat')
  self.desc.grid(row=3,column=0,columnspan=2,sticky='ew',pady=4)
  actions = ttk.Frame(fields)
  actions.grid(row=3,column=0,sticky='ew',pady=10)
  ttk.Button(actions,text='Apply card changes',command=self.apply_card,style='Primary.TButton').pack(side='left')
  ttk.Button(actions,text='Reset all card edits',command=self.reset_all_cards).pack(side='right')
 def fill(self):
  selected=self.tree.selection()[0] if self.tree.selection() else None;self.tree.delete(*self.tree.get_children());q=self.query.get().lower()
  entries=list(self.cards.cards.items())
  entries=[(i,c) for i,c in entries if self.card_filter.criteria.matches(c)]
  if self.card_sort.get()=='Card ID':entries.sort(key=lambda x:x[0])
  elif self.card_sort.get()=='ATK':entries.sort(key=lambda x:(x[1].atk,x[1].name))
  elif self.card_sort.get()=='DEF':entries.sort(key=lambda x:(x[1].def_,x[1].name))
  elif self.card_sort.get()=='Level':entries.sort(key=lambda x:(getattr(x[1],'level',0),x[1].name))
  else:entries.sort(key=lambda x:x[1].name.lower())
  for i,c in entries:
   if not q or q in c.name.lower() or q in str(i):self.tree.insert('','end',iid=str(i),text=f'{c.name}   ·   {c.atk} / {c.def_}',image=self.mini_photo(i))
  if selected and self.tree.exists(selected):self.tree.selection_set(selected);self.tree.focus(selected)
 def reset_card_filters(self):
  self.query.set('');self.card_filter.reset();self.card_sort.set('Name');self.fill()
 def card_context_menu(self,event):
  row=self.tree.identify_row(event.y)
  if not row:return
  self.tree.selection_set(row);self.tree.focus(row);self.select();menu=tk.Menu(self,tearoff=False);menu.add_command(label='Change artwork…',command=self.art_import);menu.add_command(label='Reset this card',command=self.reset_card);menu.add_separator()
  cid=int(row)
  for slot,label in enumerate(('Use as Fusion Material 1','Use as Fusion Material 2','Use as Fusion Result')):menu.add_command(label=label,command=lambda n=slot,card_id=cid:self.assign_fusion_card(n,card_id))
  menu.add_separator()
  for scope,label in (('Material','Find recipes using this card'),('Result','Find recipes making this card')):
   menu.add_command(label=label,command=lambda where=scope:self.find_card_recipes(cid,where))
  menu.tk_popup(event.x_root,event.y_root)
 def find_card_recipes(self, cid, scope):
  self.reset_recipe_search()
  self.fusion_scope.set(scope)
  self.fusion_query.set(f'#{cid}')
  self.show_page('fusion')
 def reset_card(self):
  if not hasattr(self,'original_cards') or self.current not in self.original_cards:return
  self.cards.cards[self.current]=copy.deepcopy(self.original_cards[self.current]);self.art.clear_custom_art(self.current);self.mini_photos.pop(self.current,None);self.dirty=True;self.fill();self.fill_starter_cards();self.show_card_preview(self.current);
  if self.tree.exists(str(self.current)):self.tree.selection_set(str(self.current));self.select()
  self.set_card_picker_values();self.load_fusions();self.refresh_deck_view();self.load_drops()
 def reset_all_cards(self):
  if not hasattr(self,'original_cards') or not self.original_cards:return messagebox.showinfo('Card Studio','Open a ROM before resetting card edits.')
  self.cards.cards=copy.deepcopy(self.original_cards);self.art._custom_artworks.clear();self.art._cached_images.clear();self.mini_photos.clear();self.dirty=True;self.fill();self.fill_starter_cards();self.set_card_picker_values();self.load_fusions();self.refresh_deck_view();self.load_drops()
  target=str(self.current) if self.tree.exists(str(self.current)) else (self.tree.get_children('')[0] if self.tree.get_children('') else None)
  if target:self.tree.selection_set(target);self.tree.focus(target);self.tree.see(target);self.select()
  self.status.configure(text='All card data and artwork edits reset to the loaded ROM.')
 def select(self,_=None):
  if not self.tree.selection():return
  self.current=int(self.tree.selection()[0]);c=self.cards.get(self.current)
  for k in ('name','atk','def_','password','star_cost'):self.v[k].set(str(getattr(c,k)))
  self.v['type_id'].set(CARD_TYPES[c.type_id] if 0<=c.type_id<len(CARD_TYPES) else CARD_TYPES[0]);self.v['gs1'].set(GUARDIAN_STARS[c.gs1] if 0<=c.gs1<len(GUARDIAN_STARS) else GUARDIAN_STARS[0]);self.v['gs2'].set(GUARDIAN_STARS[c.gs2] if 0<=c.gs2<len(GUARDIAN_STARS) else GUARDIAN_STARS[0]);self.v['level'].set(str(getattr(c,'level',0)));self.v['attribute'].set(ATTRIBUTES[c.attribute] if 0<=c.attribute<len(ATTRIBUTES) else ATTRIBUTES[0]);self.desc.delete('1.0','end');self.desc.insert('1.0',c.description);im=self.art.get_card_art(self.current)
  self.show_card_preview(self.current)
 def show_card_preview(self,cid):
  c=self.cards.get(cid);im=self.art.get_card_art(cid) if c else None
  if c and im:self.photo=ImageTk.PhotoImage(self.render_card_preview(c,im));self.pic.configure(image=self.photo,text='')
  else:self.pic.configure(image='',text='Artwork unavailable' if c else 'Select a card')
 def render_card_preview(self,card,art):
  edge=CARD_TYPE_FRAME_COLORS.get(card.type_id,'#c9a963');img=Image.new('RGB',(260,360),edge);d=ImageDraw.Draw(img);d.rectangle((7,7,252,353),outline='#211b18',width=4);d.rectangle((11,11,248,349),outline='#e1c77b',width=2);d.rectangle((14,14,246,40),fill='#eee5c8');d.text((20,21),card.name[:28],fill='#201810');art=art.convert('RGB').resize((226,214));img.paste(art,(17,48));d.rectangle((16,269,244,346),fill='#eee5c8');d.text((22,276),f'{CARD_TYPES[card.type_id]}  ·  {ATTRIBUTES[card.attribute]}',fill='#201810');d.text((22,300),f'Level {card.level}  ·  {card.gs1_name} / {card.gs2_name}',fill='#201810');d.text((22,326),f'ATK {card.atk}   DEF {card.def_}',fill='#201810');return img
 def refresh_previews(self,_=None):
  self.select();self.select_starter_card()
  for i in range(3):self.preview_fusion_card(i)
 def apply_card(self):
  try:
   original=self.cards.get(self.current)
   if original is None:raise ValueError('Select a card before applying changes.')
   c=copy.deepcopy(original)
   for k in ('name','password'):setattr(c,k,self.v[k].get())
   for k in ('atk','def_','star_cost'):setattr(c,k,int(self.v[k].get()))
   c.type_id=CARD_TYPES.index(self.v['type_id'].get());c.gs1=GUARDIAN_STARS.index(self.v['gs1'].get());c.gs2=GUARDIAN_STARS.index(self.v['gs2'].get());c.attribute=ATTRIBUTES.index(self.v['attribute'].get())
   c.level=int(self.v['level'].get())
   if not (0<=c.atk<=5110 and c.atk%10==0 and 0<=c.def_<=5110 and c.def_%10==0):raise ValueError('ATK and DEF must be multiples of 10 from 0 to 5110.')
   if not 0<=c.type_id<=23:raise ValueError('Type ID must be 0–23.')
   if not 0<=c.gs1<=10 or not 0<=c.gs2<=10:raise ValueError('Guardian star IDs must be 0–10.')
   if not 0<=c.star_cost<=999999:raise ValueError('Starchip cost must be 0–999999.')
   if len(c.name)>36:raise ValueError('Card names must be 36 characters or fewer.')
   if len(c.password)!=8 or any(ch not in string.hexdigits for ch in c.password):raise ValueError('Password must contain exactly eight hexadecimal digits (0–9, A–F).')
   if not 0<=c.level<=12 or not 0<=c.attribute<len(ATTRIBUTES):raise ValueError('Monster level must be 0–12 and attribute must be a listed game attribute.')
   c.description=self.desc.get('1.0','end-1c');self.cards.cards[self.current]=c;self.mini_photos.pop(self.current,None);self.dirty=True;self.fill();self.fill_starter_cards();self.set_card_picker_values();self.load_fusions();self.refresh_deck_view();self.load_drops()
   if self.tree.exists(str(self.current)):self.tree.selection_set(str(self.current));self.tree.focus(str(self.current));self.tree.see(str(self.current))
   self.select();self.status.configure(text=f'{c.name} updated; export the patched game image to save');return True
  except Exception as e:messagebox.showerror('Invalid value',str(e));return False
 def fusion_ui(self):
  page = self.fusion_page
  page.columnconfigure(0, weight=1)
  page.rowconfigure(3, weight=1)
  self.fv = [tk.StringVar() for _ in range(3)]
  self.undo_recipe_state = None
  self.fusion_picks = []
  self.fusion_photos = {}
  self.material_choices = [set(), set()]
  slots = ttk.Frame(page)
  slots.grid(row=0, column=0, sticky='ew')
  for i, label in enumerate(('First material', 'Second material', 'Result')):
   slots.columnconfigure(i, weight=1, uniform='slots')
   box = ttk.LabelFrame(slots, text=label, padding=6)
   box.grid(row=0, column=i, sticky='nsew', padx=2)
   preview = ttk.Label(box, anchor='center', wraplength=120, text='Choose a card')
   preview.pack(side='left', padx=(0, 6))
   panel = ttk.Frame(box)
   panel.pack(side='left', fill='x', expand=True)
   pick = ttk.Button(panel, text='Choose card…', command=lambda n=i:self.open_card_picker(n))
   pick.pack(fill='x')
   preview.bind('<Button-1>', lambda e,n=i:self.open_card_picker(n))
   self.fusion_picks.append((pick, preview))
  edit = ttk.Frame(page)
  edit.grid(row=1, column=0, sticky='ew', pady=6)
  ttk.Button(edit, text='Apply recipe', command=self.fusion_add).pack(side='left')
  self.new_pairs_only = tk.BooleanVar(value=False)
  ttk.Checkbutton(edit, text='Skip existing pairs', variable=self.new_pairs_only, command=self.update_fusion_summary).pack(side='left', padx=8)
  self.fusion_summary = ttk.Label(edit)
  self.fusion_summary.pack(side='left', padx=8)
  ttk.Button(edit, text='Reset all recipes', command=self.reset_all_fusions).pack(side='right')
  tools = ttk.Frame(page)
  tools.grid(row=2, column=0, sticky='ew', pady=4)
  self.fusion_query = tk.StringVar()
  self.fusion_scope = tk.StringVar(value='Everywhere')
  self.fusion_sort = tk.StringVar(value='Result name')
  self.fusion_deck_only = tk.BooleanVar()
  ttk.Label(tools, text='Find recipe').pack(side='left')
  ttk.Entry(tools, textvariable=self.fusion_query, width=16).pack(side='left', fill='x', expand=True, padx=4)
  for scope in ('Everywhere','Result','Material'):
   ttk.Radiobutton(tools, text=scope, value=scope, variable=self.fusion_scope,
                   command=self.load_fusions).pack(side='left')
  self.result_filter = self.filter_button(tools,self.load_fusions,'Result filters')
  self.result_filter.pack(side='left')
  ttk.Combobox(tools, textvariable=self.fusion_sort, values=('Result name','Material name','Card ID'), state='readonly', width=13).pack(side='left', padx=4)
  ttk.Checkbutton(tools, text='In starter deck', variable=self.fusion_deck_only, command=self.load_fusions).pack(side='left')
  ttk.Button(tools, text='Clear filters', command=self.reset_recipe_search).pack(side='left')
  listing = ttk.Frame(page)
  listing.grid(row=3, column=0, sticky='nsew')
  listing.rowconfigure(0, weight=1)
  listing.columnconfigure(0, weight=1)
  self.ft = RecipeSheet(listing, self.cards.get, self.art.get_card_art, self.select_fusion, self.fusion_context_menu)
  self.ft.grid(row=0,column=0,sticky='nsew')
  footer = ttk.Frame(page)
  footer.grid(row=4, column=0, sticky='ew', pady=(5,0))
  ttk.Button(footer, text='Delete selected', command=self.fusion_del).pack(side='left', padx=5)
  self.undo_recipe_button = ttk.Button(footer, text='Undo recipe edit', command=self.undo_recipe_edit)
  self.undo_recipe_button.pack(side='left')
  self.undo_recipe_button.state(['disabled'])
  self.fusion_count = ttk.Label(footer)
  self.fusion_count.pack(side='left', padx=8)
  self.recipe_next = ttk.Button(footer,text='Next →',command=lambda:self.load_fusions(self.recipe_page+1))
  self.recipe_prev = ttk.Button(footer,text='← Previous',command=lambda:self.load_fusions(self.recipe_page-1))
  self.recipe_next.pack(side='right')
  self.recipe_prev.pack(side='right', padx=4)
  self.fusion_query.trace_add('write', lambda *_:self.load_fusions())
  self.fusion_sort.trace_add('write', lambda *_:self.load_fusions())
  self.load_fusions()
 def reset_recipe_search(self):
  self.fusion_scope.set('Everywhere')
  self.result_filter.reset()
  self.fusion_deck_only.set(False)
  self.fusion_query.set('')
  self.fusion_sort.set('Result name')
 def replace_recipes(self, updated):
  self.undo_recipe_state = self.fusions
  self.fusions = updated
  self.undo_recipe_button.state(['!disabled'])
  self.dirty = True
  self.load_fusions(getattr(self, 'recipe_page', 0))
  self.update_fusion_summary()
 def undo_recipe_edit(self):
  if self.undo_recipe_state is None:return
  self.fusions = self.undo_recipe_state
  self.undo_recipe_state = None
  self.undo_recipe_button.state(['disabled'])
  self.dirty = True
  self.load_fusions(self.recipe_page)
  self.update_fusion_summary()
 def reset_all_fusions(self):
  if not getattr(self,"original_wa",None):return messagebox.showinfo('Fusion Lab','Open a ROM before resetting recipes.')
  restored=FusionDatabase();restored.load_from_wa(self.original_wa);self.replace_recipes(restored);self.status.configure(text='All fusion recipes reset to the loaded ROM.')
 def card_option(self,cid):
  c=self.cards.get(cid);return f'{c.name}  ·  {CARD_TYPES[c.type_id]}  ·  ATK {c.atk} / DEF {c.def_}'
 def card_from_option(self,value):
  return getattr(self,'card_option_ids',{}).get(value)
 def card_option_for_id(self,cid):
  return getattr(self,'card_option_by_id',{}).get(cid,self.card_option(cid))
 def set_card_picker_values(self):
  selected=[self.card_from_option(v.get()) for v in self.fv];values=[];self.card_option_ids={};self.card_option_by_id={}
  for cid in self.cards.cards:
   value=self.card_option(cid)
   if value in self.card_option_ids:value+=f'  ·  card {cid}'
   values.append(value);self.card_option_ids[value]=cid;self.card_option_by_id[cid]=value
  if values:
   available_ids=list(self.card_option_by_id)
   for i,(pick,_) in enumerate(getattr(self,'fusion_picks',[])):
    cid=selected[i] if i<len(selected) and selected[i] in self.card_option_by_id else available_ids[min(i,len(available_ids)-1)]
    self.fv[i].set(self.card_option_by_id[cid])
    pick.configure(text=self.card_button_text(cid))
    self.preview_fusion_card(i)
  self.update_fusion_summary()
 def material_card_ids(self,index):
  return sorted(self.material_choices[index])
 def expanded_material_pairs(self):
  from itertools import product
  return {(min(a,b),max(a,b)) for a,b in product(self.material_card_ids(0),self.material_card_ids(1))}
 def update_fusion_summary(self):
  if not hasattr(self,'fusion_summary'):return
  cards=[set(self.material_card_ids(i)) for i in range(2)];counts=[len(group) for group in cards];shared=len(cards[0]&cards[1]);pair_count=counts[0]*counts[1]-shared*(shared-1)//2 if all(counts) else 0
  existing=sum(1 for a,b in self.fusions.fusions if (a in cards[0] and b in cards[1]) or (b in cards[0] and a in cards[1]))
  action = 'skip' if self.new_pairs_only.get() else 'update'
  self.fusion_summary.configure(text=f'{pair_count:,} pairs · {pair_count-existing:,} new · {existing:,} to {action}')
 def preview_fusion_card(self,index):
  cid=self.card_from_option(self.fv[index].get())
  if index<2:
   choices=self.material_choices[index]
   if not choices and cid:choices.add(cid)
   cid=min(choices) if choices else None
   self.fusion_picks[index][0].configure(text=f'Choose cards ({len(choices)} selected)…')
  elif cid:
   self.fusion_picks[index][0].configure(text=self.card_button_text(cid))
  if not cid:
   self.fusion_picks[index][1].configure(image='',text='Choose a card',font=('Segoe UI',10))
   return
  image=self.art.get_card_art(cid)
  if image:
   photo=ImageTk.PhotoImage(self.render_card_preview(self.cards.get(cid),image).resize((68,94),Image.Resampling.LANCZOS));self.fusion_photos[index]=photo;self.fusion_picks[index][1].configure(image=photo,text='')
 def card_button_text(self,cid):
  card=self.cards.get(cid)
  return f'{card.name}  ·  ID {cid}' if card else 'Browse cards…'
 def assign_fusion_card(self,index,cid):
  if cid not in self.cards.cards:return
  self.fv[index].set(self.card_option_for_id(cid));self.fusion_picks[index][0].configure(text=self.card_button_text(cid))
  if index<2:
   self.material_choices[index]={cid};self.preview_fusion_card(index)
  else:self.preview_fusion_card(index)
  self.update_fusion_summary()
 def open_card_picker(self,index):
  if not self.cards.cards:return messagebox.showinfo('Card picker','Open a ROM image first.')
  win=tk.Toplevel(self);win.title(('Choose material 1','Choose material 2','Choose fusion result')[index]);win.geometry('920x700');win.minsize(760,560);win.transient(self);win.grab_set()
  win.columnconfigure(0,weight=1);win.rowconfigure(1,weight=1)
  tools=ttk.Frame(win,padding=10);tools.grid(row=0,column=0,sticky='ew');tools.columnconfigure(0,weight=1);query=tk.StringVar();sort=tk.StringVar(value='Name')
  search=ttk.Entry(tools,textvariable=query);search.grid(row=0,column=0,sticky='ew',padx=(0,6));picker_filter=self.filter_button(tools,lambda:refresh());picker_filter.grid(row=0,column=1,padx=4);ttk.Combobox(tools,textvariable=sort,values=['Name','Card ID','ATK','DEF','Level'],state='readonly',width=11).grid(row=0,column=2,padx=4)
  body=ttk.Frame(win,padding=(10,0,10,8));body.grid(row=1,column=0,sticky='nsew')
  body.columnconfigure(0,weight=1);body.rowconfigure(0,weight=1)
  canvas=tk.Canvas(body,highlightthickness=0,yscrollincrement=30)
  canvas.grid(row=0,column=0,sticky='nsew')
  scroll=ttk.Scrollbar(body,orient='vertical',command=canvas.yview)
  scroll.grid(row=0,column=1,sticky='ns')
  footer=ttk.Frame(win,padding=10);footer.grid(row=2,column=0,sticky='ew')
  count=ttk.Label(footer);count.pack(side='left')
  multiple=index<2
  result_id=self.card_from_option(self.fv[index].get())
  working=set(self.material_choices[index]) if multiple else {result_id}
  selected_only=tk.BooleanVar(win,value=False)
  ttk.Checkbutton(tools,text='Show selected only',variable=selected_only,command=lambda:refresh()).grid(row=0,column=3)
  filtered_ids=set()
  entries=[]
  tiles={}
  render_job=None
  columns,row_height=6,180
  def bulk(select):
   if select:working.update(filtered_ids)
   else:working.difference_update(filtered_ids)
   refresh(keep_position=True)
  def apply_selection():
   if not working:return
   self.material_choices[index]=working.copy()
   self.fv[index].set(self.card_option_for_id(min(working)))
   self.preview_fusion_card(index);self.update_fusion_summary()
   win.destroy()
  if multiple:
   actions=ttk.Frame(win,padding=(10,4));actions.grid(row=3,column=0,sticky='ew')
   ttk.Button(actions,text='Select all matches',command=lambda:bulk(True)).pack(side='left')
   ttk.Button(actions,text='Deselect all matches',command=lambda:bulk(False)).pack(side='left',padx=5)
   apply_button=ttk.Button(actions,text='Use selected cards',command=apply_selection);apply_button.pack(side='right')
  def set_card(cid):
   if multiple:
    working.symmetric_difference_update((cid,))
    refresh(keep_position=True)
   else:
    self.assign_fusion_card(index,cid);win.destroy()
  def refresh(*_,keep_position=False):
   nonlocal entries
   needle=query.get().strip().lower()
   entries=[(cid,c) for cid,c in self.cards.cards.items()
            if (not selected_only.get() or cid in working) and picker_filter.criteria.matches(c)
            and (not needle or needle in c.name.lower() or needle in str(cid))]
   filtered_ids.clear();filtered_ids.update(cid for cid,_ in entries)
   sort_key={'Card ID':lambda pair:pair[0], 'ATK':lambda pair:(pair[1].atk,pair[1].name.lower()),
             'DEF':lambda pair:(pair[1].def_,pair[1].name.lower()),'Level':lambda pair:(pair[1].level,pair[1].name.lower())}
   entries.sort(key=sort_key.get(sort.get(),lambda pair:pair[1].name.lower()))
   canvas.configure(scrollregion=(0,0,1,((len(entries)+columns-1)//columns)*row_height))
   if not keep_position:canvas.yview_moveto(0)
   count.configure(text=f'{len(working)} selected · {len(entries)} matching')
   if multiple:apply_button.configure(state='normal' if working else 'disabled')
   schedule_render()
  def wheel(event):
   amount=-1 if getattr(event,'num',None)==4 else 1 if getattr(event,'num',None)==5 else (-1 if event.delta>0 else 1)*max(1,abs(event.delta)//120)
   canvas.yview_scroll(amount,'units')
   return 'break'
  def bind_wheel(widget):
   for sequence in ('<MouseWheel>','<Button-4>','<Button-5>'):widget.bind(sequence,wheel)
  def draw_tiles():
   nonlocal render_job
   render_job=None
   top=max(0,int(canvas.canvasy(0)))
   first=top//row_height*columns
   end=((top+canvas.winfo_height())//row_height+2)*columns
   visible=entries[first:end]
   visible_ids={cid for cid,_ in visible}
   for cid in tiles.keys()-visible_ids:
    item,tile=tiles.pop(cid);canvas.delete(item);tile.destroy()
   width=max(1,canvas.winfo_width()//columns)
   for position,(cid,card) in enumerate(visible,first):
    if cid not in tiles:
     tile=tk.Button(canvas,compound='top',command=lambda n=cid:set_card(n),borderwidth=2,takefocus=True)
     art=self.art.get_card_art(cid)
     if art:
      tile.photo=ImageTk.PhotoImage(self.render_card_preview(card,art).resize((100,138),Image.Resampling.LANCZOS))
      tile.configure(image=tile.photo)
     bind_wheel(tile);tile.bind('<Button-3>',lambda e,n=cid:picker_context(e,n))
     tiles[cid]=(canvas.create_window(0,0,window=tile,anchor='nw'),tile)
    item,tile=tiles[cid];chosen=cid in working
    label=('✓ Selected' if chosen else 'Select') if hasattr(tile,'photo') else card.name
    tile.configure(text=label,relief='sunken' if chosen else 'flat',background='#b8e893' if chosen else '#30363c',foreground='#102018' if chosen else '#e2e5e9')
    canvas.coords(item,(position%columns)*width+2,(position//columns)*row_height+2)
    canvas.itemconfigure(item,width=max(1,width-4),height=row_height-4)
  def schedule_render(*_):
   nonlocal render_job
   if render_job is None:render_job=canvas.after_idle(draw_tiles)
  def scrolled(first,last):
   if scroll.get()!=(float(first),float(last)):
    scroll.set(first,last);schedule_render()
  canvas.configure(yscrollcommand=scrolled);canvas.bind('<Configure>',schedule_render);bind_wheel(canvas)
  def cancel_render(event):
   if render_job is not None:canvas.after_cancel(render_job)
  canvas.bind('<Destroy>',cancel_render)
  def picker_context(event,cid):
   menu=tk.Menu(win,tearoff=False)
   if multiple:
    menu.add_command(label='Remove from selection' if cid in working else 'Add to selection',command=lambda:set_card(cid));menu.tk_popup(event.x_root,event.y_root);return
   for slot,label in enumerate(('Use as Material 1','Use as Material 2','Use as Fusion Result')):menu.add_command(label=label,command=lambda n=slot,card_id=cid:set_card_for_slot(n,card_id))
   menu.tk_popup(event.x_root,event.y_root)
  def set_card_for_slot(slot,cid):
   self.assign_fusion_card(slot,cid)
   if slot==index:win.destroy()
  query.trace_add('write',refresh);sort.trace_add('write',refresh);search.bind('<Return>',refresh);refresh()
 def select_fusion(self,_=None):
  if self.ft.selected is None:return
  a,b,r=self.ft.rows[self.ft.selected]
  for idx,cid in enumerate((a,b,r)):
   self.fv[idx].set(self.card_option_for_id(cid));self.fusion_picks[idx][0].configure(text=self.card_button_text(cid))
   if idx<2:self.material_choices[idx]={cid}
   self.preview_fusion_card(idx)
  self.update_fusion_summary()
 def fusion_context_menu(self,event):
  menu = tk.Menu(self, tearoff=False)
  menu.add_command(label='Load recipe into editor',command=self.select_fusion)
  menu.add_command(label='Copy recipe',command=self.copy_recipe)
  menu.add_separator()
  menu.add_command(label='Delete this recipe',command=self.fusion_del)
  menu.tk_popup(event.x_root,event.y_root)
 def copy_recipe(self):
  if self.ft.selected is None:return
  a,b,result = (self.cards.get(i).name for i in self.ft.rows[self.ft.selected])
  self.clipboard_clear()
  self.clipboard_append(f'{a} + {b} → {result}')
  self.status.configure(text=f'Copied recipe for {result}.')
 def drop_ui(self):
  p=self.drop_page;p.columnconfigure(0,weight=0,minsize=250);p.columnconfigure(1,weight=1);p.rowconfigure(0,weight=1);self.duelist=tk.StringVar(value=DUELISTS[0]);self.opponent_photos={}
  gallery=ttk.LabelFrame(p,text='OPPONENTS',padding=8);gallery.grid(row=0,column=0,sticky='nsew',padx=(0,10));gallery.columnconfigure(0,weight=1);gallery.rowconfigure(0,weight=1)
  self.opponent_tree=ttk.Treeview(gallery,show='tree',height=20);self.opponent_tree.heading('#0',text='39 duelists · choose a portrait');self.opponent_tree.column('#0',width=210,stretch=True);self.opponent_tree.grid(row=0,column=0,sticky='nsew');ys=ttk.Scrollbar(gallery,orient='vertical',command=self.opponent_tree.yview);ys.grid(row=0,column=1,sticky='ns');self.opponent_tree.configure(yscrollcommand=ys.set);self.opponent_tree.bind('<<TreeviewSelect>>',self.select_duelist);self.opponent_tree.bind('<Button-3>',self.opponent_context_menu);self.opponent_tree.bind('<Button-2>',self.opponent_context_menu)
  detail=ttk.Frame(p);detail.grid(row=0,column=1,sticky='nsew');detail.columnconfigure(0,weight=1);detail.rowconfigure(2,weight=1)
  identity=ttk.LabelFrame(detail,text='SELECTED DUELIST',padding=10);identity.grid(row=0,column=0,sticky='ew');self.dp=ttk.Label(identity,text='Open a ROM to load portraits',anchor='center');self.dp.pack(side='left',padx=(0,14));self.drop_title=ttk.Label(identity,text=DUELISTS[0],font=('Segoe UI',18,'bold'));self.drop_title.pack(side='left',anchor='center');ttk.Button(identity,text='Change portrait…',command=self.import_portrait).pack(side='right',padx=6)
  tools=ttk.Frame(detail);tools.grid(row=1,column=0,sticky='ew',pady=8);self.pool=tk.StringVar(value='S/A POW');ttk.Label(tools,text='REWARD POOL').pack(side='left',padx=(0,5));ttk.Combobox(tools,textvariable=self.pool,values=['S/A POW','B/C/D','S/A TEC'],state='readonly',width=12).pack(side='left');self.pool.trace_add('write',lambda *_:self.load_drops());self.drop_query=tk.StringVar();self.drop_sort=tk.StringVar(value='Card name');search=ttk.Entry(tools,textvariable=self.drop_query);search.pack(side='left',fill='x',expand=True,padx=(12,4));search.bind('<KeyRelease>',lambda e:self.load_drops());self.drop_filter=self.filter_button(tools,self.load_drops);self.drop_filter.pack(side='left',padx=3);ttk.Combobox(tools,textvariable=self.drop_sort,values=['Card name','Card ID','Weight','Chance'],state='readonly',width=11).pack(side='left',padx=3);self.drop_sort.trace_add('write',lambda *_:self.load_drops())
  drop_list=ttk.Frame(detail);drop_list.grid(row=2,column=0,sticky='nsew');drop_list.columnconfigure(0,weight=1);drop_list.rowconfigure(0,weight=1);self.dt=ttk.Treeview(drop_list,columns=('weight','chance'),show='tree headings');self.dt.heading('#0',text='Reward card');self.dt.column('#0',width=390);self.dt.heading('weight',text='Weight');self.dt.heading('chance',text='Drop chance');self.dt.column('weight',width=75,stretch=False,anchor='e');self.dt.column('chance',width=100,stretch=False,anchor='center');self.dt.grid(row=0,column=0,sticky='nsew');drop_scroll=ttk.Scrollbar(drop_list,orient='vertical',command=self.dt.yview);drop_scroll.grid(row=0,column=1,sticky='ns');self.dt.configure(yscrollcommand=drop_scroll.set);self.dt.bind('<Double-1>',self.edit_drop);self.dt.bind('<Button-3>',self.drop_context_menu);self.dt.bind('<Button-2>',self.drop_context_menu);actions=ttk.Frame(detail);actions.grid(row=3,column=0,sticky='ew',pady=8);ttk.Button(actions,text='Reset all drop edits',command=self.reset_all_drops).pack(side='left',padx=3);ttk.Button(actions,text='Reset filters',command=self.reset_drop_filters).pack(side='left',padx=3);ttk.Button(actions,text='Reset this pool',command=self.reset_drop_pool).pack(side='left',padx=3);ttk.Button(actions,text='Add card…',command=self.add_drop).pack(side='left',padx=3);ttk.Button(actions,text='Balance weights',command=self.normalize_pool).pack(side='left',padx=3)
  self.refresh_opponent_gallery()
 def refresh_opponent_gallery(self):
  if not hasattr(self,'opponent_tree'):return
  self.opponent_tree.delete(*self.opponent_tree.get_children());self.opponent_photos={}
  for portrait_id,name in enumerate(DUELISTS,1):
   if self.wa:
    try:im=portraits.read(self.wa,portrait_id).resize((48,48),Image.Resampling.NEAREST)
    except Exception:im=Image.new('RGB',(52,52),'#445166')
   else:im=Image.new('RGB',(52,52),'#445166')
   photo=ImageTk.PhotoImage(im);self.opponent_photos[portrait_id]=photo;self.opponent_tree.insert('','end',iid=str(portrait_id),text=name,image=photo)
  if hasattr(self, 'free_duel_grid'):
   self.free_duel_grid.refresh_images(self.opponent_photos if self.wa else {})
  selected=str(DUELISTS.index(self.duelist.get())+1)
  if self.opponent_tree.exists(selected):self.opponent_tree.selection_set(selected);self.opponent_tree.see(selected)
 def select_duelist(self,_=None):
  selection=self.opponent_tree.selection()
  if not selection:return
  index=int(selection[0])-1
  if 0<=index<len(DUELISTS):self.duelist.set(DUELISTS[index]);self.load_drops()
 def opponent_context_menu(self,event):
  row=self.opponent_tree.identify_row(event.y)
  if not row:return
  self.opponent_tree.selection_set(row);self.opponent_tree.focus(row);index=int(row)-1
  if 0<=index<len(DUELISTS):self.duelist.set(DUELISTS[index]);self.load_drops()
  menu=tk.Menu(self,tearoff=False);menu.add_command(label='Change portrait…',command=self.import_portrait);menu.add_command(label='Reset this opponent’s drops and portrait',command=self.reset_duelist_data);menu.add_separator();menu.add_command(label='Balance this reward pool',command=self.normalize_pool);menu.tk_popup(event.x_root,event.y_root)
 def reset_duelist_data(self):
  if not self.wa or not hasattr(self,'original_wa'):return
  d=DUELISTS.index(self.duelist.get())
  for pool in range(3):
   start=0xE9B000+d*0x1800+(pool+1)*1460;self.wa[start:start+1444]=self.original_wa[start:start+1444]
  portrait_id=d+1;start=portraits.BASE+portrait_id*portraits.RECORD;end=start+portraits.RECORD;self.wa[start:end]=self.original_wa[start:end]
  self.dirty=True;self.refresh_opponent_gallery();self.load_drops();self.status.configure(text=f'{self.duelist.get()} drop lists and portrait reset to the loaded ROM.')
 def save_ui(self):
  p=self.save_page
  for i in range(3):p.columnconfigure(i,weight=1)
  p.rowconfigure(0,weight=1);self.player=tk.StringVar(value='PLAYER');self.chips=tk.StringVar(value='0');self.deck_ids=[1]*3+[2]*3+[3]*3+[4]*3+[5]*3+[6]*3+[7]*3+[8]*3+[9]*3+[10]*3+[11]*3+[12]*3+[13]*3+[14];self.mini_photos={};self.placeholder_photo=ImageTk.PhotoImage(Image.new('RGB',(164,48),'#263449'))
  browse=ttk.LabelFrame(p,text='CARD LIBRARY',padding=8);browse.grid(row=0,column=0,sticky='nsew',padx=5);browse.columnconfigure(0,weight=1);browse.rowconfigure(1,weight=1);self.starter_query=tk.StringVar();self.starter_sort=tk.StringVar(value='Name');tools=ttk.Frame(browse);tools.grid(row=0,column=0,sticky='ew',pady=(0,6));tools.columnconfigure(0,weight=1);se=ttk.Entry(tools,textvariable=self.starter_query);se.grid(row=0,column=0,sticky='ew');se.bind('<KeyRelease>',lambda e:self.fill_starter_cards());self.starter_filter=self.filter_button(tools,self.fill_starter_cards);self.starter_filter.grid(row=0,column=1,padx=3);ttk.Combobox(tools,textvariable=self.starter_sort,values=['Name','Card ID','ATK','DEF'],state='readonly',width=9).grid(row=0,column=2,padx=3);ttk.Button(tools,text='Reset',command=self.reset_starter_filters).grid(row=0,column=3);self.starter_sort.trace_add('write',lambda *_:self.fill_starter_cards());card_list=ttk.Frame(browse);card_list.grid(row=1,column=0,sticky='nsew');card_list.columnconfigure(0,weight=1);card_list.rowconfigure(0,weight=1);self.starter_tree=ttk.Treeview(card_list,show='tree');self.starter_tree.heading('#0',text='CARD · TYPE · ATTRIBUTE · GUARDIAN · LEVEL · ATK / DEF');self.starter_tree.column('#0',width=360);self.starter_tree.grid(row=0,column=0,sticky='nsew');starter_scroll=ttk.Scrollbar(card_list,orient='vertical',command=self.starter_tree.yview);starter_scroll.grid(row=0,column=1,sticky='ns');self.starter_tree.configure(yscrollcommand=starter_scroll.set);self.starter_tree.bind('<<TreeviewSelect>>',self.select_starter_card);self.starter_tree.bind('<ButtonRelease-1>',self.starter_library_add);self.starter_tree.bind('<ButtonRelease-3>',self.starter_library_remove);ttk.Label(browse,text='Left-click adds · right-click removes one copy · game icons show type, attribute, Guardian Stars, and level',font=('Segoe UI',9)).grid(row=2,column=0,sticky='w')
  preview=ttk.LabelFrame(p,text='SELECTED CARD',padding=12);preview.grid(row=0,column=2,sticky='nsew',padx=5);self.starter_art=ttk.Label(preview,text='Open a ROM to view cards',anchor='center');self.starter_art.pack(fill='x',pady=8);self.starter_name=ttk.Label(preview,text='Choose a card',font=('Segoe UI',16,'bold'),wraplength=280);self.starter_name.pack(pady=6);self.starter_stats=ttk.Label(preview,text='',justify='center');self.starter_stats.pack(pady=4);ttk.Button(preview,text='Add selected card to deck',command=self.starter_add).pack(pady=12)
  deck=ttk.LabelFrame(p,text='STARTER DECK  •  40 CARDS',padding=8);deck.grid(row=0,column=1,sticky='nsew',padx=5);deck.columnconfigure(0,weight=1);deck.columnconfigure(1,weight=1);deck.rowconfigure(0,weight=1);deck_list=ttk.Frame(deck);deck_list.grid(row=0,column=0,columnspan=2,sticky='nsew');deck_list.columnconfigure(0,weight=1);deck_list.rowconfigure(0,weight=1);self.deck_tree=ttk.Treeview(deck_list,show='tree');self.deck_tree.heading('#0',text='CARD · TYPE · ATTRIBUTE · GUARDIAN · LEVEL · COPIES');self.deck_tree.column('#0',width=340);self.deck_tree.grid(row=0,column=0,sticky='nsew');deck_scroll=ttk.Scrollbar(deck_list,orient='vertical',command=self.deck_tree.yview);deck_scroll.grid(row=0,column=1,sticky='ns');self.deck_tree.configure(yscrollcommand=deck_scroll.set);self.deck_tree.bind('<ButtonRelease-3>',self.deck_right_remove)
  self.random_deck_style=tk.StringVar(value='Balanced');ttk.Combobox(deck,textvariable=self.random_deck_style,values=['Balanced','Monster-heavy','Anything goes'],state='readonly').grid(row=1,column=0,columnspan=2,sticky='ew',pady=(6,2));ttk.Button(deck,text='Build random 40-card deck',command=self.randomize_starter_deck).grid(row=2,column=0,columnspan=2,sticky='ew',pady=3);ttk.Button(deck,text='Fill empty slots randomly',command=self.fill_random_deck_slots).grid(row=3,column=0,columnspan=2,sticky='ew',pady=3)
  ttk.Button(deck,text='Remove selected',command=self.starter_remove).grid(row=4,column=0,sticky='ew',pady=4);ttk.Button(deck,text='Clear deck',command=self.starter_clear).grid(row=4,column=1,sticky='ew',padx=5,pady=4);ttk.Button(deck,text='Reset default deck',command=self.reset_default_deck).grid(row=5,column=0,columnspan=2,sticky='ew');self.deck_count=ttk.Label(deck,text='0 / 40 cards');self.deck_count.grid(row=7,column=0,columnspan=2)
  footer=ttk.LabelFrame(p,text='SAVE FILE',padding=10);footer.grid(row=1,column=0,columnspan=3,sticky='ew',pady=10);ttk.Label(footer,text='Player name').pack(side='left');ttk.Entry(footer,textvariable=self.player,width=15).pack(side='left',padx=6);ttk.Label(footer,text='Starting starchips').pack(side='left',padx=(18,4));ttk.Entry(footer,textvariable=self.chips,width=10).pack(side='left');ttk.Button(footer,text='Reset all starter changes',command=self.reset_all_starter).pack(side='right',padx=5);ttk.Button(footer,text='Create DuckStation .mcd',command=self.save_mcd).pack(side='right');self.refresh_deck_view()
 def savedata_ui(self):
  p=self.savedata_page;p.columnconfigure(0,weight=1);p.rowconfigure(3,weight=1);self.sd_doc=None;self.sd_path=None;self.sd_deck=[];self.sd_quantities=[];self.sd_selected_card=None;self.sd_selected_slot=None;self.sd_progress_initial={}
  header=ttk.Frame(p);header.grid(row=0,column=0,sticky='ew');ttk.Button(header,text='Open memory card or save…',command=self.open_savedata).pack(side='left');ttk.Button(header,text='Save edited data as…',command=self.save_savedata).pack(side='left',padx=6);ttk.Button(header,text='Reload current file',command=self.reload_savedata).pack(side='left');self.sd_status=ttk.Label(header,text='Open a DuckStation .mcd card or exported FM .mcs save.');self.sd_status.pack(side='left',padx=12)
  profile=ttk.LabelFrame(p,text='PLAYER PROFILE',padding=8);profile.grid(row=1,column=0,sticky='ew',pady=(8,10))
  for column in range(8):profile.columnconfigure(column,weight=1 if column in (1,3,5,7) else 0)
  self.sd_name=tk.StringVar(value='PLAYER');self.sd_chips=tk.StringVar(value='0');self.sd_wins=tk.StringVar(value='0');self.sd_losses=tk.StringVar(value='0');self.sd_progress_vars={key:tk.BooleanVar(value=False) for key in CAMPAIGN_CHECKPOINTS}
  ttk.Label(profile,text='Name').grid(row=0,column=0,sticky='w');ttk.Entry(profile,textvariable=self.sd_name,width=10).grid(row=0,column=1,sticky='ew',padx=(5,12));ttk.Label(profile,text='Starchips').grid(row=0,column=2,sticky='w');ttk.Spinbox(profile,textvariable=self.sd_chips,from_=0,to=999999,width=10).grid(row=0,column=3,sticky='ew',padx=(5,12));ttk.Label(profile,text='Wins').grid(row=0,column=4,sticky='w');ttk.Spinbox(profile,textvariable=self.sd_wins,from_=0,to=65535,width=8).grid(row=0,column=5,sticky='ew',padx=(5,12));ttk.Label(profile,text='Losses').grid(row=0,column=6,sticky='w');ttk.Spinbox(profile,textvariable=self.sd_losses,from_=0,to=65535,width=8).grid(row=0,column=7,sticky='ew',padx=(5,12))
  pages = ttk.Notebook(p)
  pages.grid(row=3,column=0,sticky='nsew')
  progress = ttk.Frame(pages,padding=16)
  for column in range(3):progress.columnconfigure(column,weight=1)
  for index,(key,definition) in enumerate(CAMPAIGN_CHECKPOINTS.items()):ttk.Checkbutton(progress,text=definition['label'],variable=self.sd_progress_vars[key],command=lambda k=key:self.toggle_savedata_checkpoint(k)).grid(row=index//3,column=index%3,sticky='w',padx=5,pady=2)
  ttk.Button(progress,text='Reset to loaded save',command=self.reset_savedata_progress).grid(row=0,column=3,rowspan=2,sticky='ne',padx=(8,3),pady=2)
  ttk.Label(progress,text='Milestones update documented story flags and duel unlocks. The save keeps its existing campaign scene, so it resumes at that saved map/menu point; this does not create a mid-duel or cutscene save. Changes apply when you save a copy.',wraplength=1000).grid(row=(len(CAMPAIGN_CHECKPOINTS)+2)//3,column=0,columnspan=4,sticky='w',padx=5,pady=(5,0))
  body = ttk.Frame(pages)
  pages.add(body, text='Collection and deck')
  self.free_duel_grid = FreeDuelGrid(pages, self.opponent_photos if self.wa else {})
  pages.add(self.free_duel_grid, text='Free Duel opponents')
  pages.add(progress,text='Campaign milestones')
  body.columnconfigure(0,weight=5,minsize=420);body.columnconfigure(1,weight=6,minsize=570);body.rowconfigure(0,weight=1)
  library=ttk.LabelFrame(body,text='CARD COLLECTION · TRUNK COPIES',padding=8);library.grid(row=0,column=0,sticky='nsew',padx=(0,8));library.columnconfigure(0,weight=1);library.rowconfigure(1,weight=1);self.sd_query=tk.StringVar();search=ttk.Entry(library,textvariable=self.sd_query);search.grid(row=0,column=0,sticky='ew',pady=(0,6));search.bind('<KeyRelease>',lambda e:self.refresh_savedata_card_list());self.collection_filter=self.filter_button(library,self.refresh_savedata_card_list);self.collection_filter.grid(row=0,column=1);self.collection_filter.state(['disabled']);self.sd_cards_tree=ttk.Treeview(library,columns=('id','qty','deck'),show='tree headings');self.sd_cards_tree.heading('#0',text='CARD · GAME ICONS');self.sd_cards_tree.heading('id',text='ID');self.sd_cards_tree.heading('qty',text='Trunk');self.sd_cards_tree.heading('deck',text='Deck');self.sd_cards_tree.column('#0',width=285);self.sd_cards_tree.column('id',width=48,anchor='center');self.sd_cards_tree.column('qty',width=60,anchor='center');self.sd_cards_tree.column('deck',width=55,anchor='center');self.sd_cards_tree.grid(row=1,column=0,sticky='nsew');libscroll=ttk.Scrollbar(library,orient='vertical',command=self.sd_cards_tree.yview);libscroll.grid(row=1,column=1,sticky='ns');self.sd_cards_tree.configure(yscrollcommand=libscroll.set);self.sd_cards_tree.bind('<<TreeviewSelect>>',self.select_savedata_card)
  detail=ttk.Frame(body);detail.grid(row=0,column=1,sticky='nsew');detail.columnconfigure(0,weight=1);detail.rowconfigure(1,weight=1)
  selected=ttk.LabelFrame(detail,text='SELECTED CARD · COLLECTION AND DECK',padding=8);selected.grid(row=0,column=0,sticky='ew',pady=(0,8));self.sd_preview=ttk.Label(selected,text='Choose a save file and card',anchor='center');self.sd_preview.grid(row=0,column=0,rowspan=4,sticky='n',padx=(0,12));self.sd_card_title=ttk.Label(selected,text='No card selected',font=('Segoe UI',13,'bold'));self.sd_card_title.grid(row=0,column=1,columnspan=4,sticky='w');self.sd_card_stats=ttk.Label(selected,text='',justify='left');self.sd_card_stats.grid(row=1,column=1,columnspan=4,sticky='w',pady=4);self.sd_qty=tk.StringVar(value='0');ttk.Label(selected,text='Copies in trunk').grid(row=2,column=1,sticky='w',pady=3);ttk.Spinbox(selected,textvariable=self.sd_qty,from_=0,to=250,width=8).grid(row=2,column=2,sticky='w',padx=6);ttk.Button(selected,text='Apply trunk quantity',command=self.apply_savedata_quantity).grid(row=2,column=3,sticky='w',padx=5);ttk.Button(selected,text='Replace selected deck slot with this card',command=self.replace_savedata_deck_slot).grid(row=3,column=1,columnspan=3,sticky='w',pady=(6,0))
  deck=ttk.LabelFrame(detail,text='40-CARD DECK · SELECT A SLOT, THEN REPLACE OR CLEAR',padding=8);deck.grid(row=1,column=0,sticky='nsew');deck.columnconfigure(0,weight=1);deck.rowconfigure(0,weight=1);self.sd_deck_tree=ttk.Treeview(deck,columns=('id',),show='tree headings');self.sd_deck_tree.heading('#0',text='DECK SLOT · CARD');self.sd_deck_tree.heading('id',text='ID');self.sd_deck_tree.column('#0',width=420);self.sd_deck_tree.column('id',width=60,anchor='center');self.sd_deck_tree.grid(row=0,column=0,sticky='nsew');deckscroll=ttk.Scrollbar(deck,orient='vertical',command=self.sd_deck_tree.yview);deckscroll.grid(row=0,column=1,sticky='ns');self.sd_deck_tree.configure(yscrollcommand=deckscroll.set);self.sd_deck_tree.bind('<<TreeviewSelect>>',self.select_savedata_deck_slot);self.sd_deck_tree.bind('<Double-1>',self.replace_savedata_deck_slot);actions=ttk.Frame(deck);actions.grid(row=1,column=0,columnspan=2,sticky='ew',pady=(6,0));self.sd_deck_count=ttk.Label(actions,text='0 / 40 occupied');self.sd_deck_count.pack(side='left');ttk.Button(actions,text='Clear selected slot',command=self.clear_savedata_deck_slot).pack(side='right')
  self.refresh_savedata_card_list();self.refresh_savedata_deck()
 def open_savedata(self):
  path=filedialog.askopenfilename(filetypes=[('DuckStation memory cards and FM saves','*.mcd *.mcs'),('All files','*.*')])
  if not path:return
  try:
   doc=SaveDataDocument.open(path);self.sd_doc=doc;self.sd_path=Path(path);self.sd_name.set(doc.player_name());self.sd_chips.set(str(doc.starchips()));wins,losses=doc.duel_record();self.sd_wins.set(str(wins));self.sd_losses.set(str(losses));self.load_savedata_progress(doc);self.sd_deck=doc.deck();self.sd_quantities=[doc.card_quantity(cid) for cid in range(1,723)];self.sd_selected_slot=None;self.sd_status.configure(text=f'{self.sd_path.name} · integrity verified · {"memory card" if doc.blocks is not None else "single save"}');self.refresh_savedata_card_list();self.refresh_savedata_deck()
  except (OSError,SaveDataError) as exc:messagebox.showerror('Could not open save data',str(exc))
 def reload_savedata(self):
  if not self.sd_path:return messagebox.showinfo('Save Data Editor','Open a save file first.')
  try:
   doc=SaveDataDocument.open(self.sd_path);self.sd_doc=doc;self.sd_name.set(doc.player_name());self.sd_chips.set(str(doc.starchips()));wins,losses=doc.duel_record();self.sd_wins.set(str(wins));self.sd_losses.set(str(losses));self.load_savedata_progress(doc);self.sd_deck=doc.deck();self.sd_quantities=[doc.card_quantity(cid) for cid in range(1,723)];self.sd_selected_slot=None;self.sd_status.configure(text=f'{self.sd_path.name} · reloaded · integrity verified');self.refresh_savedata_card_list();self.refresh_savedata_deck()
  except (OSError,SaveDataError) as exc:messagebox.showerror('Could not reload save data',str(exc))
 def toggle_savedata_checkpoint(self, key):
  if self.sd_doc is None:
   return
  enabled = self.sd_progress_vars[key].get()
  for opponent in CAMPAIGN_CHECKPOINTS[key]['duelists']:
   self.free_duel_grid.values[opponent].set(enabled)
 def load_savedata_progress(self,doc):
  self.free_duel_grid.load(doc)
  self.sd_selected_card = None
  self.sd_progress_initial={}
  for key,var in self.sd_progress_vars.items():
   enabled=doc.campaign_checkpoint(key);var.set(enabled);self.sd_progress_initial[key]=enabled
 def reset_savedata_progress(self):
  for key,var in self.sd_progress_vars.items():
   if var.get() != self.sd_progress_initial.get(key, False) and self.sd_doc is not None:
    for opponent in CAMPAIGN_CHECKPOINTS[key]['duelists']:
     self.free_duel_grid.values[opponent].set(self.sd_doc.campaign_flag(0x6e0 + opponent))
   var.set(self.sd_progress_initial.get(key,False))
  if self.sd_doc is not None:self.sd_status.configure(text=f'{self.sd_path.name if self.sd_path else "Save"} · campaign checkpoints restored to loaded values')
 def save_savedata(self):
  if self.sd_doc is None:return messagebox.showinfo('Save Data Editor','Open a valid save file first.')
  suggested_suffix='.mcd' if self.sd_doc.blocks is not None else '.mcs';initial=OUTPUT_BASENAME+suggested_suffix;kind='DuckStation memory card' if self.sd_doc.blocks is not None else 'FM single save'
  path=filedialog.asksaveasfilename(defaultextension=suggested_suffix,initialfile=initial,filetypes=[(kind,'*'+suggested_suffix),('All files','*.*')])
  if not path:return
  try:
   if Path(path).suffix.lower()!=suggested_suffix:path=str(Path(path).with_suffix(suggested_suffix))
   if self.sd_selected_card is not None:
    quantity=int(self.sd_qty.get())
    if not 0<=quantity<=250:raise SaveDataError('Trunk copies must be between 0 and 250.')
    self.sd_quantities[self.sd_selected_card-1]=quantity
   doc = copy.deepcopy(self.sd_doc)
   doc.set_player_name(self.sd_name.get());doc.set_starchips(int(self.sd_chips.get()));doc.set_duel_record(int(self.sd_wins.get()),int(self.sd_losses.get()))
   for key,var in self.sd_progress_vars.items():
    if bool(var.get())!=self.sd_progress_initial.get(key,False):doc.set_campaign_checkpoint(key,bool(var.get()))
   self.free_duel_grid.apply(doc)
   doc.set_deck(self.sd_deck)
   for cid,quantity in enumerate(self.sd_quantities,1):doc.set_card_quantity(cid,quantity)
   Path(path).write_bytes(doc.to_bytes());self.sd_doc=doc;self.sd_path=Path(path);self.sd_progress_initial={key:bool(var.get()) for key,var in self.sd_progress_vars.items()};self.sd_status.configure(text=f'{self.sd_path.name} · saved with valid checksums');messagebox.showinfo('Save data saved',f'Edited save data saved to:\n{path}')
  except (OSError,ValueError,SaveDataError) as exc:messagebox.showerror('Could not save data',str(exc))
 def refresh_savedata_card_list(self):
  if not hasattr(self,'sd_cards_tree'):return
  tree=self.sd_cards_tree;selected=tree.selection()[0] if tree.selection() else None;tree.delete(*tree.get_children());query=self.sd_query.get().strip().lower();deck_counts={}
  for cid in self.sd_deck:deck_counts[cid]=deck_counts.get(cid,0)+1
  if self.sd_doc is None:return
  for cid in sorted(CARD_NAMES,key=lambda card_id:CARD_NAMES[card_id].lower()):
   c=self.cards.get(cid);name=c.name if c else CARD_NAMES[cid]
   if not self.collection_filter.criteria.matches(c):continue
   if query and query not in name.lower() and query not in str(cid):continue
   quantity=self.sd_quantities[cid-1] if len(self.sd_quantities)>=cid else 0;tree.insert('','end',iid=str(cid),text=name,image=self.mini_photo(cid),values=(cid,quantity,deck_counts.get(cid,0)))
  if selected and tree.exists(selected):tree.selection_set(selected);tree.focus(selected)
 def select_savedata_card(self,_=None):
  if not self.sd_cards_tree.selection():return
  self.sd_selected_card=int(self.sd_cards_tree.selection()[0]);cid=self.sd_selected_card;c=self.cards.get(cid);self.sd_qty.set(str(self.sd_quantities[cid-1] if self.sd_quantities else 0));name=c.name if c else CARD_NAMES.get(cid,f'Card {cid}');self.sd_card_title.configure(text=f'{name} · ID {cid}')
  if c:self.sd_card_stats.configure(text=f'{CARD_TYPES[c.type_id]} · {ATTRIBUTES[c.attribute]}\nLevel {c.level} · {c.gs1_name} / {c.gs2_name}\nATK {c.atk} / DEF {c.def_} · In deck: {self.sd_deck.count(cid)}')
  else:self.sd_card_stats.configure(text=f'In deck: {self.sd_deck.count(cid)}\nOpen a ROM image to show stats, icons, and card artwork.')
  art=self.art.get_card_art(cid)
  if art:self.sd_preview_photo=ImageTk.PhotoImage(self.render_card_preview(c,art).resize((145,201),Image.Resampling.LANCZOS));self.sd_preview.configure(image=self.sd_preview_photo,text='')
  else:self.sd_preview.configure(image='',text='Artwork unavailable')
 def apply_savedata_quantity(self):
  if self.sd_doc is None or self.sd_selected_card is None:return messagebox.showinfo('Save Data Editor','Open a save and select a card first.')
  try:quantity=int(self.sd_qty.get())
  except ValueError:return messagebox.showerror('Trunk quantity','Enter a whole number from 0 to 250.')
  if not 0<=quantity<=250:return messagebox.showerror('Trunk quantity','Enter a whole number from 0 to 250.')
  self.sd_quantities[self.sd_selected_card-1]=quantity;self.refresh_savedata_card_list();
  if self.sd_cards_tree.exists(str(self.sd_selected_card)):self.sd_cards_tree.selection_set(str(self.sd_selected_card));self.select_savedata_card()
 def refresh_savedata_deck(self):
  if not hasattr(self,'sd_deck_tree'):return
  tree=self.sd_deck_tree;tree.delete(*tree.get_children());occupied=0
  for slot,cid in enumerate(self.sd_deck):
   c=self.cards.get(cid) if cid else None;name=c.name if c else (CARD_NAMES.get(cid,f'Card {cid}') if cid else 'Empty slot');occupied+=bool(cid);tree.insert('','end',iid=str(slot),text=f'{slot+1:02d}  ·  {name}',image=self.mini_photo(cid) if cid else '',values=(cid if cid else '—',))
  self.sd_deck_count.configure(text=f'{occupied} / 40 occupied')
  if self.sd_selected_slot is not None and tree.exists(str(self.sd_selected_slot)):tree.selection_set(str(self.sd_selected_slot))
 def select_savedata_deck_slot(self,_=None):
  selected=self.sd_deck_tree.selection()
  if selected:self.sd_selected_slot=int(selected[0])
 def replace_savedata_deck_slot(self,_=None):
  if self.sd_doc is None or self.sd_selected_card is None:return messagebox.showinfo('Save Data Editor','Open a save, select a card, and select a deck slot first.')
  if self.sd_selected_slot is None:return messagebox.showinfo('Save Data Editor','Select one of the 40 deck slots first.')
  cid=self.sd_selected_card;old=self.sd_deck[self.sd_selected_slot]
  if old!=cid and self.sd_deck.count(cid)>=3:return messagebox.showerror('Deck copy limit','The game allows at most three copies of a card in the deck.')
  self.sd_deck[self.sd_selected_slot]=cid;self.refresh_savedata_deck();self.refresh_savedata_card_list();
  if self.sd_cards_tree.exists(str(cid)):self.sd_cards_tree.selection_set(str(cid));self.select_savedata_card()
 def clear_savedata_deck_slot(self):
  if self.sd_doc is None or self.sd_selected_slot is None:return messagebox.showinfo('Save Data Editor','Open a save and select a deck slot first.')
  self.sd_deck[self.sd_selected_slot]=0;self.refresh_savedata_deck();self.refresh_savedata_card_list()
 def fill_starter_cards(self):
  selected=self.starter_tree.selection()[0] if self.starter_tree.selection() else None;self.starter_tree.delete(*self.starter_tree.get_children());q=self.starter_query.get().strip().lower();entries=list(self.cards.cards.items())
  entries=[(i,c) for i,c in entries if self.starter_filter.criteria.matches(c)]
  if self.starter_sort.get()=='Card ID':entries.sort(key=lambda x:x[0])
  elif self.starter_sort.get()=='ATK':entries.sort(key=lambda x:(x[1].atk,x[1].name.lower()))
  elif self.starter_sort.get()=='DEF':entries.sort(key=lambda x:(x[1].def_,x[1].name.lower()))
  else:entries.sort(key=lambda x:x[1].name.lower())
  for cid,c in entries:
   if not q or q in c.name.lower() or q in str(cid):self.starter_tree.insert('','end',iid=str(cid),text=f'{c.name}   ·   {c.atk} / {c.def_}',image=self.mini_photo(cid))
  if selected and self.starter_tree.exists(selected):self.starter_tree.selection_set(selected);self.starter_tree.focus(selected);self.select_starter_card()
 def reset_starter_filters(self):
  self.starter_query.set('');self.starter_filter.reset();self.starter_sort.set('Name');self.fill_starter_cards()
 def reset_default_deck(self):
  self.deck_ids=[cid for cid in range(1,14) for _ in range(3)]+[14];self.dirty=True;self.refresh_deck_view()
 def randomize_starter_deck(self):
  if not self.cards.cards:return messagebox.showinfo('Random deck','Open a ROM before building a random deck.')
  monsters=[cid for cid,c in self.cards.cards.items() if 0<=c.type_id<20];support=[cid for cid,c in self.cards.cards.items() if 20<=c.type_id<24];style=self.random_deck_style.get()
  if style=='Balanced':groups=((monsters,32),(support,8))
  elif style=='Monster-heavy':groups=((monsters,36),(support,4))
  else:groups=((list(self.cards.cards),40),)
  counts={};deck=[]
  for pool,amount in groups:
   for _ in range(amount):
    available=[cid for cid in pool if counts.get(cid,0)<3]
    if not available:return messagebox.showerror('Random deck','There are not enough cards in this category to build a 40-card deck.')
    cid=random.choice(available);deck.append(cid);counts[cid]=counts.get(cid,0)+1
  random.shuffle(deck);self.deck_ids=deck;self.dirty=True;self.refresh_deck_view();self.status.configure(text=f'Built a random {style.lower()} starter deck with 40 cards and no more than three copies each.')
 def fill_random_deck_slots(self):
  if not self.cards.cards:return messagebox.showinfo('Random deck','Open a ROM before filling the deck.')
  remaining=40-len(self.deck_ids)
  if remaining<=0:return messagebox.showinfo('Deck is full','There are no empty slots to fill.')
  counts={}
  for cid in self.deck_ids:counts[cid]=counts.get(cid,0)+1
  updated=list(self.deck_ids);all_cards=list(self.cards.cards)
  for _ in range(remaining):
   available=[cid for cid in all_cards if counts.get(cid,0)<3]
   if not available:return messagebox.showerror('Random deck','There are not enough eligible cards to fill every empty slot.')
   cid=random.choice(available);updated.append(cid);counts[cid]=counts.get(cid,0)+1
  self.deck_ids=updated;self.dirty=True;self.refresh_deck_view();self.status.configure(text=f'Filled {remaining} empty deck slot(s) with random cards.')
 def reset_all_starter(self):
  self.reset_default_deck();self.player.set('PLAYER');self.chips.set('0');self.status.configure(text='Starter deck, player name, and starchips reset.')
 def select_starter_card(self,_=None):
  s=self.starter_tree.selection()
  if not s:return
  self.starter_selected=int(s[0]);c=self.cards.get(self.starter_selected);self.starter_name.configure(text=c.name);self.starter_stats.configure(text=f'{CARD_TYPES[c.type_id]}   •   {c.atk} ATK / {c.def_} DEF\nLevel {getattr(c,"level",0)}   •   {ATTRIBUTES[getattr(c,"attribute",0)]}\nGuardian Stars: {c.gs1_name} / {c.gs2_name}')
  im=self.art.get_card_art(self.starter_selected)
  if im:self.starter_photo=ImageTk.PhotoImage(self.render_card_preview(c,im));self.starter_art.configure(image=self.starter_photo,text='')
 def starter_add(self):
  if not getattr(self,'starter_selected',None):return
  self.add_card_to_starter_deck(self.starter_selected)
 def starter_card_name(self, cid):
  card = self.cards.get(cid)
  return card.name if card else CARD_NAMES.get(cid, str(cid))
 def add_card_to_starter_deck(self,cid):
  if len(self.deck_ids)>=40:return messagebox.showinfo('Deck is full','The starter deck has 40 cards.')
  if self.deck_ids.count(cid)>=3:return messagebox.showinfo('Copy limit','A starter deck can contain up to three copies of a card.')
  self.deck_ids.append(cid);self.dirty=True;self.refresh_deck_view();self.status.configure(text=f'Added {self.starter_card_name(cid)} to the starter deck.')
 def starter_library_add(self,event):
  row=self.starter_tree.identify_row(event.y)
  if not row:return
  def add_row():
   if not self.starter_tree.exists(row):return
   self.starter_tree.selection_set(row);self.starter_tree.focus(row);self.select_starter_card();self.add_card_to_starter_deck(int(row))
  self.after_idle(add_row)
 def starter_library_remove(self,event):
  row=self.starter_tree.identify_row(event.y)
  if not row:return
  self.starter_tree.selection_set(row);self.starter_tree.focus(row);self.select_starter_card()
  self.remove_card_from_starter_deck(int(row))
 def deck_right_remove(self,event):
  row=self.deck_tree.identify_row(event.y)
  if not row:return
  self.deck_tree.selection_set(row);self.deck_tree.focus(row);self.remove_card_from_starter_deck(int(row))
 def remove_card_from_starter_deck(self,cid):
  try:self.deck_ids.remove(cid)
  except ValueError:
   self.status.configure(text=f'{self.starter_card_name(cid)} has no copy in the starter deck.')
   return
  self.dirty=True;self.refresh_deck_view();self.status.configure(text=f'Removed one copy of {self.starter_card_name(cid)} from the starter deck.')
 def starter_remove(self):
  s=self.deck_tree.selection()
  if s:self.remove_card_from_starter_deck(int(s[0]))
 def starter_clear(self):
  self.deck_ids.clear();self.dirty=True;self.refresh_deck_view()
 def mini_photo(self,cid):
  if cid not in self.mini_photos:
   im=self.art._custom_artworks.get(cid)
   if im:im=im.convert('RGB')
   else:im=self.art._extract_mini_art(cid)
   thumb=Image.new('RGBA',(164,48))
   if im:
    thumb.paste(im.convert('RGB').resize((42,42),Image.Resampling.LANCZOS),(3,3))
    draw=ImageDraw.Draw(thumb);draw.rectangle((0,0,47,47),outline='#20242c',width=1);draw.rectangle((1,1,46,46),outline='#c9a963',width=1)
   card=self.cards.get(cid)
   if card:
    values=(('type',card.type_id),('attribute',card.attribute),('guardian',card.gs1),('guardian',card.gs2))
    for x,(kind,index) in zip((51,71,91,111),values):
     group=self.card_list_icons.get(kind,())
     icon=group[index] if 0<=index<len(group) else None
     if icon:thumb.alpha_composite(icon,(x,16))
    star=ImageDraw.Draw(thumb);cx,cy=139,24;points=[]
    for vertex in range(10):
     radius=8 if vertex%2==0 else 3.7;angle=-math.pi/2+vertex*math.pi/5;points.append((round(cx+radius*math.cos(angle)),round(cy+radius*math.sin(angle))))
    star.polygon(points,fill='#f5cf58',outline='#80662a');star.rounded_rectangle((147,15,163,33),radius=3,fill='#263040');star.text((149,17),str(getattr(card,'level',0)),fill='#f5cf58')
   self.mini_photos[cid]=ImageTk.PhotoImage(thumb)
  return self.mini_photos.get(cid,self.placeholder_photo)
 def refresh_deck_view(self):
  if not hasattr(self,'deck_tree'):return
  self.deck_tree.delete(*self.deck_tree.get_children());counts={}
  for cid in self.deck_ids:counts[cid]=counts.get(cid,0)+1
  for cid,count in counts.items():
   c=self.cards.get(cid);name=c.name if c else f'Card {cid}';self.deck_tree.insert('','end',iid=str(cid),text=f'{name}   ×{count}',image=self.mini_photo(cid))
  self.deck_count.configure(text=f'{len(self.deck_ids)} / 40 cards')
 def build_ui(self):
  page = self.build_page
  for col in range(2):page.columnconfigure(col,weight=1,uniform='export')
  self.dropcount = tk.StringVar(value='1')
  reward = ttk.LabelFrame(page,text='Victory rewards',padding=18)
  reward.grid(row=0,column=0,sticky='nsew',padx=(0,8))
  controls = ttk.Frame(reward)
  controls.pack(anchor='w')
  self.override_rewards = tk.BooleanVar(value=False)
  ttk.Checkbutton(controls, text='Override reward routine', variable=self.override_rewards).pack(side='left')
  self.reward_count_box = ttk.Spinbox(controls, textvariable=self.dropcount, from_=1, to=100, width=5)
  self.reward_count_box.pack(side='left', padx=(16, 5))
  ttk.Label(controls, text='cards per win (1–100)').pack(side='left')
  def sync_count_state(*_):
   self.reward_count_box.state(['!disabled' if self.override_rewards.get() else 'disabled'])
  self.override_rewards.trace_add('write', sync_count_state)
  sync_count_state()
  self.reward_rom_status=tk.StringVar(value='Open a ROM to identify its reward routine.')
  ttk.Label(reward,textvariable=self.reward_rom_status,font=('Segoe UI',10,'bold'),wraplength=430).pack(anchor='w',pady=(14,4))
  ttk.Label(reward,text='Enable the override to replace the card reward hooks. The results screen shows the first card. Extra rolls go directly to the trunk.',wraplength=430).pack(anchor='w',pady=(2,2))
  ttk.Button(reward,text='Reset reward settings',command=self.reset_build_tab).pack(anchor='w',pady=(14,0))
  output = ttk.LabelFrame(page,text='Disc for DuckStation',padding=18)
  output.grid(row=0,column=1,sticky='nsew',padx=(8,0))
  self.export_source = ttk.Label(output,text='Open a game image to build a disc.',wraplength=410)
  self.export_source.pack(anchor='w')
  self.export_format = ttk.Label(output,font=('Segoe UI',12,'bold'),wraplength=410)
  self.export_format.pack(anchor='w',pady=(10,16))
  actions = ttk.Frame(output)
  actions.pack(anchor='w')
  ttk.Button(actions,text='Build patched disc…',style='Primary.TButton',command=self.export).pack(side='left')
  ttk.Button(actions,text='Export BPS patch…',command=lambda:self.export(patch=True)).pack(side='left',padx=6)
  ttk.Label(output,text='Apply the BPS to the same source disc image in a BPS patcher. For a CUE, select its binary data track.',wraplength=410).pack(anchor='w',pady=(10,0))
  self.progress = ttk.Label(output,wraplength=410)
  self.progress.pack(anchor='w',pady=(12,0))
 def reset_build_tab(self):
  self.dropcount.set('1');self.override_rewards.set(True);self.dirty=True;self.status.configure(text='Reward count reset to one card per duel.')
 def configure_reward_controls(self, exe):
  kind, count = reward_layout(exe)
  self.dropcount.set(str(count or 1))
  self.override_rewards.set(kind in ('native', 'installed', 'legacy'))
  messages = {
   'native': 'Native reward routine. Multi-card rewards are available.',
   'installed': f'Workshop reward override detected: {count} cards per win.',
   'legacy': 'Earlier Workshop patch detected. Export with override enabled to restore the normal victory screen.',
   'custom hooks': 'Custom hooks found in a matching results controller. Enable override to replace these hooks.',
   'unsupported': 'Unknown results controller. Export with override off to keep its reward behavior.',
   'occupied': 'Reward patch space is occupied. Export with override off to keep the existing rewards.',
  }
  self.reward_rom_status.set(messages[kind])
 def open(self):
  f=filedialog.askopenfilename(filetypes=[('Disc images','*.img *.bin *.iso *.cue *.ccd'),('All files','*.*')])
  if not f:return
  if self.disc and self.dirty and not messagebox.askyesno('Discard unsaved edits','Opening another image will replace the current ROM edits. Continue?'):return
  stage='opening disc image'
  try:
   d=Disc(f);stage='extracting game files';e=d.extract_file('SLUS_014.11');w=d.extract_file('DATA/WA_MRG.MRG');self.disc=d;self.exe=bytearray(e);self.wa=bytearray(w)
   stage='building opponent portrait gallery';self.refresh_opponent_gallery()
   stage='checking duel reward code';self.configure_reward_controls(e)
   stage='loading card records';self.cards.load_from_exe_and_wa(e,w);self.original_cards=copy.deepcopy(self.cards.cards);self.original_wa=bytes(w)
   stage='loading card artwork';self.art._custom_artworks.clear();self.art.set_wa_data(w);self.card_list_icons=extract_card_list_icons(w);self.mini_photos.clear()
   self.refresh_banner_art()
   stage='loading fusion data';self.fusions.load_from_wa(w)
   self.undo_recipe_state = None
   self.undo_recipe_button.state(['disabled'])
   self.new_pairs_only.set(False)
   self.reset_recipe_search()
   self.collection_filter.reset()
   self.collection_filter.state(["!disabled"])
   for i in range(2):
    self.material_choices[i].clear()
   stage='resetting card and list filters';self.reset_card_filters();self.starter_query.set('');self.starter_filter.reset();self.starter_sort.set('Name');self.fusion_query.set('');self.fusion_sort.set('Result name');self.drop_query.set('');self.drop_filter.reset();self.drop_sort.set('Card name')
   stage='building Card Studio list';self.fill()
   stage='building starter deck card list';self.fill_starter_cards()
   stage='building fusion card selectors';self.set_card_picker_values();self.refresh_deck_view()
   self.dirty=False;self.status.configure(text=f'{Path(f).name} • {len(self.cards.cards):,} cards');selected='1' if self.tree.exists('1') else next(iter(self.tree.get_children()),None)
   stage='selecting the first card'
   if selected:self.tree.selection_set(selected);self.select()
   stage='building fusion recipe list';self.load_fusions()
   stage='building opponent drop list';self.load_drops()
   self.export_source.configure(text=f'Source disc: {Path(f).name}')
   extension = '.iso' if d.sector_size == 2048 else '.bin + .cue'
   self.export_format.configure(text=f'{OUTPUT_BASENAME}{extension}')
   if self.sd_doc is not None:self.refresh_savedata_card_list();self.refresh_savedata_deck()
  except Exception as ex:
   details=traceback.format_exc();log=Path(__file__).with_name('rom_open_error.log')
   try:log.write_text(f'ROM: {f}\nStage: {stage}\n\n{details}',encoding='utf-8')
   except OSError:log=None
   hint=f'Full traceback saved to:\n{log}' if log else 'Could not save the traceback beside the editor.'
   messagebox.showerror('Could not open ROM',f'Failed while {stage}.\n{type(ex).__name__}: {ex!r}\n\n{hint}')
 def fusion_add(self):
  try:
   result=self.card_from_option(self.fv[2].get())
   if result is None:raise ValueError('Select a result card.')
   material_sets=[set(self.material_card_ids(i)) for i in range(2)]
   overlap=len(material_sets[0]&material_sets[1]);pair_count=len(material_sets[0])*len(material_sets[1])-overlap*(overlap-1)//2 if all(material_sets) else 0
   if not pair_count:raise ValueError('Choose a card or at least one matching card for each material.')
   if pair_count>5000 and not messagebox.askyesno('Large fusion batch',f'These filters expand to {pair_count:,} recipe pairs. The editor will check whether the complete batch fits before changing anything. Continue?'):return
   pairs=self.expanded_material_pairs()
   if self.new_pairs_only.get():
    pairs.difference_update(self.fusions.fusions)
    if not pairs:return messagebox.showinfo('Fusion Lab', 'All matching pairs already have recipes.')
   trial=FusionDatabase();trial.raw_table=bytearray(self.fusions.raw_table);trial.fusions=dict(self.fusions.fusions)
   self.fusion_summary.configure(text=f'Applying {len(pairs):,} card pairs…');self.update_idletasks();trial.fusions.update((pair,result) for pair in pairs)
   if not trial.compact():raise ValueError(f'The selected filters expand to {len(pairs):,} recipes, which do not fit in the game fusion table. Narrow the filters or add exceptions.')
   self.replace_recipes(trial);messagebox.showinfo('Fusion recipe',f'Added or updated {len(pairs):,} card pair(s) to produce {self.cards.get(result).name}.')
  except Exception as e:self.update_fusion_summary();messagebox.showerror('Fusion',str(e))
 def fusion_del(self):
  if self.ft.selected is not None:
   a,b,_=self.ft.rows[self.ft.selected]
   trial = FusionDatabase()
   trial.raw_table = self.fusions.raw_table.copy()
   trial.fusions = self.fusions.fusions.copy()
   if not trial.delete_fusion(a,b):return messagebox.showerror('Fusion recipe','There is not enough free space to safely detach this shared recipe list.')
   self.replace_recipes(trial)
 def load_fusions(self, page=0):
  if not hasattr(self,'ft'):return
  query=self.fusion_query.get().strip().lower();rows=[]
  from collections import Counter
  deck = Counter(getattr(self,"deck_ids",())) if self.fusion_deck_only.get() else None
  scope = self.fusion_scope.get()
  for (a,b),r in self.fusions.fusions.items():
   if deck is not None and (deck[a] < 1 or deck[b] < 1 + (a == b)):continue
   ca=self.cards.get(a);cb=self.cards.get(b);cr=self.cards.get(r)
   if ca is None or cb is None or cr is None:continue
   if not self.result_filter.criteria.matches(cr):continue
   na=ca.name;nb=cb.name;nr=cr.name
   if query:
    fields = ((a,na),(b,nb)) if scope=='Material' else ((r,nr),) if scope=='Result' else ((a,na),(b,nb),(r,nr))
    if query.startswith('#'):
     if not any(query==f'#{cid}' for cid,_ in fields):continue
    elif not any(query in name.lower() or query==str(cid) for cid,name in fields):continue
   rows.append((a,b,r,na,nb,nr))
  if self.fusion_sort.get()=='Material name':rows.sort(key=lambda x:(x[3].lower(),x[4].lower(),x[5].lower()))
  elif self.fusion_sort.get()=='Card ID':rows.sort(key=lambda x:(x[0],x[1],x[2]))
  else:rows.sort(key=lambda x:(x[5].lower(),x[3].lower(),x[4].lower()))
  pages = max(1,(len(rows)+99)//100)
  self.recipe_page = max(0,min(page,pages-1))
  start = self.recipe_page*100
  self.ft.set_rows([row[:3] for row in rows[start:start+100]])
  self.recipe_prev.state(['disabled' if self.recipe_page==0 else '!disabled'])
  self.recipe_next.state(['disabled' if self.recipe_page+1>=pages else '!disabled'])
  self.fusion_count.configure(text=f'{len(rows):,} matches · Page {self.recipe_page+1} of {pages}')
 def load_drops(self):
  if not self.wa or not hasattr(self,'dt'):return
  if self.duelist.get() not in DUELISTS:self.duelist.set(DUELISTS[0])
  d=DUELISTS.index(self.duelist.get());self.drop_title.configure(text=self.duelist.get());self.dt.delete(*self.dt.get_children());self.drop_weights={};pool=['S/A POW','B/C/D','S/A TEC'].index(self.pool.get());base=0xE9B000+d*0x1800+(pool+1)*1460;rows=[];query=self.drop_query.get().strip().lower()
  for i in range(722):
   weight=struct.unpack_from('<H',self.wa,base+i*2)[0]
   if weight:
    cid=i+1;c=self.cards.get(cid)
    if c is None:continue
    if query and query not in c.name.lower() and query not in str(cid):continue
    if not self.drop_filter.criteria.matches(c):continue
    self.drop_weights[cid]=weight;rows.append((cid,c,weight))
  if self.drop_sort.get()=='Card ID':rows.sort(key=lambda x:x[0])
  elif self.drop_sort.get()=='Weight':rows.sort(key=lambda x:(x[2],x[1].name.lower()),reverse=True)
  elif self.drop_sort.get()=='Chance':rows.sort(key=lambda x:(x[2]/2048,x[1].name.lower()),reverse=True)
  else:rows.sort(key=lambda x:x[1].name.lower())
  for cid,c,weight in rows:self.dt.insert('','end',iid=str(cid),text=c.name,values=(weight,f'{weight/2048*100:.2f}%'),image=self.mini_photo(cid))
  try:
   im=portraits.read(self.wa,d+1);self.dp_photo=ImageTk.PhotoImage(im.resize((160,160),Image.Resampling.NEAREST));self.dp.configure(image=self.dp_photo,text='')
  except Exception:self.dp.configure(image='',text='Portrait unavailable')
  if self.opponent_tree.exists(str(d+1)):
   try:
    im=portraits.read(self.wa,d+1).resize((48,48),Image.Resampling.NEAREST);photo=ImageTk.PhotoImage(im);self.opponent_photos[d+1]=photo;self.opponent_tree.item(str(d+1),image=photo)
   except Exception:pass
 def reset_drop_filters(self):
  self.drop_query.set('');self.drop_filter.reset();self.drop_sort.set('Card name');self.duelist.set(DUELISTS[0]);self.pool.set('S/A POW')
  if self.opponent_tree.exists('1'):self.opponent_tree.selection_set('1');self.opponent_tree.see('1')
  self.load_drops()
 def reset_drop_pool(self):
  if not self.wa or not hasattr(self,'original_wa'):return
  d=DUELISTS.index(self.duelist.get());pool=['S/A POW','B/C/D','S/A TEC'].index(self.pool.get());start=0xE9B000+d*0x1800+(pool+1)*1460;self.wa[start:start+1444]=self.original_wa[start:start+1444];self.dirty=True;self.load_drops()
 def reset_all_drops(self):
  if not self.wa or not hasattr(self,'original_wa'):return messagebox.showinfo('Duelist Drops','Open a ROM before resetting opponent data.')
  for duelist in range(len(DUELISTS)):
   for pool in range(3):
    start=0xE9B000+duelist*0x1800+(pool+1)*1460;self.wa[start:start+1444]=self.original_wa[start:start+1444]
  for portrait_id in range(1,len(DUELISTS)+1):
   start=portraits.BASE+portrait_id*portraits.RECORD;end=start+portraits.RECORD;self.wa[start:end]=self.original_wa[start:end]
  self.dirty=True;self.refresh_opponent_gallery();self.load_drops();self.status.configure(text='All opponent drop lists and portraits reset to the loaded ROM.')
 def import_portrait(self):
  f=filedialog.askopenfilename(filetypes=[('Images','*.png *.jpg *.jpeg *.bmp *.webp')])
  if f and self.wa:
   try:portraits.write(self.wa,DUELISTS.index(self.duelist.get())+1,Image.open(f));self.dirty=True;self.refresh_opponent_gallery();self.load_drops()
   except Exception as e:messagebox.showerror('Opponent portrait',str(e))
 def edit_drop(self,e):
  s=self.dt.selection()
  if not s:return
  from tkinter import simpledialog
  cid=int(s[0]);v=simpledialog.askinteger('Drop weight',f'{self.cards.get(cid).name} weight (0–2048)',initialvalue=self.drop_weights.get(cid,0),minvalue=0,maxvalue=2048)
  if v is not None:
   d=DUELISTS.index(self.duelist.get());pool=['S/A POW','B/C/D','S/A TEC'].index(self.pool.get());struct.pack_into('<H',self.wa,0xE9B000+d*0x1800+(pool+1)*1460+(cid-1)*2,v);self.dirty=True;self.load_drops()
 def drop_context_menu(self,event):
  row=self.dt.identify_row(event.y)
  if not row:return
  self.dt.selection_set(row);self.dt.focus(row);menu=tk.Menu(self,tearoff=False);menu.add_command(label='Edit drop weight…',command=lambda:self.edit_drop(None));menu.add_command(label='Remove card from this pool',command=lambda:self.set_drop_weight(int(row),0));menu.tk_popup(event.x_root,event.y_root)
 def set_drop_weight(self,cid,value):
  d=DUELISTS.index(self.duelist.get());pool=['S/A POW','B/C/D','S/A TEC'].index(self.pool.get());offset=0xE9B000+d*0x1800+(pool+1)*1460+(cid-1)*2;struct.pack_into('<H',self.wa,offset,value);self.dirty=True;self.load_drops()
 def add_drop(self):
  win=tk.Toplevel(self);win.title('Choose a card for this reward pool');win.geometry('720x600');win.transient(self);win.grab_set();win.columnconfigure(0,weight=1);win.rowconfigure(1,weight=1);query=tk.StringVar();entry=ttk.Entry(win,textvariable=query);entry.grid(row=0,column=0,sticky='ew',padx=12,pady=12);list_frame=ttk.Frame(win);list_frame.grid(row=1,column=0,sticky='nsew',padx=12);list_frame.columnconfigure(0,weight=1);list_frame.rowconfigure(0,weight=1);tree=ttk.Treeview(list_frame,columns=('stats',),show='tree headings');tree.heading('#0',text='CARD · TYPE / ATTRIBUTE / STARS');tree.heading('stats',text='ATK / DEF');tree.column('#0',width=500);tree.column('stats',width=130,anchor='center');tree.grid(row=0,column=0,sticky='nsew');scroll=ttk.Scrollbar(list_frame,orient='vertical',command=tree.yview);scroll.grid(row=0,column=1,sticky='ns');tree.configure(yscrollcommand=scroll.set)
  def fill_choices(*_):
   tree.delete(*tree.get_children());needle=query.get().strip().lower()
   for cid,c in self.cards.cards.items():
    if not choices_filter.criteria.matches(c):continue
    if not needle or needle in c.name.lower() or needle in str(cid):tree.insert('','end',iid=str(cid),text=f'{c.name}   ·   {c.atk} / {c.def_}',image=self.mini_photo(cid))
  choices_filter=self.filter_button(win,fill_choices);choices_filter.grid(row=0,column=1,padx=8)
  def choose(_=None):
   if not tree.selection():return
   cid=int(tree.selection()[0]);d=DUELISTS.index(self.duelist.get());pool=['S/A POW','B/C/D','S/A TEC'].index(self.pool.get());off=0xE9B000+d*0x1800+(pool+1)*1460+(cid-1)*2
   if struct.unpack_from('<H',self.wa,off)[0]==0:struct.pack_into('<H',self.wa,off,1)
   self.dirty=True;self.load_drops();win.destroy()
   if self.dt.exists(str(cid)):self.dt.selection_set(str(cid))
  query.trace_add('write',fill_choices);entry.bind('<Return>',lambda e:choose());tree.bind('<Double-1>',choose);fill_choices();buttons=ttk.Frame(win);buttons.grid(row=2,column=0,sticky='e',padx=12,pady=10);ttk.Button(buttons,text='Cancel',command=win.destroy).pack(side='right',padx=4);ttk.Button(buttons,text='Add selected card',command=choose).pack(side='right',padx=4)
 def normalize_pool(self):
  d=DUELISTS.index(self.duelist.get());pool=['S/A POW','B/C/D','S/A TEC'].index(self.pool.get());base=0xE9B000+d*0x1800+(pool+1)*1460;weights=[struct.unpack_from('<H',self.wa,base+i*2)[0] for i in range(722)];total=sum(weights)
  if total==0:return messagebox.showerror('Empty drop pool','Add at least one card before balancing the pool.')
  active=[(i,w) for i,w in enumerate(weights) if w];scaled=[0]*722;used=0
  for i,w in active:scaled[i]=max(1,round(w*2048/total));used+=scaled[i]
  best=max(active,key=lambda p:p[1])[0];scaled[best]=max(1,scaled[best]+2048-used)
  for i,w in enumerate(scaled):struct.pack_into('<H',self.wa,base+i*2,w)
  self.dirty=True;self.load_drops()
 def art_import(self):
  f=filedialog.askopenfilename(filetypes=[('Images','*.png *.jpg *.jpeg *.bmp *.webp')])
  if f:
   try:
    with Image.open(f) as source:self.art.set_custom_art(self.current,source.convert('RGB'))
    self.mini_photos.pop(self.current,None);self.dirty=True;self.fill();self.fill_starter_cards();self.refresh_deck_view();self.load_fusions();self.load_drops()
    if self.tree.exists(str(self.current)):self.tree.selection_set(str(self.current));self.tree.focus(str(self.current));self.tree.see(str(self.current))
    self.show_card_preview(self.current);self.status.configure(text=f'Artwork updated for {self.cards.get(self.current).name}; export to patch the game image')
   except Exception as e:messagebox.showerror('Artwork import',str(e))
 def save_mcd(self):
  if not self.exe:return messagebox.showinfo('ROM','Open a ROM first.')
  try:
   if len(self.deck_ids)!=40:raise ValueError(f'Starter deck must contain exactly 40 cards; it currently has {len(self.deck_ids)}.')
   data=create_card(self.exe,self.deck_ids,self.player.get(),int(self.chips.get()));f=filedialog.asksaveasfilename(defaultextension='.mcd',filetypes=[('PS1 memory card','*.mcd')],initialfile=f'{OUTPUT_BASENAME}.mcd')
   if f:Path(f).write_bytes(data);messagebox.showinfo('Saved',f'Created {f}')
  except Exception as e:messagebox.showerror('Memory card',str(e))
 def export(self, *, patch=False):
  if getattr(self,"building",False):return
  if not self.disc:return messagebox.showinfo('ROM','Open a ROM image first.')
  try:
   if not self.apply_card():return
   rawcount=int(self.dropcount.get()) if self.override_rewards.get() else 1
   if not 1<=rawcount<=100:raise ValueError('The card count must be between 1 and 100.')
   out_exe=bytearray(self.exe);out_wa=bytearray(self.wa)
   legacy_frame_patch_removed=remove_legacy_frame_color_patch(out_exe)
   self.cards.save_to_exe_and_wa(out_exe,out_wa)
   # Guardian stars are the two 4-bit fields consumed by the duel engine.
   # Write them explicitly after the full stats serializer so no other card
   # field or legacy metadata can mask these bits.
   guardian_mask=(0xF<<18)|(0xF<<22)
   for cid,card in self.cards.cards.items():
    stat_offset=SLUS_STATS_OFFSET+(cid-1)*4;word=struct.unpack_from('<I',out_exe,stat_offset)[0]
    word=(word&~guardian_mask)|((card.gs2&0xF)<<18)|((card.gs1&0xF)<<22)
    struct.pack_into('<I',out_exe,stat_offset,word)
   self.fusions.save_to_wa(out_wa);self.art.apply_to_wa(out_wa,self.cards.cards,self.original_cards)
   serialized=CardDatabase();serialized.load_from_exe_and_wa(out_exe,out_wa)
   for cid,expected in self.cards.cards.items():
    actual=serialized.cards[cid]
    fields=('name','atk','def_','type_id','gs1','gs2','level','attribute','star_cost','password','description')
    mismatch=[field for field in fields if getattr(expected,field,None)!=getattr(actual,field,None)]
    if mismatch:raise ValueError(f'Card {cid} ({expected.name}) did not survive ROM serialization: {", ".join(mismatch)}.')
    stat_word=struct.unpack_from('<I',out_exe,SLUS_STATS_OFFSET+(cid-1)*4)[0]
    if ((stat_word>>22)&0xF)!=expected.gs1 or ((stat_word>>18)&0xF)!=expected.gs2:raise ValueError(f'Card {cid} ({expected.name}) guardian stars failed binary verification.')
   if self.override_rewards.get():
    set_reward_count(self.exe, out_exe, rawcount)
    reward_note = f'{rawcount} card(s) per win. The first card appears on the results screen.'
   else:
    kind, count = reward_layout(self.exe)
    if kind == 'installed':
     set_reward_count(self.exe, out_exe, count)
    reward_note = 'Kept the reward routine from the loaded disc.'
   if legacy_frame_patch_removed:reward_note=(reward_note+' Removed the obsolete frame-color game patch.').strip()
   output_ext='.iso' if self.disc.sector_size==2048 else '.bin'
   if patch:output_ext='.bps'
   filetypes=[('BPS patch','*.bps')] if patch else [('PS1 disc image','*.bin *.iso')]
   f=filedialog.asksaveasfilename(defaultextension=output_ext,initialfile=f'{OUTPUT_BASENAME}{output_ext}',filetypes=filetypes)
   if f:
    self.progress.configure(text='Preparing patched image…');self.nb.state(['disabled']);self.open_btn.state(['disabled']);self.building=True
    for button in self.page_nav_buttons.values():button.state(['disabled'])
    def worker():
     try:
      self.disc.export(f,{'SLUS_014.11':bytes(out_exe),'DATA/WA_MRG.MRG':bytes(out_wa)},lambda p,s:self.events.put(('progress',s)),patch=patch)
      self.events.put(('done',(f,reward_note,patch)))
     except Exception as e:self.events.put(('error',str(e)))
    threading.Thread(target=worker,daemon=True).start()
  except Exception as e:messagebox.showerror('Export failed',str(e))
 def poll_events(self):
  try:
   while True:
    kind,value=self.events.get_nowait()
    if kind=='progress':self.progress.configure(text=value)
    elif kind=='done':
     self.nb.state(['!disabled']);self.open_btn.state(['!disabled']);self.building=False
     for button in self.page_nav_buttons.values():button.state(['!disabled'])
     path,note,patch=value
     self.dirty=False
     if patch:
      description=f'BPS patch created ({Path(path).stat().st_size:,} bytes). Apply it to {self.disc.path.name}.'
     else:
      description='Patched disc verified.' if self.disc.sector_size==2048 else 'Patched disc verified. Open the companion CUE in DuckStation.'
     self.progress.configure(text=f'Exported {Path(path).name}')
     messagebox.showinfo('Export finished',f'{description}\n{path}\n\n{note}')

    else:
     self.nb.state(['!disabled']);self.open_btn.state(['!disabled']);self.building=False
     for button in self.page_nav_buttons.values():button.state(['!disabled'])
     messagebox.showerror('Export failed',value)
  except queue.Empty:pass
  self.after(100,self.poll_events)
 def close_app(self):
  if getattr(self,'building',False):return messagebox.showinfo('Export in progress','Wait for the image export to finish before closing the editor.')
  if self.dirty and not messagebox.askyesno('Unsaved edits','You have edits that are not in an exported disc. Close anyway?'):return
  self.destroy()
if __name__=='__main__':App().mainloop()
