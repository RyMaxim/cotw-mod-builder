from modbuilder import mods
from deca.ff_rtpc import RtpcNode

DEBUG = False
NAME = "Modify Reticle Cost"
DESCRIPTION = "Reduce the cost of changing the reticle on your scopes. Requires the Scopes and Crosshairs DLC pack. Reticles have a minimum price of $1"
WARNING = 'Values may be overwritten if using a "Category Discount" on Skins with Modify Store.'
FILE = mods.EQUIPMENT_DATA_FILE
OPTIONS = [
    {
     "name": "Cost",
     "style": "slider",
     "min": 0.0,
     "max": 4500.0,
     "initial": 4500.0,
     "increment": 10,
     "note": "True minimum value is 1. Value of 0 will be overridden to prevent errors"
    }
]
PRESETS = [
  {
   "name": "Game Defaults",
   "options": [
     {"name": "cost", "value": 4500.0},
    ]
  },
  {
   "name": "Free",
   "options": [
     {"name": "cost", "value": 0.0},
    ]
  },
]

class Reticle:
  def __init__(self, equipment_node: RtpcNode) -> None:
    if type(equipment_node.prop_table[2].data) == bytes:
      name = equipment_node.prop_table[2].data.decode('utf-8')
      if "reticle" in name:
        self.name = name
        if type(equipment_node.prop_table[0].data) == int:
          self.cost = equipment_node.prop_table[0].data
          self.offset = equipment_node.prop_table[0].data_pos
        else:
          raise ValueError("Item does not have an integer at position 0")
      else:
        raise ValueError('Name does not contain "reticle"')
    else:
      raise ValueError("Item does not have a name at position 2")

def load_reticles() -> list[Reticle]:
  reticles = []
  equipment_data = mods.open_rtpc(mods.APP_DIR_PATH / "org" / FILE)
  # reticles are stored in the "skins" table at index 6
  for equipment_node in equipment_data.child_table[6].child_table:
    try:
      reticle = Reticle(equipment_node)
      reticles.append(reticle)
    except ValueError as e:  # Reticle.__init__ () returns a ValueError if it fails to match reticle data
      continue  # safely ignore the error and skip the item
  return reticles

def format_options(options: dict) -> str:
  cost = int(options['cost'])
  return f"Modify Reticle Cost (${cost})"

def update_values_at_offset(options: dict) -> list[dict]:
  offsets_and_values = []
  cost = max(int(options["cost"]), 1)
  reticles = load_reticles()
  for reticle in reticles:
    update = {"offset": reticle.offset, "value": cost}
    offsets_and_values.append(update)
  return offsets_and_values

def handle_update(mod_key: str, mod_options: dict, version: str) -> tuple[str, dict]:
  """
  2.7.0
  - Reticles have a minimum price of 1 to prevent errors
  """
  updated_mod_key = mod_key
  # Reticles do not work properly with a price of 0. Enforce a minimum value of 1
  updated_mod_options = {
    "cost": max(mod_options["cost"], 1)
  }
  return updated_mod_key, updated_mod_options
