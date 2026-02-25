from deca.ff_rtpc import rtpc_from_binary, RtpcProperty, RtpcNode
from pathlib import Path
from modbuilder import mods
from modbuilder.mods import StatWithOffset
from enum import Enum
from modbuilder.logging_config import get_logger

logger = get_logger(__name__)

DEBUG = False
NAME = "Increase Deployables"
DESCRIPTION = "Increases the number of deployable structures you can place on all reserves."
FILE = "settings/hp_settings/reserve_*.bin"
OPTIONS = [
  { "name": "Deployable Multiplier", "min": 0.1, "max": 20, "default": 1, "increment": 0.1 }
]

TROPHY_LODGE_IDS = [
  5, # Spring Creek Manor
  7, # Saseka Safari Lodge
  15, # Layton Lakes Trophy Cabin
]

def format_options(options: dict) -> str:
  return f"Increase Deployables ({int(options['deployable_multiplier'])}x)"

class Deployable(str, Enum):
  DECOY = "decoy"
  BAIT_FEEDER = "bait_feeder"
  GROUNDBLIND = "groundblind"
  LAYOUTBLIND = "layoutblind"
  TENT = "tent"
  TREESTAND = "treestand"
  TRIPOD = "tripodstand"
  WATERFOWLBLIND = "waterfowlblind"

def _is_deployable_prop(value: str) -> bool:
  return any(d.value in value for d in Deployable)

def _is_deployable(props: list[RtpcProperty]) -> bool:
  for prop in props:
    if isinstance(prop.data, bytes) and _is_deployable_prop(prop.data.decode("utf-8")):
      return True
  return False

def _get_deployable_max_count(deployable: RtpcNode) -> StatWithOffset:
  for prop in deployable.prop_table:
    if prop.name_hash == 2415882446:  # 0x8fff70ce
      return StatWithOffset(prop)

def update_uint(data: bytearray, offset: int, new_value: int) -> None:
    value_bytes = new_value.to_bytes(4, byteorder='little')
    for i in range(0, len(value_bytes)):
        data[offset + i] = value_bytes[i]

def _get_world_items_tables(root: RtpcNode) -> RtpcNode:
  for table in root.child_table:
    if table.name_hash == 3050727908:  # 0xb5d669e4
      return table.child_table
  return None

def update_reserve_deployables(root: RtpcNode, f_bytes: bytearray, multiply: int, reserve_id: int) -> None:
  world_items_tables = _get_world_items_tables(root)
  if not world_items_tables:
    raise ValueError(f"Unable to parse world items data table for reserve {reserve_id}")
  deployable_values = []
  for table in world_items_tables:
    if _is_deployable(table.prop_table):
      max_count = _get_deployable_max_count(table)
      if max_count:
        deployable_values.append(max_count)

  try:
    for deployable_value in deployable_values:
      update_uint(f_bytes, deployable_value.offset, deployable_value.value * multiply)
  except Exception as ex:
     logger.exception(f"received error: {ex}")

def save_file(filename: str, data: bytearray) -> None:
    base_path = mods.APP_DIR_PATH / "mod/dropzone/settings/hp_settings"
    base_path.mkdir(exist_ok=True, parents=True)
    (base_path / filename).write_bytes(data)

def open_reserve(filename: Path) -> tuple[RtpcNode, bytearray]:
  with(filename.open("rb") as f):
    data = rtpc_from_binary(f)
  f_bytes = bytearray(filename.read_bytes())
  return (data.root_node, f_bytes)

def update_all_deployables(source: Path, multiply: int) -> None:
  for file in list(source.glob("reserve_*.bin")):
    reserve_id = int(file.stem.split("_")[1])
    if reserve_id in TROPHY_LODGE_IDS:
      continue
    root, data = open_reserve(file)
    update_reserve_deployables(root, data, multiply, reserve_id)
    save_file(file, data)

def process(options: dict) -> None:
  multiply = int(options["deployable_multiplier"])
  update_all_deployables(mods.APP_DIR_PATH / "mod/dropzone/settings/hp_settings", multiply)
