import FreeSimpleGUI as sg

from deca.ff_rtpc import RtpcNode
from modbuilder import mods
from pathlib import Path

DEBUG = False
NAME = "Modify Animal Classes"
DESCRIPTION = "Modify the class rating of individual animals. Classes range from 1 to 15. Type to search for an animal, select it from the dropdown, then set the desired class."
FILE = "global/global_animal_types.blo"

# Property hash IDs from global_animal_types.blo
HASH_ANIMAL_CLASS = 0x27808D4A  # int: class rating (e.g. 2)
HASH_ANIMAL_NAME  = 0xD31AB684  # string: internal name (e.g. "raccoon_dog")


class AnimalType:
  __slots__ = ('name', 'display_name', 'animal_class', 'class_offset')

  def __init__(self, node: RtpcNode) -> None:
    self.name         = None
    self.display_name = None
    self.animal_class = None
    self.class_offset = None
    self._parse(node)

  def __repr__(self) -> str:
    return f"{self.name} (class {self.animal_class})"

  def _parse(self, node: RtpcNode) -> None:
    name_prop  = node.prop_map.get(HASH_ANIMAL_NAME)
    class_prop = node.prop_map.get(HASH_ANIMAL_CLASS)

    if name_prop:
      raw = name_prop.data
      self.name = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
      self.display_name = " ".join(word.capitalize() for word in self.name.split("_"))

    if class_prop:
      self.animal_class = class_prop.data
      self.class_offset = class_prop.data_pos


def load_animal_types() -> list[AnimalType]:
  rtpc = mods.open_rtpc(mods.APP_DIR_PATH / "org" / FILE)
  animal_list_node = rtpc.child_table[0]
  animals = []
  for child in animal_list_node.child_table:
    animal = AnimalType(child)
    if animal.name and animal.animal_class is not None:
      animals.append(animal)
  return sorted(animals, key=lambda a: a.display_name)


def get_option_elements() -> sg.Column:
  animal_names = [a.display_name for a in ALL_ANIMALS]
  label_size = (7, 1)  # fixed label width so Search/Animal left edges align
  layout = [
    [
      sg.T("Search:", size=label_size, p=((10, 0), (15, 0))),
      sg.Input("", size=33, key="animal_class_search", enable_events=True, p=((0, 0), (15, 0))),
    ],
    [
      sg.T("Animal:", size=label_size, p=((10, 0), (8, 0))),
      sg.Combo(
        animal_names,
        size=33,
        key="animal_class_name",
        enable_events=True,
        readonly=True,
        p=((0, 0), (8, 0))
      ),
      sg.T("Class (1-15):", p=((20, 0), (8, 0))),
      sg.Input("", size=6, key="animal_class_value", p=((10, 0), (8, 0))),
    ],
    [
      sg.T("Current class:", p=((10, 0), (5, 0))),
      sg.T("—", key="animal_class_current", p=((5, 0), (5, 0)), text_color="orange"),
    ],
  ]
  return sg.Column(layout)


def handle_event(event: str, window: sg.Window, values: dict) -> None:
  if event == "animal_class_search":
    # Filter the combo list based on what's typed in the search box
    typed = values.get("animal_class_search", "")
    all_names = [a.display_name for a in ALL_ANIMALS]
    filtered = [n for n in all_names if typed.lower() in n.lower()] if typed else all_names
    window["animal_class_name"].update(values=filtered, value="")
    window["animal_class_current"].update("—")
    window["animal_class_value"].update("")

  if event == "animal_class_name":
    # Animal selected from dropdown — populate class fields
    selected_name = values.get("animal_class_name")
    animal = next((a for a in ALL_ANIMALS if a.display_name == selected_name), None)
    if animal:
      window["animal_class_current"].update(str(animal.animal_class))
      window["animal_class_value"].update(str(animal.animal_class))


def add_mod(window: sg.Window, values: dict) -> dict:
  selected_name = values.get("animal_class_name")
  if not selected_name:
    return {"invalid": "Please select an animal first"}

  animal = next((a for a in ALL_ANIMALS if a.display_name == selected_name), None)
  if not animal:
    return {"invalid": "Could not find the selected animal"}


  new_class = mods.coerce_int(values["animal_class_value"])
  if new_class is None or not 1 <= new_class <= 15:
    return {"invalid": "Class must be a whole number between 1 and 15"}

  return {
    "key": f"modify_animal_class_{animal.name}",
    "invalid": None,
    "options": {
      "name": animal.name,
      "display_name": animal.display_name,
      "animal_class": new_class,
    }
  }


def format_options(options: dict) -> str:
  return f"Modify Animal Class: {options['display_name']} → Class {options['animal_class']}"


def handle_key(mod_key: str) -> bool:
  return mod_key.startswith("modify_animal_class_")


def get_files(options: dict) -> list[str]:
  return [FILE]


def process(options: dict) -> None:
  rtpc = mods.open_rtpc(mods.APP_DIR_PATH / "org" / FILE)
  animal_list_node = rtpc.child_table[0]

  for child in animal_list_node.child_table:
    name_prop  = child.prop_map.get(HASH_ANIMAL_NAME)
    class_prop = child.prop_map.get(HASH_ANIMAL_CLASS)
    if not name_prop or not class_prop:
      continue
    raw = name_prop.data
    name = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
    if name == options["name"]:
      mods.update_file_at_offsets(Path(FILE), [class_prop.data_pos], options["animal_class"])
      return

  raise ValueError(f"Animal '{options['name']}' not found in {FILE} — has the org file been refreshed?")


ALL_ANIMALS = load_animal_types()