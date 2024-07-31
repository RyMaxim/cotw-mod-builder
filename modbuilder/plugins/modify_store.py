from typing import List, Tuple
from modbuilder import mods, PySimpleGUI_License
from pathlib import Path
from deca.ff_rtpc import rtpc_from_binary, RtpcNode
import PySimpleGUI as sg
import re

DEBUG = False
NAME = "Modify Store"
DESCRIPTION = "Modify the store prices. I would discourage you from adding individual and bulk modifications for the same category at the same time."
EQUIPMENT_FILE = "settings/hp_settings/equipment_data.bin"

class StoreItem:
  def __init__(self, type: str, name: str, price: int, price_offset: int, quantity: int, quantity_offset: int) -> None:
    self.type = type
    self.name = name
    self.price = price
    self.price_offset = price_offset
    self.quantity = quantity
    self.quantity_offset = quantity_offset
  
  def __repr__(self) -> str:
    return f"{self.type}, {self.name} ({self.price}, {self.price_offset}, {self.quantity}, {self.quantity_offset})"

def open_rtpc(filename: Path) -> RtpcNode:
  with filename.open("rb") as f:
    data = rtpc_from_binary(f) 
  root = data.root_node
  return root

def load_price_node(items: List[RtpcNode], type: str, name_offset: int = 4, price_offset: int = 7, quantity_offset = 13, name_handle: callable = None, price_handle: callable = None):
  prices = []
  for item in items:
    if name_handle:
      name = name_handle(item)
    else:
      try:
        name = item.prop_table[name_offset].data.decode("utf-8")
      except:
        name = "unknown"
    if price_handle:
      price, price_offset_value = price_handle(item)
    else:
      price_item = item.prop_table[price_offset]
      if isinstance(price_item.data, bytes):
        price_item = item.prop_table[price_offset + 1]
      price = price_item.data
      price_offset_value = price_item.data_pos
    
    if quantity_offset is None:
      quantity = 0
      quantity_offset_value = -1
    else:
      quantity_item = item.prop_table[quantity_offset]
      quantity = quantity_item.data
      if (isinstance(quantity, int) and quantity > 100) or not isinstance(quantity, int):
        quantity = 0
        quantity_offset_value = -1
      else:
        quantity_offset_value = quantity_item.data_pos
    
    prices.append(StoreItem(type, f"{name} (id: {price_offset_value})", price, price_offset_value, quantity, quantity_offset_value))
  return sorted(prices, key=lambda x: x.name)

def handle_lure_name(item: RtpcNode) -> str:
  if isinstance(item.prop_table[1].data, bytes):
    return item.prop_table[1].data.decode("utf-8")
  elif isinstance(item.prop_table[4].data, bytes):
    return item.prop_table[4].data.decode("utf-8")
  return "Unknown Lure"

def  handle_lure_price(item: RtpcNode) -> Tuple[int,int]:
  if isinstance(item.prop_table[1].data, bytes):
    second_prop = item.prop_table[1].data.decode("Utf-8").lower()
    if "caller" in second_prop or "call" in second_prop or "rattler" in second_prop:
      return (item.prop_table[0].data, item.prop_table[0].data_pos)
  else:
    return (item.prop_table[7].data, item.prop_table[7].data_pos)

def handle_skin_name(item: RtpcNode) -> str:
  if isinstance(item.prop_table[9].data, bytes):
    parts = item.prop_table[9].data.decode("utf-8").split("\\")
    map = " ".join([x.capitalize() for x in parts[-2].split("_")])
    name = parts[-1].replace(".ddsc", "").replace("_dif", "")
    name = f"{map} {name}"
    return re.sub(r'_(\w+)$', '', name)
  return "Unknown Skin"

def handle_misc_name(item: RtpcNode) -> str:
  name = item.prop_table[4].data
  if type(name) is bytes:
    name = name.decode("utf-8")
  else:
    name = item.prop_table[5].data
    if type(name) is bytes:
      name = name.decode("utf-8")
    else:
      name = "unknown"
  if len(name) > 40:
    return re.sub(r'\([\w\s\-\'\./]+\)$', "", name)
  else:
    return name

def load_equipement_prices() -> dict:
  equipment = open_rtpc(mods.APP_DIR_PATH / "org" / EQUIPMENT_FILE)
  ammo_items = equipment.child_table[0].child_table
  misc_items = equipment.child_table[1].child_table
  sights_items = equipment.child_table[2].child_table
  optic_items = equipment.child_table[3].child_table
  skin_items = equipment.child_table[5].child_table
  weapon_items = equipment.child_table[6].child_table
  portable_items = equipment.child_table[7].child_table
  lures_items = equipment.child_table[8].child_table
  
  return {
    "ammo": load_price_node(ammo_items, "Ammo", name_offset=1, price_offset=0),
    "misc": load_price_node(misc_items, "Misc", name_handle=handle_misc_name, quantity_offset=15),
    "sight": load_price_node(sights_items, "Sight", name_offset=1, price_offset=0, quantity_offset=None),
    "optic": load_price_node(optic_items, "Optic", quantity_offset=None),
    "skin": load_price_node(skin_items, "Skin", name_handle=handle_skin_name, quantity_offset=None),
    "weapon": load_price_node(weapon_items, "Weapon", price_offset=8, name_handle=handle_misc_name, quantity_offset=None),
    "structure": load_price_node(portable_items, "Structure", quantity_offset=None),
    "lure": load_price_node(lures_items, "Lure", name_handle=handle_lure_name, price_handle=handle_lure_price, quantity_offset=15)
  }

def build_tab(type: str, items: List[StoreItem], include_quantity: bool = True) -> sg.Tab:
  type_key = type.lower()
  layout = [
    [sg.T("Individual:", p=((10,0),(20,0)), text_color="orange")],
    [sg.T("Item", p=((30,7),(10,0))), sg.Combo([x.name for x in items], metadata=items, k=f"{type_key}_item_name", p=((10,10),(10,0)), enable_events=True)],
    [sg.T("Price", p=((30,0),(10,0))), sg.Input("", size=10, p=((10,0),(10,0)), k=f"{type_key}_item_price")]
  ]
  if include_quantity:
    layout.append(
      [sg.T("Quantity", p=((30,0),(10,0))), sg.Input("", size=10, p=((10,0),(10,0)), k=f"{type_key}_item_quantity")],  
    )
  layout.extend([
      [sg.T("Bulk:", p=((10,0),(20,0)), text_color="orange"), sg.T("(applies to all items in this category)", font="_ 12", p=((0,0),(20,0)))],
      [sg.T("Change Free to Price", p=((30,0),(10,0)))],
      [sg.Input("", size=10, p=((60,0),(10,0)), k=f"{type_key}_free_price")], 
      [sg.T("Discount Percent", p=((30,0),(10,0)))],
      [sg.Slider((0,100), 0, 1, orientation="h", p=((60,0),(10,0)), k=f"{type_key}_discount")],             
  ])
  if include_quantity:
    layout.extend([
      [sg.T("Quantity", p=((30,0),(10,0)))],
      [sg.Input("", size=10, p=((60,0),(10,0)), k=f"{type_key}_bulk_quantity")],       
      [sg.T("")] 
    ])
  else:
    layout.append([sg.T("")])
  
  return sg.Tab(type, layout, k=f"{type_key}_store_tab")

def get_option_elements() -> sg.Column:
  equipment_prices = load_equipement_prices()
  
  layout = [[
    sg.TabGroup([[
      build_tab("Ammo", equipment_prices["ammo"]),
      build_tab("Misc", equipment_prices["misc"]),
      build_tab("Sight", equipment_prices["sight"], include_quantity=False),
      build_tab("Optic", equipment_prices["optic"], include_quantity=False),
      build_tab("Skin", equipment_prices["skin"], include_quantity=False),
      build_tab("Weapon", equipment_prices["weapon"], include_quantity=False),
      build_tab("Structure", equipment_prices["structure"], include_quantity=False),
      build_tab("Lure", equipment_prices["lure"]),
    ]], k="store_group")
  ]]
  return sg.Column(layout)

def handle_event(event: str, window: sg.Window, values: dict) -> None:
  if event.endswith("item_name"):
    type_key = event.split("_")[0]
    item_name = values[event]
    item_index = window[event].Values.index(item_name)
    item_price = window[event].metadata[item_index].price
    window[f"{type_key}_item_price"].update(item_price)
    
    item_quantity = window[event].metadata[item_index].quantity
    quantity_key = f"{type_key}_item_quantity"    
    if item_quantity > 0:
      window[quantity_key].update(item_quantity, disabled=False)      
    elif quantity_key in window.key_dict:
      window[quantity_key].update(item_quantity, disabled=True)

def add_mod(window: sg.Window, values: dict) -> dict:
  active_tab = window["store_group"].find_currently_active_tab_key().lower() 
  active_tab = active_tab.split("_")[0]
  
  discount = int(values[f"{active_tab}_discount"])
  free_price = values[f"{active_tab}_free_price"]
  if f"{active_tab}_bulk_quantity" in values:
    bulk_quantity = values[f"{active_tab}_bulk_quantity"]
  else:
    bulk_quantity = "0"
    
  if free_price.isdigit():
    free_price = int(free_price)
  elif free_price != "":
    return {
      "invalid": "Provide a valid free price"
    }    
  else:
    free_price = 0
  if bulk_quantity.isdigit():
    bulk_quantity = int(bulk_quantity)
  elif bulk_quantity == "":
    bulk_quantity = 0
  else:
    return {
      "invalid": f"Provide a valid bulk quantity ({bulk_quantity})"
    }    

  bulk_provided = discount != 0 or free_price != 0 or bulk_quantity != 0
  
  item_key = f"{active_tab}_item_name"
  item_metadata = window[item_key].metadata
  if not bulk_provided:    
    item_name = values[item_key]
    if not item_name:
      return {
        "invalid": "Please select an item first"
      }
    item_index = window[item_key].Values.index(item_name)
    item = item_metadata[item_index]
    item_price = values[f"{active_tab}_item_price"]
    if f"{active_tab}_item_quantity" in values:
      item_quantity = values[f"{active_tab}_item_quantity"]
    else:
      item_quantity = "0"
      
    if item_price.isdigit():
      item_price = int(item_price)
    else:
      return {
        "invalid": "Provide a valid item price"
      }
    if item_quantity.isdigit():
      item_quantity = int(item_quantity)
    else:
      return {
        "invalid": "Provide a valid item quantity"
      }      
    
    return {
      "key": f"modify_store_{item.name}",
      "invalid": None,
      "options": {
        "type": active_tab,
        "name": item.name,
        "file": EQUIPMENT_FILE,
        "price_offset": item.price_offset,
        "price": item_price,
        "quantity_offset": item.quantity_offset,
        "quantity": item_quantity
      }    
    }
  else:
    return {
      "key": f"modify_store_{active_tab}",
      "invalid": None,
      "options": {
        "type": active_tab,
        "file": EQUIPMENT_FILE,
        "discount": discount,
        "free_price": free_price,
        "bulk_quantity": bulk_quantity
    }
  }

def format(options: dict) -> str:
  if "free_price" in options:
    return f"Modify Store {options['type'].capitalize()} ({options['discount']}%, {options['free_price']}, {options['bulk_quantity'] if 'bulk_quantity' in options else '0'})"
  else:
    return f"{options['name']} ({options['price']}, {options['quantity']})"

def handle_key(mod_key: str) -> bool:
  return mod_key.startswith("modify_store")

def get_files(options: dict) -> List[str]:
  return [EQUIPMENT_FILE]

def process(options: dict) -> None:
  file = options["file"]
  if "free_price" in options:
    discount = options["discount"]
    free_price = options["free_price"]
    bulk_quantity = options["bulk_quantity"] if "bulk_quantity" in options else 0
    prices = load_equipement_prices()[options["type"]]
    if discount != 0:
      offsets = [x.price_offset for x in prices]
      mods.update_file_at_offsets(file, offsets, 1 - discount / 100, transform="multiply")
    if free_price != 0:
      offsets = [x.price_offset for x in prices if x.price == 0]
      mods.update_file_at_offsets(file, offsets, free_price)
    if bulk_quantity != 0:
      offsets = [x.quantity_offset for x in prices]
      offsets = list(filter(lambda x: x != -1, offsets))
      mods.update_file_at_offsets(file, offsets, bulk_quantity)
  else:
    mods.update_file_at_offset(file, options["price_offset"], options["price"])
    if options["quantity"] > 0:
      mods.update_file_at_offset(file, options["quantity_offset"], options["quantity"])