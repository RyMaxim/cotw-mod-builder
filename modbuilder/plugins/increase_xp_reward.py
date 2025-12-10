DEBUG = False
NAME = "Increase XP Reward"
DESCRIPTION = "Increase the player experience and weapon score rewards when harvesting kills, completing missions, and finding points of interest."
FILE = "settings/hp_settings/player_rewards.bin"
OPTIONS = [
  { "name": "XP Reward Multiplier", "min": 0.1, "max": 20.0, "default": 1.0, "initial": 1.0, "increment": 0.1 },
  { "name": "Weapon Score Multiplier", "min": 0.1, "max": 20.0, "default": 1.0, "initial": 1.0, "increment": 0.1 },
]

def format_options(options: dict) -> str:
  xp_reward_multiplier = int(options['xp_reward_multiplier'])
  weapon_score_multiplier = int(options.get('weapon_score_multiplier', xp_reward_multiplier))
  return f"Increase XP Reward ({xp_reward_multiplier}x XP, {weapon_score_multiplier}x weapon score)"

def update_values_at_coordinates(options: dict) -> list[dict]:
  xp_reward_multiplier = options['xp_reward_multiplier']
  weapon_score_multiplier = options.get('weapon_score_multiplier', xp_reward_multiplier)

  return [
    {
      # Base XP
      "coordinates": "B3",
      "sheet": "harvest_reward_globals",
      "value": xp_reward_multiplier,
      "transform": "multiply",
    },
    {
      # XP Span
      "coordinates": "B4",
      "sheet": "harvest_reward_globals",
      "value": xp_reward_multiplier,
      "transform": "multiply",
    },
    {
      # Base Weapon Score
      "coordinates": "B11",
      "sheet": "harvest_reward_globals",
      "value": weapon_score_multiplier,
      "transform": "multiply",
    },
    {
      # Weapon Score Span
      "coordinates": "B12",
      "sheet": "harvest_reward_globals",
      "value": weapon_score_multiplier,
      "transform": "multiply",
    },
    {
      # reward_mission_cash_small  (Row name, we are modifying the XP column)
      "coordinates": "C3",
      "sheet": "custom_rewards",
      "value": xp_reward_multiplier,
      "transform": "multiply",
    },
    {
      # reward_mission_cash_medium  (Row name, we are modifying the XP column)
      "coordinates": "C4",
      "sheet": "custom_rewards",
      "value": xp_reward_multiplier,
      "transform": "multiply",
    },
    {
      # reward_mission_cash_large  (Row name, we are modifying the XP column)
      "coordinates": "C5",
      "sheet": "custom_rewards",
      "value": xp_reward_multiplier,
      "transform": "multiply",
    },
    {
      # reward_poi_unlocked
      "coordinates": "C7",
      "sheet": "custom_rewards",
      "value": xp_reward_multiplier,
      "transform": "multiply",
    },
    {
      # reward_shed_collected
      "coordinates": "C8",
      "sheet": "custom_rewards",
      "value": xp_reward_multiplier,
      "transform": "multiply",
    },
    {
      # reward_artifact_collected
      "coordinates": "C9",
      "sheet": "custom_rewards",
      "value": xp_reward_multiplier,
      "transform": "multiply",
    },
    {
      # reward_mission_sm8645
      "coordinates": "C18",
      "sheet": "custom_rewards",
      "value": xp_reward_multiplier,
      "transform": "multiply",
    },
    {
      # reward_mission_mm10310
      "coordinates": "C19",
      "sheet": "custom_rewards",
      "value": xp_reward_multiplier,
      "transform": "multiply",
    },
    {
      # reward_mission_mm20130_pop_haggis_cash_medium
      "coordinates": "C26",
      "sheet": "custom_rewards",
      "value": xp_reward_multiplier,
      "transform": "multiply",
    },
    {
      # reward_achievement_small
      "coordinates": "C28",
      "sheet": "custom_rewards",
      "value": xp_reward_multiplier,
      "transform": "multiply",
    },
    {
      # reward_achievement_medium
      "coordinates": "C29",
      "sheet": "custom_rewards",
      "value": xp_reward_multiplier,
      "transform": "multiply",
    },
    {
      # reward_achievement_large
      "coordinates": "C30",
      "sheet": "custom_rewards",
      "value": xp_reward_multiplier,
      "transform": "multiply",
    },
  ]
