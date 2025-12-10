from typing import List

DEBUG = False
NAME = "Increase Cash Reward"
DESCRIPTION = "Increase the cash reward when harvesting kills, completing missions, and finishing competitions."
FILE = "settings/hp_settings/player_rewards.bin"
OPTIONS = [
  { "name": "Cash Reward Multiplier", "min": 0.1, "max": 20.0, "default": 1.0, "initial": 1.0, "increment": 0.1 }
]

def format_options(options: dict) -> str:
  cash_reward_multiplier = int(options['cash_reward_multiplier'])
  return f"Increase Cash Reward ({cash_reward_multiplier}x)"

def update_values_at_coordinates(options: dict) -> List[dict]:
  cash_reward_multiplier = options['cash_reward_multiplier']

  return [
    {
      # Base Cash
      "coordinates": "B7",
      "sheet": "harvest_reward_globals",
      "transform": "multiply",
      "value": cash_reward_multiplier,
    },
    {
      # Cash Span
      "coordinates": "B8",
      "sheet": "harvest_reward_globals",
      "transform": "multiply",
      "value": cash_reward_multiplier
    },
    {
      # reward_mission_cash_small
      "coordinates": "B3",
      "sheet": "custom_rewards",
      "transform": "multiply",
      "value": cash_reward_multiplier
    },
    {
      # reward_mission_cash_medium
      "coordinates": "B4",
      "sheet": "custom_rewards",
      "transform": "multiply",
      "value": cash_reward_multiplier
    },
    {
      # reward_mission_cash_large
      "coordinates": "B5",
      "sheet": "custom_rewards",
      "transform": "multiply",
      "value": cash_reward_multiplier
    },
        {
      # reward_mission_sm8645
      "coordinates": "B18",
      "sheet": "custom_rewards",
      "transform": "multiply",
      "value": cash_reward_multiplier
    },
    {
      # reward_mission_mm10310
      "coordinates": "B19",
      "sheet": "custom_rewards",
      "transform": "multiply",
      "value": cash_reward_multiplier
    },
    {
      # reward_mission_mm20130_pop_haggis_cash_medium
      "coordinates": "B26",
      "sheet": "custom_rewards",
      "transform": "multiply",
      "value": cash_reward_multiplier
    },
    {
      # reward_competition_bronze
      "coordinates": "B33",
      "sheet": "custom_rewards",
      "transform": "multiply",
      "value": cash_reward_multiplier
    },
    {
      # reward_competition_silver
      "coordinates": "B34",
      "sheet": "custom_rewards",
      "transform": "multiply",
      "value": cash_reward_multiplier
    },
    {
      # reward_competition_gold
      "coordinates": "B35",
      "sheet": "custom_rewards",
      "transform": "multiply",
      "value": cash_reward_multiplier
    },
    {
      # reward_halloween_200
      "coordinates": "B37",
      "sheet": "custom_rewards",
      "transform": "multiply",
      "value": cash_reward_multiplier
    },
    {
      # reward_halloween_500
      "coordinates": "B38",
      "sheet": "custom_rewards",
      "transform": "multiply",
      "value": cash_reward_multiplier
    },
    {
      # reward_halloween_1000
      "coordinates": "B39",
      "sheet": "custom_rewards",
      "transform": "multiply",
      "value": cash_reward_multiplier
    },
]
