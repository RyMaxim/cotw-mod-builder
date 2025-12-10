from deca.ff_rtpc import rtpc_from_binary, RtpcProperty, RtpcNode
from pathlib import Path
from modbuilder import mods
from enum import Enum
from modbuilder.logging_config import get_logger

logger = get_logger(__name__)

DEBUG = False
NAME = "Increase Deployables"
DESCRIPTION = "Increases the number of deployable structures you can place on all reserves."
FILE = "settings/hp_settings/reserve_*.bin"
OPTIONS = [
  { "name": "Deployable Multiplier", "min": 2, "max": 20, "default": 1, "increment": 1 }
]

TROPHY_LODGE_IDS = [
  5, # Spring Creek Manor
  7, # Saseka Safari Lodge
  15, # Layton Laykes Trophy Cabin
]

def format_options(options: dict) -> str:
  return f"Increase Deployables ({int(options['deployable_multiplier'])}x)"

class Deployable(str, Enum):
  LAYOUTBLIND = "layoutblind"
  TREESTAND = "treestand"
  TENT = "tent"
  TRIPOD = "tripodstand"
  GROUNDBLIND = "groundblind"
  DECOY = "decoy"
  BAIT_FEEDER = "bait_feeder"

class DeployableValue:
  def __init__(self, value: int, offset: int) -> None:
    self.value = value
    self.offset = offset

  def __repr__(self) -> str:
    return f"{self.value:} ({self.offset}))"

def is_deployable_prop(value: str) -> bool:
  return any(x in value for x in (
    Deployable.LAYOUTBLIND,
    Deployable.TREESTAND,
    Deployable.TENT,
    Deployable.TRIPOD,
    Deployable.GROUNDBLIND,
    Deployable.DECOY,
    Deployable.BAIT_FEEDER,
  ))

def is_deployable(props: list[RtpcProperty]) -> bool:
  for prop in props:
    if isinstance(prop.data, bytes) and is_deployable_prop(prop.data.decode("utf-8")):
      return True
  return False

def update_uint(data: bytearray, offset: int, new_value: int) -> None:
    value_bytes = new_value.to_bytes(4, byteorder='little')
    for i in range(0, len(value_bytes)):
        data[offset + i] = value_bytes[i]

def update_reserve_deployables(root: RtpcNode, f_bytes: bytearray, multiply: int) -> None:
  for data_table in root.child_table:
    if data_table.name_hash == 3050727908:  # 0xb5d669e4
      deployables = data_table.child_table
  deployable_values = []
  for deployable in deployables:
    if is_deployable(deployable.prop_table):
      prop = deployable.prop_table[-1]
      deployable_values.append(DeployableValue(prop.data, prop.data_pos))

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
    update_reserve_deployables(root, data, multiply)
    save_file(file, data)

def process(options: dict) -> None:
  multiply = int(options["deployable_multiplier"])
  update_all_deployables(mods.APP_DIR_PATH / "mod/dropzone/settings/hp_settings", multiply)
