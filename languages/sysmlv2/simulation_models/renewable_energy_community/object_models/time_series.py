"""Shared helper for reading one scalar out of a CityLearn-managed
time-series array -- factored out so every device file under this package
(plus `Building` in `citylearn_simulation_model.py`) reads its own arrays
the same way, once, instead of repeating the guard in every file.
"""


def current_value(time_series, index: int) -> float:
    """Safely reads one scalar out of a CityLearn-managed time-series array
    at `index`, or 0.0 if that index isn't populated yet -- guards both ends
    (`index < 0`, deliberately, so a not-yet-ticked flow-type reading (see
    below) never silently wraps around to the array's *last* element via
    Python's negative indexing; and `index >= len(time_series)`).

    Two different indexing conventions exist across CityLearn's own arrays,
    verified by tracing both tick-by-tick against a real CityLearnEnv rather
    than assumed -- callers must pass the right one:
      * state-type (`soc`): valid at index `self.time_step` itself -- index
        0 already holds the initial condition, written by reset(), before
        any tick() has run.
      * flow-type (`electricity_consumption`, `net_electricity_consumption`):
        valid only at index `self.time_step - 1` -- after N tick() calls,
        exactly N entries exist (indices 0..N-1); index `self.time_step`
        itself is always still the unwritten future.
    """
    return float(time_series[index]) if 0 <= index < len(time_series) else 0.0
