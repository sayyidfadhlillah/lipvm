"""Observers on the sysmlv2 runtime registry.

They watch the runtime model (runtime.py) and report its changes to the
generic SynchronizationManager (simulation_models/facade_proxy.py), which
sends them to the simulation. Kept out of runtime.py, which only defines the
model, and out of facade_proxy.py, which knows nothing about SysML.
"""
from pyecore.notification import EObserver, Kind

from languages.sysmlv2.runtime import CompositeCustomValue, _custom_attribute_value


class ConfiguredValueObserver(EObserver):
    """Watches one PartInstantiation's configured values (its
    attribute_redefinitions) and records every change in the
    SynchronizationManager, converted the same way instantiation converts
    them (design doc, Topic 10 "Syncing a runtime change to the simulation").

    One observer per part, self-maintaining: on the part it reacts only to a
    redefinition being added (watch it, record its value); on a redefinition
    only to its `value` being set. Everything else is ignored, notably the
    part's observed_values, which every refresh sets: those come from the
    simulation and are never sent back. Updates always replace a value rather
    than change it in place, so nested value objects need no observers.
    """

    def __init__(self, part: "PartInstantiation", manager: "SynchronizationManager"):
        super().__init__()
        self._part = part
        self._manager = manager
        self.observe(part)
        for redefinition in part.attribute_redefinitions:
            self.observe(redefinition)

    def notifyChanged(self, notification):
        feature_name = notification.feature.name
        if notification.notifier is self._part:
            if notification.kind == Kind.ADD and feature_name == "attribute_redefinitions":
                redefinition = notification.new
                self.observe(redefinition)
                if redefinition.value is not None:
                    self._record(redefinition.name, redefinition.value)
        elif notification.kind == Kind.SET and feature_name == "value":
            self._record(notification.notifier.name, notification.new)

    def _record(self, attr_name: str, value: "Value") -> None:
        # Only composite values are sent, as at instantiation
        # (PartInstantiation.evaluate); a scalar has no simulation-side
        # conversion yet, so refuse it rather than drop it silently.
        if not isinstance(value, CompositeCustomValue):
            raise TypeError(
                f"Can't sync {self._part.qualified_name}'s {attr_name!r} to the simulation: "
                f"only composite values are supported, got {type(value).__name__}")
        self._manager.record(self._part.qualified_name, attr_name, _custom_attribute_value(value))
