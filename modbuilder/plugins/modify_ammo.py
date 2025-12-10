import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import FreeSimpleGUI as sg

from deca.ff_adf import Adf
from modbuilder import mods, mods2
from modbuilder.logging_config import get_logger
from modbuilder.mods import StatWithOffset

logger = get_logger(__name__)

DEBUG = False
NAME = "Modify Ammo"
DESCRIPTION = 'Modify ammo attributes. It is easy to over-adjust these settings and create unrealistic ammo. Use "Advanced Editor" to modify raw values beyond the slider ranges. Changes to a category may conflict with individual ammo changes.'


# These variables can be modified and paired with custom classes in "Modify Animals" to widen the class range beyond 1-9
# Some UI elements are not fully supported without custom .gfx files such as "Recommended Classes" on the weapon wheel
MAX_SUPPORTED_CLASS = 9  # DEFAULT = 9. Changes the max supported class
CLASS_0 = False  # DEFAULT = False.  Enable a class "0" below class 1

AMMO_CLASS_BUTTONS_STATE = [True] * (MAX_SUPPORTED_CLASS + 1)
AMMO_UI_DATA: dict[str, dict] = {}
ALL_AMMO: dict[str, list['Ammo']] = {}
STATS = ["damage", "expansion", "kinetic_energy", "mass", "max_range", "penetration", "projectiles"]


@dataclass
class AmmoStats:
  kinetic_energy: StatWithOffset
  mass: StatWithOffset
  penetration: StatWithOffset
  damage: StatWithOffset
  expansion: StatWithOffset
  contraction: StatWithOffset
  max_expansion: StatWithOffset
  projectiles: StatWithOffset
  max_range: StatWithOffset

@dataclass
class AmmoClassesData:
  items: list[int]
  offset: int
  info_offset: int
  length_offset: int
  missing_class_data: bool

class Ammo:
  __slots__ = (
    'file',
    "name",
    "display_name",
    "type",
    'stats',
    'classes',
    'ui_data',
  )

  file: str
  name: str
  display_name: str
  type: str
  stats: AmmoStats
  classes: AmmoClassesData
  ui_data: dict

  def __init__(self, file: str) -> None:
    self.file = file
    self._parse_name_and_type()
    extracted_adf = mods2.deserialize_adf(mods.get_org_file(file))
    self._get_classes_data(extracted_adf)
    self._get_stats(extracted_adf)
    self.ui_data = AMMO_UI_DATA.get(self.name)

  def __repr__(self) -> str:
    return f"Name: {self.name}   Display Name: {self.display_name}   Type: {self.type}   Classes: {self.classes}   Offsets: {self.offsets}   File: {self.file}"

  def _parse_name_and_type(self) -> None:
    # example file: editor/entities/hp_weapons/ammunition/bows/equipment_ammo_jp_crossbow_arrow_300gr_01.ammotunec
    split_file = self.file.split("/")
    self.type = split_file[-2].removesuffix("s")
    filename = split_file[-1].removesuffix(".ammotunec")
    if (mapped_equipment := mods.map_equipment(filename, "ammo")):
      self.name = mapped_equipment["map_name"]
      self.display_name = mapped_equipment["name"]
    else:
      self.name = filename
      self.display_name = self.name

  def _get_stats(self, extracted_adf: Adf) -> AmmoStats:
    ammo_data = extracted_adf.table_instance_full_values[0].value
    self.stats = AmmoStats(
      kinetic_energy=StatWithOffset(ammo_data["kinetic_energy"]),
      mass=StatWithOffset(ammo_data["mass"]),
      penetration=StatWithOffset(ammo_data["projectile_penetration"]),
      damage=StatWithOffset(ammo_data["projectile_damage"]),
      expansion=StatWithOffset(ammo_data["projectile_expansion_rate"]),
      contraction=StatWithOffset(ammo_data["projectile_contraction_rate"]),
      max_expansion=StatWithOffset(ammo_data["projectile_max_expansion"]),
      projectiles=StatWithOffset(ammo_data["projectiles_per_shot"]),
      max_range=StatWithOffset(ammo_data["max_range"]),
    )

  def _get_classes_data(self, extracted_adf: Adf) -> AmmoClassesData:
    ammo_data = extracted_adf.table_instance_full_values[0].value
    if ammo_data["ammunition_class"].data_offset == ammo_data["ammunition_class"].info_offset:
      # ammo has no classes array. Set a flag to insert data in the correct position
      classes_offset = extracted_adf.table_instance[0].offset + extracted_adf.table_instance[0].size - 4
      missing_class_data = True
    else:
      classes_offset = ammo_data["ammunition_class"].data_offset
      missing_class_data = False
    self.classes = AmmoClassesData(
      items=self._get_classes(extracted_adf),
      offset=classes_offset,
      info_offset=ammo_data["ammunition_class"].info_offset,
      length_offset=ammo_data["ammunition_class"].info_offset + 8,
      missing_class_data=missing_class_data,
    )

  def _get_classes(self, extracted_adf: Adf) -> list[int]:
    # There are "placeholder" ammos in the game files that are not available in game and do not have Class data
    # This will return a blank classes list. Examples include:
    #  - .410 Slug for the Mangiafico 410/45 Colt handgun
    #  - 7.62x54R Full Metal Jacket for the Solokhin MN1890
    #  - 28 Gauge bird and buckshot for an unreleased shotgun
    ammo_data = extracted_adf.table_instance_full_values[0].value
    return [ammo_class.value["level"].value for ammo_class in ammo_data["ammunition_class"].value]

  def _has_pellets(self) -> bool:
    return self.stats.projectiles.value > 1 # and self.type == "shotgun"

def load_ammo_type(ammo_type: str) -> list[Ammo]:
  root_path = mods.APP_DIR_PATH / "org/editor/entities/hp_weapons/ammunition"
  name_pattern = re.compile(r'^equipment_ammo_(\w+)_\d+\.ammotunec$')
  ammo_list = []
  for file in (root_path / ammo_type).glob("*.ammotunec"):
    name_match = name_pattern.match(file.name)
    if name_match:
      relative_file = mods.get_relative_path(file)
      ammo = Ammo(relative_file)
      ammo_list.append(ammo)
  ammo_list.sort(key=lambda x: x.display_name)
  return ammo_list

def load_all_ammo() -> None:
  global ALL_AMMO
  ALL_AMMO = {
    "bow": load_ammo_type("bows"),
    "handgun": load_ammo_type("handguns"),
    "rifle": load_ammo_type("rifles"),
    "shotgun": load_ammo_type("shotguns"),
  }
  logger.debug("Loaded ammo")

def load_ammo_ui_data() -> None:
  global AMMO_UI_DATA
  ammo_sheet, _i = mods2.get_sheet(mods.EQUIPMENT_UI_DATA, "ammo")
  for i in range(2,ammo_sheet["Rows"].value + 1): # skip header row
    name_cell = mods2.XlsxCell(mods.EQUIPMENT_UI_FILE, mods.EQUIPMENT_UI_DATA, {"sheet": "ammo", "coordinates": f"A{i}"})
    penetration_cell = mods2.XlsxCell(mods.EQUIPMENT_UI_FILE, mods.EQUIPMENT_UI_DATA, {"sheet": "ammo", "coordinates": f"C{i}"})
    expansion_cell = mods2.XlsxCell(mods.EQUIPMENT_UI_FILE, mods.EQUIPMENT_UI_DATA, {"sheet": "ammo", "coordinates": f"D{i}"})
    if name_cell.data_array_name == "StringData":  # file contains "blank" rows with True values as placeholders
      ammo_name = mods.clean_equipment_name(name_cell.value.decode("utf-8"), "ammo")
      AMMO_UI_DATA[ammo_name] = {"row": i, "penetration": penetration_cell.value, "expansion": expansion_cell.value}

def build_tab(ammo_type: str) -> sg.Tab:
  ammo_list = ALL_AMMO[ammo_type]
  return sg.Tab(ammo_type.capitalize(), [
    [sg.Combo([ammo.display_name for ammo in ammo_list], metadata=ammo_list, size=(30, 1), k=f"modify_ammo_list_{ammo_type}", enable_events=True)]
  ], k=f"modify_ammo_tab_{ammo_type}")

def get_option_elements() -> sg.Column:
  buttons_row = [sg.Button(str(i), k=f"modify_ammo_class_button_{i}", enable_events=True) for i in range(len(AMMO_CLASS_BUTTONS_STATE))]
  if not CLASS_0:  # disable and hide the class 0 button
    buttons_row[0] = sg.Button("0", k="modify_ammo_class_button_0", enable_events=False, visible=False)
    AMMO_CLASS_BUTTONS_STATE[0] = False

  layout = [[
      sg.TabGroup([[
        build_tab(key) for key in ALL_AMMO
        ]], k="modify_ammo_tab_group", enable_events=True),
      sg.Column([[
          sg.Text("Classes", justification="left"),
          sg.Push(),
          sg.Checkbox("Auto-select ammo defaults", font="_ 12", default=True, k="modify_ammo_update_default_values", enable_events=True, p=((25,0),(0,0)))
        ],
        buttons_row,
      ], p=((15,0),(0,0)), vertical_alignment='top'),
      sg.Column([
        [sg.Checkbox("Apply classes to category", default=False, font="_ 12", k="modify_ammo_category_classes", p=((0,0),(0,0)))],
        [sg.Button("Add Category Modification", k="add_mod_group_ammo", button_color=f"{sg.theme_element_text_color()} on brown", p=((5,0),(5,0)))],
      ], p=((15,0),(0,0))),
      sg.Column([
        [
          sg.Checkbox("Advanced Editor", default=False, k="modify_ammo_advanced_checkbox", enable_events=True, p=((5,0),(0,0))),
          sg.Button("Reset", font="_ 12", k="modify_ammo_reset_stats", p=((5,0),(0,0))),
        ],
        [sg.T( " No UI data for ammo ", font="_ 12", text_color="firebrick1", background_color="black", k="modify_ammo_ui_error", visible=False, p=((5,0),(0,0)))],
      ], p=((15,0),(0,0))),
    ],
    [sg.pin(
      sg.Column([
        [
          sg.Column([
            [sg.Text("Increase Penetration Percent:", p=((0,10),(13,4)))],
            [sg.Text("Increase Expansion Percent:", p=((0,10),(13,4)))],
            [sg.Text("Increase Damage Percent:", p=((0,10),(13,4)))],
            [sg.Text("Increase Kinetic Energy Percent:", p=((0,10),(13,4)))],
            [sg.Text("Increase Mass Percent:", p=((0,10),(13,4)))],
            [sg.Text("Maximum Ammo Range:", p=((0,10),(13,4)))],
            [sg.Text("Increase Projectile Count:", p=((0,10),(13,4)), k="modify_ammo_projectiles_label", visible=False)],
          ], p=((10,10),(0,0)), element_justification='left', vertical_alignment='top'),
          sg.Column([
            [sg.Slider((0, 100), 0, 1, orientation="h", size=(35,15), p=(0,1), enable_events=True, k="modify_ammo_stat_penetration")],
            [sg.Slider((0, 300), 0, 1, orientation="h", size=(35,15), p=(0,1), enable_events=True, k="modify_ammo_stat_expansion")],
            [sg.Slider((0, 300), 0, 1, orientation="h", size=(35,15), p=(0,1), enable_events=True, k="modify_ammo_stat_damage")],
            [sg.Slider((0, 300), 0, 1, orientation="h", size=(35,15), p=(0,1), enable_events=True, k="modify_ammo_stat_kinetic_energy")],
            [sg.Slider((0, 300), 0, 1, orientation="h", size=(35,15), p=(0,1), enable_events=True, k="modify_ammo_stat_mass")],
            [sg.Slider((0, 2000), 0, 10, orientation="h", size=(35,15), p=(0,1), enable_events=True, k="modify_ammo_stat_max_range")],
            [sg.Slider((0, 255), 0, 1, orientation="h", size=(35,15), p=(0,1), enable_events=True, k="modify_ammo_stat_projectiles", visible=False)],
          ], p=(0,0), element_justification='left', vertical_alignment='top'),
          sg.Column([
            [
              sg.Input("", s=(22,1), p=((0,0),(17,0)), disabled=True, enable_events=True, k="modify_ammo_stat_advanced_penetration"),
              sg.T("Lower raw value = better", p=((10,0),(17,0)), font="_ 12 italic", text_color="orange"),
            ],
            [sg.Input("", s=(22,1), p=((0,0),(17,0)), disabled=True, enable_events=True, k="modify_ammo_stat_advanced_expansion")],
            [sg.Input("", s=(22,1), p=((0,0),(17,0)), disabled=True, enable_events=True, k="modify_ammo_stat_advanced_damage")],
            [
              sg.Input("", s=(22,1), p=((0,0),(17,0)), disabled=True, enable_events=True, k="modify_ammo_stat_advanced_kinetic_energy"),
              sg.T("Affects bullet drop", p=((10,0),(17,0)), font="_ 12 italic", text_color="orange"),
            ],
            [
              sg.Input("", s=(22,1), p=((0,0),(17,0)), disabled=True, enable_events=True, k="modify_ammo_stat_advanced_mass"),
              sg.T("Affects bullet drop", p=((10,0),(17,0)), font="_ 12 italic", text_color="orange",)
            ],
            [
              sg.Input("", s=(22,1), p=((0,0),(17,0)), disabled=True, enable_events=True, k="modify_ammo_stat_advanced_max_range"),
              sg.T("Meters. 0 = keep default", p=((10,0),(17,0)), font="_ 12 italic", text_color="orange"),
            ],
            [
              sg.Input("", s=(22,1), p=((0,0),(17,0)), disabled=True, enable_events=True, k="modify_ammo_stat_advanced_projectiles", visible=False),
              sg.T("Game limit is 255 pellets", p=((10,0),(17,0)), font="_ 12 italic", text_color="orange", k="modify_ammo_stat_advanced_projectiles_note", visible=False),
            ],
          ], p=((25,0),(0,0)), element_justification='left', vertical_alignment='top')
        ],
      ])
    )],
  ]

  return sg.Column(layout)

def get_selected_ammo(window: sg.Window, values: dict) -> Ammo | None:
  active_tab = str(window["modify_ammo_tab_group"].find_currently_active_tab_key()).lower()
  ammo_type = active_tab.removeprefix("modify_ammo_tab_")
  ammo_list = f"modify_ammo_list_{ammo_type}"
  ammo_name = values.get(ammo_list)
  if ammo_name:
    try:
      ammo_index = window[ammo_list].Values.index(ammo_name)
      return window[ammo_list].metadata[ammo_index]
    except ValueError as _e:  # user typed/edited data in box and we cannot match
      pass
  return None

def handle_event(event: str, window: sg.Window, values: dict) -> None:
  active_tab = str(window["modify_ammo_tab_group"].find_currently_active_tab_key()).lower()
  selected_ammo = get_selected_ammo(window, values)
  # select an ammo or swap tabs
  if event.startswith("modify_ammo_list_") or event == "modify_ammo_tab_group":
    toggle_ui_error(selected_ammo, window)
    sliders_to_advanced(selected_ammo, window, values)
    # show projectiles options if shotgun tab is selected, hide if non-shotgun tab is selected
    has_pellets = (selected_ammo and selected_ammo._has_pellets()) or (selected_ammo is None and active_tab == "modify_ammo_tab_shotgun")
    window["modify_ammo_projectiles_label"].update(visible=has_pellets)
    window["modify_ammo_stat_projectiles"].update(visible=has_pellets)
    window["modify_ammo_stat_advanced_projectiles"].update(visible=has_pellets)
    window["modify_ammo_stat_advanced_projectiles_note"].update(visible=has_pellets)
  # toggle Advanced Editor
  if event == "modify_ammo_advanced_checkbox":
    toggle_advanced_editor(window, values)
  # type in a stat box
  if event.startswith("modify_ammo_stat_advanced_"):
    stat = event.removeprefix("modify_ammo_stat_advanced_")
    advanced_to_slider(selected_ammo, stat, window, values)
    return
  # drag a slider
  if event.startswith("modify_ammo_stat_"):
    stat = event.removeprefix("modify_ammo_stat_")
    slider_to_advanced(selected_ammo, stat, window, values)
    return
  # reset stats
  if event == "modify_ammo_reset_stats":
    reset_displayed_stats(selected_ammo, window, values, only_advanced=False)
    return
  # update/refresh class buttons and max_range on ammo swap or toggle "auto-select defaults"
  if (
    event.startswith("modify_ammo_list_")
    or event == "modify_ammo_tab_group"
    or event == "modify_ammo_update_default_values"
  ):
    update_ammo_class_buttons(selected_ammo, window, values)
    sliders_to_advanced(selected_ammo, window, values)
  # press a class button = toggle that button
  if event.startswith("modify_ammo_class_button_"):
    selected_class = int(event.rsplit("_",1)[-1])
    AMMO_CLASS_BUTTONS_STATE[selected_class] = not AMMO_CLASS_BUTTONS_STATE[selected_class]
    _paint_ammo_class_buttons(window)
  # force refresh
  window["options"].contents_changed()

def toggle_ui_error(selected_ammo: Ammo, window: sg.Window) -> None:
  show_error = selected_ammo and not selected_ammo.ui_data
  window["modify_ammo_ui_error"].update(visible=show_error)

def toggle_advanced_editor(window: sg.Window, values: dict) -> None:
  show_advanced = values["modify_ammo_advanced_checkbox"]
  for stat in STATS:
    window[f"modify_ammo_stat_advanced_{stat}"].update(disabled=(not show_advanced))
  # no category mods for advanced editor
  window["add_mod_group_ammo"].update(disabled=(show_advanced))
  window["modify_ammo_category_classes"].update(disabled=(show_advanced))

def _format_display_value(stat: str, value: float) -> float | int | str:
  value = mods.coerce_int(value) if stat in ["max_range", "projectiles"] else mods.coerce_float(value)
  if value is None:
    return None
  return value

def _write_advanced(window: sg.Window, stat: str, value) -> None:
  window[f"modify_ammo_stat_advanced_{stat}"].update(value=_format_display_value(stat, value))

def _write_slider(window: sg.Window, stat: str, value) -> None:
  window[f"modify_ammo_stat_{stat}"].update(value=value)

def sliders_to_advanced(selected_ammo, window: sg.Window, values: dict) -> None:
  # Read sliders, compute modified stats, and write them to advanced input boxes
  if not selected_ammo:
    reset_displayed_stats(selected_ammo, window, values, only_advanced=True)
    return
  modifiers = {stat: mods.coerce_float(values.get(f"modify_ammo_stat_{stat}")) or 0.0 for stat in STATS}
  modified = calculate_modified_stats(selected_ammo, modifiers)
  # force ammo default max_range if "auto-select defaults" is checked
  if values.get("modify_ammo_update_default_values"):
    modified["max_range"] = selected_ammo.stats.max_range.value
  # force 1 projectile if not pellet ammo
  if not selected_ammo._has_pellets():
      modified["projectiles"] = 1
  for stat in STATS:
    value = modified[stat]
    _write_advanced(window, stat, value)
    if stat in ["max_range"]: # sync max_range slider
      modifier = calculate_stat_modifier(selected_ammo, stat, value)
      if modifier is not None:
        _write_slider(window, stat, modifier)

def slider_to_advanced(selected_ammo, stat: str, window: sg.Window, values: dict) -> None:
  # Read slider value for `stat`, compute advanced value,  write to advanced input box
  if not selected_ammo:
    return
  modifier = mods.coerce_float(values.get(f"modify_ammo_stat_{stat}"))
  if modifier is None:
    return
  value = calculate_modified_stat(selected_ammo, stat, modifier)
  if value is not None:
    _write_advanced(window, stat, value)

def advanced_to_slider(selected_ammo, stat: str, window: sg.Window, values: dict) -> None:
  # Read advanced input value for `stat`, compute slider modifier, and update slider
  if not selected_ammo:
    return
  value = mods.coerce_float(values.get(f"modify_ammo_stat_advanced_{stat}"))
  if value is None:
    return
  modifier = calculate_stat_modifier(selected_ammo, stat, value)
  if modifier is not None:
    _write_slider(window, stat, modifier)

def reset_displayed_stats(selected_ammo, window: sg.Window, values: dict, only_advanced: bool = False) -> None:
  # Zero sliders and load ammo defaults into advanced boxes
  # pass only_advanced=True to leave sliders where they are
  # keep max_range slider in sync
  for stat in STATS:
    if not only_advanced:
      _write_slider(window, stat, 0)
    _write_advanced(window, stat, "")

  if selected_ammo: # load ammo defaults
    for stat in STATS:
      value = getattr(selected_ammo.stats, stat).value
      # force 1 projectile if not pellet ammo
      if stat == "projectiles" and not selected_ammo._has_pellets():
        value = 1
      _write_advanced(window, stat, value)
      # sync max_range slider
      if stat == "max_range":
        _write_slider(window, stat, value)

def reset_ammo_class_buttons() -> None:
  pass

def update_ammo_class_buttons(selected_ammo, window: sg.Window, values: dict) -> None:
  if values.get("modify_ammo_update_default_values"):
    # sync stat of class buttons with ammo's default classes
    classes = None if selected_ammo is None else getattr(selected_ammo.classes, "items", [])
    _apply_class_buttons_state(classes)
  _paint_ammo_class_buttons(window)

def _apply_class_buttons_state(classes: Iterable[int] | None) -> None:
  n = len(AMMO_CLASS_BUTTONS_STATE)
  if classes is None:
    # reset class buttons
    AMMO_CLASS_BUTTONS_STATE[:] = [True] * n
  else:
    # update buttons state to match selected classes
    members = set(classes)
    AMMO_CLASS_BUTTONS_STATE[:] = [i in members for i in range(n)]

  if not CLASS_0:  # keep button 0 disabled if required
    AMMO_CLASS_BUTTONS_STATE[0] = False

def _paint_ammo_class_buttons(window: sg.Window) -> None:
  on_color = sg.theme_button_color()
  off_color = ("orange", "black")
  for i, enabled in enumerate(AMMO_CLASS_BUTTONS_STATE):
    window[f"modify_ammo_class_button_{i}"].update(
      button_color=on_color if enabled else off_color
    )

def format_class_selection() -> list[int]:
  # convert the list of True/False values from the buttons into a list of class numbers
  return [i for i, v in enumerate(AMMO_CLASS_BUTTONS_STATE) if v]

def add_mod(window: sg.Window, values: dict) -> dict:
  selected_ammo = get_selected_ammo(window, values)
  if selected_ammo is None:
    return {
      "invalid": "Please select an ammo first"
    }
  classes = format_class_selection()
  advanced = values["modify_ammo_advanced_checkbox"]
  adv_prefix = "advanced_" if advanced else ""

  mod_settings = {
    "key": f"modify_ammo_{selected_ammo.name}",
    "invalid": None,
    "options": {
      "name": selected_ammo.display_name,
      "type": selected_ammo.type,
      "file": selected_ammo.file,
      "classes": classes,
      "advanced_editor": advanced
    }
  }

  for stat in STATS:
    # pull values from "advanced" input boxes if using Advanced Editor
    stat_key = f"{adv_prefix}{stat}"
    # use mods.coerce_float to validate values
    value = values[f"modify_ammo_stat_{stat_key}"]
    f_value =  mods.coerce_float(value)
    if f_value is None:
      return {
        "invalid": f"Invalid value for {stat_key}: {value}"
      }
    mod_settings["options"][stat_key] = f_value

  return mod_settings

def add_mod_group(window: sg.Window, values: dict) -> dict:
  active_tab = window["modify_ammo_tab_group"].find_currently_active_tab_key().lower()
  ammo_type = active_tab.removeprefix("modify_ammo_tab_")
  if not ammo_type:
    return {
      "invalid": "Please select an ammo type first"
    }
  if values["modify_ammo_category_classes"]:
    classes = format_class_selection()
  else:
    classes = []

  mod_settings = {
    "key": f"modify_ammo_type_{ammo_type}",
    "invalid": None,
    "options": {
      "type": ammo_type,
      "classes": classes,
      "max_range": values["modify_ammo_stat_max_range"],
      "penetration": values["modify_ammo_stat_penetration"],
      "expansion": values["modify_ammo_stat_expansion"],
      "damage": values["modify_ammo_stat_damage"],
      "kinetic_energy": values["modify_ammo_stat_kinetic_energy"],
      "mass": values["modify_ammo_stat_mass"],
      "projectiles": values["modify_ammo_stat_projectiles"] if ammo_type == "shotgun" else 0,
    }
  }

  return mod_settings

def format_options(options: dict) -> str:
  advanced = options.get("advanced_editor", False)

  if not advanced:
    penetration = options.get("penetration", 0)
    penetration_text = f'P +{int(penetration)}%' if penetration else ""
    expansion = options.get("expansion", 0)
    expansion_text = f'E +{int(expansion)}%' if expansion else ""
    damage = options.get("damage", 0)
    damage_text = f'D +{int(damage)}%' if damage else ""
    kinetic_energy = options.get("kinetic_energy", 0)
    kinetic_energy_text = f'KE +{int(kinetic_energy)}%' if kinetic_energy else ""
    mass = options.get("mass", 0)
    mass_text = f'M +{int(mass)}%' if mass else ""
    projectiles = options.get("projectiles", 0)
    projectiles_text = f"Pellets +{int(projectiles)}" if projectiles else ""
    max_range = options.get("max_range", 0)
    max_range_text = f'Range {int(max_range)}m' if max_range else ""

  else:
    penetration = options.get("advanced_penetration")
    penetration_text = f'P {mods.format_float(penetration)}' if penetration is not None else ""
    expansion = options.get("advanced_expansion")
    expansion_text = f'E {mods.format_float(expansion)}' if expansion is not None else ""
    damage = options.get("advanced_damage")
    damage_text = f'D {mods.format_float(damage)}' if damage is not None else ""
    kinetic_energy = options.get("advanced_kinetic_energy")
    kinetic_energy_text = f'KE {mods.format_float(kinetic_energy)}' if kinetic_energy is not None else ""
    mass = options.get("advanced_mass")
    mass_text = f'M {mods.format_float(mass)}' if mass is not None else ""
    projectiles = options.get("advanced_projectiles", 0)
    projectiles_text = f"Pellets {int(projectiles)}" if projectiles else ""
    max_range = options.get("advanced_max_range", 0)
    max_range_text = f'Range {int(max_range)}m' if max_range else ""

  classes = options.get("classes", [])

  stats_array = [penetration_text, expansion_text, damage_text, kinetic_energy_text, mass_text, projectiles_text, max_range_text]
  stats_text = ", ".join([s for s in stats_array if s and s.strip()])
  details_text = f'({stats_text if stats_text else "No Stat Changes"})  Classes: {classes if classes else "Default"}'
  if "file" in options:  # single ammo
    ammo_name = options["name"]
    return f"Modify Ammo{" Advanced" if advanced else ""}: {ammo_name} {details_text}"
  else:  # category
    ammo_type = options["type"]
    return f"Modify Ammo Type: {ammo_type.capitalize()} {details_text}"

def handle_key(mod_key: str) -> bool:
  return mod_key.startswith("modify_ammo")

def get_files(options: dict) -> list[str]:
  if "file" in options:
    return [options["file"], mods.EQUIPMENT_UI_FILE]
  else:
    selected_ammo_files = [ammo.file for ammo in ALL_AMMO[options["type"]]]
    return [*selected_ammo_files, mods.EQUIPMENT_UI_FILE]

def get_bundle_file(file: str) -> Path:
  return Path(file).parent / f"{Path(file).name.split('.')[0]}.ee"

def merge_files(files: list[str], options: dict) -> None:
  for file in files:
    if file is not mods.EQUIPMENT_UI_FILE:
      bundle_file = get_bundle_file(file)
      mods.expand_into_archive(file, str(bundle_file))

def update_classes_array(ammo: Ammo, classes: list[int]) -> list[dict]:
  updates = []
  if classes:
    # Update classes length value
    updates.append({"offset": ammo.classes.length_offset, "value": len(classes)})
    # Create arrays
    old_classes_array = mods.create_bytearray(ammo.classes.items, "classes")
    classes_array = mods.create_bytearray(classes, "classes")
    # Increase offsets
    extracted_adf = mods2.deserialize_adf(ammo.file)
    added_size = len(classes_array) - len(old_classes_array)
    if added_size != 0:
      updates.extend(mods.update_non_instance_offsets(extracted_adf, added_size))
    # Remove the old array and insert the new array
    updates.append({
      "offset": ammo.classes.offset,
      "value": classes_array,
      "transform": "insert",
      "bytes_to_remove": len(old_classes_array),
    })
    if ammo.classes.missing_class_data:
      # Enforce info/data offsets. This lets us modify "_PLACEHOLDER" ammos that have no class data
      added_offset = ammo.classes.offset - ammo.classes.info_offset
      updates.append({"offset": ammo.classes.info_offset, "value": added_offset})
      # Add missing separator after classes (uint32 "4" - 04 00 00 00)
      updates.append({"offset": ammo.classes.offset + len(classes_array), "value": mods.create_bytearray(4, "uint32"), "transform": "insert"})
      updates.extend(mods.update_non_instance_offsets(extracted_adf, 4))
  return updates

def _pct_signed(base: float, modifier: float) -> float:
  # Signed percent modifier so +% always increases the result even if base < 0
  # This fixes calculations for some ammos (arrows) with negative base kinetic energy
  return base * (1 + (modifier / 100.0) * (1 if base > 0 else -1))

def _safe_ratio(modified: float, base: float) -> float | None:
  # Divide modifed by base, safely avoid divide-by-zero
  return None if base == 0 else (modified / base)

def _pct_modified_signed(value: float, base: float) -> float | None:
  # Signed percent change that moves 'up' even if base < 0
  # This fixes calculations for some ammos (arrows) with negative base kinetic energy
  if base == 0:
    return 0
  ratio = value / base
  if base >= 0:
    return (ratio - 1.0) * 100.0
  else:
    return (1.0 - ratio) * 100.0

def calculate_modified_stats(ammo: Ammo, modifiers: dict) -> dict:
  modified_stats = {
    "penetration": calculate_modified_stat(ammo, "penetration", modifiers["penetration"]),
    "expansion": calculate_modified_stat(ammo, "expansion", modifiers["expansion"]),
    "contraction": calculate_modified_stat(ammo, "contraction", modifiers["expansion"]),
    "max_expansion": calculate_modified_stat(ammo, "max_expansion", modifiers["expansion"]),
    "kinetic_energy": calculate_modified_stat(ammo, "kinetic_energy", modifiers["kinetic_energy"]),
    "damage":calculate_modified_stat(ammo, "damage", modifiers["damage"]),
    "mass": calculate_modified_stat(ammo, "mass", modifiers["mass"]),
    "max_range": calculate_modified_stat(ammo, "max_range", modifiers["max_range"]),
    "projectiles": calculate_modified_stat(ammo, "projectiles", modifiers["projectiles"]),
  }
  return modified_stats

def calculate_modified_stat(ammo: Ammo, stat: str, modifier: float | None, ui_data: bool = False) -> float:
  if modifier is None:
    return None

  if ui_data:
    base_value = ammo.ui_data[stat]
  else:
    base_value = getattr(ammo.stats, stat).value

  if stat == "penetration":
    # penetration in tuning files uses an inverse formula with a range of 0.0 - 1.0
    # penetration UI value uses the standard _pct_signed() formula
    if not ui_data:
      return base_value * (1 - modifier / 100)

  if stat == "max_range": # max_range is an exact value. 0 = use ammo default
    return int(modifier) if modifier > 0 else ammo.stats.max_range.value

  if stat == "projectiles": # projectiles is a flat modifier. Pellet ammos only.
    projectiles = int(base_value + int(modifier) if ammo._has_pellets() else base_value)
    return min(255, max(0, projectiles))  # ammo breaks with 256+ pellets

  # other stats use a signed percent modifier so +% always increases the result, even if base < 0
  return _pct_signed(base_value, modifier)

def calculate_stat_modifier(ammo: Ammo, stat: str, value: float) -> float:
  if stat == "penetration": # penetration uses an inverse formula
    pen_ratio = _safe_ratio(value, ammo.stats.penetration.value)
    return 0 if pen_ratio is None else (1 - pen_ratio) * 100

  if stat == "max_range": # max_range is an exact value
    return value

  if stat == "projectiles": # projectiles is a flat modifier. Pellet ammos only
    return value - ammo.stats.projectiles.value if ammo._has_pellets() else 0

  # other stats use signed percent change that moves 'up' even if base_value < 0
  base_value = getattr(ammo.stats, stat).value
  return _pct_modified_signed(value, base_value)

def process(options: dict) -> None:
  advanced = options.get("advanced_editor", False)
  classes = options.get("classes", [])

  file = options.get("file")
  if file:  # single ammo
    selected_ammos = [Ammo(file)]
  else:  # category
    selected_ammos = ALL_AMMO[options["type"]]

  for ammo in selected_ammos:
    if advanced:
      modified_stats = {
        key.removeprefix("advanced_"): value
        for key, value in options.items()
        if key.removeprefix("advanced_") in STATS
      }
    else:
      modified_stats = calculate_modified_stats(ammo, options)

    # calculate some modifiers that we need to update UI values
    penetration_modifier = calculate_stat_modifier(ammo, "penetration", options["advanced_penetration"]) if advanced else options["penetration"]
    expansion_modifier = calculate_stat_modifier(ammo, "expansion", modified_stats["expansion"])

    if advanced:
      # the plugin does not include sliders for max_expansion and contraction
      # calculate those based off of "expansion" modifier
      modified_stats["contraction"] = calculate_modified_stat(ammo, "contraction", expansion_modifier)
      modified_stats["max_expansion"] = calculate_modified_stat(ammo, "max_expansion", expansion_modifier)

    modified_stats = {key: modified_stats[key] for key in sorted(modified_stats.keys())}

    int_stats = ["projectiles"]  # all other stats are float
    updates = []
    for stat, value in modified_stats.items():
      offset = getattr(ammo.stats, stat).offset
      fmt_value = mods.coerce_int(value) if stat in int_stats else mods.coerce_float(value)
      if value is None:
        raise ValueError("Unable to convert stat %s to %s: %s", stat, "int" if stat in int_stats else "float", value)
      updates.append({"offset": offset, "value": fmt_value})

    updates.extend(update_classes_array(ammo, classes))
    mods.apply_updates_to_file(ammo.file, updates)

    # use calculated modifiers to update the UI values
    if ammo.ui_data:
      ui_penetration = calculate_modified_stat(ammo, "penetration", penetration_modifier, ui_data=True)
      ui_expansion = calculate_modified_stat(ammo, "expansion", expansion_modifier, ui_data=True)
      ui_updates = [
        {
          "coordinates": f"C{ammo.ui_data["row"]}",  # penetration
          "value": max(min(int(ui_penetration), 100), 1),
        },
        {
          "coordinates": f"D{ammo.ui_data["row"]}",  # expansion
          "value": max(min(int(ui_expansion), 100), 1),
        },
      ]
      if classes:
        ui_updates.append(
          {
            "coordinates": f"F{ammo.ui_data["row"]}",  # classes
            "value": ";".join(map(str,classes)),
          }
        )
      for update in ui_updates:
        update["sheet"] = "ammo"
        update["allow_new_data"] = True
      mods2.apply_coordinate_updates_to_file(mods.EQUIPMENT_UI_FILE, ui_updates)

def handle_update(mod_key: str, mod_options: dict, version: str) -> tuple[str, dict]:
  """
  2.2.10
  - Add support for editing exact values with Advanced Editor
  2.2.2
  - Replace full filepath with just ammo name in mod_key
  - Separate key for category mods
  2.2.1
  - Use formatted name from 'name_map.yaml' as "display_name"
  """
  # 2.2.0 and prior saved the name with an old format (not from `name_map.yaml`)
  # 2.2.1 saved the full filename in the key
  # Update the config to use the display name and add ammo type
  advanced = mod_options.get("advanced_editor", False)
  if "file" in mod_options:  # single ammo
    ammo = Ammo(mod_options["file"])
    updated_mod_key = f"modify_ammo_{ammo.name}"
    updated_mod_options = {
      "name": ammo.display_name,
      "type": ammo.type,
      "file": ammo.file,
      "classes": mod_options.get("classes", []),
      "advanced_editor": advanced
    }
  else:  # category
    updated_mod_key = f"modify_ammo_type_{mod_options['type']}"
    updated_mod_options = {
      "type": mod_options["type"],
      "classes": mod_options.get("classes", []),
    }

  # if values are from the Advanced Editor then enforce `advanced_ ` prefix
  for stat in STATS:
    if advanced:
      updated_mod_options[f"advanced_{stat}"] = mod_options.get(f"advanced_{stat}", None)
    else:
      updated_mod_options[stat] = mod_options.get(stat, 0)

  return updated_mod_key, updated_mod_options

load_ammo_ui_data()
load_all_ammo()
