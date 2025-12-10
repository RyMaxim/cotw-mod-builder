import json
import math
import textwrap
import traceback
import webbrowser
from importlib.metadata import version
from pathlib import Path

import FreeSimpleGUI as sg
from tkinter import TclError
import requests
from deepmerge import always_merger
from packaging.version import Version as package_version

from modbuilder import logo, mods, party
from modbuilder.logging_config import get_logger
from modbuilder.widgets import create_option, generate_buttons, valid_option_value

logger = get_logger(__name__)

__version__ = version("modbuilder-revived")

DEFAULT_FONT = "_ 14"
SMALL_FONT = "_ 11"
TEXT_WRAP = 142

def _get_mods(window: sg.Window) -> None:
  window.refresh()
  height = window["options"].Widget.winfo_height()  # column sometimes shrinks after window.extend_layout()
  mods.load_mods()
  mod_names = [m.NAME for m in mods.MODS_LIST.values()]
  window["modification"].update(values=mod_names)
  window["modification"].metadata=mod_names
  window.extend_layout(window["options"], _get_mod_options())
  window['options'].Widget.config(height=height)  # reset column height to preserve layout
  window.set_icon(logo.value)  # fix taskbar icon if it didn't load properly
  window.refresh()

def _check_for_update() -> None:
  release_data = _get_latest_release()
  if release_data:
    latest_tag = release_data.get("tag_name", "").lstrip("v")
    if package_version(latest_tag) > package_version(__version__):
      _show_update_popup(release_data)

def _get_latest_release() -> dict:
  try:
    resp = requests.get("https://api.github.com/repos/RyMaxim/cotw-mod-builder/releases/latest", timeout=2)
    resp.raise_for_status()
    data = resp.json()
    return data
  except Exception as e:
    logger.error(f"Check for update failed: {e}")
  return {}

def _show_update_popup(release_data: dict) -> None:
  nexus_url = "https://www.nexusmods.com/thehuntercallofthewild/mods/410?tab=files"
  github_url = release_data["html_url"]
  layout = [
    [sg.Text(f"A newer version is available!", text_color="yellow")],
    [sg.Text(release_data["name"])],
    [sg.Button("NexusMods", key="-NEXUSMODS-"), sg.Button("GitHub", key="-GITHUB-")],
  ]

  window = sg.Window("Update Available", layout, icon=logo.value, modal=True)
  while True:
    event, _values = window.read()
    if event in (sg.WINDOW_CLOSED, "Close"):
      break
    elif event == "-NEXUSMODS-":
      webbrowser.open(nexus_url)
      break
    elif event == "-GITHUB-":
      webbrowser.open(github_url)
      break
  window.close()

def _warn_user_onedrive_folder() -> None:
  parts = [p.lower() for p in mods.APP_DIR_PATH.parts]
  if "onedrive" in parts:
    idx = parts.index("onedrive")
    recommended = Path(*mods.APP_DIR_PATH.parts[:idx])
    onedrive_warning = (
      'Mod Builder has detected that it is running from inside a OneDrive-synced folder. This can cause errors and unexpected behavior.\n'
      '\n'
      'Please close this application and move the entire "modbuilder" folder to a non-OneDrive location before continuing.\n\n'
      f'Recommended path: {recommended}'
    )
    sg.PopupOK(onedrive_warning, icon=logo.value, title="OneDrive folder detected", font=SMALL_FONT)

def _warn_user_permissions_error() -> None:
  permissions_warning = (
    'Failed to load mods into the "dropzone" folder.\n'
    '> PermissionError: Access is denied\n'
    '\n'
    'Please close this application and run it as Administrator:\n'
    ' - Right-click "modbuilder.exe"\n'
    ' - Choose "Run as Administrator"'
  )
  sg.PopupOK(permissions_warning, icon=logo.value, title="Administrator permissions required", font=SMALL_FONT)

def _show_popup_message(message: str) -> str:
  sg.popup_quick_message(message, font="_ 28", background_color="brown")

def _show_error_window(error: Exception, mod_key: str = None, mod_options: dict = None):
  nexus_url = "https://www.nexusmods.com/thehuntercallofthewild/mods/410?tab=bugs"
  logger.error(f"ERROR! {mod_key} : {error}")
  header = [f"Version: {__version__}"]
  err_msg = ["", f"Error: {error}"]
  mod_msg = ["", f"Mod: {mod_key}"] if mod_key else []
  opts_msg = ["", "Options:", json.dumps(mod_options, indent=4)] if mod_options else []
  message = "\n".join(header + err_msg + mod_msg + opts_msg)

  layout = [
    [sg.T(f"Please paste this error as a new bug on NexusMods:")],
    [sg.Multiline(message, font=SMALL_FONT ,expand_x=True, expand_y=True, disabled=True)],
    [sg.Button("Copy to Clipboard", key="-CLIPBOARD-"), sg.Push(), sg.Button("Open NexusMods", key="-NEXUSMODS-")],
  ]

  window = sg.Window("🚨 UNEXPECTED ERROR", layout, modal=True, size=(600, 500), icon=logo.value)
  while True:
    event, _values = window.read()
    if event in (sg.WINDOW_CLOSED, "Close"):
      break
    elif event == "-CLIPBOARD-":
      sg.clipboard_set(message)
      _show_popup_message("Copied to Clipboard")
    elif event == "-NEXUSMODS-":
      webbrowser.open(nexus_url)
      break
  window.close()

def _mod_name_to_key(name: str) -> str:
  if name is None:
    return ""
  return mods.get_mod_key_from_name(name)

def _get_mod_options() -> list[dict]:
  possible_mods = mods.MODS_LIST
  options = []
  for mod_key, mod in possible_mods.items():
    mod_details = []
    mod_details.append([sg.T("Description:", p=(10, 10), font="_ 14 underline", text_color="orange")])
    mod_details.append([sg.T(textwrap.fill(mod.DESCRIPTION, TEXT_WRAP), p=(10,0))])

    if hasattr(mod, "WARNING"):
      warning_header = sg.T(" WARNING ", font="_ 14", text_color="firebrick1", p=(10, 10), background_color="black")
      warning = sg.T(textwrap.fill(mod.WARNING, TEXT_WRAP), p=(10,0))
      mod_details.append([warning_header])
      mod_details.append([warning])

    if hasattr(mod, "PRESETS"):
      mod_details.append([sg.T("Presets:", font="_ 14 underline", text_color="orange", p=((10,10),(10,0)))])
      presets = []
      for preset in mod.PRESETS:
        presets.append(preset["name"])
      mod_details.append([sg.Combo(presets, k=f"preset__{mod_key}", enable_events=True, p=(30,10))])

    mod_details.append([sg.T("Options:", font="_ 14 underline", text_color="orange", p=((10,10),(10,0)))])
    if hasattr(mod, "OPTIONS"):
      for mod_option in mod.OPTIONS:
        mod_name = mod_option['name'] if "name" in mod_option else None
        key = f"{mod_key}__{_mod_name_to_key(mod_name)}"
        mod_details.extend(create_option(mod_option, key))
    else:
      mod_details.append([mod.get_option_elements()])

    options.append([sg.pin(sg.Column(mod_details, k=mod_key, visible=False, expand_y=True, expand_x=True))])
  return options

def _show_mod_options(mod_name: str, window: sg.Window) -> None:
  for mod in window["modification"].metadata:
    if mod == mod_name:
      window[_mod_name_to_key(mod)].update(visible=True)
    else:
      window[_mod_name_to_key(mod)].update(visible=False)

def _format_selected_mods(selected_mods: dict, window: sg.Window) -> list[str]:
  formatted_mod_options = []
  error_keys = []
  for mod_key, mod_options in selected_mods.items():
    mod = mods.get_mod(mod_key)
    if mod is not None:
      try:
        formatted_mod_options.append(mod.format_options(mod_options))
      except Exception as error:
        error_keys.append(mod_key)
        _show_error_window(error, mod_key=mod_key, mod_options=mod_options)
  for error_key in error_keys:
    del selected_mods[error_key]
  window["selected_mods"].update(formatted_mod_options)
  return selected_mods

def _valid_option_value(mod_option: dict, mod_value: any) -> str:
  return valid_option_value(mod_option, mod_value)

def _enable_mod_button(window: sg.Window) -> None:
  selected_mod_size = len(window["selected_mods"].get_list_values())
  window["build_mod_tab"].update(title=f"Build Modifications ({selected_mod_size})")
  window["build_mod"].update(disabled=(selected_mod_size == 0))
  window["save"].update(disabled=(selected_mod_size == 0))
  window["move_up"].update(disabled=(selected_mod_size == 0))
  window["move_down"].update(disabled=(selected_mod_size == 0))

def _create_party() -> None:
  layout = [
    [sg.Image(party.value), sg.Column([
      [sg.T("Your mods have successfully been created!", font="_ 20")],
      [sg.T(mods.APP_DIR_PATH / "mod", text_color="orange")],
      [sg.T(textwrap.fill("Load: copy mods to the dropzone folder, overwrite changed files.", 60))],
      [sg.T(textwrap.fill("Replace: delete the old folder before copying.", 60))],
      [sg.VPush()],
      [sg.Push(), sg.Button("Load", k="load"), sg.Button("Replace", k="load_replace"), sg.Button("Close")]
    ], expand_x=True, expand_y=True)]
  ]

  window = sg.Window("Mod Created", layout, modal=True, icon=logo.value, font=DEFAULT_FONT)

  while True:
    event, _values = window.read()
    if event == sg.WIN_CLOSED or event == "Close":
      break
    try:
      if event in ["load", "load_replace"]:
        mods.copy_dropzone(replace=(event == "load_replace"))
        _show_popup_message("Mods Loaded")
        break
    except FileNotFoundError as ex:
      sg.Popup(ex, title="Error", icon=logo.value, font=DEFAULT_FONT)
  window.close()

def _show_load_mod_list() -> tuple[bool, list[dict], str]:
  saved_mod_lists = mods.load_saved_mod_lists()
  layout = [
    [sg.T("Saved Mod Lists", font="_ 18")],
    [sg.Listbox(saved_mod_lists, expand_x=True, expand_y=True, k="saved_mod_lists", enable_events=True)],
    [sg.Button("Delete", k="delete", disabled=True), sg.Push(), sg.Button("Cancel", k="cancel"), sg.Button("Merge", k="merge", disabled=True), sg.Button("Load", k="load", disabled=True)],
    [sg.ProgressBar(100, orientation="h", k="load_progress", expand_x=True, s=(10,20))]
  ]
  window = sg.Window("Load Saved Mod List", layout, modal=True, size=(600, 300), icon=logo.value, font=DEFAULT_FONT)
  merge = False
  loaded_mods = []
  selected_save_file = None

  while True:
    event, values = window.read()
    if event == sg.WIN_CLOSED or event == "cancel":
      break
    if event == "delete":
      delete_confirm = sg.PopupOKCancel("Are you sure you want to delete the saved mod list?", title="Delete Confirm", icon=logo.value, font=DEFAULT_FONT)
      if delete_confirm == "OK":
        mods.delete_saved_mod_list(values["saved_mod_lists"][0])
        window["saved_mod_lists"].update(mods.load_saved_mod_lists())
        window["delete"].update(disabled=True)
        window["load"].update(disabled=True)
        window["merge"].update(disabled=True)
    elif event == "saved_mod_lists":
      if len(values["saved_mod_lists"]) == 0:
        continue
      window["delete"].update(disabled=False)
      window["load"].update(disabled=False)
      window["merge"].update(disabled=False)
    elif event == "load" or event == "merge":
      selected_save_file = values["saved_mod_lists"][0]
      loaded_mods = _load_and_validate_saved_mods(selected_save_file, window, event)
      merge = event == "merge"
      break
  window.close()
  return (merge, loaded_mods, selected_save_file)

def _load_and_validate_saved_mods(mod_list_name: str, window: sg.Window, event: str) -> dict:
  loaded_mods_json = mods.load_saved_mod_list(mod_list_name)
  version = loaded_mods_json.get("version", "0.0.0")
  imported_mods = _validate_saved_mod_list(loaded_mods_json, version, window)
  loaded_mods_list = imported_mods["load"]
  if imported_mods["remove"]:
    imported_mods["remove"] = _handle_unsupported_mods(imported_mods, mod_list_name)
  if imported_mods["error"]:
    _show_update_errors(imported_mods["error"])
  if imported_mods["update"]:
    _handle_updated_mods(imported_mods, mod_list_name, event)
    loaded_mods_list = always_merger.merge(loaded_mods_list, imported_mods["update"])
  return loaded_mods_list

def _validate_saved_mod_list(loaded_mods_json: dict, version: str, window: sg.Window) -> dict[str, dict[str, dict]]:
  mods_to_keep = {}
  updated_mods = {}
  update_errors = {}
  mods_to_remove = {}
  loaded_saved_mods = loaded_mods_json["mod_options"] if version != "0.0.0" else loaded_mods_json
  window["load_progress"].update(0)
  step = 1
  progress_step = 100 / len(loaded_saved_mods)
  for mod_key, mod_options in loaded_saved_mods.items():
    result, output = mods.validate_and_update_mod(mod_key, mod_options, version)
    if result == "invalid":
      mods_to_remove[mod_key] = mod_options
    elif result == "update":
      updated_mods = always_merger.merge(updated_mods, output)
    elif result == "error":
      update_errors[mods.format_mod_display_name(mod_key, mod_options)] = output
    elif result == "valid":
      mods_to_keep[mod_key] = mod_options
    else:
      raise ValueError(f"Error validating/updating mod: {mods.format_mod_display_name(mod_key, mod_options)}")
    load_progress = math.floor(step * progress_step)
    window["load_progress"].update(load_progress)
    step += 1
  return {"load": mods_to_keep, "update": updated_mods, "error": update_errors, "remove": mods_to_remove}

def _handle_unsupported_mods(imported_mods: dict, mod_list_name: str) -> dict:
  formatted_mods = [mods.format_mod_display_name(mod_key, mod_options) for mod_key, mod_options in imported_mods["remove"].items()]
  count = len(formatted_mods)
  s = "s" if count > 1 else ""
  remove_confirm = _show_mods_popup(
    "Unsupported mod configuration",
    "UNSUPPORTED MODS!", "firebrick1",
    f"The following mod{s} are unsupported and cannot be loaded.",
    "Do you want to remove them from the save file?",
    ["yes", "no"],
    formatted_mods,
  )
  if remove_confirm == "Yes":
    mods_to_keep = always_merger.merge(imported_mods["load"], imported_mods["update"])
    mods.save_mod_list(mods_to_keep, mod_list_name)
    return {}
  return imported_mods["remove"]

def _handle_updated_mods(imported_mods: dict, mod_list_name: str, event: str) -> None:
  formatted_mods = [mods.format_mod_display_name(new_key, new_options) for new_key, new_options in imported_mods["update"].items()]
  count = len(formatted_mods)
  s = "s" if count > 1 else ""
  update_confirm = _show_mods_popup(
      f"Updated {count} mod{s}",
      "UPDATE SUCCESS!", "green",
      f"{len(formatted_mods)} mod{s} were updated and will be loaded",
      "Do you want to update the save file?",
      ["yes", "no"],
      formatted_mods,
    )
    # update_confirm = sg.popup_yes_no(f"Updated configuration for {len(imported_mods["update"])} mods. Do you want to update the save file?", title=f"Update success!", icon=logo.value, font=DEFAULT_FONT)
  if update_confirm == "Yes":
    mods_to_keep = always_merger.merge(always_merger.merge(imported_mods["remove"], imported_mods["load"]), imported_mods["update"])
    mods.save_mod_list(mods_to_keep, mod_list_name)
    _show_popup_message("Modifications Saved")

def _show_update_errors(update_errors: list[dict]) -> None:
  formatted_errors = [f"{key}: {value}" for key, value in update_errors.items()]
  count = len(formatted_errors)
  s = "s" if count > 1 else ""
  _show_mods_popup(
    f"Error updating {count} mod{s}",
    "ERROR!", "firebrick1",
    f"{count} mod{s} could not be loaded. Please recreate with updated settings.",
    "The save file has NOT been modified",
    ["ok"],
    formatted_errors,
  )

def _show_mods_popup(title: str, highlighted_text: str, color: str, message: str, prompt: str, button_names: list[str], formatted_list: list[str]) -> None:
  longest_line = max(formatted_list, key=len)
  width = min(len(longest_line) + 1, 110)
  height = min(len(formatted_list), 20)
  layout = [[
    sg.Column([
      [sg.T(highlighted_text, text_color=color),
       sg.T(message, p=(0,0))],
      [sg.Listbox(formatted_list, size=(width, height), expand_x=True, expand_y=True)],
      [sg.T(prompt)],
      generate_buttons(button_names)
    ], expand_x=True, expand_y=True)
  ]]
  choice,_ = sg.Window(title, layout, icon=logo.value, modal=True, resizable=True, finalize=True).read(close=True)
  return choice

def _move_mods(selected_mods: dict, listbox: sg.Listbox, direction: int) -> dict:
  selected_mod_indices = sorted(list(listbox.get_indexes()), reverse=(direction == 1))  # reverse if moving down the list
  if not selected_mod_indices:
    return selected_mods
  listbox_values = listbox.get_list_values()
  index_map = list(range(len(listbox_values)))
  new_selected_indicies = []

  for index in selected_mod_indices:
    new_index = index + direction
    if (
      new_index < 0  # cannot move above first position
      or new_index >= len(listbox_values)  # cannot move below last position
      or new_index in new_selected_indicies  # cannot move to a position an item has already moved to
    ):
      # example: move items 0,1,3 up the list
      # - 0 cannot move up
      # - 1 cannot move up because 0 was also selected and couldn't move
      # - 3 is moved up to 2
      new_selected_indicies.append(index)
      continue
    # Reorder the resulting mod indicies
    index_map[index], index_map[new_index] = index_map[new_index], index_map[index]
    new_selected_indicies.append(new_index)
  # Reorder the mods list based on the new index_map
  mod_keys = list(selected_mods.keys())
  selected_mods = {mod_keys[i]: selected_mods[mod_keys[i]] for i in index_map}
  updated_values = [listbox_values[i] for i in index_map]
  # Update the listbox and preserve scrollbar position
  scroll_position = listbox.TKListbox.yview()
  listbox.update(values=updated_values, set_to_index=new_selected_indicies)
  listbox.TKListbox.yview_moveto(scroll_position[0])
  return selected_mods

def _sort_mods(selected_mods: dict, listbox: sg.Listbox) -> dict:
    listbox_values = listbox.get_list_values()
    selected_indices = listbox.get_indexes()
    if not selected_indices:
        return selected_mods  # Nothing to do
    # Get the selected values and their original indices
    selected_items = [(i, listbox_values[i]) for i in selected_indices]
    # Sort selected items by display value (case-insensitive)
    selected_items_sorted = sorted(selected_items, key=lambda pair: pair[1].lower())
    # Build new listbox values with only the selected items reordered
    new_listbox_values = listbox_values[:]
    for (new_index, (_, value)) in zip(selected_indices, selected_items_sorted):
        new_listbox_values[new_index] = value
    # Create a mapping of listbox values to original mod keys (in order)
    mod_keys = list(selected_mods.keys())
    value_to_key = {listbox_values[i]: mod_keys[i] for i in range(len(listbox_values))}
    # Build new mod key order based on reordered listbox
    new_mod_keys = [value_to_key[val] for val in new_listbox_values]
    new_selected_mods = {k: selected_mods[k] for k in new_mod_keys}
    # Update the listbox with reordered values
    scroll_position = listbox.TKListbox.yview()
    listbox.update(values=new_listbox_values, set_to_index=selected_indices)
    listbox.TKListbox.yview_moveto(scroll_position[0])
    return new_selected_mods

def _delete_mods(selected_mods: dict, listbox: sg.Listbox) -> dict:
  selected_mod_indicies = list(listbox.get_indexes())
  if not selected_mod_indicies:
    return selected_mods
  listbox_values = listbox.get_list_values()
  mod_keys = list(selected_mods.keys())
  for index in sorted(selected_mod_indicies, reverse=True):  # delete end-to-start so we don't mess up the list
    del listbox_values[index]  # delete from listbox
    del selected_mods[mod_keys[index]]  # delete from mods dict
  listbox.update(values=listbox_values)
  return selected_mods

def main() -> None:
  sg.theme("DarkAmber")
  sg.set_options(font=DEFAULT_FONT)

  selected_mods = {}
  loaded_mod_list_name = ""
  change_path_text = "(change path)" if mods.get_dropzone() else "(set path)"
  loading_text = " Loading mods. Please wait... "

  layout = [
    [
      sg.Image(logo.value),
      sg.Column([
        [sg.T("Mod Builder - Revived", expand_x=True, font="_ 24")],
        [
          sg.T(mods.get_dropzone(), font="_ 12", k="game_path"),
          sg.T(change_path_text, font="_ 12 underline", text_color="orange", enable_events=True, k="change_path")
        ],
      ]),
      sg.Push(),
      sg.T(f"Version: {__version__}", font="_ 12", p=((0,0),(0,60)))
    ],
    [
      sg.TabGroup([[
        sg.Tab("Add Modification", [
          [
            sg.Column([
              [sg.T("Mod:", p=((18, 10), (10,0)), font="_ 14 underline", text_color="orange"), sg.Combo([loading_text], default_value=loading_text, k="modification", metadata=[], enable_events=True, p=((0, 0), (10, 0)))],
              [sg.Column([], p=(0,0), k="options", expand_x=True, expand_y=True, scrollable=True, vertical_scroll_only=True)],
              [sg.Button("Add Modification", k="add_mod", button_color=f"{sg.theme_element_text_color()} on brown", disabled=True, expand_x=True)]
            ], k="add_mod_col", expand_x=True, expand_y=True, p=((0,0), (10,0))),
          ],
        ], k="add_mod_tab"),
        sg.Tab("Build Modifications (0)", [
          [
            sg.Column([
                [sg.Listbox([], expand_x=True, k="selected_mods", enable_events=True, expand_y=True, select_mode=sg.LISTBOX_SELECT_MODE_EXTENDED)],
                [
                  sg.Button("Save", k="save", button_color=f"{sg.theme_element_text_color()} on brown", disabled=True),
                  sg.Button("Load", k="load", button_color=f"{sg.theme_element_text_color()} on brown"),
                  sg.Button("▲", k="move_up", button_color=f"{sg.theme_element_text_color()} on brown", disabled=True),
                  sg.Button("▼", k="move_down", button_color=f"{sg.theme_element_text_color()} on brown", disabled=True),
                  sg.Button("A-Z", k="sort_mods", button_color=f"{sg.theme_element_text_color()} on brown", disabled=True),
                  sg.Push(),
                  sg.Button("Remove", k="remove_mod", button_color=f"{sg.theme_element_text_color()} on brown", disabled=True)
                ],
                [sg.Button("Build Modifications", k="build_mod", button_color=f"{sg.theme_element_text_color()} on brown", expand_x=True, disabled=True)]
            ], k="build_mod_col", expand_x=True, expand_y=True, p=((0,0), (0,0))),
          ]
        ], k="build_mod_tab")
      ]], k="modbuilder_tab_group", expand_x=True, expand_y=True)
    ],
    [
      sg.ProgressBar(100, orientation="h", k="build_progress", expand_x=True, s=(10,20))
    ]
  ]

  window = sg.Window("COTW: Mod Builder - Revived", layout, resizable=True, font=DEFAULT_FONT, icon=logo.value, size=(1300, 800), finalize=True)
  _get_mods(window)
  _check_for_update()
  _warn_user_onedrive_folder()

  while True:
    event, values = window.read()
    #logger.debug(event)
    if event == sg.WIN_CLOSED:
      break

    try:
      if event == "modification":
        mod_name = values["modification"]
        mod_key = _mod_name_to_key(mod_name)
        mod = mods.get_mod(mod_key)
        _show_mod_options(mod_name, window)
        window["add_mod"].update(disabled=False)
        window.visibility_changed()
        window["options"].contents_changed()
      elif event.startswith("add_mod"):
        mod_name = values["modification"]
        mod_key = _mod_name_to_key(mod_name)
        mod = mods.get_mod(mod_key)
        mod_options = {}
        is_invalid = None
        if event == "add_mod" and hasattr(mod, "add_mod"):
          result = mod.add_mod(window, values)
          is_invalid = result["invalid"]
          if not is_invalid:
            mod_options = result["options"]
            mod_key = result["key"]
        elif event.startswith("add_mod_group") and hasattr(mod, "add_mod_group"):
          result = mod.add_mod_group(window, values)
          is_invalid = result["invalid"]
          if not is_invalid:
            mod_options = result["options"]
            mod_key = result["key"]
        else:
          for key, value in values.items():
            if isinstance(key, str) and mod_key in key:
              option_key = key.split("__")[1]  # Modify Skills
              invalid_result = _valid_option_value(mods.get_mod_option(mod_key, option_key), value)
              if invalid_result is None:
                mod_options[option_key] = value
              else:
                is_invalid = invalid_result
                break
        if is_invalid is None:
          selected_mods[mod_key] = mod_options
          selected_mods = _format_selected_mods(selected_mods, window)
          _enable_mod_button(window)
          _show_popup_message("Mod Added")
        else:
          sg.PopupOK(is_invalid, icon=logo.value, title="Error", font=DEFAULT_FONT)
      elif event == "selected_mods":
        if len(values["selected_mods"]) == 0:
          continue
        window["remove_mod"].update(disabled=False)
        window["sort_mods"].update(disabled=False)
      elif event == "move_up":
        selected_mods = _move_mods(selected_mods, window["selected_mods"], -1)
      elif event == "move_down":
        selected_mods = _move_mods(selected_mods, window["selected_mods"], 1)
      elif event == "sort_mods":
        selected_mods = _sort_mods(selected_mods, window["selected_mods"])
      elif event == "remove_mod":
        selected_mods = _delete_mods(selected_mods, window["selected_mods"])
        window["remove_mod"].update(disabled=True)
        window["sort_mods"].update(disabled=True)
        _enable_mod_button(window)
      elif event == "build_mod":
        window["build_mod"].update(disabled=True)
        mods.clear_mod()
        mod_files = []
        step = 1
        progress_step = 95 / len(selected_mods.keys())
        for mod_key, mod_options in selected_mods.items():
          mod = mods.get_mod(mod_key)
          if hasattr(mod, "FILE"):
            modded_files = mods.copy_files_to_mod(mod.FILE)
          else:
            modded_files = mods.copy_all_files_to_mod(mod.get_files(mod_options))
          mod_files += modded_files
          mods.apply_mod(mod, mod_options)
          if hasattr(mod, "merge_files"):
            mod.merge_files(modded_files, mod_options)
          step_progress = math.floor(step * progress_step)
          window["build_progress"].update(step_progress)
          step += 1
        mods.merge_files(mod_files)
        mods.package_mod()
        selected_mods = _format_selected_mods(selected_mods, window)
        _enable_mod_button(window)
        window["remove_mod"].update(disabled=True)
        window["sort_mods"].update(disabled=True)
        window["build_progress"].update(100)
        _create_party()
        window["build_progress"].update(0)
      elif event == "save":
        save_name = sg.PopupGetText("What name would you like use to save modifications?", title="Save Mods", default_text=loaded_mod_list_name, font=DEFAULT_FONT, icon=logo.value)
        if save_name:
          mods.save_mod_list(selected_mods, save_name)
          _show_popup_message("Modifications Saved")
      elif event == "load":
        merge, loaded_mods, loaded_mod_list_name = _show_load_mod_list()
        if loaded_mods:
          selected_mods = always_merger.merge(selected_mods, loaded_mods) if merge else loaded_mods
          selected_mods = _format_selected_mods(selected_mods, window)
          _enable_mod_button(window)
          _show_popup_message("Modifications Loaded")
      elif event == "change_path":
        game_path = sg.PopupGetFolder("Select the game folder (folder with file theHunterCotW_F.exe)", "Game Path", icon=logo.value, font=DEFAULT_FONT)
        if game_path:
          mods.write_dropzone(game_path)
          window["game_path"].update(game_path)
          window["change_path"].update("(change path)")
      elif event.startswith("preset__"):
        presets = mod.PRESETS
        preset_mod_key = _mod_name_to_key(mod.NAME)
        preset_name = values[f"preset__{preset_mod_key}"]
        preset = next((preset for preset in presets if preset["name"] == preset_name), None)
        for option in preset["options"]:
          if "value" in option:
            window[f"{preset_mod_key}__{option['name']}"].update(option["value"])
          else:
            window[f"{preset_mod_key}__{option['name']}"].update(set_to_index = option["values"])
      else:
        mods.delegate_event(event, window, values)
    except PermissionError as exc:
      # catch "WinError 5: Access is denied" if Windows is preventing the user from deleting the "dropzone" folder
      if getattr(exc, "winerror", None) == 5:
        _warn_user_permissions_error()
      raise
    except TclError as exc:
      # catch and ignore a "widget is gone" error if the user hits X to close the window while mods are loading
      if "invalid command name" in str(exc):
          return
      raise
    except Exception:
      _show_error_window(traceback.format_exc())

  window.close()

if __name__ == "__main__":
    main()
