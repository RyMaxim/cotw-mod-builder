import re

import FreeSimpleGUI as sg

from deca.ff_rtpc import RtpcNode
from modbuilder import mods
from modbuilder.logging_config import get_logger
from modbuilder.mods import StatWithOffset

try:  # running normally (source)
    from modbuilder.plugins import modify_lures
except ModuleNotFoundError:  # running as an exe (PyInstaller)
    from plugins import modify_lures

logger = get_logger(__name__)


DEBUG = False
NAME = "Modify Store"
DESCRIPTION = "Modify prices and quantites of store items or apply bulk changes to an entire category. Individual and bulk changes in the same category can cause unintended results."
EQUIPMENT_FILE = mods.EQUIPMENT_DATA_FILE
LURE_FILE = modify_lures.FILE

class StoreItem:
  __slots__ = (
    'type',
    'name',
    'display_name',
    'detailed_type',
    'internal_name',
    'price',
    'quantity',
    'weight',
  )

  type: str                   # item type
  name: str                   # unique item name for specific item/variant
  display_name: str           # unique display name for specific item/variant
  detailed_type: str          # additional type data (weapon for ammo and Illuminated Iron Sights, category for Misc/Lures)
  internal_name: str          # used to match old naming schemes
  price: StatWithOffset
  quantity: StatWithOffset
  weight: StatWithOffset

  def __init__(self, equipment_node: RtpcNode, equipment_type: str) -> None:
    self.type = equipment_type
    self.internal_name = None
    self.detailed_type = None
    self._parse_prop_table(equipment_node)
    if self.type == "skin":
      self.display_name = self._parse_skin_name()
    if self.type != "skin":
      self._map_equipment_name()
    self._format_display_name()

  def __repr__(self) -> str:
    return f"{self.type}, {self.name} ({self.price.value}, {self.price.offset}, {self.quantity.value}, {self.quantity.offset})"

  def _parse_prop_table(self, equipment_node: RtpcNode) -> None:
    self.price = StatWithOffset(value=0, offset=0)
    self.quantity = StatWithOffset(value=0, offset=0)  # some items do not have quantity
    self.weight = StatWithOffset(value=-1, offset=0)  # some items do not have weight, -1 allows for legitimate items with 0 weight

    for prop in equipment_node.prop_table:
      name_hash = prop.name_hash
      data = prop.data

      if name_hash == 837395680 and self.type == "skin":  # 0x31e9a4e0, parse texture name to get skin names
        self.name = data.decode("utf-8")

      if name_hash == 3541743236 and self.type != "skin":  # 0xd31ab684 - "name", all other item types
        self.name = data.decode("utf-8")

      if name_hash == 588564970:  # 0x2314c9ea - old name pre-2.2.2
        if decoded := data.decode("utf-8"):
          self.internal_name = decoded

      if name_hash == 870267695:  # 0x33df3b2f
        self.price = StatWithOffset(prop)

      if name_hash == 1025589510:  # 0x3d214106
        self.weight = StatWithOffset(prop)

      if name_hash == 2979948800 and data != 4294967295:  # 0xb19e6900
          # some items in categories with quantity have no individual quantity (callers in "lures", backpacks in "misc")
          # those items will have a "quantity" of 4294967295 (max 32-bit integer) that we can ignore
          self.quantity = StatWithOffset(prop)

  def _parse_skin_name(self) -> None:
    skin_types = {
      "t1": "Paint",
      "t2": "Spray",
      "t3": "Material",
      "t4": "Camo",
      "t5": "Wrap",
    }
    parts = self.name.split("\\")  # parse texture name into something readable
    category = " ".join([x.capitalize() for x in parts[-2].split("_")])
    name = parts[-1].removesuffix("_dif.ddsc")
    if category == "Crosshair Thumbnails":
      category = "Reticle"
      pattern = r'^thumbnail_crosshair_(.*)_(\d\d)$'  # thumbnail_crosshair_mill_dot_01
      matches = re.match(pattern, name)
      display_name = f"Reticle: {" ".join([x.capitalize() for x in matches.group(1).split("_")])} {matches.group(2)}"
    else:
      pattern = r'(t\d)_(\d\d)$'  # camo_h2_lunar_new_year_1_t3_01 >> "Material 01"
      matches = re.search(pattern, name)
      display_name = f"{category}: {skin_types[matches.group(1)]} {matches.group(2)}"
    return display_name

  def _map_equipment_name(self) -> None:
    if (mapped_equipment := mods.map_equipment(self.name, self.type)):
      self.detailed_type = mapped_equipment.get("type", "")
      self.display_name = mods.format_variant_name(mapped_equipment)
    else:
      self.detailed_type = ""
      self.display_name = self.name

  def _format_display_name(self) -> None:
    detailed_type = self.detailed_type if self.detailed_type else ""
    if self.type in ["ammo", "misc", "weapon"]:
      self.display_name = f"{detailed_type}: {self.display_name}"
    if self.type == "sight":
      if self.display_name == "Illuminated Iron Sights":
        self.display_name = f"{self.display_name}: {detailed_type}"
    if self.type == "lure":
      self.display_name = f"{detailed_type}: {self.display_name.replace(" Decoy","").replace(" Caller","").replace(" Scent","")}"
    if self.type == "structure" and self.detailed_type:
      self.display_name = f"{detailed_type}: {self.display_name}"

def load_equipment_data(
    equipment_nodes: list[RtpcNode],
    equipment_type: str,
  ) -> list[StoreItem]:
  loaded_items = []
  for equipment_node in equipment_nodes:
    loaded_item = StoreItem(equipment_node, equipment_type)
    if (  # skip some invalid items
      (equipment_type == "optic" and loaded_item.name == "equipment_optics_camera_01")  # in-game "camera" item
      or (equipment_type == "weapon" and loaded_item.name == "equipment_weapon_clay_pigeon_01")  # Salzwiesen shooting range launcher
      or (equipment_type == "ammo" and loaded_item.name == "equipment_ammo_clay_pigeon_01")  # Salzwiesen shooting range ammo
    ):
      continue
    loaded_items.append(loaded_item)
  return sorted(loaded_items, key=lambda x: x.display_name)

def load_feeder_bait_data() -> list[modify_lures.Lure]:
  feeder_bait = [item for item in modify_lures.ALL_LURES if item.type == "feeder_bait"]
  return sorted(feeder_bait, key=lambda x: x.display_name)

def load_store_items() -> dict[str, list[StoreItem]]:
  equipment = mods.open_rtpc(mods.APP_DIR_PATH / "org" / EQUIPMENT_FILE)
  store_items = {}

  store_items["ammo"] = load_equipment_data(equipment.child_table[0].child_table, "ammo")
  store_items["misc"] = load_equipment_data( equipment.child_table[1].child_table, "misc")
  store_items["sight"] = load_equipment_data(equipment.child_table[2].child_table, "sight")
  store_items["optic"] = load_equipment_data(equipment.child_table[3].child_table, "optic")
  # store_items["vehicle"] = load_equipment_data(equipment.child_table[4].child_table, "vehicle")  # free with DLC, $20000 without (multiplayer only). Where is this value?
  store_items["skin"] = load_equipment_data(equipment.child_table[5].child_table, "skin")
  store_items["weapon"] = load_equipment_data(equipment.child_table[6].child_table, "weapon")
  store_items["structure"] = load_equipment_data(equipment.child_table[7].child_table, "structure")
  store_items["lure"] = load_equipment_data(equipment.child_table[8].child_table, "lure")
  store_items["feeder_bait"] = load_feeder_bait_data()
  logger.debug("Loaded store items")
  return store_items

def build_tab(item_type: str) -> sg.Tab:
  item_list = ALL_STORE_ITEMS[item_type]
  return sg.Tab(mods.title_from_key(item_type), [
    [sg.Combo([item.display_name for item in item_list], metadata=item_list, size=30, key=f"store_list_{item_type}", enable_events=True, expand_x=True)]
  ], key=f"store_tab_{item_type}")

def get_option_elements() -> sg.Column:
  layout = [[
      sg.TabGroup([[
        build_tab(key) for key in ALL_STORE_ITEMS
      ]], k="store_tab_group", enable_events=True),
      sg.Button("Add Category Modification", k="add_mod_group_store", button_color=f"{sg.theme_element_text_color()} on brown", p=((30,0),(30,0))),
    ],
    [sg.Column([
        [
          sg.T("Individual:", p=((10,0),(10,0)), text_color="orange"),
          sg.Checkbox("Auto-update price, quantity, and weight", font="_ 12", default=True, k="store_update_item_values", enable_events=True, p=((15,0),(10,0))),
        ],
        [sg.T("Price:", p=((30,0),(10,0))), sg.Input("", size=10, p=((34,0),(10,0)), k="store_item_price")],
        [sg.T("Quantity:", p=((30,0),(10,0)), k="store_item_quantity_label"), sg.Input("", size=10, p=((10,0),(10,0)), k="store_item_quantity")],
        [sg.T("Weight:", p=((30,0),(10,0)), k="store_item_weight_label"), sg.Input("", size=10, p=((17,0),(10,0)), k="store_item_weight")],
      ], p=(0,0), element_justification='left', vertical_alignment='top'),
      sg.Column([
        [sg.T("Bulk:", p=((0,0),(10,0)), text_color="orange"), sg.T('(use "Add Category Modification" to apply changes to all items in this category)', font="_ 12 italic", p=((0,0),(10,0)))],
        [sg.T("Category Discount Percent:", p=((20,0),(10,0))), sg.Slider((0,100), 0, 1, orientation="h", p=((10,0),(0,0)), k="store_bulk_discount")],
        [
          sg.T("Free to Price:", p=((20,0),(10,0))),
          sg.Input("0", size=10, p=((10,0),(10,0)), k="store_bulk_free_price"),
          sg.T('Set a price for "free" DLC / mission items in this category', font="_ 12 italic", text_color="orange", p=((10,10),(10,0)))
        ],
        [
          sg.T("Category Quantity:", p=((20,0),(12,0)), k="store_bulk_quantity_label"),
          sg.Input("", size=10, p=((10,0),(12,0)), k="store_bulk_quantity"),
          sg.T('Leave blank to use defaults', font="_ 12 italic", text_color="orange", p=((10,10),(10,0)))
        ],
        [
          sg.T("Category Weight:", p=((20,0),(12,0)), k="store_bulk_weight_label"),
          sg.Input("", size=10, p=((10,0),(12,0)), k="store_bulk_weight"),
          sg.T('Leave blank to use defaults', font="_ 12 italic", text_color="orange", p=((10,10),(10,0)))
        ],
      ], p=((130,0),(0,0)), element_justification='left', vertical_alignment='top'),
    ],
  ]
  return sg.Column(layout)

def get_selected_category(window: sg.Window) -> str:
  active_tab = str(window["store_tab_group"].find_currently_active_tab_key()).lower()
  return active_tab.removeprefix("store_tab_")

def get_selected_item(window: sg.Window, values: dict) -> StoreItem:
  item_type = get_selected_category(window)
  item_list = f"store_list_{item_type}"
  item_name = values.get(item_list)
  if item_name:
    try:
      item_index = window[item_list].Values.index(item_name)
      return window[item_list].metadata[item_index]
    except ValueError as _e:  # user typed/edited data in box and we cannot match
      pass
  return None

def handle_event(event: str, window: sg.Window, values: dict) -> None:
  if event.startswith("store_"):
    item_type = get_selected_category(window)
    selected_item = get_selected_item(window, values)
    if values["store_update_item_values"]:  # box checked = update values
      if selected_item:
        window["store_item_price"].update(selected_item.price.value)
        window["store_item_quantity"].update(selected_item.quantity.value)
        window["store_item_weight"].update(selected_item.weight.value)
      else:
        window["store_item_price"].update("")
        window["store_item_quantity"].update("")
        window["store_item_weight"].update("")
    if event.startswith("store_tab_"):
      category_quantity_disabled = bool(item_type in ["sight", "optic", "skin", "weapon", "feeder_bait"])
      window["store_item_quantity"].update(disabled=category_quantity_disabled)
      window["store_bulk_quantity"].update(disabled=category_quantity_disabled)
      category_weight_disabled = bool(item_type in ["skin", "feeder_bait"])
      window["store_item_weight"].update(disabled=category_weight_disabled)
      window["store_bulk_weight"].update(disabled=category_weight_disabled)

def add_mod(window: sg.Window, values: dict) -> dict:
  selected_item = get_selected_item(window, values)
  if not selected_item:
    return {
      "invalid": "Please select an item first"
    }

  try:
    item_price = int(values["store_item_price"])
  except ValueError:
    return {
      "invalid": "Provide a valid item price"
    }

  try:
    item_quantity = int(values["store_item_quantity"])
  except ValueError:
    return {
      "invalid": "Provide a valid item quantity"
    }

  try:
    item_weight = float(values["store_item_weight"])
  except ValueError:
    return {
      "invalid": "Provide a valid item weight"
    }

  return {
    "key": f"modify_store_{selected_item.name}",
    "invalid": None,
    "options": {
      "type": selected_item.type,
      "name": selected_item.name,
      "display_name": selected_item.display_name,
      "file": LURE_FILE if selected_item.type == "feeder_bait" else EQUIPMENT_FILE,
      "price": item_price,
      "quantity": item_quantity,
      "weight": item_weight,
    }
  }

def add_mod_group(window: sg.Window, values: dict) -> dict:
  bulk_discount = int(values["store_bulk_discount"])

  try:
    bulk_free_price = int(values["store_bulk_free_price"])
  except ValueError:
    return {
      "invalid": "Provide a valid bulk free price"
    }

  if window["store_bulk_quantity"].Disabled or not values["store_bulk_quantity"]:
    values["store_bulk_quantity"] = "0"
  try:
    bulk_quantity = int(values["store_bulk_quantity"])
  except ValueError:
    return {
      "invalid": "Provide a valid bulk quantity"
    }

  if window["store_bulk_weight"].Disabled or not values["store_bulk_weight"]:
    values["store_bulk_weight"] = "-1"
  try:
    bulk_weight = int(values["store_bulk_weight"])
  except ValueError:
    return {
      "invalid": "Provide a valid bulk weight"
    }

  item_type = get_selected_category(window)
  return {
    "key": f"modify_store_{item_type}",
    "invalid": None,
    "options": {
      "type": item_type,
      "file": LURE_FILE if item_type == "feeder_bait" else EQUIPMENT_FILE,
      "discount": bulk_discount,
      "free_price": bulk_free_price,
      "bulk_quantity": bulk_quantity,
      "bulk_weight": bulk_weight,
    }
  }

def format_options(options: dict) -> str:
  details = []
  if "free_price" in options:  # category - some pre-2.1.0 version didn't have "bulk_quantity"
    details.append(f"-{options['discount']}% discount")
    if options['free_price'] > 0:
      details.append(f"free > {options['free_price']}")
    if (bulk_quantity := options.get("bulk_quantity", 0)) > 0:
      details.append(f"{bulk_quantity} quantity")
    if (bulk_weight := options.get("bulk_weight", -1)) >= 0:
      details.append(f"{bulk_weight} kg")
    return f"Modify Store Category: {mods.title_from_key(options["type"])} ({' ,'.join(details)})"
  else:  # single item
    display_name = options.get("display_name", options["name"])  # diplay_name added in 2.2.2
    selected_item = next((i for i in ALL_STORE_ITEMS[options["type"]] if options["name"] == i.name), None)
    if not selected_item:
      selected_item = match_old_item(options)  # try to match options to a StoreItem
    if selected_item:
      display_name = selected_item.display_name
    details.append(f"${options["price"]}")
    if options["quantity"]:
      details.append(f"{options["quantity"]} quantity")
    if (weight := options.get("weight", -1)) >= 0:
      details.append(f"{weight} kg")
    return f"Modify Store: {mods.title_from_key(options["type"])} - {display_name} ({' ,'.join(details)})"

def handle_key(mod_key: str) -> bool:
  return mod_key.startswith("modify_store")

def get_files(options: dict) -> list[str]:
  return [LURE_FILE if options["type"] == "feeder_bait" else EQUIPMENT_FILE]

def process(options: dict) -> None:
  updates = []
  item_list = ALL_STORE_ITEMS[options["type"]]

  if "quantity" in options:  # single item
    selected_item = next((i for i in item_list if i.name == options["name"]), None)
    if selected_item:
      updates.append({"offset": selected_item.price.offset, "value": options["price"]})
      if options["quantity"] > 0 and selected_item.quantity.offset > 0:
        updates.append({"offset": selected_item.quantity.offset, "value": options["quantity"]})
      if options["weight"] >= 0 and selected_item.weight.offset > 0:
        updates.append({"offset": selected_item.weight.offset, "value": options["weight"]})

  if "bulk_quantity" in options:  # category
    discount = options["discount"]
    free_price = options["free_price"]
    bulk_quantity = options["bulk_quantity"]
    bulk_weight = options["bulk_weight"]
    for item in item_list:
      if discount > 0:
        updates.append({"offset": item.price.offset, "value": 1 - discount / 100, "transform": "multiply"})
      if free_price > 0:
        updates.append({"offset": item.price.offset, "value": free_price})
      if bulk_quantity > 0 and item.quantity.offset > 0:
        updates.append({"offset": item.quantity.offset, "value": bulk_quantity})
      if bulk_weight >= 0 and item.weight.offset > 0:
        updates.append({"offset": item.weight.offset, "value": bulk_weight})

  mods.apply_updates_to_file(LURE_FILE if options["type"] == "feeder_bait" else EQUIPMENT_FILE, updates)

def match_old_item(options: dict) -> StoreItem:
  selected_item = None
  # Try to match the old name format. This doesn't work in a few cases where names are not unique
  unmatchable_names = (
    "unknown",
    "trailscout mini daypack",  # small backpack - incorrect color names in save file
    "exoadventurer 32 light daypack",  # medium backpack - incorrect color names in save file
    "summit explorer 6000 pack",  # large backpack - incorrect color names in save file
    "illuminated iron sights",  # does not include associated weapon name
    "store_featured",  # new DLC weapons
    "placeable",  # "placeable decoy" and "placeable" structures are non-unique
    "eurasian teal  decoy",   # "Eurasian Wigeon" and "Goldeneye" hen decoys are mistakenly named in game files
    "eurasian teal decoy",  # "Eurasian Wigeon" drake decoys are mistakenly named in game files
  )

  if not options["name"].lower().startswith(unmatchable_names):
    cleaned_name = re.sub(r"\s*\(id: \d+\)", "", options["name"]).rstrip()  # remove " (id: 12345)"
    selected_item = next((i for i in ALL_STORE_ITEMS[options["type"]] if cleaned_name == i.internal_name), None)
    if not selected_item and options["type"] in ["weapons", "misc"]:
      # some weapons and misc items had special parsing for internal names over 40 characters
      # check against the regex from the old "handle_misc_name()" function
      for item in ALL_STORE_ITEMS[options["type"]]:
        if len(item.internal_name) > 40:
          short_internal_name = re.sub(r'\([\w\s\-\'\./]+\)$', "", item.internal_name).rstrip()
          if cleaned_name == short_internal_name:
            selected_item = item
  # 2.2.1 and prior relied on saved price and quantity offsets
  # This breaks when new items are added to `equipment_data.bin`
  # Try to match on those values. This is less accurate the older the save file is.
  if (
    not selected_item
    and "price_offset" in options
    and "quantity_offset" in options
  ):
    selected_item = next((i for i in ALL_STORE_ITEMS[options["type"]] if (
      options["price_offset"] == i.price.offset
      and options["quantity_offset"] == i.quantity.offset
    )), None)
  return selected_item

def handle_update(mod_key: str, mod_options: dict, version: str) -> tuple[str, dict]:
  """
  2.2.13
  - Modify prices of Feeder Bait from `animal_interest.bin` + Modify Lures
  2.2.7
  - Add weight modification
  2.2.5
  - Fix name swap between Hansson .30-06 and Quist Reaper 7.62x39 from Rapid Hunt Rifle Pack
  2.2.2
  - Parse exact prop data from each node for name, price, and quantity (do not save offsets)
  - Use formatted name from 'name_map.yaml' as display_name
  - Attempt to match items from imported save files by old display name or by matching offsets
  """
  if "quantity" in mod_options:  # single item
    mod_key, mod_options = _update_rapid_hunt_name_swap(mod_key, mod_options, version)
    selected_item = next((i for i in ALL_STORE_ITEMS[mod_options["type"]] if mod_options["name"] == i.name), None)
    if not selected_item:
      selected_item = match_old_item(mod_options)  # Try to parse the old item names/offsets to match with a StoreItem object
    if not selected_item:
      raise ValueError(f"Unable to match item \"{mod_options["name"]}\"")
    updated_mod_key = f"modify_store_{selected_item.name}"
    updated_mod_options = {
      "type": selected_item.type,
      "name": selected_item.name,
      "display_name": selected_item.display_name,
      "file": LURE_FILE if selected_item.type == "feeder_bait" else EQUIPMENT_FILE,
      "price": mod_options["price"],
      "quantity": mod_options.get("quantity", 0),
      "weight": mod_options.get("weight", -1),
    }

  elif "free_price" in mod_options:  # category
    updated_mod_key = f"modify_store_{mod_options["type"]}"
    updated_mod_options = {
      "type": mod_options["type"],
      "file": LURE_FILE if mod_options["type"] == "feeder_bait" else EQUIPMENT_FILE,
      "discount": mod_options["discount"],
      "free_price": mod_options["free_price"],
      "bulk_quantity": mod_options.get("bulk_quantity", 0),  # some pre-2.1.0 version didn't have "bulk_quantity"
      "bulk_weight": mod_options.get("bulk_weight", -1),  # added in 2.2.7
    }

  else:
    raise ValueError(f"Unable to parse config: {mod_options}")
  return updated_mod_key, updated_mod_options

def _update_rapid_hunt_name_swap(mod_key: str, mod_options: dict, version: str) -> tuple[str, dict]:
  if version == "2.2.4" or version.startswith("2.2.4.dev"):
    if mod_options["display_name"] == "Rifle: Hansson .30-06":
      mod_key = "modify_store_equipment_weapon_sa_rifle_30_06_01"
      mod_options["name"] = "equipment_weapon_sa_rifle_30_06_01"
    if mod_options["display_name"] == "Rifle: Quist Reaper 7.62x39":
      mod_key = "modify_store_equipment_weapon_sa_rifle_7_62_01"
      mod_options["name"] = "equipment_weapon_sa_rifle_7_62_01"
  return mod_key, mod_options

ALL_STORE_ITEMS = load_store_items()
