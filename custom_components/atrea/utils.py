import re

from pyatrea import Atrea
from .const import (
    DOMAIN,
    CONF_PRESETS,
    ALL_PRESET_LIST,
    FAN_LEVEL_NAMES,
    FAN_MODE_OFF_LABEL,
)
from homeassistant.const import CONF_NAME


def isAtreaUnit(host, port):
    atrea = Atrea(host, port)
    return atrea.isAtreaUnit()


def value_to_label(value: int) -> str:
    """Translate raw H10510=4 register value (0, 10..38) to a human label."""
    if value == 0:
        return FAN_MODE_OFF_LABEL
    mg, units = divmod(value, 10)
    if mg in (1, 2) and 0 <= units <= 2:
        return FAN_LEVEL_NAMES[units]
    if mg == 3 and 0 <= units <= 8:
        v = FAN_LEVEL_NAMES[units // 3]
        c = FAN_LEVEL_NAMES[units % 3]
        return f"{v} vent / {c} circ"
    return f"{value}%"


_COMBINED_LABEL_RE = re.compile(
    r"^(Min|Norm|Max)\s+vent\s*/\s*(Min|Norm|Max)\s+circ$",
)


def label_to_value(label: str, current_mg: int | None) -> int | None:
    """Translate a human label + current mode group to a raw register value, or None on mismatch."""
    if label == FAN_MODE_OFF_LABEL:
        return 0
    if current_mg in (1, 2) and label in FAN_LEVEL_NAMES:
        return current_mg * 10 + FAN_LEVEL_NAMES.index(label)
    if current_mg == 3:
        match = _COMBINED_LABEL_RE.match(label)
        if match:
            v = match.group(1).capitalize()
            c = match.group(2).capitalize()
            if v in FAN_LEVEL_NAMES and c in FAN_LEVEL_NAMES:
                return 30 + FAN_LEVEL_NAMES.index(v) * 3 + FAN_LEVEL_NAMES.index(c)
    return None


def fan_modes_for_group(mg: int | None) -> list[str]:
    """Return the dropdown contents for the given mode group, or [] if managed/unknown."""
    if mg == 0:
        return [FAN_MODE_OFF_LABEL]
    if mg in (1, 2):
        return list(FAN_LEVEL_NAMES)
    if mg == 3:
        return [
            f"{v} vent / {c} circ" for v in FAN_LEVEL_NAMES for c in FAN_LEVEL_NAMES
        ]
    return []


def transition_fan_value(old_value: int, new_mg: int) -> int:
    """Pick a new H10708 value when switching mode group, preserving level intent.

    See the transition matrix in the integration's README / project plan for the
    full mapping of (old_mg, new_mg) → new register value.
    """
    if new_mg == 0:
        return 0
    if old_value > 0:
        old_mg, old_units = divmod(old_value, 10)
    else:
        old_mg, old_units = 0, 0
    if old_mg == 0:
        return new_mg * 10 if new_mg in (1, 2) else 30
    if old_mg in (1, 2):
        if new_mg in (1, 2):
            return new_mg * 10 + old_units
        if new_mg == 3:
            return 30 + old_units * 3 + old_units  # symmetric: 30, 34, 38
    if old_mg == 3:
        if new_mg == 1:
            return 10 + (old_units // 3)
        if new_mg == 2:
            return 20 + (old_units % 3)
        if new_mg == 3:
            return old_value
    return new_mg * 10  # defensive fallback


async def update_listener(hass, entry):
    preset_list = entry.data.get(CONF_PRESETS)
    if preset_list is None:
        preset_list = ALL_PRESET_LIST
    sensor_name = entry.data.get(CONF_NAME)
    if sensor_name is None:
        sensor_name = "atrea"
    hass.data[DOMAIN][entry.entry_id]["climate"].updatePresetList(preset_list)
    hass.data[DOMAIN][entry.entry_id]["climate"].updateName(sensor_name)
    hass.data[DOMAIN][entry.entry_id]["update"].updateName(sensor_name)
