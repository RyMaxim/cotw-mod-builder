from deca.ff_rtpc import rtpc_from_binary, RtpcProperty, RtpcNode
from pathlib import Path
from modbuilder import mods
from modbuilder.mods import StatWithOffset
from modbuilder.logging_config import get_logger

logger = get_logger(__name__)

DEBUG = False
NAME = "Increase Reserve Population"
DESCRIPTION = "Increases the number of animals that get populated when loading a reserve for the first time. If you have already played a reserve, you need to delete the old population file first before you will see an increase in animals."
FILE = "settings/hp_settings/reserve_*.bin"
WARNING = "Increasing the population too much can cause the game to crash, especially when used in combination with Increase Render Distance. I personally do not go beyond a 3.0 multiplier."
OPTIONS = [
  { "name": "Population Multiplier", "min": 1.1, "max": 8, "default": 1, "increment": 0.1 }
]

TROPHY_LODGE_IDS = [
  5, # Spring Creek Manor
  7, # Saseka Safari Lodge
  15, # Layton Laykes Trophy Cabin
]

def format_options(options: dict) -> str:
  multiply = options["population_multiplier"]
  return f"Increase Reserve Population ({multiply}x)"

def _save_file(filename: str, data: bytearray) -> None:
    base_path = mods.APP_DIR_PATH / "mod/dropzone/settings/hp_settings"
    base_path.mkdir(exist_ok=True, parents=True)
    (base_path / filename).write_bytes(data)

def _update_uint(data: bytearray, offset: int, new_value: int) -> None:
    value_bytes = new_value.to_bytes(4, byteorder='little')
    for i in range(0, len(value_bytes)):
        data[offset + i] = value_bytes[i]

def _get_animal_tables(root: RtpcNode) -> RtpcNode:
  for table in root.child_table:
    if table.name_hash == 498704821:  # 0x1db9a1b5
      return table.child_table
  return None

def _get_species_id(prop_table: list[RtpcProperty]) -> int:
  for prop in prop_table:
    if prop.name_hash == 431526284:  # 0x19b8918c
      return prop.data

def _get_population_values(tables: list[RtpcNode]) -> list[StatWithOffset]:
  values = []
  value_props = [
    211387756,   # 0x0c99856c
    1677062552,  # 0x63f5f198
    709074058,   # 0x2a439c8a
    2591445387,  # 0x9a76518b
  ]
  for table in tables:
    for prop in table.prop_table:
      if prop.name_hash in value_props:
        values.append(StatWithOffset(prop))
    values.extend(_get_population_values(table.child_table))
  return values

def update_reserve_population(root: RtpcNode, f_bytes: bytearray, multiply: float, reserve_id: int) -> None:
  animal_tables = _get_animal_tables(root)
  if not animal_tables:
    raise ValueError(f"Unable to parse animal data table for reserve {reserve_id}")

  for i, animal_table in enumerate(animal_tables):
    species_id = _get_species_id(animal_table.prop_table)
    population_values = _get_population_values(animal_table.child_table)
    if not population_values:
      raise ValueError(f"Unable to parse population values for animal {i} on reserve {reserve_id}")
    logger.debug(f"species {species_id} has {len(population_values)} values to update")

    try:
      for pop_value in population_values:
        new_value = round(pop_value.value * multiply)
        _update_uint(f_bytes, pop_value.offset, new_value)
    except Exception as ex:
      logger.exception(f"received error: {ex}")

  logger.debug(f"Updates all population values in reserve {reserve_id}")
  return

def _open_reserve(filename: Path) -> tuple[RtpcNode, bytearray]:
  with(filename.open("rb") as f):
    data = rtpc_from_binary(f)
  f_bytes = bytearray(filename.read_bytes())
  return (data.root_node, f_bytes)

def update_all_populations(source: Path, multiply: float) -> None:
  for file in list(source.glob("reserve_*.bin")):
    reserve_id = int(file.stem.split("_")[1])
    if reserve_id in TROPHY_LODGE_IDS:
      continue
    root, data = _open_reserve(file)
    update_reserve_population(root, data, multiply, reserve_id)
    _save_file(file, data)

def process(options: dict) -> None:
  multiply = options["population_multiplier"]
  update_all_populations(mods.APP_DIR_PATH / "mod/dropzone/settings/hp_settings", multiply)
