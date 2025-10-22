import importlib.util
import io
import json
import os
import re
import shutil
import struct
import sys
from importlib.metadata import version
from pathlib import Path
from types import ModuleType

import FreeSimpleGUI as sg
import yaml

from deca.ff_adf import Adf, AdfValue
from deca.ff_rtpc import RtpcNode, RtpcProperty, rtpc_from_binary
from deca.ff_sarc import EntrySarc, FileSarc
from deca.file import ArchiveFile
from modbuilder import adf_profile, mods2
from modbuilder.logging_config import get_logger

logger = get_logger(__name__)

__version__ = version("modbuilder-revived")

APP_DIR_PATH = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
MOD_PATH = APP_DIR_PATH / "mod/dropzone"
LOOKUP_PATH = APP_DIR_PATH / "org/lookups"
PLUGINS_FOLDER = "plugins"
GLOBAL_SRC_PATH = "gdc/global.gdcc"
GLOBAL_PATH = APP_DIR_PATH / "org" / GLOBAL_SRC_PATH
ELMER_MOVEMENT_LOCAL_SRC_PATH = "editor/entities/hp_characters/main_characters/local_player_character.ee"
ELMER_MOVEMENT_NETWORK_SRC_PATH = "editor/entities/hp_characters/main_characters/network_player_character.ee"
ELMER_MOVEMENT_LOCAL_PATH = APP_DIR_PATH / "org" / ELMER_MOVEMENT_LOCAL_SRC_PATH
ELMER_MOVEMENT_NETWORK_PATH = APP_DIR_PATH / "org" / ELMER_MOVEMENT_NETWORK_SRC_PATH
GLOBAL_ANIMALS_SRC_PATH = "global/global_animal_types.bl"
GLOBAL_ANIMALS_PATH = APP_DIR_PATH / "org" / GLOBAL_ANIMALS_SRC_PATH
GAME_PATH_FILE = APP_DIR_PATH / "game_path.txt"
EQUIPMENT_DATA_FILE = "settings/hp_settings/equipment_data.bin"
EQUIPMENT_UI_FILE = "settings/hp_settings/equipment_stats_ui.bin"
ANIMAL_INTEREST_FILE = "settings/hp_settings/animal_interest.bin"
MODS_EQUIPMENT_UI_DATA = None
MODS_LIST = DEBUG_MODS_LIST = None
GLOBAL_FILES = LOCAL_PLAYER_FILES = NETWORK_PLAYER_FILES = GLOBAL_ANIMAL_FILES = None
with open(APP_DIR_PATH / "name_map.yaml", "r") as file:
    NAME_MAP = yaml.safe_load(file)

GLOBAL_FILES: dict
LOCAL_PLAYER_FILES: dict
NETWORK_PLAYER_FILES: dict
GLOBAL_ANIMAL_FILES: dict
MODS_LIST: dict[str, ModuleType]
DEBUG_MODS_LIST: dict[str, ModuleType]
MODS_EQUIPMENT_UI_DATA: Adf
NAME_MAP: dict[str, dict]


class StatWithOffset:
  value: int | float
  offset: int

  def __init__(self, stat: AdfValue | RtpcProperty = None, value: any = None, offset: int = None) -> None:
    if stat is None and (value is None and offset is None):
      raise ValueError("Cannot create object: Missing stat or value + offset")

    if value is not None:
      self.value = value
    elif isinstance(stat, AdfValue):
      self.value = stat.value
    elif isinstance(stat, RtpcProperty):
      self.value = stat.data
    if isinstance(self.value, bytes):
      self.value = self.value.decode("utf-8")

    if offset is not None:
      self.offset = offset
    elif isinstance(stat, AdfValue):
      self.offset = stat.data_offset
    elif isinstance(stat, RtpcProperty):
      self.offset = stat.data_pos

  def __repr__(self):
    return f"Value: {self.value}   Offset: {self.offset}"

def load_mods() -> None:
  load_global_files()
  load_equipment_ui_data()
  get_mods()

def load_global_files() -> None:
  global GLOBAL_FILES, LOCAL_PLAYER_FILES, NETWORK_PLAYER_FILES, GLOBAL_ANIMAL_FILES
  GLOBAL_FILES = get_global_file_info()
  LOCAL_PLAYER_FILES = get_player_file_info(ELMER_MOVEMENT_LOCAL_PATH)
  NETWORK_PLAYER_FILES = get_player_file_info(ELMER_MOVEMENT_NETWORK_PATH)
  GLOBAL_ANIMAL_FILES = get_global_animal_info(GLOBAL_ANIMALS_PATH)

def load_equipment_ui_data() -> Adf:
  global EQUIPMENT_UI_DATA
  EQUIPMENT_UI_DATA = mods2.deserialize_adf(APP_DIR_PATH / "org" / EQUIPMENT_UI_FILE)

def get_mods() -> None:
  mod_filenames = _get_mod_filenames()
  global MODS_LIST, DEBUG_MODS_LIST
  MODS_LIST = {}
  DEBUG_MODS_LIST = {}
  clear_mod()
  for mod_filename in mod_filenames:
    loaded_mod = _load_mod(mod_filename)
    if getattr(loaded_mod, "DEBUG", True):
      DEBUG_MODS_LIST[mod_filename] = loaded_mod
    else:
      MODS_LIST[mod_filename] = loaded_mod

def _get_mod_filenames() -> list[str]:
  mod_filenames = []
  for mod_filename in os.listdir(APP_DIR_PATH / PLUGINS_FOLDER):
    file_name, file_ext = os.path.splitext(os.path.split(mod_filename)[-1])
    if file_ext.lower() == '.py':
      mod_filenames.append(file_name)
  return mod_filenames

def _load_mod(filename: str) -> ModuleType:
  spec = importlib.util.spec_from_file_location(filename, str(APP_DIR_PATH / PLUGINS_FOLDER / f"{filename}.py"))
  py_mod = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(py_mod)
  return py_mod

def get_mod_keys() -> list[str]:
  return _get_mod_filenames()

def get_mod(mod_key: str) -> ModuleType:
  if mod_key in MODS_LIST:
    return MODS_LIST[mod_key]
  else:
    for mod in list(MODS_LIST.values()) + list(DEBUG_MODS_LIST.values()):
      if hasattr(mod, "handle_key"):
        if mod.handle_key(mod_key):
          return mod
    return None

def format_mod_display_name(mod_key:str, mod_options) -> str:
  mod = get_mod(mod_key)
  if mod is None:
    formatted_name = get_mod_name_from_key(mod_key).title()
  elif hasattr(mod, "format_options"):
    formatted_name = mod.format_options(mod_options)
  else:
    formatted_name = get_mod_full_name_from_key(mod_key).title()
  return formatted_name

def delegate_event(event: str, window: sg.Window, values: dict) -> None:
  for mod in MODS_LIST.values():
    if hasattr(mod, "handle_event"):
      mod.handle_event(event, window, values)

def title_from_key(key: str) -> str:
  return " ".join(key.split("_")).title()

def get_mod_name_from_key(mod_key: str) -> str:
  return " ".join(mod_key.lower().split("_"))

def get_mod_full_name_from_key(mod_name: str) -> str:
  mod = get_mod(mod_name)
  if mod:
    return mod.NAME
  return mod_name

def get_mod_key_from_name(mod_name: str) -> str:
  return "_".join(mod_name.lower().split(" "))

def get_mod_option(mod_key: str, option_key: str) -> dict:
  mod = get_mod(mod_key)
  for option in mod.OPTIONS:
    mod_name = get_mod_key_from_name(option["name"]) if "name" in option else None
    if mod_name == option_key:
      return option
  return None

def get_mod_option_default(option_key: str, options: list[dict] = None, mod_key: str = None) -> float:
  default = None
  if options is None and mod_key is None:
    raise ValueError(f"Unable to get default value for {option_key}: no options or mod_key provided. ")
  if options:
    for option in options:
      if option_key == get_mod_key_from_name(option["name"]):
        default = option.get("default", "initial")
  if options is None:
    option = get_mod_option(option_key, mod_key)
    default = option.get("default", "initial")
  if default is None:
    raise ValueError(f"Unable to get default value for {option_key}: no matching option found")
  return default

def get_mod_option_defaults(options: list[dict] = None) -> dict:
  defaults = {}
  for option in options:
    key = get_mod_key_from_name(option["name"])
    defaults[key] = get_mod_option_default(key, options)
  return defaults

def list_mod_files() -> list[str]:
  return _get_mod_filenames()

def clear_mod() -> None:
  path = APP_DIR_PATH / "mod"
  if path.exists():
    shutil.rmtree(path)

def get_relative_path(path: str) -> str:
  return os.path.relpath(path, APP_DIR_PATH / "org").replace("\\", "/")

def copy_file(src_path: Path, dest_path: Path) -> None:
  if not dest_path.exists():
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(src_path, dest_path)

def copy_file_to_mod(src_filename: str) -> None:
  dest_path = APP_DIR_PATH / "mod/dropzone" / src_filename
  src_path = APP_DIR_PATH / "org" / src_filename
  copy_file(src_path, dest_path)

def copy_glob_to_mod(src_filename: str) -> list[str]:
  org_basepath = APP_DIR_PATH / "org"
  files = []
  for file in list(org_basepath.glob(src_filename)):
    file = str(Path(f"{Path(src_filename).parent}/{file.name}"))
    copy_file_to_mod(file)
    files.append(file.replace("\\", "/"))
  return files

def copy_files_to_mod(src_filename: str) -> list[str]:
  if "*" in src_filename:
    return copy_glob_to_mod(src_filename)
  else:
    copy_file_to_mod(src_filename)
    return [src_filename]

def copy_all_files_to_mod(filenames: list[str]) -> list[str]:
  for filename in filenames:
    copy_file_to_mod(filename)
  return filenames

def get_org_file(src_filename: str) -> Path:
  return APP_DIR_PATH / "org" / src_filename

def get_modded_file(src_filename: str) -> Path:
  return APP_DIR_PATH / "mod/dropzone" / src_filename

def read_file_at_offset(src_filename: str, offset: int, format: str) -> any:
  src_path = get_org_file(src_filename)
  value_at_offset = None
  with open(src_path, "rb") as fp:
    fp.seek(offset)
    if format == "f32":
      value_at_offset = struct.unpack("f", fp.read(4))[0]
  return value_at_offset

def update_file_at_offsets(src_filename: str, offsets: list[int], value: any, transform: str = None, format: str = None) -> None:
  dest_path = get_modded_file(src_filename)
  with open(dest_path, "r+b") as fp:
    for offset in offsets:
      # logger.debug(f"Value: {value}   Offset: {offset}   Transform: {transform}   Format: {format}")
      fp.seek(offset)
      if format:
        if format == "sint08":
          fp.write(struct.pack("h", value))
      else:
        if isinstance(value, str):
          fp.write(struct.pack(f"{len(value)}s", value.encode("utf-8")))
        elif isinstance(value, float):
          new_value = value
          if transform == "multiply":
            existing_value = struct.unpack('f', fp.read(4))[0]
            new_value = value * existing_value
            fp.seek(offset)
          fp.write(struct.pack("f", new_value))
        elif isinstance(value, int):
          new_value = value
          if transform == "add":
            existing_value = struct.unpack("i", fp.read(4))[0]
            new_value = value + existing_value
          elif transform == "multiply":
            existing_value = struct.unpack("i", fp.read(4))[0]
            new_value = round(value * existing_value)
          fp.seek(offset)
          fp.write(struct.pack("i", new_value))
      fp.flush()

def update_file_at_offsets_with_values(src_filename: str, values: list[(int, any)]) -> None:
  dest_path = get_modded_file(src_filename)
  with open(dest_path, "r+b") as fp:
    for offset, value in values:
      fp.seek(offset)
      if isinstance(value, int):
        fp.write(struct.pack("i", value))
      elif isinstance(value, str):
        fp.write(struct.pack(f"{len(value)}s", value.encode("utf-8")))
      elif isinstance(value, bytes):
        fp.write(struct.pack(f"{len(value)}s", value))
      elif isinstance(value, float):
        fp.write(struct.pack("f", value))
      fp.flush()

def update_file_at_offset(src_filename: str, offset: int, value: any, transform: str = None, format: str = None) -> None:
  update_file_at_offsets(src_filename, [offset], value, transform, format)

def apply_updates_to_file(src_filename: str, updates: list[dict]):
  dest_path = get_modded_file(src_filename)
  with open(dest_path, "r+b") as fp:
    for update in updates:
      value = update["value"]
      offset = update["offset"]
      transform = update.get("transform")
      format = update.get("format")
      # logger.debug(f"Value: {value}   Offset: {offset}   Transform: {transform}   Format: {format}")
      if transform == "insert":
        insert_bytearray(fp, update)
      else:
        fp.seek(offset)
        if format:
          if format == "sint08":
            fp.write(struct.pack("h", value))
          if format == "uint08":
            fp.write(struct.pack("B", value))
        else:
          if isinstance(value, str):
            fp.write(struct.pack(f"{len(value)}s", value.encode("utf-8")))
          elif isinstance(value, bytes):
            fp.write(struct.pack(f"{len(value)}s", value))
          elif isinstance(value, float):
            new_value = value
            if transform == "multiply":
              existing_value = struct.unpack('f', fp.read(4))[0]
              new_value = value * existing_value
              fp.seek(offset)
            fp.write(struct.pack("f", new_value))
          elif isinstance(value, int):
            new_value = value
            if transform == "add":
              existing_value = struct.unpack("i", fp.read(4))[0]
              new_value = value + existing_value
            elif transform == "multiply":
              existing_value = struct.unpack("i", fp.read(4))[0]
              new_value = round(value * existing_value)
            fp.seek(offset)
            fp.write(struct.pack("i", new_value))
      fp.flush()

def apply_mod(mod: any, options: dict) -> None:
  if hasattr(mod, "update_values_at_offset"):
    updates = mod.update_values_at_offset(options)
    if updates:
      apply_updates_to_file(mod.FILE, updates)
  elif hasattr(mod, "update_values_at_coordinates"):
    updates = mod.update_values_at_coordinates(options)
    if updates:
      mods2.apply_coordinate_updates_to_file(mod.FILE, updates)
  else:
    mod.process(options)

def open_rtpc(filename: Path) -> RtpcNode:
  with filename.open("rb") as f:
    data = rtpc_from_binary(f)
  root = data.root_node
  return root

def get_global_file_info() -> dict:
  global_files = {}
  return global_files

def get_sarc_file_info(filename: Path, include_details: bool = False) -> dict:
  bundle_files = {}
  sarc = FileSarc()
  with filename.open("rb") as fp:
    sarc.header_deserialize(fp)
    for sarc_file in sarc.entries:
      bundle_files[sarc_file.v_path.decode("utf-8")] = sarc_file if include_details else sarc_file.offset
  return bundle_files

def get_sarc_file_info_details(bundle_file: Path, filename: str) -> EntrySarc:
  sarc_info = get_sarc_file_info(bundle_file, True)
  for file, info in sarc_info.items():
    if file == filename:
      return info
  return None

def get_player_file_info(filename: Path) -> dict:
  return get_sarc_file_info(filename)

def get_global_animal_info(filename: Path) -> dict:
  return get_sarc_file_info(filename)

def is_file_in_global(filename: str) -> bool:
  return filename in GLOBAL_FILES.keys()

def is_file_in_bundle(filename: str, lookup: dict) -> bool:
  return filename in lookup.keys()

def merge_into_archive(filename: str, merge_path: str, merge_lookup: dict, delete_src: bool = False) -> None:
  src_path = APP_DIR_PATH / "mod/dropzone" / filename
  mod_merge_path = APP_DIR_PATH / "mod/dropzone" / merge_path
  copy_files_to_mod(merge_path)
  filename_bytes = bytearray(src_path.read_bytes())
  merge_bytes = bytearray(mod_merge_path.read_bytes())
  filename_offset = merge_lookup[filename]
  merge_bytes[filename_offset:filename_offset+len(filename_bytes)] = filename_bytes
  mod_merge_path.write_bytes(merge_bytes)
  if delete_src:
    src_path.unlink()

def recreate_archive(changed_filenames: list[str], archive_path: str) -> None:
  org_archive_path = APP_DIR_PATH / "org" / archive_path
  new_archive_path = APP_DIR_PATH / "mod/dropzone" / archive_path

  sarc_file = FileSarc()
  sarc_file.header_deserialize(org_archive_path.open("rb"))

  org_entries = {}
  for entry in sarc_file.entries:
    file = entry.v_path.decode("utf-8")
    if file in changed_filenames:
      entry.length = (APP_DIR_PATH / "mod/dropzone" / file).stat().st_size
    else:
      org_entries[file] = entry.offset

  new_archive_path.parent.mkdir(parents=True, exist_ok=True)

  with ArchiveFile(new_archive_path.open("wb")) as new_archive:
    with org_archive_path.open("rb") as org_archive:
      sarc_file.header_serialize(new_archive)

      for entry in sarc_file.entries:
        data = None
        file = entry.v_path.decode("utf-8")
        if file in changed_filenames:
          data = (APP_DIR_PATH / "mod/dropzone" / file).read_bytes()
        elif entry.is_symlink:
          continue
        else:
          org_archive.seek(org_entries[file])
          data = org_archive.read(entry.length)

        new_archive.seek(entry.offset)
        new_archive.write(data)

def expand_into_archive(filename: str, merge_path: str) -> None:
  src_path = APP_DIR_PATH / "mod/dropzone" / filename
  mod_merge_path = APP_DIR_PATH / "mod/dropzone" / merge_path
  copy_files_to_mod(merge_path)
  archive_info = get_sarc_file_info(mod_merge_path, True)
  offsets_to_update = []
  old_file_size = None
  new_file_size = len(src_path.read_bytes())
  file_offset = None
  file_length_offset = None
  prev_offset = None
  for file, sarc_entry in archive_info.items():
    if file == filename:
      file_offset = sarc_entry.offset
      file_length_offset = sarc_entry.META_entry_size_ptr
    if file_offset != None and prev_offset == file_offset:
      old_file_size = sarc_entry.offset - file_offset
    if file_offset and sarc_entry.offset > file_offset:
      offsets_to_update.append((file, sarc_entry.META_entry_offset_ptr, sarc_entry.offset + (new_file_size - old_file_size)))
    prev_offset = sarc_entry.offset

  merge_bytes = bytearray(mod_merge_path.read_bytes())
  for file_to_update in offsets_to_update:
    merge_bytes[file_to_update[1]:file_to_update[1]+4] = adf_profile.create_u32(file_to_update[2])

  filename_bytes = bytearray(src_path.read_bytes())
  merge_bytes[file_length_offset:file_length_offset+4] = adf_profile.create_u32(new_file_size)
  del merge_bytes[file_offset:file_offset+old_file_size]
  merge_bytes[file_offset:file_offset] = filename_bytes
  mod_merge_path.write_bytes(merge_bytes)

def merge_files(filenames: list[str]) -> None:
  filenames = [*set(filenames)]
  for filename in filenames:
    if is_file_in_global(filename):
      merge_into_archive(filename, GLOBAL_SRC_PATH, GLOBAL_FILES, False)
    if is_file_in_bundle(filename, LOCAL_PLAYER_FILES):
      merge_into_archive(filename, ELMER_MOVEMENT_LOCAL_SRC_PATH, LOCAL_PLAYER_FILES)
    if is_file_in_bundle(filename, NETWORK_PLAYER_FILES):
      merge_into_archive(filename, ELMER_MOVEMENT_NETWORK_SRC_PATH, NETWORK_PLAYER_FILES)
    if is_file_in_bundle(filename, GLOBAL_ANIMAL_FILES):
      merge_into_archive(filename, GLOBAL_ANIMALS_SRC_PATH, GLOBAL_ANIMAL_FILES)

def package_mod() -> None:
  for p in list(Path(APP_DIR_PATH / "mod").glob("**/*")):
    if p.is_dir() and len(list(p.iterdir())) == 0:
      os.removedirs(p)

def save_mod_list(selected_mods: dict, save_name: str) -> None:
  save_path = APP_DIR_PATH / "saves"
  save_path.mkdir(parents=True, exist_ok=True)
  save_path = save_path / f"{save_name}.json"
  save_data = {
    "version": __version__,
    "mod_options": selected_mods
  }
  save_path.write_text(json.dumps(save_data, indent=2))

def load_saved_mod_lists() -> list[str]:
  save_names = []
  for save in os.listdir(APP_DIR_PATH / "saves"):
    name, _ext = os.path.splitext(save)
    save_names.append(name)
  return save_names

def delete_saved_mod_list(name: str) -> None:
  Path(APP_DIR_PATH / "saves"/ f"{name}.json").unlink()

def load_saved_mod_list(name: str) -> dict:
  return json.load(Path(APP_DIR_PATH / "saves"/ f"{name}.json").open())

def validate_and_update_mod(mod_key: str, mod_options: dict, version: str) -> tuple[str, dict[str, dict]]:
  mod = get_mod(mod_key)
  if not _is_mod_valid(mod):
    return ("invalid", None)
  elif hasattr(mod, "handle_update"):
    try:
      new_key, new_options = mod.handle_update(mod_key, mod_options, version)
      if new_key != mod_key or new_options != mod_options:
        return ("update", {new_key: new_options})
    except ValueError as update_error:
      return ("error", update_error)
  return ("valid", None)

def _is_mod_valid(mod: ModuleType) -> bool:
  # make sure mod exists and is not set to DEBUG mode (default to True if mod.DEBUG doesn't exist)
  return mod is not None and not getattr(mod, "DEBUG", True)

def read_dropzone() -> Path:
  return Path(GAME_PATH_FILE.read_text())

def write_dropzone(folder: str) -> None:
  GAME_PATH_FILE.write_text(folder)

def get_dropzone() -> Path:
  steam_path = Path("C:/Program Files (x86)/Steam/steamapps/common/theHunterCotW")
  epic_games_path = Path("C:/Program Files/Epic Games/theHunterCotW")
  if GAME_PATH_FILE.exists():
    return read_dropzone()
  elif steam_path.exists():
    return steam_path
  elif epic_games_path.exists():
    return epic_games_path
  return None

def copy_dropzone(replace: bool = False) -> None:
  dropzone_path = get_dropzone()
  if dropzone_path:
    dropzone_path = dropzone_path / "dropzone"
    if replace:
      try:
        shutil.rmtree(dropzone_path)
      except FileNotFoundError as e:  # suppress error if user hits "Replace" when there is no /dropzone folder
        pass
    shutil.copytree(APP_DIR_PATH / "mod/dropzone", dropzone_path, dirs_exist_ok=True)
  else:
    raise FileNotFoundError('Could not find game path to save mods!\nUse the "set path" button to select your game directory.')

def find_closest_lookup(desired_value: float, filename: str) -> int:
  root, _ = os.path.splitext(filename)
  numbers = json.load((LOOKUP_PATH / f"{root}.json").open())["numbers"]
  exact_match = None
  for number, cell_index in numbers.items():
    if float(number) == desired_value:
      exact_match = int(cell_index)
      break
  if exact_match:
    return exact_match
  else:
    closest_delta = 9999999
    closest_match = None
    for number, cell_index in numbers.items():
      delta = abs(float(number) - desired_value)
      if delta < closest_delta:
        closest_match = int(cell_index)
        closest_delta = delta
    return closest_match

def find_closest_lookup2(desired_value: float, numbers: dict) -> int:
  exact_match = None
  for number, cell_index in numbers.items():
    if float(number) == desired_value:
      exact_match = int(cell_index)
      break
  if exact_match:
    return exact_match
  else:
    closest_delta = 9999999
    closest_match = None
    for number, cell_index in numbers.items():
      delta = abs(float(number) - desired_value)
      if delta < closest_delta:
        closest_match = int(cell_index)
        closest_delta = delta
    return closest_match

def lookup_column(
  filename: str,
  sheet: str,
  col_label: str,
  start_row: int,
  end_row: int,
  multiplier: float
) -> tuple[list[int], list[int]]:
  root, _ = os.path.splitext(filename)
  data = json.load((LOOKUP_PATH / f"{root}.json").open())
  cells = data["sheets"][sheet]
  cell_indices = []
  for row in range(start_row, end_row + 1):
    cell_indices.append(f"{col_label}{row}")
  # logger.debug("Cells", cell_indices)
  target_cells = list(filter(lambda x: x["cell"] in cell_indices, cells))
  target_cells = sorted(target_cells, key=lambda x: x["cell"])
  # logger.debug("Target", [c["value"] for c in target_cells])
  result = []
  for c in target_cells:
    cell_index = find_closest_lookup2(c["value"] * multiplier, data["numbers"])
    result.append((c["cell_index_offset"], cell_index))
  return result

def create_bytearray(values: any, data_format: str) -> bytearray:
  result = bytearray()
  if not isinstance(values, list):
    values = [values]
  if data_format == "bytes":
    for v in values:
      result += v
  if data_format == "uint08":
    for v in values:
      result += adf_profile.create_u8(v)
  if data_format == "uint32":
    for v in values:
      result += adf_profile.create_u32(v)
  if data_format == "float32":
    for v in values:
      result += adf_profile.create_f32(v)
  if data_format == "classes":
    # class arrays are a list of uint08 padded to a multiple of 4 bytes
    result = create_bytearray(values, "uint08")
    padding = (4 - len(result) % 4) % 4
    result += b'\x00' * padding
  if data_format == "string":
    for v in values:
      if isinstance(v, str):
        v = v.encode("utf-8")
      # strings must be padded to a multiple of 8 bytes and end in a null character
      v += b'\00'
      padding = (8 - len(v) % 8) % 8
      result += v + (b'\x00' * padding)
  if data_format == "cell_definition":
    for v in values:
      result += adf_profile.create_u16(v.value["Type"].value)
      result += adf_profile.create_u16(0)
      result += adf_profile.create_u32(v.value["DataIndex"].value)
      result += adf_profile.create_u32(v.value["AttributeIndex"].value)
  return result

def update_non_instance_offsets(extracted_adf: Adf, added_size: int) -> list[dict]:
  updates = []
  logger.debug(f"  Updating file header offsets by {added_size}")
  offsets_and_values = [
    (extracted_adf.header_profile["instance_offset_offset"], extracted_adf.instance_offset),
    (extracted_adf.header_profile["typedef_offset_offset"], extracted_adf.typedef_offset),
    (extracted_adf.header_profile["stringhash_offset_offset"], extracted_adf.stringhash_offset),
    (extracted_adf.header_profile["nametable_offset_offset"], extracted_adf.nametable_offset),
    (extracted_adf.header_profile["total_size_offset"], extracted_adf.total_size),
    (extracted_adf.table_instance[0].header_profile["size_offset"], extracted_adf.table_instance[0].size),
  ]

  # Add offsets and values to updates list
  for offset, value in offsets_and_values:
    if value > 0:  # do not add to offsets of 0
      new_value = max(value + added_size, 0)
      updates.append({"offset": offset, "value": new_value})

  # Update values in the extractd ADF
  extracted_adf.instance_offset += added_size
  extracted_adf.typedef_offset += added_size
  if extracted_adf.stringhash_offset:  # ADF that extracts to XLSX don't have `stringhash_offset`
    extracted_adf.stringhash_offset += added_size
  extracted_adf.nametable_offset += added_size
  extracted_adf.total_size += added_size
  extracted_adf.table_instance[0].size += added_size
  # Update offsets in header_profile
  for k, v in extracted_adf.table_instance[0].header_profile.items():
    extracted_adf.table_instance[0].header_profile[k] = v + added_size

  return updates

def insert_bytearray(fp: io.BufferedRandom, update: dict) -> None:
  # Read data after the section to delete
  bytes_to_delete = update.get("bytes_to_remove", 0)
  fp.seek(update["offset"] + bytes_to_delete)
  remaining_data = fp.read()
  # Write new data at the original offset
  fp.seek(update["offset"])
  fp.write(update["value"])
  # Write back the remaining data and truncate to remove extra bytes if the new array is smaller
  fp.write(remaining_data)
  fp.truncate()

def clean_equipment_name(name: str, equipment_type: str) -> str:
  name = name.removeprefix("equipment_").removeprefix(f"{equipment_type}_")
  if equipment_type == "optic":
    name = name.removeprefix("optics_")
  if equipment_type == "sight":
    name = name.removeprefix("scope_")
  if equipment_type == "weapon":
    name = name.removesuffix("_slugs")
  return name

def parse_variant_key(name: str, equipment_type: str) -> tuple[str, str]:
  # some equipments have multiple variants that end in an identifier (eg. _01, _02, etc)
  # parsing the name and variant ID separately lets us group variants under a single entry in name_map.yaml
  base_name = name
  variant_key = ""
  if equipment_type == "misc":
    for color in ["blaze", "evergreen", "glacier"]:  # backpacks have color names as their variant identifiers
      if name.endswith(color):
        variant_key = color
        base_name = name.removesuffix(f"_{color}")
  if equipment_type in ["weapon", "structure", "lure"]:
    pattern = r'^([a-zA-Z_0-9]+?)(?:_(0\d))?$'
    matches = re.match(pattern, name)
    if matches:
      base_name = matches.group(1)
      variant_key = str(matches.group(2))
  return base_name, variant_key

def map_equipment(name: str, equipment_type: str) -> dict:
  clean_name = clean_equipment_name(name, equipment_type)
  if (mapped_equipment := NAME_MAP[equipment_type].get(clean_name)):
    mapped_equipment["map_name"] = clean_name
    return mapped_equipment
  base_name, variant_key = parse_variant_key(clean_name, equipment_type)
  if (mapped_equipment := NAME_MAP[equipment_type].get(base_name)):
    mapped_equipment["variant_key"] = variant_key
    mapped_equipment["map_name"] = base_name
    return mapped_equipment
  return {}

def format_variant_name(mapped_equipment: dict) -> str:
  formatted_name = mapped_equipment["name"]
  if "variant_key" in mapped_equipment:
    variant_key = mapped_equipment["variant_key"]
    if "variant" in mapped_equipment:
      variant_name = mapped_equipment["variant"].get(variant_key)
      if variant_name:
        formatted_name = variant_name
      else:
        formatted_name = f"{mapped_equipment["name"]} {variant_key}"  # unknown variant
    elif "style" in mapped_equipment:
      style_name = mapped_equipment["style"].get(variant_key)
      if style_name:
       formatted_name = f'{mapped_equipment["name"]} - {style_name}'
      else:
        formatted_name = f"{mapped_equipment["name"]} - {variant_key}"  # unknown style
  return formatted_name

def format_float(value: any, decimals: int = 4):
  value = coerce_float(value)
  if value is None:
    return ""
  float_string = f"{value:.{decimals}f}"
  return float_string.rstrip("0").rstrip(".")

def coerce_float(value: any) -> float | None:
  try:
    return float(value)
  except (TypeError, ValueError):
    return None

def coerce_int(value: any) -> float | None:
  try:
    return int(value)
  except (TypeError, ValueError):
    return None
