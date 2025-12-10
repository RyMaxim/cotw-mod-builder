import re
from pathlib import Path

import FreeSimpleGUI as sg

from deca.ff_adf import Adf, AdfValue
from deca.ff_rtpc import RtpcNode
from modbuilder import mods, mods2

DEBUG = False
NAME = "Modify Weapon"
DESCRIPTION = 'Modify weapon magazine size, recoil, scope wobble, zeroing settings, and scope offsets. Use "Modify Ammo" to edit damage and classes.'


class WeaponMagazine:
    __slots__ = (
        'name', 'internal_names', 'display_name', 'type', 'size', 'offsets'
    )
    name: str
    internal_names: list[str]  # list so we can merge variants
    type: str
    size: int
    offsets: list[int]  # list so we can merge variants

    def __repr__(self) -> str:
        return f"( {self.name}, {self.type}, {self.size}, {self.offsets}, {self.internal_names} )"

    def __init__(self, weapon_data: RtpcNode) -> None:
        for prop in weapon_data.prop_table:
            if prop.name_hash == 3541743236:  # 0xd31ab684 - "name"
                self.name = prop.data.decode("utf-8")
            if prop.name_hash == 588564970:  # 0x2314c9ea - internal variant display name
                self.internal_names = [prop.data.decode("utf-8")]
        self._get_weapon_name_and_type()
        magazine = weapon_data.child_table[1].prop_table[2]
        self.size = magazine.data
        self.offsets = [magazine.data_pos]

    def _get_weapon_name_and_type(self) -> None:
        if (mapped_equipment := mods.map_equipment(self.name, "weapon")):
            self.name = mapped_equipment["map_name"]
            self.display_name = mapped_equipment["name"]
            self.type = mapped_equipment.get("type", "")
        else:
            self.name = mods.clean_equipment_name(self.name, "weapon")
            self.display_name = self.name
            self.type = ""


class WeaponZeroing:
    __slots__ = (
        "level_2_distance", "level_2_distance_offset", "level_2_angle", "level_2_angle_offset",
        "level_1_distance", "level_1_distance_offset", "level_1_angle", "level_1_angle_offset",
        "level_3_distance", "level_3_distance_offset", "level_3_angle","level_3_angle_offset",
        "bullet_overrides",
    )

    def __init__(self, extracted_adf: Adf) -> None:
        data = extracted_adf.table_instance_full_values[0].value["ZeroingSettings"].value
        try:
            # zeroing settings in file: 0 = short, 1 = default, 2 = long
            # the mod lists Level 1-3 where 1 = default, 2 = short, 3 = long to match the "Zeroing" perk levels
            self.level_2_distance: float  = data[0].value["zero_distance"].value
            self.level_2_distance_offset: int = data[0].value["zero_distance"].data_offset
            self.level_2_angle: float = data[0].value["angle"].value
            self.level_2_angle_offset: int = data[0].value["angle"].data_offset
            self.level_1_distance: float = data[1].value["zero_distance"].value
            self.level_1_distance_offset: int = data[1].value["zero_distance"].data_offset
            self.level_1_angle: float = data[1].value["angle"].value
            self.level_1_angle_offset: int = data[1].value["angle"].data_offset
            self.level_3_distance: float = data[2].value["zero_distance"].value
            self.level_3_distance_offset: int = data[2].value["zero_distance"].data_offset
            self.level_3_angle: float = data[2].value["angle"].value
            self.level_3_angle_offset: int = data[2].value["angle"].data_offset
        except:
            raise ValueError("Failed to load zeroing")

        self.bullet_overrides: dict[str, dict] = {}
        for i, zeroing_setting in enumerate(data):
            level_map = {0: 2, 1: 1, 2: 3}
            for override in zeroing_setting.value["BulletOverrides"].value:
                bullet_name = override.value["BulletName"].hash_string
                if bullet_name:
                    bullet_name: str = bullet_name.decode("utf-8")
                    if bullet_name not in self.bullet_overrides:
                        self.bullet_overrides[bullet_name] = {}
                    self.bullet_overrides[bullet_name][f"level_{level_map[i]}_angle"] = override.value["Angle"].value
                    self.bullet_overrides[bullet_name][f"level_{level_map[i]}_angle_offset"] = override.value["Angle"].data_offset


class WeaponScopeSettings:
    def __init__(self, scope_index: int, scope_data: AdfValue) -> None:
        self.index = scope_index
        self._parse_name(scope_data)
        self.horizontal_offset: float = round(scope_data.value["HorizontalOffset"].value, 5)
        self.horizontal_data_offset = int(scope_data.value["HorizontalOffset"].data_offset)
        self.vertical_offset: float = round(scope_data.value["VerticalOffset"].value, 5)
        self.vertical_data_offset = int(scope_data.value["VerticalOffset"].data_offset)

    def _parse_name(self, scope_data: dict) -> None:
        # clean_name, _v = mods.clean_equipment_name(scope, "sight")
        scope_hash = scope_data.value["ScopeNameHash"].hash_string
        if scope_hash == None:
            raise ValueError("Scope has no hash string")
        self.name = mods.clean_equipment_name(scope_hash.decode("utf-8"), "sight")
        if self.name == "":
            self.name = f"{scope_hash} [{self.index}]"
        mapped_equipment = mods.map_equipment(self.name, "sight")
        if mapped_equipment:
            self.display_name = mapped_equipment["name"]
        else:
            self.display_name = f"_PLACEHOLDER [{self.index}]"

    def __repr__(self) -> str:
        return f"{self.display_name} [{self.index}], {self.horizontal_offset}, {self.vertical_offset}"


class WeaponTuning:
    __slots__ = (
        'file',
        'name',
        'weapon_display_name',
        'display_name',
        'ammo_name',
        'type',
        'offsets',
        'magazine',
        'zeroing',
        'scopes',
        'ui_data',
    )

    file: str
    name: str                           # cleaned filename - eg. "shotgun_drilling_slugs"
    weapon_display_name: str            # mapped from name_map.yaml - eg. "Grelck Drilling Rifle"
    display_name: str                   # weapon_display_name + ammo_name - eg. "Grelck Drilling Rifle (Slugs)"
    ammo_name: str
    type: str
    offsets: dict
    zeroing: WeaponZeroing
    scopes: list[WeaponScopeSettings]
    magazine: WeaponMagazine
    ui_data: dict

    def __init__(self, file: str) -> None:
        self.file = file
        self._parse_name_and_type()
        extracted_adf = mods2.deserialize_adf(mods.get_org_file(file))
        try:
            self._get_offsets(extracted_adf)
            self._get_scopes_data(extracted_adf)
            self.zeroing = WeaponZeroing(extracted_adf)
            self.ui_data = WEAPON_UI_DATA.get(self.weapon_display_name, None)
            self.magazine = WEAPON_MAGAZINE_DATA.get(self.weapon_display_name, None)
        except (ValueError, KeyError) as e:
            raise ValueError(f"Unable to load game data for {self.display_name}: {e}")

    def _parse_name_and_type(self) -> None:
        # example file: editor/entities/hp_weapons/weapon_bows_01/tuning/equipment_weapon_compound_bow_01.wtunec
        split_file = self.file.split("/")
        filename = split_file[-1].removesuffix(".wtunec")
        self.type = split_file[-3].removeprefix("weapon_").removesuffix("s_01")
        self.name = filename.removeprefix("equipment_").removeprefix("weapon_")
        self.ammo_name = ""
        if self.type == "shotgun":
            self.ammo_name = "Slugs" if filename.endswith("_slugs") else "Bird/Buckshot"
        if (mapped_weapon := mods.map_equipment(self.name, "weapon")):
            self.ammo_name = mapped_weapon.get("ammo", self.ammo_name)
            self.weapon_display_name = mapped_weapon["name"]
        else:
            self.weapon_display_name = self.name
        formatted_ammo = f" ({self.ammo_name})" if self.ammo_name else ""
        self.display_name = self.weapon_display_name + formatted_ammo

    def _get_offsets(self, extracted_adf: Adf) -> None:
        self.offsets = {}
        adf_values = extracted_adf.table_instance_full_values[0].value
        base_tuning = adf_values["bullet_weapon"].value[0].value["tuning"].value["base_tuning"].value
        self.offsets["recoil"] = [  # recoil_yaw and recoil_pitch
            base_tuning["recoil"].value["recoil_yaw"].data_offset,
            base_tuning["recoil"].value["recoil_yaw"].data_offset + 4,
            base_tuning["recoil"].value["recoil_pitch"].data_offset,
            base_tuning["recoil"].value["recoil_pitch"].data_offset + 4
        ]
        bullet_tuning = adf_values["bullet_weapon"].value[0].value["tuning"].value["bullet_base_tuning"].value
        self.offsets["gravity_on"] = bullet_tuning["gravity_on"].data_offset
        self.offsets["gravity_strength"] = bullet_tuning["gravity_strength"].data_offset
        self.offsets["wobble_modifier"] = adf_values["weapon_wobble_modifier"].data_offset

    def _get_scopes_data(self, extracted_adf: Adf) -> None:
        self.scopes = []
        adf_values = extracted_adf.table_instance_full_values[0].value
        if "ScopeOffsetSettings" in adf_values:
            scope_settings = adf_values["ScopeOffsetSettings"].value
            for scope_i, scope_data in enumerate(scope_settings):
                try:
                    scope = WeaponScopeSettings(scope_i, scope_data)
                    self.scopes.append(scope)
                except ValueError as e:
                    continue
        self.scopes.sort(key=lambda x: x.name)


def load_weapon_type(type_key: str) -> list[WeaponTuning]:
    base_path = mods.APP_DIR_PATH / "org/editor/entities/hp_weapons"
    name_pattern = re.compile(r'^(?:equipment_)?weapon_([\w\d\-]+).wtunec$')
    root = base_path / f"weapon_{type_key}_01/tuning"
    weapons = []
    for file in root.glob("*.wtunec"):
        name_match = name_pattern.match(file.name)
        if name_match and not file.name.startswith("weapon_sway"):
            relative_file = mods.get_relative_path(file)
            try:
                weapon = WeaponTuning(relative_file)
                weapons.append(weapon)
            except ValueError as e:
                continue
    weapons.sort(key=lambda weapon: weapon.display_name)
    return weapons


def load_weapons() -> dict[str, list[WeaponTuning]]:
    bows = load_weapon_type("bows")
    handguns = load_weapon_type("handguns")
    rifles = load_weapon_type("rifles")
    shotguns = load_weapon_type("shotguns")

    return {
        "bow": bows,
        "handgun": handguns,
        "rifle": rifles,
        "shotgun": shotguns
    }


def load_weapon_ui_data() -> dict[str, dict]:
    weapons_sheet, _i = mods2.get_sheet(mods.EQUIPMENT_UI_DATA, "weapons")
    weapon_ui_data = {}
    for i in range(2, weapons_sheet["Rows"].value + 1):  # skip header row
        name_cell = mods2.XlsxCell(mods.EQUIPMENT_UI_FILE,
                                   mods.EQUIPMENT_UI_DATA,
                                   {"sheet": "weapons", "coordinates": f"A{i}"})
        # accuracy_cell = mods2.XlsxCell(mods.EQUIPMENT_UI_FILE,
        #                              mods.EQUIPMENT_UI_DATA,
        #                              {"sheet": "weapons", "coordinates": f"B{i}"})
        recoil_cell = mods2.XlsxCell(mods.EQUIPMENT_UI_FILE,
                                     mods.EQUIPMENT_UI_DATA,
                                     {"sheet": "weapons", "coordinates": f"C{i}"})
        if name_cell.data_array_name == "StringData":  # file contains "blank" rows with True values as placeholders
            name = name_cell.value.decode("utf-8")
            if (mapped_equipment := mods.map_equipment(name, "weapon")):
                weapon_name = mapped_equipment["name"]
            else:
                weapon_name = name
            if weapon_name in weapon_ui_data:
                weapon_ui_data[weapon_name]["rows"].append(i)
            else:
                weapon_ui_data[weapon_name] = {
                    "rows": [i],
                    # "accuracy": accuracy_cell.value,
                    "recoil": recoil_cell.value
                }
    return weapon_ui_data


def load_weapon_magazine_data() -> dict[str, WeaponMagazine]:
    equipment = mods.open_rtpc(mods.APP_DIR_PATH / "org" / mods.EQUIPMENT_DATA_FILE)
    weapons_table = equipment.child_table[7].child_table
    weapon_magazine_data = {}
    for weapon_data in weapons_table:
        magazine = WeaponMagazine(weapon_data)
        if magazine.display_name in weapon_magazine_data:  # if it's a variant then copy over the offsets and internal_names
            weapon_magazine_data[magazine.display_name].offsets.extend(magazine.offsets)
            weapon_magazine_data[magazine.display_name].internal_names.extend(magazine.internal_names)
        else:
            weapon_magazine_data[magazine.display_name] = magazine
    return weapon_magazine_data


def build_tab(weapon_type: str) -> sg.Tab:
    weapon_list = ALL_WEAPONS[weapon_type]
    return sg.Tab(weapon_type.capitalize(), [
        [sg.Combo([weapon.display_name for weapon in weapon_list], metadata=weapon_list, p=((10,0),(20,10)), k=f"modify_weapon_list_{weapon_type}", enable_events=True, expand_x=True)],
    ], key=f"modify_weapon_tab_{weapon_type}")


def get_option_elements() -> sg.Column:
    layout = [[
        sg.TabGroup([[
            build_tab(key) for key in ALL_WEAPONS
        ]], k="modify_weapon_tab_group", enable_events=True),
        sg.Column([
            [sg.Checkbox("Mag Size", font="_ 12", default=True, k="modify_weapon_category_magazine", enable_events=True, p=((5,0),(0,0))),
             sg.Checkbox("Recoil+Wobble", font="_ 12", default=True, k="modify_weapon_category_recoil_wobble", enable_events=True, p=((5,0),(0,0))),
             sg.Checkbox("Bullet Drop", font="_ 12", default=True, k="modify_weapon_category_bullet_drop", enable_events=True, p=((5,0),(0,0)))],
            [sg.Button("Add Category Modification", k="add_mod_group_weapon", button_color=f"{sg.theme_element_text_color()} on brown", p=((65,0),(5,0)))],
        ], p=((25, 0), (0, 0))),
        sg.Column([
            [sg.pin(sg.T(" No UI data for weapon ", text_color="firebrick1", background_color="black", k="modify_weapon_ui_error", visible=False, p=((0,0),(0,0))))],
            [sg.pin(sg.T(" No magazine data for weapon ", text_color="firebrick1", background_color="black", k="modify_weapon_magazine_error", visible=False, p=((0,0),(5,0))))],
        ], p=((25,0),(0,0))),
    ],
        [sg.Column([
            [sg.TabGroup([[
                sg.Tab("Ammo + Handling", [
                    [sg.Column([
                        [sg.Checkbox("Auto-select default magazine size", font="_ 12", default=True, k="modify_weapon_select_default_magazine_size", enable_events=True, p=((10,0),(10,0)))],
                        [sg.T("Magazine Size:", p=((10,0),(0,0))),
                         sg.Slider((1, 99), 1, 1, orientation = "h", k="modify_weapon_magazine_size", p=((10,0),(0,5))),
                         sg.pin(sg.T("Weapon will still reload after each shot. Magazine change is only cosmetic.", k="modify_weapon_magazine_note", font="_ 12 italic", text_color="orange", p=((10,10),(5,0)), visible=False))],
                        [sg.T("Decrease Recoil Percentage:", p=((10,0),(0,0))),
                         sg.Slider((0,100), 0, 1, orientation="h", p=((10,0),(0,5)), k="modify_weapon_recoil_percent")],
                        [sg.T("Decrease Wobble Percentage:", p=((10,0),(0,0))),
                         sg.Slider((0,100), 0, 1, orientation="h", p=((10,0),(0,5)), k="modify_weapon_wobble_percent")],
                        [sg.Checkbox("Disable Bullet Drop", p=((10,0),(10,10)), k="modify_weapon_disable_bullet_drop", default=False, enable_events=True),
                         sg.T('"Perfect" zeroing at all ranges. NOT HITSCAN! Bullets still have travel time - you need to lead a moving target.', font="_ 12", text_color="orange", p=((10,0),(10,10)))],
                    ])],
                ], k="modify_weapon_settings_tab_ammo_handling", ),
                sg.Tab("Zeroing", [
                    [sg.Column([
                        [sg.T("Zeroing Settings:", p=((10,0),(0,0))),
                         sg.T('(distance, angle)', font="_ 12", p=((10,0),(0,0))),
                         sg.T('Level 1 is default. Levels 2 and 3 require the "Zeroing" perk', font="_ 12", text_color="orange", p=((10,0),(0,0)))],
                        [sg.T(' WARNING ', font="_ 12", text_color="firebrick1", background_color="black", p=((10,5),(5,0))),
                         sg.T('Zeroing settings do not auto-adjust for bullet drop - test in the firing range! Use the "Modify Ammo" mod to increase "kinetic energy" for better long-range accuracy.', font="_ 12", p=((0,0),(5,0)))],
                        [sg.T("Level 1: ", p=((25,0),(5,5))),
                         sg.Input("0", size=4, p=((10,0),(0,0)), k="modify_weapon_level_1_distance"),
                         sg.Input("0", p=((10,0),(0,0)), k="modify_weapon_level_1_angle")],
                        [sg.T("Level 2: ", p=((25,0),(5,5))),
                         sg.Input("0", size=4, p=((10,0),(0,0)), k="modify_weapon_level_2_distance"),
                         sg.Input("0", p=((10,10),(0,0)), k="modify_weapon_level_2_angle")],
                        [sg.T("Level 3: ", p=((25,0),(5,5))),
                         sg.Input("0", size=4, p=((10,0),(0,0)), k="modify_weapon_level_3_distance"),
                         sg.Input("0", p=((10,10),(0,0)), k="modify_weapon_level_3_angle")],
                    ])],
                ], k="modify_weapon_settings_tab_zeroing"),
                sg.Tab("Scope Offsets", [
                    [sg.T("Scope Settings:", p=((10,0),(15,0))),
                     sg.T('Modify horizontal and vertical alignment of sights.', font="_ 12", text_color="orange", p=((10,0),(15,0)))],
                    [sg.T(' WARNING ', font="_ 12", text_color="firebrick1", background_color="black", p=((10,5),(5,0))),
                     sg.T("Scope offsets are saved per scope and applied separately from other mods. Changes here won't affect other sections.", font="_ 12", p=((0,0),(5,0)))],
                    [sg.Column([
                        [sg.T("Scope: ", p=((10,0),(5,5))),
                         sg.Combo([], k="modify_weapon_scope_list", p=((10,0),(0,0)), enable_events=True, expand_x=True)],
                        [sg.T("Horizontal Offset: ", p=((10,0),(5,5))),
                         sg.Input("0", k="modify_weapon_scope_horizontal_offset", p=((10,0),(0,0)), expand_x=True)],
                        [sg.T("Vertical Offset: ", p=((10,0),(5,5))),
                         sg.Input("0", k="modify_weapon_scope_vertical_offset", p=((10,0),(0,0)), expand_x=True)],
                    ], p=((20,0),(0,0)))],
                ], k="modify_weapon_settings_tab_scope_offsets"),
            ]], k="modify_weapon_settings_tab_group", enable_events=True)]
        ])],
    ]
    return sg.Column(layout)


def get_selected_category(window: sg.Window) -> str:
    active_tab = str(window["modify_weapon_tab_group"].find_currently_active_tab_key()).lower()
    return active_tab.removeprefix("modify_weapon_tab_")


def get_selected_settings_tab(window: sg.Window) -> str:
    active_tab = str(window["modify_weapon_settings_tab_group"].find_currently_active_tab_key()).lower()
    return active_tab.removeprefix("modify_weapon_settings_tab_")


def get_selected_weapon(window: sg.Window, values: dict) -> WeaponTuning:
    item_type = get_selected_category(window)
    item_list = f"modify_weapon_list_{item_type}"
    item_name = values.get(item_list)
    if item_name:
        try:
            item_index = window[item_list].Values.index(item_name)
            return window[item_list].metadata[item_index]
        except ValueError as _e:  # user typed/edited data in box and we cannot match
            pass
    return None


def get_selected_scope(window: sg.Window, values: dict) -> WeaponScopeSettings:
    selected_scope = values.get("modify_weapon_scope_list")
    if selected_scope:
        try:
            scope_index = window["modify_weapon_scope_list"].Values.index(selected_scope)
            return window["modify_weapon_scope_list"].metadata[scope_index]
        except ValueError as _e:  # user typed/edited data in box and we cannot match
            pass
    return None


def update_magazine_settings(selected_weapon: WeaponTuning, window: sg.Window, values: dict) -> None:
    if selected_weapon and selected_weapon.magazine:
        window["modify_weapon_magazine_note"].update(visible=(selected_weapon.magazine.size == 1))
        if values["modify_weapon_select_default_magazine_size"]:
            window["modify_weapon_magazine_size"].update(selected_weapon.magazine.size)
            return
    window["modify_weapon_magazine_note"].update(visible=False)


def update_zeroing(selected_weapon: WeaponTuning, window: sg.Window) -> None:
    weapon_zeroing = selected_weapon.zeroing if selected_weapon else None
    disabled = not bool(weapon_zeroing)

    for i in [1, 2, 3]:
        window[f"modify_weapon_level_{i}_distance"].update(
            int(getattr(weapon_zeroing, f"level_{i}_distance", 0)), disabled=disabled
        )
        window[f"modify_weapon_level_{i}_angle"].update(
            getattr(weapon_zeroing, f"level_{i}_angle", "0"), disabled=disabled
        )


def update_scope_settings(selected_weapon: WeaponTuning, event: str, window: sg.Window, values: dict) -> None:
    scope_dropdown = window["modify_weapon_scope_list"]
    if selected_weapon and (weapon_scopes := selected_weapon.scopes):
        h_offset = values["modify_weapon_scope_horizontal_offset"]
        v_offset = values["modify_weapon_scope_vertical_offset"]
        if event.startswith("modify_weapon_list_") or event.startswith("modify_weapon_tab_"):  # new weapon = reset scope data
            scope_dropdown.update(values=[s.display_name for s in weapon_scopes], disabled=False)
            scope_dropdown.metadata = weapon_scopes
            h_offset = v_offset = ""  # blank out offsets
        if (selected_scope := get_selected_scope(window, values)):  # scope selected = load scope settings
            h_offset = f"{selected_scope.horizontal_offset:.6f}"
            v_offset = f"{selected_scope.vertical_offset:.6f}"
        window["modify_weapon_scope_horizontal_offset"].update(h_offset, disabled=False)
        window["modify_weapon_scope_vertical_offset"].update(v_offset, disabled=False)
        return
    # no weapon selected or no scope data = disable scope settings
    scope_dropdown.update(values=[], disabled=True)
    scope_dropdown.metadata = []
    window["modify_weapon_scope_horizontal_offset"].update("0", disabled=True)
    window["modify_weapon_scope_vertical_offset"].update("0", disabled=True)


def toggle_bullet_drop(selected_weapon: WeaponTuning, window: sg.Window, values: dict) -> None:
    disabled = selected_weapon and values["modify_weapon_disable_bullet_drop"]
    for i in [1,2,3]:
        window[f"modify_weapon_level_{i}_distance"].update(disabled=disabled)
        window[f"modify_weapon_level_{i}_angle"].update(disabled=disabled)


def toggle_error_messages(selected_weapon: WeaponTuning, window: sg.Window) -> None:
    window["modify_weapon_ui_error"].update(visible=bool(selected_weapon and not selected_weapon.ui_data))
    window["modify_weapon_magazine_error"].update(visible=bool(selected_weapon and not selected_weapon.magazine))


def handle_event(event: str, window: sg.Window, values: dict) -> None:
    if event.startswith("modify_weapon"):
        group_mod_disabled_tabs = ["zeroing", "scope_offsets"]
        window["add_mod_group_weapon"].update(disabled=(get_selected_settings_tab(window) in group_mod_disabled_tabs))
        selected_weapon = get_selected_weapon(window, values)
        update_magazine_settings(selected_weapon, window, values)
        update_zeroing(selected_weapon, window)
        update_scope_settings(selected_weapon, event, window, values)
        toggle_error_messages(selected_weapon, window)
        toggle_bullet_drop(selected_weapon, window, values)


def add_mod(window: sg.Window, values: dict) -> dict:
    selected_weapon = get_selected_weapon(window, values)
    if not selected_weapon:
        return {
            "invalid": "Please select a weapon first"
        }

    if get_selected_settings_tab(window) == "scope_offsets":
        selected_scope = get_selected_scope(window, values)
        if not selected_scope:
            return {
                "invalid": "Please select a scope first"
            }
        if selected_scope:  # scope changes are applied separately on a per-scope basis
            return {
                "key": f"weapon_scope_{selected_weapon.name}_{selected_scope.name}",
                "invalid": None,
                "options": {
                    "name": selected_scope.name,
                    "display_name": selected_scope.display_name,
                    "weapon_name": selected_weapon.name,
                    "weapon_display_name": selected_weapon.display_name,
                    "file": selected_weapon.file,
                    "horizontal_offset": float(values["modify_weapon_scope_horizontal_offset"]),
                    "vertical_offset": float(values["modify_weapon_scope_vertical_offset"]),
                }
            }

    # base modify_weapon options should always include "Ammo + Handling" tab plus some zeroing setting
    mod_options = {
        "name": selected_weapon.name,
        "display_name": selected_weapon.display_name,
        "file": selected_weapon.file,
        "magazine_size": int(values["modify_weapon_magazine_size"]),
        "recoil_percent": int(values["modify_weapon_recoil_percent"]),
        "wobble_percent": int(values["modify_weapon_wobble_percent"]),
    }
    if values["modify_weapon_disable_bullet_drop"]:
        mod_options["disable_bullet_drop"] = True
    else:
        mod_options["one_distance"] = float(values["modify_weapon_level_1_distance"])
        mod_options["one_angle"] = float(values["modify_weapon_level_1_angle"])
        mod_options["two_distance"] = float(values["modify_weapon_level_2_distance"])
        mod_options["two_angle"] = float(values["modify_weapon_level_2_angle"])
        mod_options["three_distance"] = float(values["modify_weapon_level_3_distance"])
        mod_options["three_angle"] =  float(values["modify_weapon_level_3_angle"])
    return {
        "key": f"modify_weapon_{selected_weapon.name}",
        "invalid": None,
        "options": mod_options
    }


def add_mod_group(window: sg.Window, values: dict) -> dict:
    active_tab = window["modify_weapon_tab_group"].find_currently_active_tab_key().lower()
    weapon_type = active_tab.removeprefix("modify_weapon_tab_")
    if not weapon_type:
        return {
            "invalid": "Please select a weapon type first"
        }

    mod_options = {
        "type": weapon_type,
    }
    if values["modify_weapon_category_magazine"]:
        mod_options["magazine_size"] = int(values["modify_weapon_magazine_size"])
    if values["modify_weapon_category_recoil_wobble"]:
        mod_options["recoil_percent"] = int(values["modify_weapon_recoil_percent"])
        mod_options["wobble_percent"] = int(values["modify_weapon_wobble_percent"])
    if values["modify_weapon_category_bullet_drop"] and values["modify_weapon_disable_bullet_drop"]:
        mod_options["disable_bullet_drop"] = True
    return {
        "key": f"modify_weapon_type_{weapon_type}",
        "invalid": None,
        "options": mod_options
    }


def format_options(options: dict) -> str:
    # need to match old keys if reading from an old save file
    if "horizontal_offset" in options:  # scope offsets
        scope_name = options.get("display_name", options.get("name"))
        weapon_name = options.get("weapon_display_name", options.get("weapon_name"))
        return f'Modify Weapon Scope Offsets: {weapon_name} - {scope_name} (H: {options["horizontal_offset"]}, V: {options["vertical_offset"]})'
    # ammo, handling, zeroing
    magazine_size_text = f'{options.get("magazine_size", options.get("weapon_mag_size", "default"))} magazine'
    recoil_percent = options.get("recoil_percent")
    recoil_text = f'-{recoil_percent}% recoil' if recoil_percent else ""
    wobble_percent = options.get("wobble_percent")
    wobble_text = f'-{wobble_percent}% wobble' if wobble_percent else ""
    bullet_drop_text = "Disable Bullet Drop" if options.get("disable_bullet_drop", False) else ""

    stats = [magazine_size_text, recoil_text, wobble_text, bullet_drop_text]
    stats_text = ", ".join([s for s in stats if s and s.strip()])
    details_text = f'({stats_text if stats_text else "No Stat Changes"})'
    if "type" in options:  # category
        formatted_name = f"Modify Weapon Type: {options['type'].title()}"
    else:  # single weapon
        weapon_name = options.get("display_name", options.get("name", options.get("weapon_display_name", options.get("weapon_name"))))
        formatted_name = f"Modify Weapon: {weapon_name}"
    return f"{formatted_name} {details_text}"


def handle_key(mod_key: str) -> bool:
    return mod_key.startswith(("modify_weapon", "weapon_recoil", "weapon_scope", "weapon_magazine"))


def get_files(options: dict) -> list[str]:
    if "file" in options:
        return [options["file"], mods.EQUIPMENT_DATA_FILE, mods.EQUIPMENT_UI_FILE]
    else:
        selected_weapon_files = [weapon.file for weapon in ALL_WEAPONS[options["type"]]]
        return [*selected_weapon_files, mods.EQUIPMENT_DATA_FILE, mods.EQUIPMENT_UI_FILE]


def load_archive_files(base_path: Path) -> dict[str, list[str]]:
    archives = {}
    for file in base_path.rglob("*.ee"):
        archive_files = list(mods.get_sarc_file_info(file).keys())
        archives[str(file)] = archive_files
    return archives


def find_archive_files(archive_files: dict, file: str) -> str:
    found_archives = []
    for archive, files in archive_files.items():
        if file in files:
            found_archives.append(mods.get_relative_path(archive))
    return found_archives


def merge_files(files: list[str], options: dict) -> None:
    base_path = mods.APP_DIR_PATH / "org/editor/entities/hp_weapons"
    archives = load_archive_files(base_path)
    for file in files:
        bundle_files = find_archive_files(archives, file)
        for bundle_file in bundle_files:
            bundle_lookup = mods.get_sarc_file_info(mods.APP_DIR_PATH / "org" / bundle_file)
            mods.merge_into_archive(file, bundle_file, bundle_lookup)


def process(options: dict) -> None:
    file = options.get("file")
    if file:  # single weapon
        selected_weapons = [WeaponTuning(file)]
    else:  # category
        selected_weapons = ALL_WEAPONS[options["type"]]

    for weapon in selected_weapons:
        updates = []
        # scope offsets in `.wtunec`
        if "horizontal_offset" in options:
            selected_scope = next((s for s in weapon.scopes if options["name"] == s.name), None)
            updates.append({"offset": selected_scope.horizontal_data_offset, "value": options["horizontal_offset"]})
            updates.append({"offset": selected_scope.vertical_data_offset, "value": options["vertical_offset"]})
            mods.apply_updates_to_file(weapon.file, updates)
            continue

        # recoil, wobble, zeroing in `.wtunec`
        recoil_multiplier = 1 - options.get("recoil_percent", 0) / 100
        for offset in weapon.offsets["recoil"]:
            updates.append({"offset": offset, "value": recoil_multiplier, "transform": "multiply"})
        wobble_multiplier = 1 - options.get("wobble_percent", 0) / 100
        updates.append({"offset": weapon.offsets["wobble_modifier"], "value": wobble_multiplier, "transform": "multiply"})

        if options.get("disable_bullet_drop"):  # set gravity_strngeh and all angles to 0
            updates.append({"offset": weapon.offsets["gravity_on"], "value": 0, "format": "uint08"})
            updates.append({"offset": weapon.offsets["gravity_strength"], "value": float(0)})
            updates.append({"offset": weapon.zeroing.level_1_angle_offset, "value": float(0)})
            updates.append({"offset": weapon.zeroing.level_2_angle_offset, "value": float(0)})
            updates.append({"offset": weapon.zeroing.level_3_angle_offset, "value": float(0)})
            # some weapons (mostly bows, some shotguns) have per-ammo zeroing
            for override in weapon.zeroing.bullet_overrides.values():
                for i in [1,2,3]:
                    updates.append({"offset": override[f"level_{i}_angle_offset"], "value": float(0)})
        elif "one_distance" in options:  # regular zeroing
            updates.append({"offset": weapon.zeroing.level_1_distance_offset, "value": float(options["one_distance"])})
            updates.append({"offset": weapon.zeroing.level_1_angle_offset, "value": float(options["one_angle"])})
            updates.append({"offset": weapon.zeroing.level_2_distance_offset, "value": float(options["two_distance"])})
            updates.append({"offset": weapon.zeroing.level_2_angle_offset, "value": float(options["two_angle"])})
            updates.append({"offset": weapon.zeroing.level_3_distance_offset, "value": float(options["three_distance"])})
            updates.append({"offset": weapon.zeroing.level_3_angle_offset, "value": float(options["three_angle"])})
        mods.apply_updates_to_file(weapon.file, updates)

        # magazine size in equipment_data.bin
        if "magazine_size" in options and weapon.magazine:  # skip "_PLACEHOLDER" ammo without mag data
            mods.update_file_at_offsets(Path(mods.EQUIPMENT_DATA_FILE), weapon.magazine.offsets, options["magazine_size"])

        # ui data in equipment_stats_ui.bin
        if weapon.ui_data:
            ui_recoil = max(min(int(weapon.ui_data["recoil"] * recoil_multiplier), 100), 0)
            ui_updates = [{"coordinates": f"C{row}", "value": ui_recoil} for row in weapon.ui_data["rows"]]
            for update in ui_updates:
                update["sheet"] = "weapons"
                update["allow_new_data"] = True
            mods2.apply_coordinate_updates_to_file(mods.EQUIPMENT_UI_FILE, ui_updates)


def handle_update(mod_key: str, mod_options: dict, version: str) -> tuple[str, dict]:
    if mod_key.startswith("weapon_magazine"):  # convert "Increase Weapon Magazine" saves
        return update_weapon_magazine_options(mod_key, mod_options)
    if mod_key.startswith("weapon_scope"):  # update "Modify Weapon Scope" saves
        return update_scope_options(mod_key, mod_options, version)
    if "file" in mod_options:  # update "Modify Weapon" saves
        return update_weapon_options(mod_key, mod_options, version)
    return mod_key, mod_options


def _update_rapid_hunt_name_swap(mod_key: str, mod_options: dict) -> tuple[str, dict]:
    """
    2.2.5
    - Fix name swap between Hansson .30-06 and Quist Reaper 7.62x39 from Rapid Hunt Rifle Pack
    - This cannot be done for scope offset changes. Return an error for scope changes
    """
    if mod_key.startswith("weapon_scope_") and mod_options.get("weapon_display_name") in ["Hansson .30-06", "Quist Reaper 7.62x39"]:
        raise ValueError(f"Cannot load scope {mod_options["display_name"]} for weapon {mod_options["weapon_display_name"]}. Please recreate this mod.")
    if mod_options.get("display_name") == "Hansson .30-06":
        mod_key = "modify_weapon_sa_rifle_30_06"
        mod_options["name"] = "sa_rifle_30_06"
        mod_options["file"] = "editor/entities/hp_weapons/weapon_rifles_01/tuning/weapon_sa_rifle_30_06.wtunec"
    if mod_options.get("display_name") == "Quist Reaper 7.62x39":
        mod_key = "modify_weapon_sa_rifle_7_62"
        mod_options["name"] = "sa_rifle_7_62"
        mod_options["file"] = "editor/entities/hp_weapons/weapon_rifles_01/tuning/weapon_sa_rifle_7_62.wtunec"
    # Must remove specific zeroing settings
    keys_to_remove = ["one_distance", "one_angle", "two_distance", "two_angle", "three_distance", "three_angle"]
    cleaned_mod_options = {k: v for k, v in mod_options.items() if k not in keys_to_remove}
    return mod_key, cleaned_mod_options


def update_weapon_magazine_options(mod_key: str, mod_options: dict) -> tuple[str, dict]:
    """
    Try to match a WeaponTuning object to old "Increase Weapon Magazine" data.

    2.2.4: Separated Razorback and Bearclaw compound bows. This will cause errors
    2.2.2: Remove variant suffix (_01, _02, etc) from mod_key
    2.2.0: Use formatted name from 'name_map.yaml' as "display_name"
    2.1.3: Use formatted name instead of parsed internal name
    """
    def _match_increase_magazine_weapon(mod_options: dict) -> WeaponTuning:
        # Attempt to match the saved weapon name to a WeaponTuning object
        all_weapons_list = [weapon for weapon_list in ALL_WEAPONS.values() for weapon in weapon_list]
        weapon_name = mod_options.get("weapon_display_name", mod_options["weapon_name"])
        # Fix a few naming errors
        regent_magnum_names = ["7mm Empress/Regent Magnum", "7mm Regent/Empress Magnum"]
        weapon_name = "7mm Regent Magnum" if weapon_name in regent_magnum_names else weapon_name
        weapon_name = ".44 Panther Magnum" if weapon_name == ".44 Magnum" else weapon_name
        weapon_name = "Virant .22LR" if weapon_name == "Viriant .22LR" else weapon_name
        # 2.2.4 - Razorback and Bearclaw separated. Raise an error - user will have to recreate their mod
        if (weapon_name == "Bearclaw/Razorback Lite CB-60"):
            raise ValueError(f"Razorback and Bearclaw cannot be modified together")
        # Check if we have an easy match
        if (selected_weapon := next((w for w in all_weapons_list if w.weapon_display_name == weapon_name), None)):
            return selected_weapon
        # Try to map the saved weapon_name with name_map.yaml
        if (mapped_equipment := mods.map_equipment(weapon_name, "weapon")):
            if (selected_weapon := next((w for w in all_weapons_list if w.weapon_display_name == mapped_equipment["name"]), None)):
                return selected_weapon
        # Pre-2.1.3 used an "internal" weapon name found in `equipment_data.bin` and did not combine variants
        if (selected_weapon := next((w for w in all_weapons_list if w.magazine and weapon_name in w.magazine.internal_names), None)):
            return selected_weapon
        return None

    if (selected_weapon := _match_increase_magazine_weapon(mod_options)):
        updated_mod_key = f"modify_weapon_{selected_weapon.name}"
        updated_mod_options = {
            "name": selected_weapon.name,
            "display_name": selected_weapon.display_name,
            "file": selected_weapon.file,
            "magazine_size": mod_options["weapon_mag_size"],
        }
        return updated_mod_key, updated_mod_options
    raise ValueError(f"Unable to match weapon {mod_options.get("weapon_display_name", mod_options["weapon_name"])}")


def update_scope_options(mod_key: str, mod_options: dict, version: str) -> tuple[str, dict]:
    """
    2.2.5
    - Fix name swap between Hansson .30-06 and Quist Reaper 7.62x39 from Rapid Hunt Rifle Pack
    2.2.4
    - Remove hard-coded scope offsets from JSON save file
    - Fix names for very old save files
    """
    if version == "2.2.4" or version.startswith("2.2.4.dev"):
        mod_key, mod_options = _update_rapid_hunt_name_swap(mod_key, mod_options)
    def _match_saved_scope(mod_options: dict, scopes: list[WeaponScopeSettings]):
        # try to match old scope data to fix names and remove offsets from save files
        # 1: direct match on internal name
        if (selected_scope := next((s for s in scopes if mod_options["name"] == s.name), None)):
            return selected_scope
        # 2: try to match on display_name
        mapped_name = _map_scope_name(mod_options)
        if (selected_scope := next((s for s in scopes if mapped_name == s.display_name), None)):
            return selected_scope
        # try to match scope based on offsets stored in old save files
        if (selected_scope := next((s for s in scopes if (
            mod_options.get("horizontal_pos") == s.horizontal_data_offset
            and mod_options.get("vertical_pos") == s.vertical_data_offset
            )), None)):
            return selected_scope
        raise ValueError(f"Unable to match scope {mod_options["name"]} for weapon {mod_options["weapon_name"]}")

    def _map_scope_name(mod_options: dict) -> WeaponScopeSettings:
        # 2.1: direct match to name_map.yaml
        # regex away formatted indicies (eg. "reflex_01 [3]")
        cleaned_name = re.sub(r'\s*\[.*?\]$', '', mod_options["name"])
        if (mapped_scope := mods.map_equipment(cleaned_name, "sight")):
            return mapped_scope["name"]
        # 2.2: manual match to old names that were hard-coded
        # old versions of Mod Builder only saved a formatted scope name and not the internal name from game files
        # unfortutnately those names were hard-coded into this mod and some were incorrect
        old_scope_names = {
            "Red Dot": "Red Raptor Reflex",
            "Iron Sights": "Illuminated Iron Sights",
            "GenZero Night Vision 1-4x24": "GenZero 1-4x24 Night Vision",
            "Galileo 4-8x32": "Galileo 4-8x32 Muzzleloader",
            "Bow 1-pin": "Brightsight Illuminated Single-Pin",
            "Bow 3-pin": "Swift-Mark 3-pin",
            "Bow 5-pin": "Swift-Mark 5-pin",
            "Rangefinder": "Brightsignt Rangefinder",
            "Hawken 1-4x24": "Hawken 1-5x30",
        }
        scope_display_name = mod_options.get("display_name", mod_options["name"])
        return old_scope_names.get(scope_display_name, scope_display_name)

    weapon = WeaponTuning(mod_options["file"])
    selected_scope = _match_saved_scope(mod_options, weapon.scopes)
    updated_mod_key = f"weapon_scope_{weapon.name}_{selected_scope.name}"
    updated_mod_options = {
        "name": selected_scope.name,
        "display_name": selected_scope.display_name,
        "weapon_name": weapon.name,
        "weapon_display_name": weapon.display_name,
        "file": weapon.file,
        "horizontal_offset": mod_options["horizontal_offset"],
        "vertical_offset": mod_options["vertical_offset"],
    }
    return updated_mod_key, updated_mod_options


def update_weapon_options(mod_key: str, mod_options: dict, version: str) -> tuple[str, dict]:
    """
    2.2.5
    - Fix name swap between Hansson .30-06 and Quist Reaper 7.62x39 from Rapid Hunt Rifle Pack
    """
    if version == "2.2.4" or version.startswith("2.2.4.dev"):
        mod_key, mod_options = _update_rapid_hunt_name_swap(mod_key, mod_options)
    # no scope selected - handle all other weapon updates
    weapon = WeaponTuning(mod_options["file"])
    updated_mod_key = f"modify_weapon_{weapon.name}"
    updated_mod_options = {
        "name": weapon.name,
        "display_name": weapon.display_name,
        "file": weapon.file,
    }
    keys_to_copy = ["recoil_percent", "wobble_percent",
                    "magazine_size", "disable_bullet_drop",
                    "one_distance", "one_angle",
                    "two_distance", "two_angle",
                    "three_distance", "three_angle"]
    for key in keys_to_copy:
        if key in mod_options:
            updated_mod_options[key] = mod_options[key]

    return updated_mod_key, updated_mod_options


WEAPON_UI_DATA = load_weapon_ui_data()
WEAPON_MAGAZINE_DATA = load_weapon_magazine_data()
ALL_WEAPONS = load_weapons()
