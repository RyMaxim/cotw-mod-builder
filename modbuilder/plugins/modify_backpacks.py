DEBUG = False
NAME = "Modify Backpacks"
DESCRIPTION = "Adjust the carry weight, noise, and visibility stats of backpacks. Cost can be edited with Modify Store."
FILE = "settings/hp_settings/equipment_stats_ui.bin"
BACKPACK_STATS = {
    "large": {"weight": 9, "noise": 9, "scent": 0, "vision": 7},
    "medium": {"weight": 6, "noise": 6, "scent": 0, "vision": 4},
    "small": {"weight": 3, "noise": 3, "scent": 0, "vision": 1},
}

OPTIONS = [
    {
        "name": "Large Backpack Carry Weight",
        "style": "slider",
        "min": 0,
        "max": 1000,
        "initial": BACKPACK_STATS["large"]["weight"],
        "increment": 1,
        "note": "Summit Explorer 6000 Pack",
    },
    {
        "name": "Large Backpack Noise",
        "style": "slider",
        "min": 0,
        "max": 100,
        "initial": BACKPACK_STATS["large"]["noise"],
        "increment": 1,
    },
    {
        "name": "Large Backpack Visibility",
        "style": "slider",
        "min": 0,
        "max": 100,
        "initial": BACKPACK_STATS["large"]["vision"],
        "increment": 1,
    },
    {
        "name": "Medium Backpack Carry Weight",
        "style": "slider",
        "min": 0,
        "max": 1000,
        "initial": BACKPACK_STATS["medium"]["weight"],
        "increment": 1,
        "note": "ExoAdventurere 32 Light Daypack",
    },
    {
        "name": "Medium Backpack Noise",
        "style": "slider",
        "min": 0,
        "max": 100,
        "initial": BACKPACK_STATS["medium"]["noise"],
        "increment": 1,
    },
    {
        "name": "Medium Backpack Visibility",
        "style": "slider",
        "min": 0,
        "max": 100,
        "initial": BACKPACK_STATS["medium"]["vision"],
        "increment": 1,
    },
    {
        "name": "Small Backpack Carry Weight",
        "style": "slider",
        "min": 0,
        "max": 1000,
        "initial": BACKPACK_STATS["small"]["weight"],
        "increment": 1,
        "note": "TrailScout Mini Daypack",
    },
    {
        "name": "Small Backpack Noise",
        "style": "slider",
        "min": 0,
        "max": 100,
        "initial": BACKPACK_STATS["small"]["noise"],
        "increment": 1,
    },
    {
        "name": "Small Backpack Visibility",
        "style": "slider",
        "min": 0,
        "max": 100,
        "initial": BACKPACK_STATS["small"]["vision"],
        "increment": 1,
    },
]


def format_options(options: dict) -> str:
    lg_size = int(options["large_backpack_carry_weight"])
    lg_noise = int(options["large_backpack_noise"])
    lg_visiblity = int(options["large_backpack_visibility"])

    med_size = int(options["medium_backpack_carry_weight"])
    med_noise = int(options["medium_backpack_noise"])
    med_visiblity = int(options["medium_backpack_visibility"])

    sm_size = int(options["small_backpack_carry_weight"])
    sm_noise = int(options["small_backpack_noise"])
    sm_visiblity = int(options["small_backpack_visibility"])

    formatted = (
        "Modify Backpacks ("
        f"Large: {lg_size}kg, {lg_noise}, {lg_visiblity} | "
        f"Meddium: {med_size}kg, {med_noise}, {med_visiblity} | "
        f"Small: {sm_size}kg, {sm_noise}, {sm_visiblity}"
        ")"
    )
    return formatted


def update_values_at_coordinates(options: dict) -> list[dict]:
    lg_size = int(options["large_backpack_carry_weight"])
    lg_noise = int(options["large_backpack_noise"])
    lg_visiblity = int(options["large_backpack_visibility"])

    lg_updates = [
        {
            "coordinates": "B4",
            "value": lg_size,
        },
        {
            "coordinates": "B5",
            "value": lg_size,
        },
        {
            "coordinates": "B6",
            "value": lg_size,
        },
        {
            "coordinates": "C4",
            "value": lg_noise,
        },
        {
            "coordinates": "C5",
            "value": lg_noise,
        },
        {
            "coordinates": "C6",
            "value": lg_noise,
        },
        {
            "coordinates": "E4",
            "value": lg_visiblity,
        },
        {
            "coordinates": "E5",
            "value": lg_visiblity,
        },
        {
            "coordinates": "E6",
            "value": lg_visiblity,
        },
    ]

    med_size = int(options["medium_backpack_carry_weight"])
    med_noise = int(options["medium_backpack_noise"])
    med_visiblity = int(options["medium_backpack_visibility"])

    med_updates = [
        {
            "coordinates": "B7",
            "value": med_size,
        },
        {
            "coordinates": "B8",
            "value": med_size,
        },
        {
            "coordinates": "B9",
            "value": med_size,
        },
        {
            "coordinates": "C7",
            "value": med_noise,
        },
        {
            "coordinates": "C8",
            "value": med_noise,
        },
        {
            "coordinates": "C9",
            "value": med_noise,
        },
        {
            "coordinates": "E7",
            "value": med_visiblity,
        },
        {
            "coordinates": "E8",
            "value": med_visiblity,
        },
        {
            "coordinates": "E9",
            "value": med_visiblity,
        },
    ]

    sm_size = int(options["small_backpack_carry_weight"])
    sm_noise = int(options["small_backpack_noise"])
    sm_visiblity = int(options["small_backpack_visibility"])

    sm_updates = [
        {
            "coordinates": "B10",
            "value": sm_size,
        },
        {
            "coordinates": "B11",
            "value": sm_size,
        },
        {
            "coordinates": "B12",
            "value": sm_size,
        },
        {
            "coordinates": "C10",
            "value": sm_noise,
        },
        {
            "coordinates": "C11",
            "value": sm_noise,
        },
        {
            "coordinates": "C12",
            "value": sm_noise,
        },
        {
            "coordinates": "E10",
            "value": sm_visiblity,
        },
        {
            "coordinates": "E11",
            "value": sm_visiblity,
        },
        {
            "coordinates": "E12",
            "value": sm_visiblity,
        },
    ]

    updates = lg_updates + med_updates + sm_updates
    for update in updates:
        update["sheet"] = "equipment"
        update["allow_new_data"] = True

    return updates
