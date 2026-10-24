"""Bounded owner preferences are data, never executable configuration."""
from .broker import Denied
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULTS={"quiet":False,"pinned":False,"roam":True,"reduced_motion":False,
          "dnd":False,"paused":False,"mute":False,"sound_volume":15,
          "initiative":True,"min_gap_minutes":45,"max_gap_minutes":120,
          "hourly_bubbles":2,"daily_bubbles":8,"daily_model_requests":8,
          "timezone":"America/Edmonton","quiet_start":"","quiet_end":"","send_with_ctrl":False,"character_size":280}
BOOLS={k for k,v in DEFAULTS.items() if type(v) is bool}
BOUNDS={"sound_volume":(0,100),"character_size":(160,420),"min_gap_minutes":(15,240),
        "max_gap_minutes":(30,480),"hourly_bubbles":(0,4),"daily_bubbles":(0,16),"daily_model_requests":(0,16)}

def validate(changes):
    if not isinstance(changes,dict) or not changes or not set(changes)<=set(DEFAULTS):
        raise Denied("Only the documented appearance/behavior settings can change")
    for key,value in changes.items():
        if key in BOOLS and type(value) is not bool:
            raise Denied("Expected a boolean preference")
        if key in BOUNDS:
            low,high=BOUNDS[key]
            if type(value) is not int or not low<=value<=high:
                raise Denied("Preference outside its supported range")
        if key=='timezone':
            if not isinstance(value,str) or len(value)>64:raise Denied('Invalid local timezone')
            try:ZoneInfo(value)
            except (ZoneInfoNotFoundError,ValueError):raise Denied('Choose an installed IANA timezone')
        if key in ("quiet_start","quiet_end"):
            if not isinstance(value,str) or (value and (len(value)!=5 or value[2]!=":" or not value[:2].isdigit() or not value[3:].isdigit() or int(value[:2])>23 or int(value[3:])>59)):
                raise Denied("Quiet hours use HH:MM in the local timezone")
    return changes


def load(store):
    saved=store.value("local-owner","profile",{})
    return {**DEFAULTS,**validate(saved)} if saved else dict(DEFAULTS)


def update(store,changes):
    result={**load(store),**validate(changes)}
    if result['min_gap_minutes']>result['max_gap_minutes']:
        raise Denied("Minimum cadence cannot exceed maximum cadence")
    store.set_value("local-owner","profile",result)
    return result
