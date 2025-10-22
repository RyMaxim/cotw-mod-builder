import json
import os
from pathlib import Path

from deca.ff_rtpc import RtpcNode, RtpcProperty, rtpc_from_binary
from modbuilder import mods
from modbuilder.mods import StatWithOffset

DEBUG = False
NAME = "Modify Lures"
DESCRIPTION = 'Increase the range and duration of different animal lure types. Pair with the "Increase Render Distance" mod to support ranges over 400m.'
FILE = mods.ANIMAL_INTEREST_FILE
OPTIONS = [
    {"name": "Remote Caller Range", "min": 200.0, "max": 990.0, "default": 200.0, "increment": 10},
    {"name": "Handheld Caller Range", "min": 150.0, "max": 990.0, "default": 150.0, "increment": 10, "note": "Default range varies from 150-500 meters depending on the caller"},
    {"name": "Scent Range", "min": 200.0, "max": 990.0, "default": 200.0, "increment": 10, "note": "Wind direction and strength impact effective range"},
    {"name": "Decoy Range", "min": 500.0, "max": 990.0, "default": 500.0, "increment": 10,},
    {"name": "Feeder Range", "min": 400.0, "max": 990.0, "default": 400.0, "increment": 10,},
    # {"name": "Feeder Proximity", "min": 0.0, "max": 400.0, "default": 400.0, "increment": 10, "note": "Minimum distance between two feeders"},
]

def format_options(options: dict) -> str:
  default_options = mods.get_mod_option_defaults(OPTIONS)
  remote_caller_range = options.get("remote_caller_range", default_options["remote_caller_range"])
  handheld_caller_range = options.get("handheld_caller_range", default_options["handheld_caller_range"])
  scent_range = options.get("scent_range", default_options["scent_range"])
  decoy_range = options.get("decoy_range", default_options["decoy_range"])
  feeder_range = options.get("feeder_range", default_options["feeder_range"])
  return f"Modify Lures (Remote: {remote_caller_range}m, Caller: {handheld_caller_range}m, Scent: {scent_range}m, Decoy: {decoy_range}m, Feeder: {feeder_range}m)"

class Lure:
  __slots__ = (
    'name_hash', 'name', 'type', 'display_name', 'range', 'price', 'quantity', 'weight'
  )
  name_hash: str
  name: str
  display_name: str
  type: str
  range: StatWithOffset
  price: StatWithOffset      # allows Modify Store to edit bait
  quantity: StatWithOffset   # allows Modify Store to edit bait
  weight: StatWithOffset     # allows Modify Store to edit bait

  def __init__(self, equipment: RtpcNode, name_hash: int, name: str) -> None:
    self.name_hash = name_hash
    self.name = name
    self._parse_type()
    self._map_display_name()
    self.price = StatWithOffset(value=0, offset=0)     # allows Modify Store to edit bait
    self.quantity = StatWithOffset(value=0, offset=0)  # allows Modify Store to edit bait
    self.weight = StatWithOffset(value=-1, offset=0)   # allows Modify Store to edit bait
    self._parse_prop_table(equipment)

  def __repr__(self) -> str:
    return f' Name: {self.display_name} [{self.name_hash} : {self.name}]  Type: {self.type}  Range: {self.range.value} @ {self.range.offset}  Quantity: {self.quantity.value} @ {self.quantity.offset}  Weight: {self.weight.value} @ {self.weight.offset}'

  def _map_display_name(self) -> None:
    if self.type == "feeder_bait" and (mapped_equipment := mods.map_equipment(self.name, self.type)):
      self.display_name = f"{mapped_equipment['type']}: {mapped_equipment['name']}"
    else:
      self.display_name = self.name

  def _parse_type(self) -> None:
    prefix_map = {
      "equipment_prc_caller": "remote_caller",
      "equipment_lure_caller": "handheld_caller",
      "equipment_lure_scent": "scent",
      "equipment_lure_decoy": "decoy",
      "equipment_bait_site": "feeder_bait",
    }
    for prefix, lure_type in prefix_map.items():
      if self.name.startswith(prefix):
        self.type = lure_type
        return
    raise KeyError(f"Unable to parse equipment type for {self.name} (hash {self.name_hash})")

  def _parse_prop_table(self, node: RtpcNode) -> dict:
    prop_hashes = {
      # 2739436891: "name",?
      3789380005: "price",
      2080442156: "range",
      # 2827970935: "proximity",?
      # 3921912834: "duration",?
      # 3799764358: "description",?
    }

    for prop in node.prop_table:
      if (prop_name := prop_hashes.get(prop.name_hash)):
        setattr(self, prop_name, StatWithOffset(prop))

def open_file(filename: Path) -> tuple[RtpcNode, bytearray]:
  with(filename.open("rb")) as f:
    data = rtpc_from_binary(f)
  f_bytes = bytearray(filename.read_bytes())
  return (data.root_node, f_bytes)

def load_lures() -> list[Lure]:
  root, _ext = os.path.splitext(FILE)
  equipment_name_hashes = json.load((mods.LOOKUP_PATH / f"{root}.json").open())["equipment_name_hash"]
  rtpc_root, _data = open_file(mods.get_org_file(FILE))

  lures = []
  for equipment_node in rtpc_root.child_table:
    name = equipment_name_hashes[str(equipment_node.name_hash)]
    if name:
      lures.append(Lure(equipment_node, equipment_node.name_hash, name))
  return lures

def format_range_updates(lures: list[Lure], new_ranges: dict) -> list[tuple[int, float]]:
  offsets_and_values = []
  for lure in lures:
    new_range = new_ranges[lure.type]
    offsets_and_values.append((lure.range.offset, new_range))
  return offsets_and_values

def process(options: dict) -> None:
  default_options = mods.get_mod_option_defaults(OPTIONS)
  remote_caller_range = options.get("remote_caller_range", default_options["remote_caller_range"])
  handheld_caller_range = options.get("handheld_caller_range", default_options["handheld_caller_range"])
  scent_range = options.get("scent_range", default_options["scent_range"])
  decoy_range = options.get("decoy_range", default_options["decoy_range"])
  feeder_range = options.get("feeder_range", default_options["feeder_range"])

  new_ranges = {
    "remote_caller": remote_caller_range,
    "handheld_caller": handheld_caller_range,
    "scent": scent_range,
    "decoy": decoy_range,
    "feeder_bait": feeder_range,
  }

  offsets_and_new_values = format_range_updates(ALL_LURES, new_ranges)
  mods.update_file_at_offsets_with_values(FILE, offsets_and_new_values)

ALL_LURES = load_lures()
