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
from .save_data import SaveDataDocument, SaveDataError
from . import portraits

ATTRIBUTES=['Light','Dark','Earth','Water','Fire','Wind','Magic','Trap']
CARD_TYPE_FRAME_COLORS={20:'#2b9a72',21:'#bb4b83',22:'#557db5',23:'#2b9a72'}
DUELISTS=OPPONENT_NAMES
OUTPUT_BASENAME='Yu-Gi-Oh! - Forbidden Memories'
RETAIL_US_EXE_SHA256='84a54ed74f3d0edd6d81380839f7e4ef5bfb21ecea18be9a062bd6bfa5a45c88'
RETAIL_REWARD_HOOKS=((0x12460,bytes.fromhex('0486000c21800000e002848f1d80033c0a80013c38b322a43c0082a40014020003140200a85662ac3a00829000000000')),(0x12710,bytes.fromhex('3c0044842586000c000000002788000800000000')))
REWARD_CODE_CAVES=((0x1cbc30,0x1cbc98),(0x1cbf60,0x1cc020),(0x1cc730,0x1cc7a4))
REWARD_PROTECTED_RANGES=((0x12460,0x12490),(0x12710,0x12724))+REWARD_CODE_CAVES
COLOR_SCHEMES={'Midnight':('#111827','#1d293b','#172235','#eef2ff','#263449'),'Light':('#edf1f7','#ffffff','#f4f6fa','#202938','#ffffff'),'Forest':('#0e1f1b','#19332c','#132820','#e5f5eb','#234337'),'Plum':('#211725','#38253c','#2a1c30','#fff0ff','#49304f')}
class App(tk.Tk):
 def __init__(self):
  super().__init__();self.title('Forbidden Memories Workshop');self.geometry('1440x900');self.minsize(1180,780);self.configure(bg='#111827');self._layout_counter=0;self.disc=None;self.exe=None;self.wa=None;self.card_list_icons={};self.dirty=False;self.cards=CardDatabase();self.art=CardGraphicsDatabase();self.fusions=FusionDatabase();self.current=1;self.v={};self.events=queue.Queue();self.after(100,self.poll_events);self.protocol('WM_DELETE_WINDOW',self.close_app)
  style=ttk.Style(self);style.theme_use('clam');self.color_scheme=tk.StringVar(value='Midnight');self.apply_color_scheme()
  shell=ttk.Frame(self,style='App.TFrame');shell.pack(fill='both',expand=True);shell.columnconfigure(1,weight=1);shell.rowconfigure(0,weight=1)
  sidebar=ttk.Frame(shell,style='Sidebar.TFrame',padding=(12,14),width=205);sidebar.grid(row=0,column=0,sticky='ns');sidebar.grid_propagate(False);sidebar.rowconfigure(8,weight=1)
  ttk.Label(sidebar,text='FM',font=('Segoe UI',25,'bold'),style='Brand.TLabel').pack(anchor='w',padx=7);ttk.Label(sidebar,text='WORKSHOP',font=('Segoe UI',10,'bold'),style='Brand.TLabel').pack(anchor='w',padx=9,pady=(0,22))
  sections=(('cards','01','Card Studio'),('fusion','02','Fusion Lab'),('drops','03','Duelist Drops'),('starter','04','Starter Deck & Save'),('savedata','05','Save Data Editor'),('export','06','Rewards & Export'))
  self.page_frames={};self.page_nav_buttons={};self.page_titles={key:title for key,number,title in sections}
  for key,number,title in sections:
   button=ttk.Button(sidebar,text=f'{number}   {title}',style='Nav.TButton',command=lambda page=key:self.show_page(page));button.pack(fill='x',pady=3);self.page_nav_buttons[key]=button
  ttk.Label(sidebar,text='USA DISC EDITOR\nDuckStation ready',style='BrandNote.TLabel',justify='left').pack(side='bottom',anchor='w',padx=8,pady=12)
  workspace=ttk.Frame(shell,style='App.TFrame');workspace.grid(row=0,column=1,sticky='nsew');workspace.columnconfigure(0,weight=1);workspace.rowconfigure(1,weight=1)
  head=ttk.Frame(workspace,padding=(20,14));head.grid(row=0,column=0,sticky='ew');head.columnconfigure(0,weight=1);titlebox=ttk.Frame(head);titlebox.grid(row=0,column=0,sticky='w');self.page_heading=ttk.Label(titlebox,text='Card Studio',font=('Segoe UI',17,'bold'));self.page_heading.pack(anchor='w');self.page_note=ttk.Label(titlebox,text='Card data, artwork, type, attribute, level, and Guardian Stars');self.page_note.pack(anchor='w',pady=(2,0))
  controls=ttk.Frame(head);controls.grid(row=0,column=1,sticky='e');self.status=ttk.Label(controls,text='Open a USA Forbidden Memories image',wraplength=270,justify='right');self.status.pack(side='left',padx=(0,12));ttk.Label(controls,text='Theme').pack(side='left',padx=(0,4));theme=ttk.Combobox(controls,textvariable=self.color_scheme,values=list(COLOR_SCHEMES),state='readonly',width=10);theme.pack(side='left',padx=(0,8));theme.bind('<<ComboboxSelected>>',lambda e:self.apply_color_scheme());self.open_btn=ttk.Button(controls,text='Open ROM image',command=self.open);self.open_btn.pack(side='left')
  self.nb=ttk.Frame(workspace,style='App.TFrame');self.nb.grid(row=1,column=0,sticky='nsew',padx=10,pady=(0,10));self.nb.columnconfigure(0,weight=1);self.nb.rowconfigure(0,weight=1)
  self.cards_page=ttk.Frame(self.nb,padding=12);self.cards_page.grid(row=0,column=0,sticky='nsew');self.page_frames['cards']=self.cards_page;self.card_ui()
  self.fusion_page=ttk.Frame(self.nb,padding=12);self.fusion_page.grid(row=0,column=0,sticky='nsew');self.page_frames['fusion']=self.fusion_page;self.fusion_ui()
  self.drop_page=ttk.Frame(self.nb,padding=12);self.drop_page.grid(row=0,column=0,sticky='nsew');self.page_frames['drops']=self.drop_page;self.drop_ui()
  self.save_page=ttk.Frame(self.nb,padding=12);self.save_page.grid(row=0,column=0,sticky='nsew');self.page_frames['starter']=self.save_page;self.save_ui()
  self.savedata_page=ttk.Frame(self.nb,padding=12);self.savedata_page.grid(row=0,column=0,sticky='nsew');self.page_frames['savedata']=self.savedata_page;self.savedata_ui()
  self.build_page=ttk.Frame(self.nb,padding=22);self.build_page.grid(row=0,column=0,sticky='nsew');self.page_frames['export']=self.build_page;self.build_ui();self.show_page('cards')
 def show_page(self,key):
  page=self.page_frames.get(key)
  if page is None:return
  page.tkraise();self.page_heading.configure(text=self.page_titles[key]);notes={'cards':'Card data, artwork, type, attribute, level, and Guardian Stars','fusion':'Build recipes from exact cards or filtered material groups','drops':'Opponent portraits, reward pools, and individual card drops','starter':'Build a 40-card starting deck and create a memory card','savedata':'Edit a player profile, collection, and saved deck','export':'Duel reward count and patched disc output'};self.page_note.configure(text=notes.get(key,''))
  for name,button in self.page_nav_buttons.items():button.configure(style='NavActive.TButton' if name==key else 'Nav.TButton')
 def has_retail_reward_layout(self,exe):
  return all(exe[offset:offset+len(expected)]==expected for offset,expected in RETAIL_REWARD_HOOKS) and not any(exe[start:end] for start,end in REWARD_CODE_CAVES)
 def apply_color_scheme(self):
  root,panel,surface,fg,field=COLOR_SCHEMES[self.color_scheme.get()];self.configure(bg=root);s=ttk.Style(self)
  r,g,b=(int(field[i:i+2],16) for i in (1,3,5));field_fg='#172235' if (r*299+g*587+b*114)/1000>145 else '#f4f6fa'
  s.configure('.',background=panel,foreground=fg,fieldbackground=field);s.configure('TFrame',background=panel);s.configure('TLabel',background=panel,foreground=fg);s.configure('TLabelframe',background=panel,foreground=fg);s.configure('TLabelframe.Label',background=panel,foreground=fg);s.configure('TButton',background=surface,foreground=fg)
  s.configure('TEntry',fieldbackground=field,foreground=field_fg);s.configure('TSpinbox',fieldbackground=field,foreground=field_fg);s.configure('TCombobox',fieldbackground=field,foreground=field_fg);s.map('TCombobox',fieldbackground=[('readonly',field),('disabled',field)],foreground=[('readonly',field_fg),('disabled',field_fg)])
  s.configure('App.TFrame',background=root);s.configure('Sidebar.TFrame',background=root);s.configure('Brand.TLabel',background=root,foreground=fg);s.configure('BrandNote.TLabel',background=root,foreground=fg,font=('Segoe UI',9));s.configure('Nav.TButton',background=root,foreground=fg,anchor='w',padding=(11,10),relief='flat',borderwidth=0);s.map('Nav.TButton',background=[('active',surface),('pressed',surface)],foreground=[('active',fg),('pressed',fg)]);s.configure('NavActive.TButton',background='#3b6ea8',foreground='#ffffff',anchor='w',padding=(11,10),relief='flat',borderwidth=0);s.map('NavActive.TButton',background=[('active','#477eb8'),('pressed','#315f92')],foreground=[('active','#ffffff'),('pressed','#ffffff')])
  s.configure('Treeview',background=surface,foreground=fg,fieldbackground=surface,rowheight=50);s.map('Treeview',background=[('selected','#3b6ea8')],foreground=[('selected','#ffffff')])
  self.option_add('*TCombobox*Listbox.background',field);self.option_add('*TCombobox*Listbox.foreground',field_fg);self.option_add('*TCombobox*Listbox.selectBackground','#3b6ea8');self.option_add('*TCombobox*Listbox.selectForeground','#ffffff')
  if hasattr(self,'desc'):self.desc.configure(bg=field,fg=field_fg,insertbackground=field_fg)
 def add_layout_picker(self,parent,tree,resolver,manager):
  self._layout_counter+=1;style=f'FMList{self._layout_counter}.Treeview';ttk.Style(self).configure(style,rowheight=50);tree.configure(style=style);tree._fm_compact=False;box=ttk.Combobox(parent,values=['Artwork rows','Compact rows'],state='readonly',width=13);box.set('Artwork rows')
  def change(_=None):
   compact=box.get()=='Compact rows';tree._fm_compact=compact;ttk.Style(self).configure(style,rowheight=27 if compact else 50)
   for iid in tree.get_children(''):
    cid=resolver(iid)
    if compact:tree.item(iid,image='')
    elif cid:tree.item(iid,image=self.mini_photo(cid))
  box.bind('<<ComboboxSelected>>',change);manager(box);return box
 def row_image(self,tree,cid):
  return '' if getattr(tree,'_fm_compact',False) else self.mini_photo(cid)
 def card_ui(self):
  p=self.cards_page;p.columnconfigure(0,weight=4,minsize=360);p.columnconfigure(1,weight=6,minsize=600);p.rowconfigure(1,weight=1);self.query=tk.StringVar();self.card_sort=tk.StringVar(value='Name');self.card_type_filter=tk.StringVar(value='All types');tools=ttk.Frame(p);tools.grid(row=0,column=0,sticky='ew');tools.columnconfigure(0,weight=1);q=ttk.Entry(tools,textvariable=self.query);q.grid(row=0,column=0,sticky='ew');q.bind('<KeyRelease>',lambda e:self.fill());ttk.Combobox(tools,textvariable=self.card_type_filter,values=['All types']+CARD_TYPES,state='readonly',width=15).grid(row=0,column=1,padx=4);ttk.Combobox(tools,textvariable=self.card_sort,values=['Name','Card ID','ATK','DEF','Level'],state='readonly',width=10).grid(row=0,column=2,padx=4);self.card_type_filter.trace_add('write',lambda *_:self.fill());self.card_sort.trace_add('write',lambda *_:self.fill());ttk.Button(tools,text='Reset filters',command=self.reset_card_filters).grid(row=0,column=3)
  card_list=ttk.Frame(p);card_list.grid(row=1,column=0,sticky='nsew',pady=8);card_list.columnconfigure(0,weight=1);card_list.rowconfigure(0,weight=1);self.tree=ttk.Treeview(card_list,show='tree');self.tree.heading('#0',text='CARD · TYPE · ATTRIBUTE · GUARDIAN · LEVEL · ATK / DEF');self.tree.column('#0',width=360);self.tree.grid(row=0,column=0,sticky='nsew');card_scroll=ttk.Scrollbar(card_list,orient='vertical',command=self.tree.yview);card_scroll.grid(row=0,column=1,sticky='ns');self.tree.configure(yscrollcommand=card_scroll.set);self.tree.bind('<<TreeviewSelect>>',self.select);self.tree.bind('<Button-3>',self.card_context_menu);self.tree.bind('<Button-2>',self.card_context_menu);self.add_layout_picker(tools,self.tree,lambda iid:int(iid),lambda w:w.grid(row=0,column=4,padx=4))
  ttk.Label(p,text='Game icons: type · attribute · guardian stars 1 and 2 · level star',font=('Segoe UI',9)).grid(row=2,column=0,sticky='w')
  editor=ttk.Frame(p);editor.grid(row=0,column=1,rowspan=2,sticky='nsew',padx=(14,0));editor.columnconfigure(0,weight=0,minsize=280);editor.columnconfigure(1,weight=1,minsize=300);editor.rowconfigure(0,weight=1)
  preview=ttk.LabelFrame(editor,text='CARD PREVIEW',padding=10);preview.grid(row=0,column=0,sticky='n',padx=(0,14),pady=4);self.pic=ttk.Label(preview,text='Open a ROM to view a card',anchor='center');self.pic.pack(pady=(0,8));ttk.Button(preview,text='Change artwork…',command=self.art_import).pack(fill='x',pady=3);ttk.Button(preview,text='Reset selected card',command=self.reset_card).pack(fill='x',pady=3)
  fields=ttk.LabelFrame(editor,text='CARD DATA',padding=12);fields.grid(row=0,column=1,sticky='nsew',pady=4);fields.columnconfigure(1,weight=1)
  for i,(label,key) in enumerate([('Name','name'),('ATK','atk'),('DEF','def_'),('Level / stars','level'),('Type','type_id'),('Attribute','attribute'),('Guardian star 1','gs1'),('Guardian star 2','gs2'),('Password','password'),('Starchip cost','star_cost'),('Description','description')]):
   ttk.Label(fields,text=label).grid(row=i,column=0,sticky='w',pady=4,padx=(0,12));v=tk.StringVar();self.v[key]=v
   if key=='description':w=tk.Text(fields,height=5,width=38,bg='#263449',fg='white',insertbackground='white',relief='flat');self.desc=w
   elif key=='type_id':w=ttk.Combobox(fields,textvariable=v,values=CARD_TYPES,state='readonly')
   elif key=='attribute':w=ttk.Combobox(fields,textvariable=v,values=ATTRIBUTES,state='readonly')
   elif key in ('gs1','gs2'):w=ttk.Combobox(fields,textvariable=v,values=GUARDIAN_STARS,state='readonly')
   elif key=='level':w=ttk.Spinbox(fields,textvariable=v,from_=0,to=12,width=8)
   else:w=ttk.Entry(fields,textvariable=v)
   w.grid(row=i,column=1,sticky='ew',pady=4)
  ttk.Button(fields,text='Reset all card edits',command=self.reset_all_cards).grid(row=11,column=0,sticky='ew',padx=(0,5),pady=(12,0));ttk.Button(fields,text='Apply card changes',command=self.apply_card).grid(row=11,column=1,sticky='ew',padx=(5,0),pady=(12,0))
 def fill(self):
  selected=self.tree.selection()[0] if self.tree.selection() else None;self.tree.delete(*self.tree.get_children());q=self.query.get().lower()
  entries=list(self.cards.cards.items());kind=self.card_type_filter.get()
  if kind!='All types':entries=[(i,c) for i,c in entries if CARD_TYPES[c.type_id]==kind]
  if self.card_sort.get()=='Card ID':entries.sort(key=lambda x:x[0])
  elif self.card_sort.get()=='ATK':entries.sort(key=lambda x:(x[1].atk,x[1].name))
  elif self.card_sort.get()=='DEF':entries.sort(key=lambda x:(x[1].def_,x[1].name))
  elif self.card_sort.get()=='Level':entries.sort(key=lambda x:(getattr(x[1],'level',0),x[1].name))
  else:entries.sort(key=lambda x:x[1].name.lower())
  for i,c in entries:
   if not q or q in c.name.lower() or q in str(i):self.tree.insert('','end',iid=str(i),text=f'{c.name}   ·   {c.atk} / {c.def_}',image=self.row_image(self.tree,i))
  if selected and self.tree.exists(selected):self.tree.selection_set(selected);self.tree.focus(selected)
 def reset_card_filters(self):
  self.query.set('');self.card_type_filter.set('All types');self.card_sort.set('Name');self.fill()
 def card_context_menu(self,event):
  row=self.tree.identify_row(event.y)
  if not row:return
  self.tree.selection_set(row);self.tree.focus(row);self.select();menu=tk.Menu(self,tearoff=False);menu.add_command(label='Change artwork…',command=self.art_import);menu.add_command(label='Reset this card',command=self.reset_card);menu.add_separator()
  cid=int(row)
  for slot,label in enumerate(('Use as Fusion Material 1','Use as Fusion Material 2','Use as Fusion Result')):menu.add_command(label=label,command=lambda n=slot,card_id=cid:self.assign_fusion_card(n,card_id))
  menu.tk_popup(event.x_root,event.y_root)
 def reset_card(self):
  if not hasattr(self,'original_cards') or self.current not in self.original_cards:return
  self.cards.cards[self.current]=copy.deepcopy(self.original_cards[self.current]);self.art.clear_custom_art(self.current);self.mini_photos.pop(self.current,None);self.dirty=True;self.fill();self.fill_starter_cards();self.tree.selection_set(str(self.current));self.select();self.set_card_picker_values();self.load_fusions();self.refresh_deck_view();self.load_drops()
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
  p=self.fusion_page;p.columnconfigure(0,weight=1);p.rowconfigure(2,weight=1);self.fv=[tk.StringVar() for _ in range(3)];self.fusion_picks=[];self.fusion_photos={};self.fusion_rows=[];self.material_modes=[tk.StringVar(value='Specific card') for _ in range(2)];self.material_types=[tk.StringVar(value='Any type') for _ in range(2)];self.material_levels=[tk.StringVar(value='Any level') for _ in range(2)];self.material_attributes=[tk.StringVar(value='Any attribute') for _ in range(2)];self.material_exceptions=[set(),set()];self.material_filter_controls=[];pickrow=ttk.Frame(p);pickrow.grid(row=0,column=0,sticky='ew')
  for i,label in enumerate(('MATERIAL 1','MATERIAL 2','FUSION RESULT')):
   box=ttk.LabelFrame(pickrow,text=label,padding=8);box.pack(side='left',fill='both',expand=True,padx=5);box.columnconfigure(0,weight=1);preview=ttk.Label(box,text='Select a card',anchor='center');preview.pack(fill='x');pick=ttk.Button(box,text='Browse cards…',command=lambda n=i:self.open_card_picker(n));pick.pack(fill='x',pady=(6,0));pick.bind('<Button-3>',lambda e,n=i:self.open_card_picker(n));self.fusion_picks.append((pick,preview))
   if i<2:
    mode=ttk.Combobox(box,textvariable=self.material_modes[i],values=('Specific card','Match card filters'),state='readonly');mode.pack(fill='x',pady=(5,0));mode.bind('<<ComboboxSelected>>',lambda e,n=i:self.update_material_mode(n));controls=ttk.Frame(box);controls.columnconfigure(0,weight=1);controls.columnconfigure(1,weight=1);type_box=ttk.Combobox(controls,textvariable=self.material_types[i],values=['Any type']+CARD_TYPES,state='readonly');level_box=ttk.Combobox(controls,textvariable=self.material_levels[i],values=['Any level']+[str(n) for n in range(13)],state='readonly');attribute_box=ttk.Combobox(controls,textvariable=self.material_attributes[i],values=['Any attribute']+ATTRIBUTES,state='readonly');type_box.grid(row=0,column=0,sticky='ew',padx=(0,3),pady=(4,2));level_box.grid(row=0,column=1,sticky='ew',padx=(3,0),pady=(4,2));attribute_box.grid(row=1,column=0,sticky='ew',padx=(0,3),pady=2);exclude=ttk.Button(controls,text='Exceptions (0)…',command=lambda n=i:self.edit_material_exceptions(n));exclude.grid(row=1,column=1,sticky='ew',padx=(3,0),pady=2);reset=ttk.Button(controls,text='Reset material filters',command=lambda n=i:self.reset_material_filters(n));reset.grid(row=2,column=0,columnspan=2,sticky='ew',pady=(2,0));self.material_filter_controls.append((controls,exclude));type_box.bind('<<ComboboxSelected>>',lambda e,n=i:self.update_material_filters(n));level_box.bind('<<ComboboxSelected>>',lambda e,n=i:self.update_material_filters(n));attribute_box.bind('<<ComboboxSelected>>',lambda e,n=i:self.update_material_filters(n))
  actions=ttk.Frame(p);actions.grid(row=1,column=0,sticky='ew',pady=8);self.fusion_query=tk.StringVar();self.fusion_sort=tk.StringVar(value='Result name');fsearch=ttk.Entry(actions,textvariable=self.fusion_query);fsearch.pack(side='left',fill='x',expand=True);fsearch.bind('<KeyRelease>',lambda e:self.load_fusions());ttk.Label(actions,text='Search').pack(side='left',padx=8);ttk.Combobox(actions,textvariable=self.fusion_sort,values=['Result name','Material name','Card ID'],state='readonly',width=14).pack(side='left');self.fusion_sort.trace_add('write',lambda *_:self.load_fusions());ttk.Button(actions,text='Reset filters',command=lambda:(self.fusion_query.set(''),self.fusion_sort.set('Result name'),self.load_fusions())).pack(side='left',padx=4);ttk.Button(actions,text='Reset all recipes',command=self.reset_all_fusions).pack(side='left',padx=4);ttk.Button(actions,text='Add / update recipe',command=self.fusion_add).pack(side='left',padx=6);ttk.Button(actions,text='Delete selected',command=self.fusion_del).pack(side='left');self.fusion_count=ttk.Label(actions,text='');self.fusion_count.pack(side='right',padx=10);self.fusion_summary=ttk.Label(p,text='Choose two materials and a result card.');self.fusion_summary.grid(row=3,column=0,sticky='w',pady=(6,0))
  recipe_list=ttk.Frame(p);recipe_list.grid(row=2,column=0,sticky='nsew');recipe_list.columnconfigure(0,weight=1);recipe_list.rowconfigure(0,weight=1);self.ft=ttk.Treeview(recipe_list,show='tree');self.ft.heading('#0',text='RESULT · TYPE / ATTRIBUTE / STARS  ←  MATERIALS');self.ft.column('#0',width=950);self.ft.grid(row=0,column=0,sticky='nsew');recipe_scroll=ttk.Scrollbar(recipe_list,orient='vertical',command=self.ft.yview);recipe_scroll.grid(row=0,column=1,sticky='ns');self.ft.configure(yscrollcommand=recipe_scroll.set);self.ft.bind('<<TreeviewSelect>>',self.select_fusion);self.ft.bind('<Button-3>',self.fusion_context_menu);self.ft.bind('<Button-2>',self.fusion_context_menu);self.add_layout_picker(actions,self.ft,lambda iid:self.fusion_rows[int(iid)][2],lambda w:w.pack(side='left',padx=4))
  for i in range(2):self.update_material_mode(i)
 def reset_all_fusions(self):
  if not self.original_wa:return messagebox.showinfo('Fusion Lab','Open a ROM before resetting recipes.')
  restored=FusionDatabase();restored.load_from_wa(self.original_wa);self.fusions=restored;self.dirty=True;self.load_fusions();self.update_fusion_summary();self.status.configure(text='All fusion recipes reset to the loaded ROM.')
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
    if i<2 and self.material_modes[i].get()=='Match card filters':self.update_material_filters(i)
    else:self.preview_fusion_card(i)
  self.update_fusion_summary()
 def update_material_mode(self,index):
  combo,preview=self.fusion_picks[index];controls,exclude=self.material_filter_controls[index]
  if self.material_modes[index].get()=='Match card filters':
   combo.pack_forget();controls.pack(fill='x',pady=(3,0));self.update_material_filters(index)
  else:
   controls.pack_forget();combo.pack(fill='x',pady=(6,0));self.preview_fusion_card(index)
  self.update_fusion_summary()
 def update_material_type(self,index):
  self.update_material_filters(index)
 def material_filter_label(self,index):
  parts=[]
  for value,default in ((self.material_types[index].get(),'Any type'),(self.material_levels[index].get(),'Any level'),(self.material_attributes[index].get(),'Any attribute')):
   if value!=default:parts.append(f'Type: {value}' if default=='Any type' else (f'Level {value}' if default=='Any level' else f'Attribute: {value}'))
  label='   ·   '.join(parts) if parts else 'All cards'
  excluded=len(self.material_exceptions[index])
  return label+(f'\n{excluded} excluded' if excluded else '')
 def update_material_filters(self,index):
  if self.material_modes[index].get()!='Match card filters':return self.update_fusion_summary()
  controls,button=self.material_filter_controls[index];button.configure(text=f'Exceptions ({len(self.material_exceptions[index])})…');preview=self.fusion_picks[index][1];preview.configure(image='',text=self.material_filter_label(index),font=('Segoe UI',11,'bold'))
  self.update_fusion_summary()
 def reset_material_filters(self,index):
  self.material_types[index].set('Any type');self.material_levels[index].set('Any level');self.material_attributes[index].set('Any attribute');self.material_exceptions[index].clear();self.update_material_filters(index)
 def edit_material_exceptions(self,index):
  if not self.cards.cards:return messagebox.showinfo('Fusion exceptions','Open a ROM image before choosing excluded cards.')
  if self.material_modes[index].get()!='Match card filters':return messagebox.showinfo('Fusion exceptions','Switch this material to “Match card filters” first.')
  win=tk.Toplevel(self);win.title(f'Material {index+1} · matching cards and exceptions');win.geometry('850x700');win.minsize(700,520);win.transient(self);win.grab_set();win.columnconfigure(0,weight=1);win.rowconfigure(1,weight=1)
  working=set(self.material_exceptions[index]);query=tk.StringVar();show_excluded=tk.BooleanVar(value=False);tools=ttk.Frame(win,padding=12);tools.grid(row=0,column=0,sticky='ew');tools.columnconfigure(0,weight=1)
  ttk.Label(tools,text=f'MATERIAL {index+1}  ·  {self.material_filter_label(index).replace(chr(10)," · ")}',font=('Segoe UI',12,'bold')).grid(row=0,column=0,sticky='w',pady=(0,8));search=ttk.Entry(tools,textvariable=query);search.grid(row=1,column=0,sticky='ew');ttk.Checkbutton(tools,text='Show excluded cards',variable=show_excluded,command=lambda:refresh()).grid(row=1,column=1,sticky='e',padx=(10,0));ttk.Label(tools,text='Only cards matching the selected type, level, and attribute are listed. Double-click to exclude or restore.',font=('Segoe UI',9)).grid(row=2,column=0,columnspan=2,sticky='w',pady=(6,0))
  body=ttk.Frame(win,padding=(12,0,12,8));body.grid(row=1,column=0,sticky='nsew');body.columnconfigure(0,weight=1);body.rowconfigure(0,weight=1);tree=ttk.Treeview(body,columns=('state','id','stats'),show='tree headings');tree.heading('#0',text='MATCHING CARD · GAME ICONS');tree.heading('state',text='Material');tree.heading('id',text='Card ID');tree.heading('stats',text='ATK / DEF');tree.column('#0',width=440);tree.column('state',width=115,anchor='center');tree.column('id',width=70,anchor='center');tree.column('stats',width=115,anchor='center');tree.grid(row=0,column=0,sticky='nsew');scroll=ttk.Scrollbar(body,orient='vertical',command=tree.yview);scroll.grid(row=0,column=1,sticky='ns');tree.configure(yscrollcommand=scroll.set)
  footer=ttk.Frame(win,padding=12);footer.grid(row=2,column=0,sticky='ew');count=ttk.Label(footer,text='');count.pack(side='left')
  def refresh(*_):
   tree.delete(*tree.get_children());needle=query.get().strip().lower();eligible=excluded=0
   for cid,c in sorted(self.cards.cards.items()):
    if not self.material_filter_matches(index,c):continue
    if needle and needle not in c.name.lower() and needle not in str(cid):continue
    is_excluded=cid in working
    if is_excluded:excluded+=1
    else:eligible+=1
    if is_excluded and not show_excluded.get():continue
    tree.insert('','end',iid=str(cid),text=c.name,image=self.mini_photo(cid),values=('Excluded' if is_excluded else 'Eligible',cid,f'{c.atk} / {c.def_}'))
   count.configure(text=f'{eligible:,} eligible · {excluded:,} excluded · {eligible+excluded:,} match this material')
  def toggle(_=None):
   selection=tree.selection()
   if not selection:return
   for row in selection:
    cid=int(row)
    if cid in working:working.remove(cid)
    else:working.add(cid)
   refresh()
   for row in selection:
    if tree.exists(row):tree.selection_add(row)
  def clear_exceptions():working.clear();refresh()
  def apply():self.material_exceptions[index]=working;self.update_material_filters(index);win.destroy()
  tree.bind('<Double-1>',toggle);query.trace_add('write',refresh);refresh();ttk.Button(footer,text='Toggle selected',command=toggle).pack(side='left',padx=(12,4));ttk.Button(footer,text='Clear exceptions',command=clear_exceptions).pack(side='left',padx=4);ttk.Button(footer,text='Cancel',command=win.destroy).pack(side='right',padx=4);ttk.Button(footer,text='Apply exceptions',command=apply).pack(side='right',padx=4)
 def material_filter_matches(self,index,card):
  kind=self.material_types[index].get();level=self.material_levels[index].get();attribute=self.material_attributes[index].get()
  return (kind=='Any type' or card.type_id==CARD_TYPES.index(kind)) and (level=='Any level' or getattr(card,'level',0)==int(level)) and (attribute=='Any attribute' or getattr(card,'attribute',0)==ATTRIBUTES.index(attribute))
 def material_card_ids(self,index):
  if self.material_modes[index].get()=='Match card filters':
   excluded=self.material_exceptions[index]
   return [cid for cid,c in self.cards.cards.items() if cid not in excluded and self.material_filter_matches(index,c)]
  cid=self.card_from_option(self.fv[index].get())
  return [cid] if cid is not None else []
 def expanded_material_pairs(self):
  from itertools import product
  return {(min(a,b),max(a,b)) for a,b in product(self.material_card_ids(0),self.material_card_ids(1))}
 def update_fusion_summary(self):
  if not hasattr(self,'fusion_summary'):return
  cards=[set(self.material_card_ids(i)) for i in range(2)];counts=[len(group) for group in cards];shared=len(cards[0]&cards[1]);pair_count=counts[0]*counts[1]-shared*(shared-1)//2 if all(counts) else 0
  existing=sum(1 for a,b in self.fusions.fusions if (a in cards[0] and b in cards[1]) or (b in cards[0] and a in cards[1]))
  self.fusion_summary.configure(text=f'{counts[0]:,} material cards × {counts[1]:,} material cards  ·  {pair_count:,} unique pairs  ·  {existing:,} update / {pair_count-existing:,} new')
 def preview_fusion_card(self,index):
  cid=self.card_from_option(self.fv[index].get())
  if not cid:
   self.fusion_picks[index][1].configure(image='',text='Choose a card',font=('Segoe UI',10))
   return
  image=self.art.get_card_art(cid)
  if image:
   photo=ImageTk.PhotoImage(self.render_card_preview(self.cards.get(cid),image).resize((100,139),Image.Resampling.LANCZOS));self.fusion_photos[index]=photo;self.fusion_picks[index][1].configure(image=photo,text='')
 def card_button_text(self,cid):
  card=self.cards.get(cid)
  return f'{card.name}  ·  ID {cid}' if card else 'Browse cards…'
 def assign_fusion_card(self,index,cid):
  if cid not in self.cards.cards:return
  self.fv[index].set(self.card_option_for_id(cid));self.fusion_picks[index][0].configure(text=self.card_button_text(cid))
  if index<2:
   self.material_modes[index].set('Specific card');self.update_material_mode(index)
  else:self.preview_fusion_card(index)
  self.update_fusion_summary()
 def open_card_picker(self,index):
  if not self.cards.cards:return messagebox.showinfo('Card picker','Open a ROM image first.')
  win=tk.Toplevel(self);win.title(('Choose material 1','Choose material 2','Choose fusion result')[index]);win.geometry('920x700');win.minsize(760,560);win.transient(self)
  win.columnconfigure(0,weight=1);win.rowconfigure(1,weight=1)
  tools=ttk.Frame(win,padding=10);tools.grid(row=0,column=0,sticky='ew');tools.columnconfigure(0,weight=1);query=tk.StringVar();kind=tk.StringVar(value='All types');sort=tk.StringVar(value='Name')
  search=ttk.Entry(tools,textvariable=query);search.grid(row=0,column=0,sticky='ew',padx=(0,6));ttk.Combobox(tools,textvariable=kind,values=['All types']+CARD_TYPES,state='readonly',width=15).grid(row=0,column=1,padx=4);ttk.Combobox(tools,textvariable=sort,values=['Name','Card ID','ATK','DEF','Level'],state='readonly',width=11).grid(row=0,column=2,padx=4)
  body=ttk.Frame(win,padding=(10,0,10,8));body.grid(row=1,column=0,sticky='nsew')
  for grid_index in range(4):body.columnconfigure(grid_index,weight=1);body.rowconfigure(grid_index,weight=1)
  footer=ttk.Frame(win,padding=10);footer.grid(row=2,column=0,sticky='ew');page={'value':0};images=[]
  count=ttk.Label(footer);count.pack(side='left');previous=ttk.Button(footer,text='← Previous');previous.pack(side='right',padx=4);next_page=ttk.Button(footer,text='Next →');next_page.pack(side='right',padx=4)
  def set_card(cid):self.assign_fusion_card(index,cid);win.destroy()
  def refresh(_=None):
   for child in body.winfo_children():child.destroy()
   images.clear();entries=list(self.cards.cards.items());needle=query.get().strip().lower();selected_type=kind.get()
   if selected_type!='All types':entries=[(cid,c) for cid,c in entries if CARD_TYPES[c.type_id]==selected_type]
   if needle:entries=[(cid,c) for cid,c in entries if needle in c.name.lower() or needle in str(cid)]
   if sort.get()=='Card ID':entries.sort(key=lambda x:x[0])
   elif sort.get()=='ATK':entries.sort(key=lambda x:(x[1].atk,x[1].name.lower()))
   elif sort.get()=='DEF':entries.sort(key=lambda x:(x[1].def_,x[1].name.lower()))
   elif sort.get()=='Level':entries.sort(key=lambda x:(getattr(x[1],'level',0),x[1].name.lower()))
   else:entries.sort(key=lambda x:x[1].name.lower())
   pages=max(1,(len(entries)+15)//16);page['value']=max(0,min(page['value'],pages-1));visible=entries[page['value']*16:(page['value']+1)*16];count.configure(text=f'{page["value"]+1} / {pages} pages  ·  {len(entries):,} cards')
   previous.configure(state='normal' if page['value'] else 'disabled');next_page.configure(state='normal' if page['value']+1<pages else 'disabled')
   for slot,(cid,card) in enumerate(visible):
    r,cidx=divmod(slot,4);tile=ttk.Frame(body,relief='ridge',borderwidth=1,padding=5);tile.grid(row=r,column=cidx,sticky='nsew',padx=4,pady=4)
    art=self.art.get_card_art(cid)
    if art:
     photo=ImageTk.PhotoImage(self.render_card_preview(card,art).resize((86,119),Image.Resampling.LANCZOS));images.append(photo);picture=ttk.Label(tile,image=photo);picture.pack()
    ttk.Label(tile,text=f'{card.name}\n{card.atk} / {card.def_}',justify='center',wraplength=185).pack(fill='x',pady=(4,0))
    for widget in (tile,*tile.winfo_children()):widget.bind('<Button-1>',lambda e,card_id=cid:set_card(card_id));widget.bind('<Double-1>',lambda e,card_id=cid:set_card(card_id));widget.bind('<Button-3>',lambda e,card_id=cid:picker_context(e,card_id));widget.bind('<Button-2>',lambda e,card_id=cid:picker_context(e,card_id))
   win._picker_images=images[:]
  def picker_context(event,cid):
   menu=tk.Menu(win,tearoff=False)
   for slot,label in enumerate(('Use as Material 1','Use as Material 2','Use as Fusion Result')):menu.add_command(label=label,command=lambda n=slot,card_id=cid:set_card_for_slot(n,card_id))
   menu.tk_popup(event.x_root,event.y_root)
  def set_card_for_slot(slot,cid):
   self.assign_fusion_card(slot,cid)
   if slot==index:win.destroy()
  query.trace_add('write',refresh);kind.trace_add('write',refresh);sort.trace_add('write',refresh);previous.configure(command=lambda:(page.update(value=page['value']-1),refresh()));next_page.configure(command=lambda:(page.update(value=page['value']+1),refresh()));search.bind('<Return>',refresh);refresh()
 def select_fusion(self,_=None):
  sel=self.ft.selection()
  if not sel:return
  a,b,r=self.fusion_rows[int(sel[0])]
  for idx,cid in enumerate((a,b,r)):
   self.fv[idx].set(self.card_option_for_id(cid));self.fusion_picks[idx][0].configure(text=self.card_button_text(cid))
   if idx<2:self.material_modes[idx].set('Specific card');self.update_material_mode(idx)
   else:self.preview_fusion_card(idx)
  self.update_fusion_summary()
 def fusion_context_menu(self,event):
  row=self.ft.identify_row(event.y)
  if not row:return
  self.ft.selection_set(row);self.ft.focus(row);self.select_fusion();menu=tk.Menu(self,tearoff=False);menu.add_command(label='Load recipe into editor',command=self.select_fusion);menu.add_command(label='Delete this recipe',command=self.fusion_del);menu.tk_popup(event.x_root,event.y_root)
 def drop_ui(self):
  p=self.drop_page;p.columnconfigure(0,weight=0,minsize=250);p.columnconfigure(1,weight=1);p.rowconfigure(0,weight=1);self.duelist=tk.StringVar(value=DUELISTS[0]);self.opponent_photos={}
  gallery=ttk.LabelFrame(p,text='OPPONENTS',padding=8);gallery.grid(row=0,column=0,sticky='nsew',padx=(0,10));gallery.columnconfigure(0,weight=1);gallery.rowconfigure(0,weight=1)
  self.opponent_tree=ttk.Treeview(gallery,show='tree',height=20);self.opponent_tree.heading('#0',text='39 duelists · choose a portrait');self.opponent_tree.column('#0',width=210,stretch=True);self.opponent_tree.grid(row=0,column=0,sticky='nsew');ys=ttk.Scrollbar(gallery,orient='vertical',command=self.opponent_tree.yview);ys.grid(row=0,column=1,sticky='ns');self.opponent_tree.configure(yscrollcommand=ys.set);self.opponent_tree.bind('<<TreeviewSelect>>',self.select_duelist);self.opponent_tree.bind('<Button-3>',self.opponent_context_menu);self.opponent_tree.bind('<Button-2>',self.opponent_context_menu)
  detail=ttk.Frame(p);detail.grid(row=0,column=1,sticky='nsew');detail.columnconfigure(0,weight=1);detail.rowconfigure(2,weight=1)
  identity=ttk.LabelFrame(detail,text='SELECTED DUELIST',padding=10);identity.grid(row=0,column=0,sticky='ew');self.dp=ttk.Label(identity,text='Open a ROM to load portraits',width=18,anchor='center');self.dp.pack(side='left',padx=(0,14));self.drop_title=ttk.Label(identity,text=DUELISTS[0],font=('Segoe UI',18,'bold'));self.drop_title.pack(side='left',anchor='center');ttk.Button(identity,text='Change portrait…',command=self.import_portrait).pack(side='right',padx=6)
  tools=ttk.Frame(detail);tools.grid(row=1,column=0,sticky='ew',pady=8);self.pool=tk.StringVar(value='S/A POW');ttk.Label(tools,text='REWARD POOL').pack(side='left',padx=(0,5));ttk.Combobox(tools,textvariable=self.pool,values=['S/A POW','B/C/D','S/A TEC'],state='readonly',width=12).pack(side='left');self.pool.trace_add('write',lambda *_:self.load_drops());self.drop_query=tk.StringVar();self.drop_sort=tk.StringVar(value='Card name');self.drop_type=tk.StringVar(value='All types');search=ttk.Entry(tools,textvariable=self.drop_query);search.pack(side='left',fill='x',expand=True,padx=(12,4));search.bind('<KeyRelease>',lambda e:self.load_drops());ttk.Combobox(tools,textvariable=self.drop_type,values=['All types']+CARD_TYPES,state='readonly',width=13).pack(side='left',padx=3);ttk.Combobox(tools,textvariable=self.drop_sort,values=['Card name','Card ID','Weight','Chance'],state='readonly',width=11).pack(side='left',padx=3);self.drop_type.trace_add('write',lambda *_:self.load_drops());self.drop_sort.trace_add('write',lambda *_:self.load_drops())
  drop_list=ttk.Frame(detail);drop_list.grid(row=2,column=0,sticky='nsew');drop_list.columnconfigure(0,weight=1);drop_list.rowconfigure(0,weight=1);self.dt=ttk.Treeview(drop_list,show='tree');self.dt.heading('#0',text='CARD · TYPE / ATTRIBUTE / STARS · DROP WEIGHT · CHANCE');self.dt.column('#0',width=800);self.dt.grid(row=0,column=0,sticky='nsew');drop_scroll=ttk.Scrollbar(drop_list,orient='vertical',command=self.dt.yview);drop_scroll.grid(row=0,column=1,sticky='ns');self.dt.configure(yscrollcommand=drop_scroll.set);self.dt.bind('<Double-1>',self.edit_drop);self.dt.bind('<Button-3>',self.drop_context_menu);self.dt.bind('<Button-2>',self.drop_context_menu);actions=ttk.Frame(detail);actions.grid(row=3,column=0,sticky='ew',pady=8);ttk.Button(actions,text='Reset all drop edits',command=self.reset_all_drops).pack(side='left',padx=3);ttk.Button(actions,text='Reset filters',command=self.reset_drop_filters).pack(side='left',padx=3);ttk.Button(actions,text='Reset this pool',command=self.reset_drop_pool).pack(side='left',padx=3);ttk.Button(actions,text='Add card…',command=self.add_drop).pack(side='left',padx=3);ttk.Button(actions,text='Balance weights',command=self.normalize_pool).pack(side='left',padx=3);self.add_layout_picker(actions,self.dt,lambda iid:int(iid),lambda w:w.pack(side='left',padx=3))
  self.refresh_opponent_gallery()
 def refresh_opponent_gallery(self):
  if not hasattr(self,'opponent_tree'):return
  self.opponent_tree.delete(*self.opponent_tree.get_children());self.opponent_photos={}
  for portrait_id,name in enumerate(DUELISTS,1):
   if self.wa:
    try:im=portraits.read(self.wa,portrait_id).resize((52,52),Image.Resampling.NEAREST)
    except Exception:im=Image.new('RGB',(52,52),'#445166')
   else:im=Image.new('RGB',(52,52),'#445166')
   photo=ImageTk.PhotoImage(im);self.opponent_photos[portrait_id]=photo;self.opponent_tree.insert('','end',iid=str(portrait_id),text=name,image=photo)
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
  browse=ttk.LabelFrame(p,text='CARD LIBRARY',padding=8);browse.grid(row=0,column=0,sticky='nsew',padx=5);browse.columnconfigure(0,weight=1);browse.rowconfigure(1,weight=1);self.starter_query=tk.StringVar();self.starter_sort=tk.StringVar(value='Name');self.starter_type=tk.StringVar(value='All types');tools=ttk.Frame(browse);tools.grid(row=0,column=0,sticky='ew',pady=(0,6));tools.columnconfigure(0,weight=1);se=ttk.Entry(tools,textvariable=self.starter_query);se.grid(row=0,column=0,sticky='ew');se.bind('<KeyRelease>',lambda e:self.fill_starter_cards());ttk.Combobox(tools,textvariable=self.starter_type,values=['All types']+CARD_TYPES,state='readonly',width=14).grid(row=0,column=1,padx=3);ttk.Combobox(tools,textvariable=self.starter_sort,values=['Name','Card ID','ATK','DEF'],state='readonly',width=9).grid(row=0,column=2,padx=3);ttk.Button(tools,text='Reset',command=self.reset_starter_filters).grid(row=0,column=3);self.starter_type.trace_add('write',lambda *_:self.fill_starter_cards());self.starter_sort.trace_add('write',lambda *_:self.fill_starter_cards());card_list=ttk.Frame(browse);card_list.grid(row=1,column=0,sticky='nsew');card_list.columnconfigure(0,weight=1);card_list.rowconfigure(0,weight=1);self.starter_tree=ttk.Treeview(card_list,show='tree');self.starter_tree.heading('#0',text='CARD · TYPE · ATTRIBUTE · GUARDIAN · LEVEL · ATK / DEF');self.starter_tree.column('#0',width=360);self.starter_tree.grid(row=0,column=0,sticky='nsew');starter_scroll=ttk.Scrollbar(card_list,orient='vertical',command=self.starter_tree.yview);starter_scroll.grid(row=0,column=1,sticky='ns');self.starter_tree.configure(yscrollcommand=starter_scroll.set);self.starter_tree.bind('<<TreeviewSelect>>',self.select_starter_card);self.starter_tree.bind('<ButtonRelease-1>',self.starter_library_add);self.starter_tree.bind('<ButtonRelease-3>',self.starter_library_remove);self.add_layout_picker(tools,self.starter_tree,lambda iid:int(iid),lambda w:w.grid(row=0,column=4,padx=3));ttk.Label(browse,text='Left-click adds · right-click removes one copy · game icons show type, attribute, Guardian Stars, and level',font=('Segoe UI',9)).grid(row=2,column=0,sticky='w')
  preview=ttk.LabelFrame(p,text='SELECTED CARD',padding=12);preview.grid(row=0,column=1,sticky='nsew',padx=5);self.starter_art=ttk.Label(preview,text='Open a ROM to view cards',anchor='center');self.starter_art.pack(fill='x',pady=8);self.starter_name=ttk.Label(preview,text='Choose a card',font=('Segoe UI',16,'bold'),wraplength=280);self.starter_name.pack(pady=6);self.starter_stats=ttk.Label(preview,text='',justify='center');self.starter_stats.pack(pady=4);ttk.Button(preview,text='Add selected card to deck',command=self.starter_add).pack(pady=12)
  deck=ttk.LabelFrame(p,text='STARTER DECK  •  40 CARDS',padding=8);deck.grid(row=0,column=2,sticky='nsew',padx=5);deck.columnconfigure(0,weight=1);deck.columnconfigure(1,weight=1);deck.rowconfigure(0,weight=1);deck_list=ttk.Frame(deck);deck_list.grid(row=0,column=0,columnspan=2,sticky='nsew');deck_list.columnconfigure(0,weight=1);deck_list.rowconfigure(0,weight=1);self.deck_tree=ttk.Treeview(deck_list,show='tree');self.deck_tree.heading('#0',text='CARD · TYPE · ATTRIBUTE · GUARDIAN · LEVEL · COPIES');self.deck_tree.column('#0',width=340);self.deck_tree.grid(row=0,column=0,sticky='nsew');deck_scroll=ttk.Scrollbar(deck_list,orient='vertical',command=self.deck_tree.yview);deck_scroll.grid(row=0,column=1,sticky='ns');self.deck_tree.configure(yscrollcommand=deck_scroll.set);self.deck_tree.bind('<ButtonRelease-3>',self.deck_right_remove)
  self.random_deck_style=tk.StringVar(value='Balanced');ttk.Combobox(deck,textvariable=self.random_deck_style,values=['Balanced','Monster-heavy','Anything goes'],state='readonly').grid(row=1,column=0,columnspan=2,sticky='ew',pady=(6,2));ttk.Button(deck,text='Build random 40-card deck',command=self.randomize_starter_deck).grid(row=2,column=0,columnspan=2,sticky='ew',pady=3);ttk.Button(deck,text='Fill empty slots randomly',command=self.fill_random_deck_slots).grid(row=3,column=0,columnspan=2,sticky='ew',pady=3)
  ttk.Button(deck,text='Remove selected',command=self.starter_remove).grid(row=4,column=0,sticky='ew',pady=4);ttk.Button(deck,text='Clear deck',command=self.starter_clear).grid(row=4,column=1,sticky='ew',padx=5,pady=4);ttk.Button(deck,text='Reset default deck',command=self.reset_default_deck).grid(row=5,column=0,columnspan=2,sticky='ew');self.add_layout_picker(deck,self.deck_tree,lambda iid:int(iid),lambda w:w.grid(row=6,column=0,columnspan=2,sticky='w',pady=3));self.deck_count=ttk.Label(deck,text='0 / 40 cards');self.deck_count.grid(row=7,column=0,columnspan=2)
  footer=ttk.LabelFrame(p,text='SAVE FILE',padding=10);footer.grid(row=1,column=0,columnspan=3,sticky='ew',pady=10);ttk.Label(footer,text='Player name').pack(side='left');ttk.Entry(footer,textvariable=self.player,width=15).pack(side='left',padx=6);ttk.Label(footer,text='Starting starchips').pack(side='left',padx=(18,4));ttk.Entry(footer,textvariable=self.chips,width=10).pack(side='left');ttk.Button(footer,text='Reset all starter changes',command=self.reset_all_starter).pack(side='right',padx=5);ttk.Button(footer,text='Create DuckStation .mcd',command=self.save_mcd).pack(side='right');self.refresh_deck_view()
 def savedata_ui(self):
  p=self.savedata_page;p.columnconfigure(0,weight=1);p.rowconfigure(2,weight=1);self.sd_doc=None;self.sd_path=None;self.sd_deck=[];self.sd_quantities=[];self.sd_selected_card=None;self.sd_selected_slot=None
  header=ttk.Frame(p);header.grid(row=0,column=0,sticky='ew');ttk.Button(header,text='Open memory card or save…',command=self.open_savedata).pack(side='left');ttk.Button(header,text='Save edited data as…',command=self.save_savedata).pack(side='left',padx=6);ttk.Button(header,text='Reload current file',command=self.reload_savedata).pack(side='left');self.sd_status=ttk.Label(header,text='Open a DuckStation .mcd card or exported FM .mcs save.');self.sd_status.pack(side='left',padx=12)
  profile=ttk.LabelFrame(p,text='PLAYER PROFILE',padding=8);profile.grid(row=1,column=0,sticky='ew',pady=(8,10))
  for column in range(8):profile.columnconfigure(column,weight=1 if column in (1,3,5,7) else 0)
  self.sd_name=tk.StringVar(value='PLAYER');self.sd_chips=tk.StringVar(value='0');self.sd_wins=tk.StringVar(value='0');self.sd_losses=tk.StringVar(value='0');self.sd_tournament=tk.BooleanVar(value=False)
  ttk.Label(profile,text='Name').grid(row=0,column=0,sticky='w');ttk.Entry(profile,textvariable=self.sd_name,width=10).grid(row=0,column=1,sticky='ew',padx=(5,12));ttk.Label(profile,text='Starchips').grid(row=0,column=2,sticky='w');ttk.Spinbox(profile,textvariable=self.sd_chips,from_=0,to=999999,width=10).grid(row=0,column=3,sticky='ew',padx=(5,12));ttk.Label(profile,text='Wins').grid(row=0,column=4,sticky='w');ttk.Spinbox(profile,textvariable=self.sd_wins,from_=0,to=65535,width=8).grid(row=0,column=5,sticky='ew',padx=(5,12));ttk.Label(profile,text='Losses').grid(row=0,column=6,sticky='w');ttk.Spinbox(profile,textvariable=self.sd_losses,from_=0,to=65535,width=8).grid(row=0,column=7,sticky='ew',padx=(5,12));ttk.Checkbutton(profile,text='Tournament complete',variable=self.sd_tournament).grid(row=1,column=0,columnspan=3,sticky='w',pady=(7,0))
  body=ttk.Frame(p);body.grid(row=2,column=0,sticky='nsew');body.columnconfigure(0,weight=5,minsize=420);body.columnconfigure(1,weight=6,minsize=570);body.rowconfigure(0,weight=1)
  library=ttk.LabelFrame(body,text='CARD COLLECTION · TRUNK COPIES',padding=8);library.grid(row=0,column=0,sticky='nsew',padx=(0,8));library.columnconfigure(0,weight=1);library.rowconfigure(1,weight=1);self.sd_query=tk.StringVar();search=ttk.Entry(library,textvariable=self.sd_query);search.grid(row=0,column=0,sticky='ew',pady=(0,6));search.bind('<KeyRelease>',lambda e:self.refresh_savedata_card_list());self.sd_cards_tree=ttk.Treeview(library,columns=('id','qty','deck'),show='tree headings');self.sd_cards_tree.heading('#0',text='CARD · GAME ICONS');self.sd_cards_tree.heading('id',text='ID');self.sd_cards_tree.heading('qty',text='Trunk');self.sd_cards_tree.heading('deck',text='Deck');self.sd_cards_tree.column('#0',width=285);self.sd_cards_tree.column('id',width=48,anchor='center');self.sd_cards_tree.column('qty',width=60,anchor='center');self.sd_cards_tree.column('deck',width=55,anchor='center');self.sd_cards_tree.grid(row=1,column=0,sticky='nsew');libscroll=ttk.Scrollbar(library,orient='vertical',command=self.sd_cards_tree.yview);libscroll.grid(row=1,column=1,sticky='ns');self.sd_cards_tree.configure(yscrollcommand=libscroll.set);self.sd_cards_tree.bind('<<TreeviewSelect>>',self.select_savedata_card)
  detail=ttk.Frame(body);detail.grid(row=0,column=1,sticky='nsew');detail.columnconfigure(0,weight=1);detail.rowconfigure(1,weight=1)
  selected=ttk.LabelFrame(detail,text='SELECTED CARD · COLLECTION AND DECK',padding=8);selected.grid(row=0,column=0,sticky='ew',pady=(0,8));self.sd_preview=ttk.Label(selected,text='Choose a save file and card',anchor='center');self.sd_preview.grid(row=0,column=0,rowspan=4,sticky='n',padx=(0,12));self.sd_card_title=ttk.Label(selected,text='No card selected',font=('Segoe UI',13,'bold'));self.sd_card_title.grid(row=0,column=1,columnspan=4,sticky='w');self.sd_card_stats=ttk.Label(selected,text='',justify='left');self.sd_card_stats.grid(row=1,column=1,columnspan=4,sticky='w',pady=4);self.sd_qty=tk.StringVar(value='0');ttk.Label(selected,text='Copies in trunk').grid(row=2,column=1,sticky='w',pady=3);ttk.Spinbox(selected,textvariable=self.sd_qty,from_=0,to=250,width=8).grid(row=2,column=2,sticky='w',padx=6);ttk.Button(selected,text='Apply trunk quantity',command=self.apply_savedata_quantity).grid(row=2,column=3,sticky='w',padx=5);ttk.Button(selected,text='Replace selected deck slot with this card',command=self.replace_savedata_deck_slot).grid(row=3,column=1,columnspan=3,sticky='w',pady=(6,0))
  deck=ttk.LabelFrame(detail,text='40-CARD DECK · SELECT A SLOT, THEN REPLACE OR CLEAR',padding=8);deck.grid(row=1,column=0,sticky='nsew');deck.columnconfigure(0,weight=1);deck.rowconfigure(0,weight=1);self.sd_deck_tree=ttk.Treeview(deck,columns=('id',),show='tree headings');self.sd_deck_tree.heading('#0',text='DECK SLOT · CARD');self.sd_deck_tree.heading('id',text='ID');self.sd_deck_tree.column('#0',width=420);self.sd_deck_tree.column('id',width=60,anchor='center');self.sd_deck_tree.grid(row=0,column=0,sticky='nsew');deckscroll=ttk.Scrollbar(deck,orient='vertical',command=self.sd_deck_tree.yview);deckscroll.grid(row=0,column=1,sticky='ns');self.sd_deck_tree.configure(yscrollcommand=deckscroll.set);self.sd_deck_tree.bind('<<TreeviewSelect>>',self.select_savedata_deck_slot);self.sd_deck_tree.bind('<Double-1>',self.replace_savedata_deck_slot);actions=ttk.Frame(deck);actions.grid(row=1,column=0,columnspan=2,sticky='ew',pady=(6,0));self.sd_deck_count=ttk.Label(actions,text='0 / 40 occupied');self.sd_deck_count.pack(side='left');ttk.Button(actions,text='Clear selected slot',command=self.clear_savedata_deck_slot).pack(side='right')
  self.refresh_savedata_card_list();self.refresh_savedata_deck()
 def open_savedata(self):
  path=filedialog.askopenfilename(filetypes=[('DuckStation memory cards and FM saves','*.mcd *.mcs'),('All files','*.*')])
  if not path:return
  try:
   doc=SaveDataDocument.open(path);self.sd_doc=doc;self.sd_path=Path(path);self.sd_name.set(doc.player_name());self.sd_chips.set(str(doc.starchips()));wins,losses=doc.duel_record();self.sd_wins.set(str(wins));self.sd_losses.set(str(losses));self.sd_tournament.set(doc.tournament_complete());self.sd_deck=doc.deck();self.sd_quantities=[doc.card_quantity(cid) for cid in range(1,723)];self.sd_selected_slot=None;self.sd_status.configure(text=f'{self.sd_path.name} · integrity verified · {"memory card" if doc.blocks is not None else "single save"}');self.refresh_savedata_card_list();self.refresh_savedata_deck()
  except (OSError,SaveDataError) as exc:messagebox.showerror('Could not open save data',str(exc))
 def reload_savedata(self):
  if not self.sd_path:return messagebox.showinfo('Save Data Editor','Open a save file first.')
  try:
   doc=SaveDataDocument.open(self.sd_path);self.sd_doc=doc;self.sd_name.set(doc.player_name());self.sd_chips.set(str(doc.starchips()));wins,losses=doc.duel_record();self.sd_wins.set(str(wins));self.sd_losses.set(str(losses));self.sd_tournament.set(doc.tournament_complete());self.sd_deck=doc.deck();self.sd_quantities=[doc.card_quantity(cid) for cid in range(1,723)];self.sd_selected_slot=None;self.sd_status.configure(text=f'{self.sd_path.name} · reloaded · integrity verified');self.refresh_savedata_card_list();self.refresh_savedata_deck()
  except (OSError,SaveDataError) as exc:messagebox.showerror('Could not reload save data',str(exc))
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
   self.sd_doc.set_player_name(self.sd_name.get());self.sd_doc.set_starchips(int(self.sd_chips.get()));self.sd_doc.set_duel_record(int(self.sd_wins.get()),int(self.sd_losses.get()));self.sd_doc.set_campaign_flag(0x47,bool(self.sd_tournament.get()));self.sd_doc.set_deck(self.sd_deck)
   for cid,quantity in enumerate(self.sd_quantities,1):self.sd_doc.set_card_quantity(cid,quantity)
   Path(path).write_bytes(self.sd_doc.to_bytes());self.sd_path=Path(path);self.sd_status.configure(text=f'{self.sd_path.name} · saved with valid checksums');messagebox.showinfo('Save data saved',f'Edited save data saved to:\n{path}')
  except (OSError,ValueError,SaveDataError) as exc:messagebox.showerror('Could not save data',str(exc))
 def refresh_savedata_card_list(self):
  if not hasattr(self,'sd_cards_tree'):return
  tree=self.sd_cards_tree;selected=tree.selection()[0] if tree.selection() else None;tree.delete(*tree.get_children());query=self.sd_query.get().strip().lower();deck_counts={}
  for cid in self.sd_deck:deck_counts[cid]=deck_counts.get(cid,0)+1
  if self.sd_doc is None:return
  for cid in sorted(CARD_NAMES,key=lambda card_id:CARD_NAMES[card_id].lower()):
   c=self.cards.get(cid);name=c.name if c else CARD_NAMES[cid]
   if query and query not in name.lower() and query not in str(cid):continue
   quantity=self.sd_quantities[cid-1] if len(self.sd_quantities)>=cid else 0;tree.insert('','end',iid=str(cid),text=name,image=self.row_image(tree,cid),values=(cid,quantity,deck_counts.get(cid,0)))
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
  self.sd_quantities[self.sd_selected_card-1]=quantity;self.refresh_savedata_card_list();self.sd_cards_tree.selection_set(str(self.sd_selected_card));self.select_savedata_card()
 def refresh_savedata_deck(self):
  if not hasattr(self,'sd_deck_tree'):return
  tree=self.sd_deck_tree;tree.delete(*tree.get_children());occupied=0
  for slot,cid in enumerate(self.sd_deck):
   c=self.cards.get(cid) if cid else None;name=c.name if c else (CARD_NAMES.get(cid,f'Card {cid}') if cid else 'Empty slot');occupied+=bool(cid);tree.insert('','end',iid=str(slot),text=f'{slot+1:02d}  ·  {name}',image=self.row_image(tree,cid) if cid else '',values=(cid if cid else '—',))
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
  self.sd_deck[self.sd_selected_slot]=cid;self.refresh_savedata_deck();self.refresh_savedata_card_list();self.sd_cards_tree.selection_set(str(cid));self.select_savedata_card()
 def clear_savedata_deck_slot(self):
  if self.sd_doc is None or self.sd_selected_slot is None:return messagebox.showinfo('Save Data Editor','Open a save and select a deck slot first.')
  self.sd_deck[self.sd_selected_slot]=0;self.refresh_savedata_deck();self.refresh_savedata_card_list()
 def fill_starter_cards(self):
  selected=self.starter_tree.selection()[0] if self.starter_tree.selection() else None;self.starter_tree.delete(*self.starter_tree.get_children());q=self.starter_query.get().strip().lower();entries=list(self.cards.cards.items());kind=self.starter_type.get()
  if kind!='All types':entries=[(i,c) for i,c in entries if CARD_TYPES[c.type_id]==kind]
  if self.starter_sort.get()=='Card ID':entries.sort(key=lambda x:x[0])
  elif self.starter_sort.get()=='ATK':entries.sort(key=lambda x:(x[1].atk,x[1].name.lower()))
  elif self.starter_sort.get()=='DEF':entries.sort(key=lambda x:(x[1].def_,x[1].name.lower()))
  else:entries.sort(key=lambda x:x[1].name.lower())
  for cid,c in entries:
   if not q or q in c.name.lower() or q in str(cid):self.starter_tree.insert('','end',iid=str(cid),text=f'{c.name}   ·   {c.atk} / {c.def_}',image=self.row_image(self.starter_tree,cid))
  if selected and self.starter_tree.exists(selected):self.starter_tree.selection_set(selected);self.starter_tree.focus(selected);self.select_starter_card()
 def reset_starter_filters(self):
  self.starter_query.set('');self.starter_type.set('All types');self.starter_sort.set('Name');self.fill_starter_cards()
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
 def add_card_to_starter_deck(self,cid):
  if len(self.deck_ids)>=40:return messagebox.showinfo('Deck is full','The starter deck has 40 cards.')
  if self.deck_ids.count(cid)>=3:return messagebox.showinfo('Copy limit','A starter deck can contain up to three copies of a card.')
  self.deck_ids.append(cid);self.dirty=True;self.refresh_deck_view();self.status.configure(text=f'Added {self.cards[cid].name} to the starter deck.')
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
   self.status.configure(text=f'{self.cards[cid].name} has no copy in the starter deck.')
   return
  self.dirty=True;self.refresh_deck_view();self.status.configure(text=f'Removed one copy of {self.cards[cid].name} from the starter deck.')
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
   thumb=Image.new('RGBA',(164,48),'#1d293b')
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
    star.polygon(points,fill='#f5cf58',outline='#80662a');star.text((149,17),str(getattr(card,'level',0)),fill='#f5cf58')
   self.mini_photos[cid]=ImageTk.PhotoImage(thumb)
  return self.mini_photos.get(cid,self.placeholder_photo)
 def refresh_deck_view(self):
  if not hasattr(self,'deck_tree'):return
  self.deck_tree.delete(*self.deck_tree.get_children());counts={}
  for cid in self.deck_ids:counts[cid]=counts.get(cid,0)+1
  for cid,count in counts.items():
   c=self.cards.get(cid);name=c.name if c else f'Card {cid}';self.deck_tree.insert('','end',iid=str(cid),text=f'{name}   ×{count}',image=self.row_image(self.deck_tree,cid))
  self.deck_count.configure(text=f'{len(self.deck_ids)} / 40 cards')
 def build_ui(self):
  self.build_page.columnconfigure(0,weight=1);ttk.Label(self.build_page,text='DUEL REWARDS & EXPORT',font=('Segoe UI',22,'bold')).grid(row=0,column=0,sticky='w',pady=(8,4));ttk.Label(self.build_page,text='Set how many cards are awarded after a duel, then build a patched disc image for DuckStation.',wraplength=900).grid(row=1,column=0,sticky='w',pady=(0,18));self.dropcount=tk.StringVar(value='1')
  reward=ttk.LabelFrame(self.build_page,text='CARDS DROPPED AFTER A DUEL',padding=18);reward.grid(row=2,column=0,sticky='ew',pady=8);ttk.Label(reward,text='DROP COUNT',font=('Segoe UI',10,'bold')).pack(side='left',padx=(0,14));ttk.Spinbox(reward,textvariable=self.dropcount,from_=1,to=100,width=7,font=('Segoe UI',18,'bold')).pack(side='left');ttk.Label(reward,text='cards after each win  ·  1–100',font=('Segoe UI',14)).pack(side='left',padx=12)
  self.reward_rom_status=tk.StringVar(value='Open a ROM to identify its reward routine.')
  ttk.Label(reward,textvariable=self.reward_rom_status,font=('Segoe UI',10,'bold'),wraplength=900).pack(anchor='w',pady=(14,4))
  ttk.Label(reward,text='Multi-card rewards are patched only when the executable matches the supported retail reward hooks. Custom mod reward routines are preserved to prevent victory-screen hangs.',wraplength=900).pack(anchor='w',pady=(2,2))
  actions=ttk.Frame(self.build_page);actions.grid(row=3,column=0,sticky='ew',pady=18);ttk.Button(actions,text='Reset reward settings',command=self.reset_build_tab).pack(side='left');ttk.Button(actions,text='Build patched disc for DuckStation…',command=self.export).pack(side='right');self.progress=ttk.Label(self.build_page,text='');self.progress.grid(row=4,column=0,sticky='w')
 def reset_build_tab(self):
  self.dropcount.set('1');self.dirty=True;self.status.configure(text='Reward count reset to one card per duel.')
 def inspect_reward_routine(self,exe):
  if hashlib.sha256(exe).hexdigest()==RETAIL_US_EXE_SHA256:
   return 'Verified clean USA executable (SLUS_014.11); multi-card reward override is supported.'
  from core.engine_patches import EnginePatchManager
  checks=EnginePatchManager.validate_memory_integrity(exe,bytes())
  if all(checks.get(k,False) for k in ('audio_queue_trigger_ok','post_duel_hook_ok','victory_hook_ok','victory_return_ok','dispatcher_present','block2_payload_loader_ok','drop_multiplier_valid')):
   return 'Workshop reward patch detected. Open an unpatched original image before exporting again.'
  if self.has_retail_reward_layout(exe):
   return 'Supported retail reward hooks and free code space found; multi-card reward override is available.'
  return 'Custom or modified duel reward code. The editor will preserve it; drop count may not change.'
 def open(self):
  f=filedialog.askopenfilename(filetypes=[('Disc images','*.img *.bin *.iso *.cue *.ccd'),('All files','*.*')])
  if not f:return
  if self.disc and self.dirty and not messagebox.askyesno('Discard unsaved edits','Opening another image will replace the current ROM edits. Continue?'):return
  stage='opening disc image'
  try:
   d=Disc(f);stage='extracting game files';e=d.extract_file('SLUS_014.11');w=d.extract_file('DATA/WA_MRG.MRG');self.disc=d;self.exe=bytearray(e);self.wa=bytearray(w)
   stage='building opponent portrait gallery';self.refresh_opponent_gallery()
   stage='checking duel reward code';self.reward_rom_status.set(self.inspect_reward_routine(e))
   stage='loading card records';self.cards.load_from_exe_and_wa(e,w);self.original_cards=copy.deepcopy(self.cards.cards);self.original_wa=bytes(w)
   stage='loading card artwork';self.art._custom_artworks.clear();self.art.set_wa_data(w);self.card_list_icons=extract_card_list_icons(w);self.mini_photos.clear()
   stage='loading fusion data';self.fusions.load_from_wa(w)
   stage='resetting card and list filters';self.reset_card_filters();self.starter_query.set('');self.starter_type.set('All types');self.starter_sort.set('Name');self.fusion_query.set('');self.fusion_sort.set('Result name');self.drop_query.set('');self.drop_type.set('All types');self.drop_sort.set('Card name')
   stage='building Card Studio list';self.fill()
   stage='building starter deck card list';self.fill_starter_cards()
   stage='building fusion card selectors';self.set_card_picker_values();self.refresh_deck_view()
   self.dirty=False;self.status.configure(text=f'{Path(f).name} • {len(self.cards.cards):,} cards');selected='1' if self.tree.exists('1') else next(iter(self.tree.get_children()),None)
   stage='selecting the first card'
   if selected:self.tree.selection_set(selected);self.select()
   stage='building fusion recipe list';self.load_fusions()
   stage='building opponent drop list';self.load_drops()
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
   trial=FusionDatabase();trial.raw_table=bytearray(self.fusions.raw_table);trial.fusions=dict(self.fusions.fusions)
   self.fusion_summary.configure(text=f'Applying {len(pairs):,} card pairs…');self.update_idletasks();trial.fusions.update((pair,result) for pair in pairs)
   if not trial.compact():raise ValueError(f'The selected filters expand to {len(pairs):,} recipes, which do not fit in the game fusion table. Narrow the filters or add exceptions.')
   self.fusions.raw_table=trial.raw_table;self.fusions.fusions=trial.fusions;self.dirty=True;self.update_fusion_summary();self.load_fusions();messagebox.showinfo('Fusion recipe',f'Added or updated {len(pairs):,} card pair(s) to produce {self.cards.get(result).name}.')
  except Exception as e:self.update_fusion_summary();messagebox.showerror('Fusion',str(e))
 def fusion_del(self):
  s=self.ft.selection()
  if s:
   a,b,_=self.fusion_rows[int(s[0])]
   if not self.fusions.delete_fusion(a,b):return messagebox.showerror('Fusion recipe','There is not enough free space to safely detach this shared recipe list.')
   self.dirty=True;self.load_fusions()
 def load_fusions(self):
  if not hasattr(self,'ft'):return
  self.ft.delete(*self.ft.get_children());self.fusion_rows=[];query=self.fusion_query.get().strip().lower();rows=[]
  for (a,b),r in self.fusions.fusions.items():
   ca=self.cards.get(a);cb=self.cards.get(b);cr=self.cards.get(r)
   if ca is None or cb is None or cr is None:continue
   na=ca.name;nb=cb.name;nr=cr.name
   if query and query not in na.lower() and query not in nb.lower() and query not in nr.lower():continue
   rows.append((a,b,r,na,nb,nr))
  if self.fusion_sort.get()=='Material name':rows.sort(key=lambda x:(x[3].lower(),x[4].lower(),x[5].lower()))
  elif self.fusion_sort.get()=='Card ID':rows.sort(key=lambda x:(x[0],x[1],x[2]))
  else:rows.sort(key=lambda x:(x[5].lower(),x[3].lower(),x[4].lower()))
  for a,b,r,na,nb,nr in rows[:2000]:
   row=len(self.fusion_rows);self.fusion_rows.append((a,b,r));self.ft.insert('','end',iid=str(row),text=f'{nr}   ←   {na} + {nb}',image=self.row_image(self.ft,r))
  self.fusion_count.configure(text=f'{len(self.fusion_rows):,} shown  /  {len(self.fusions.fusions):,} recipes')
 def load_drops(self):
  if not self.wa or not hasattr(self,'dt'):return
  if self.duelist.get() not in DUELISTS:self.duelist.set(DUELISTS[0])
  d=DUELISTS.index(self.duelist.get());self.drop_title.configure(text=self.duelist.get());self.dt.delete(*self.dt.get_children());self.drop_weights={};pool=['S/A POW','B/C/D','S/A TEC'].index(self.pool.get());base=0xE9B000+d*0x1800+(pool+1)*1460;rows=[];query=self.drop_query.get().strip().lower();kind=self.drop_type.get()
  for i in range(722):
   weight=struct.unpack_from('<H',self.wa,base+i*2)[0]
   if weight:
    cid=i+1;c=self.cards.get(cid)
    if c is None:continue
    if query and query not in c.name.lower() and query not in str(cid):continue
    if kind!='All types' and CARD_TYPES[c.type_id]!=kind:continue
    self.drop_weights[cid]=weight;rows.append((cid,c,weight))
  if self.drop_sort.get()=='Card ID':rows.sort(key=lambda x:x[0])
  elif self.drop_sort.get()=='Weight':rows.sort(key=lambda x:(x[2],x[1].name.lower()),reverse=True)
  elif self.drop_sort.get()=='Chance':rows.sort(key=lambda x:(x[2]/2048,x[1].name.lower()),reverse=True)
  else:rows.sort(key=lambda x:x[1].name.lower())
  for cid,c,weight in rows:self.dt.insert('','end',iid=str(cid),text=f'{c.name}   ·   weight {weight}   ·   {weight/2048*100:.2f}%',image=self.row_image(self.dt,cid))
  try:
   im=portraits.read(self.wa,d+1);self.dp_photo=ImageTk.PhotoImage(im.resize((160,160),Image.Resampling.NEAREST));self.dp.configure(image=self.dp_photo,text='')
  except Exception:self.dp.configure(image='',text='Portrait unavailable')
  if self.opponent_tree.exists(str(d+1)):
   try:
    im=portraits.read(self.wa,d+1).resize((52,52),Image.Resampling.NEAREST);photo=ImageTk.PhotoImage(im);self.opponent_photos[d+1]=photo;self.opponent_tree.item(str(d+1),image=photo)
   except Exception:pass
 def reset_drop_filters(self):
  self.drop_query.set('');self.drop_type.set('All types');self.drop_sort.set('Card name');self.duelist.set(DUELISTS[0]);self.pool.set('S/A POW')
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
  win=tk.Toplevel(self);win.title('Choose a card for this reward pool');win.geometry('720x600');win.transient(self);win.grab_set();win.columnconfigure(0,weight=1);win.rowconfigure(1,weight=1);query=tk.StringVar();entry=ttk.Entry(win,textvariable=query);entry.grid(row=0,column=0,sticky='ew',padx=12,pady=12);entry.insert(0,'Search card name');list_frame=ttk.Frame(win);list_frame.grid(row=1,column=0,sticky='nsew',padx=12);list_frame.columnconfigure(0,weight=1);list_frame.rowconfigure(0,weight=1);tree=ttk.Treeview(list_frame,columns=('stats',),show='tree headings');tree.heading('#0',text='CARD · TYPE / ATTRIBUTE / STARS');tree.heading('stats',text='ATK / DEF');tree.column('#0',width=500);tree.column('stats',width=130,anchor='center');tree.grid(row=0,column=0,sticky='nsew');scroll=ttk.Scrollbar(list_frame,orient='vertical',command=tree.yview);scroll.grid(row=0,column=1,sticky='ns');tree.configure(yscrollcommand=scroll.set)
  def fill_choices(*_):
   tree.delete(*tree.get_children());needle=query.get().strip().lower()
   for cid,c in self.cards.cards.items():
    if not needle or needle in c.name.lower() or needle in str(cid):tree.insert('','end',iid=str(cid),text=f'{c.name}   ·   {c.atk} / {c.def_}',image=self.mini_photo(cid))
  def choose(_=None):
   if not tree.selection():return
   cid=int(tree.selection()[0]);d=DUELISTS.index(self.duelist.get());pool=['S/A POW','B/C/D','S/A TEC'].index(self.pool.get());off=0xE9B000+d*0x1800+(pool+1)*1460+(cid-1)*2
   if struct.unpack_from('<H',self.wa,off)[0]==0:struct.pack_into('<H',self.wa,off,1)
   self.dirty=True;self.load_drops();self.dt.selection_set(str(cid));win.destroy()
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
 def export(self):
  if not self.disc:return messagebox.showinfo('ROM','Open a ROM image first.')
  try:
   if not self.apply_card():return
   rawcount=int(self.dropcount.get())
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
   from core.engine_patches import EnginePatchManager
   required=('audio_queue_trigger_ok','post_duel_hook_ok','victory_hook_ok','victory_return_ok','dispatcher_present','block2_payload_loader_ok','drop_multiplier_valid')
   reward_note='';reward_patch_applied=False
   source_checks=EnginePatchManager.validate_memory_integrity(bytes(self.exe),bytes())
   if all(source_checks.get(k,False) for k in required):
    raise ValueError('This image already contains the Workshop duel-reward patch that can hang at the win screen. Open the original unpatched disc image and export again; the replaced reward code cannot be safely reconstructed from this patched image.')
   else:
    retail_hooks=self.has_retail_reward_layout(self.exe)
    free_caves=retail_hooks
    if retail_hooks:
     # Card serialization must not turn a verified reward-compatible source into
     # a false custom-code detection. Restore only these reserved retail regions.
     for start,end in REWARD_PROTECTED_RANGES:out_exe[start:end]=self.exe[start:end]
    if retail_hooks and free_caves and rawcount==1:
     # The supported retail game already awards one card, so leave its engine intact.
     reward_note='The retail reward routine already awards one card per win.'
    elif retail_hooks and free_caves:
     # Only replace the known retail reward routine. A mod-specific reward hook
     # is left intact because the standalone payload is not compatible with it.
     original_reward_instruction=bytes(out_exe[0x126dc:0x126e0]);patched=EnginePatchManager.apply_drop_engine(out_exe,None,rawcount);out_exe[0x126dc:0x126e0]=original_reward_instruction
     checks=EnginePatchManager.validate_memory_integrity(bytes(out_exe),bytes())
     if patched<9 or not all(checks.get(k,False) for k in required) or checks.get('drop_multiplier')!=rawcount:raise ValueError('The duel reward override failed validation; no image was written.')
     reward_note=f'Workshop reward engine installed on the supported retail layout: {rawcount} card(s) per win.';reward_patch_applied=True
    else:
     reward_note='This ROM uses custom duel reward code, which was preserved to avoid a win-screen hang.'
     if rawcount>1:reward_note+=f' Its existing drop count remains in effect; the requested count of {rawcount} was not applied.'
   final_checks=EnginePatchManager.validate_memory_integrity(bytes(out_exe),bytes())
   if reward_patch_applied and (not all(final_checks.get(k,False) for k in required) or final_checks.get('drop_multiplier')!=rawcount):raise ValueError('The selected duel drop count could not be verified; no image was written.')
   if legacy_frame_patch_removed:reward_note=(reward_note+' Removed the obsolete frame-color game patch.').strip()
   output_ext='.iso' if self.disc.sector_size==2048 else '.bin'
   f=filedialog.asksaveasfilename(defaultextension=output_ext,initialfile=f'{OUTPUT_BASENAME}{output_ext}',filetypes=[('PS1 disc image','*.bin *.iso')])
   if f:
    self.progress.configure(text='Preparing patched image…');self.nb.state(['disabled']);self.open_btn.state(['disabled']);self.building=True
    for button in self.page_nav_buttons.values():button.state(['disabled'])
    def worker():
     try:
      self.disc.export(f,{'SLUS_014.11':bytes(out_exe),'DATA/WA_MRG.MRG':bytes(out_wa)},lambda p,s:self.events.put(('progress',s)))
      self.events.put(('done',(f,reward_note)))
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
     path,note=value;self.dirty=False;messagebox.showinfo('Export finished',f'Patched disc verified. Companion cue file created beside:\n{path}'+(f'\n\n{note}' if note else ''));self.progress.configure(text=f'Exported {Path(path).name}')
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
