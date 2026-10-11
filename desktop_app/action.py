"""Typed, serializable keyboard actions for Keyboard75.

The model in this module deliberately has no GUI dependencies.  Keyboard-page
and consumer-page usages are kept separate so callers cannot accidentally put
a media control inside a keyboard shortcut.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, ClassVar, Mapping, TypeVar


class ActionValidationError(ValueError):
    """Raised when an action or serialized action is invalid."""


@dataclass(frozen=True)
class KeyDefinition:
    """Metadata for one USB HID keyboard/keypad-page usage."""

    key_id: str
    label: str
    usage_id: int


@dataclass(frozen=True)
class ModifierDefinition:
    """Metadata for one sided USB HID keyboard modifier."""

    modifier_id: str
    label: str
    shortcut_label: str
    usage_id: int
    bit_number: int

    @property
    def bit_mask(self) -> int:
        """The modifier's bit in the HID keyboard modifier byte."""
        return 1 << self.bit_number


@dataclass(frozen=True)
class MediaDefinition:
    """Metadata for one USB HID consumer-page usage."""

    media_id: str
    label: str
    usage_id: int


def _key_definitions() -> dict[str, KeyDefinition]:
    definitions: dict[str, KeyDefinition] = {}

    def add(key_id: str, label: str, usage_id: int) -> None:
        definitions[key_id] = KeyDefinition(key_id, label, usage_id)

    for offset, letter in enumerate("abcdefghijklmnopqrstuvwxyz"):
        add(letter, letter.upper(), 0x04 + offset)
    for offset, digit in enumerate("123456789"):
        add(digit, digit, 0x1E + offset)
    add("0", "0", 0x27)

    common = (
        ("enter", "Enter", 0x28),
        ("escape", "Escape", 0x29),
        ("backspace", "Backspace", 0x2A),
        ("tab", "Tab", 0x2B),
        ("space", "Space", 0x2C),
        ("minus", "-", 0x2D),
        ("equal", "=", 0x2E),
        ("left_bracket", "[", 0x2F),
        ("right_bracket", "]", 0x30),
        ("backslash", "\\", 0x31),
        ("non_us_hash", "Non-US #", 0x32),
        ("semicolon", ";", 0x33),
        ("apostrophe", "'", 0x34),
        ("grave", "`", 0x35),
        ("comma", ",", 0x36),
        ("period", ".", 0x37),
        ("slash", "/", 0x38),
        ("caps_lock", "Caps Lock", 0x39),
    )
    for definition in common:
        add(*definition)

    for number in range(1, 13):
        add(f"f{number}", f"F{number}", 0x39 + number)

    navigation = (
        ("print", "Print Screen", 0x46),
        ("scroll_lock", "Scroll Lock", 0x47),
        ("pause", "Pause", 0x48),
        ("insert", "Insert", 0x49),
        ("home", "Home", 0x4A),
        ("page_up", "Page Up", 0x4B),
        ("delete", "Delete", 0x4C),
        ("end", "End", 0x4D),
        ("page_down", "Page Down", 0x4E),
        ("right", "Right", 0x4F),
        ("left", "Left", 0x50),
        ("down", "Down", 0x51),
        ("up", "Up", 0x52),
        ("num_lock", "Num Lock", 0x53),
        ("keypad_divide", "Keypad /", 0x54),
        ("keypad_multiply", "Keypad *", 0x55),
        ("keypad_subtract", "Keypad -", 0x56),
        ("keypad_add", "Keypad +", 0x57),
        ("keypad_enter", "Keypad Enter", 0x58),
    )
    for definition in navigation:
        add(*definition)

    for offset, digit in enumerate("123456789"):
        add(f"keypad_{digit}", f"Keypad {digit}", 0x59 + offset)
    add("keypad_0", "Keypad 0", 0x62)
    add("keypad_decimal", "Keypad .", 0x63)
    add("non_us_backslash", "Non-US Backslash", 0x64)
    add("application", "Application", 0x65)
    add("power", "Power", 0x66)
    add("keypad_equal", "Keypad =", 0x67)

    for number in range(13, 25):
        add(f"f{number}", f"F{number}", 0x68 + number - 13)

    editing = (
        ("execute", "Execute", 0x74),
        ("help", "Help", 0x75),
        ("menu", "Menu", 0x76),
        ("select", "Select", 0x77),
        ("stop", "Stop", 0x78),
        ("again", "Again", 0x79),
        ("undo", "Undo", 0x7A),
        ("cut", "Cut", 0x7B),
        ("copy", "Copy", 0x7C),
        ("paste", "Paste", 0x7D),
        ("find", "Find", 0x7E),
    )
    for definition in editing:
        add(*definition)

    return definitions


SINGLE_KEYS: Mapping[str, KeyDefinition] = MappingProxyType(_key_definitions())

MODIFIERS: Mapping[str, ModifierDefinition] = MappingProxyType(
    {
        modifier_id: ModifierDefinition(
            modifier_id, label, shortcut_label, 0xE0 + bit_number, bit_number
        )
        for bit_number, (modifier_id, label, shortcut_label) in enumerate(
            (
                ("lctrl", "Left Ctrl", "Ctrl"),
                ("lshift", "Left Shift", "Shift"),
                ("lalt", "Left Alt", "Alt"),
                ("lsuper", "Left Super", "Super"),
                ("rctrl", "Right Ctrl", "RCtrl"),
                ("rshift", "Right Shift", "RShift"),
                ("ralt", "Right Alt", "RAlt"),
                ("rsuper", "Right Super", "RSuper"),
            )
        )
    }
)

MEDIA_KEYS: Mapping[str, MediaDefinition] = MappingProxyType(
    {
        media_id: MediaDefinition(media_id, label, usage_id)
        for media_id, label, usage_id in (
            ("vol_up", "Volume Up", 0xE9),
            ("vol_down", "Volume Down", 0xEA),
            ("mute", "Mute", 0xE2),
            ("play_pause", "Play/Pause", 0xCD),
            ("next_track", "Next Track", 0xB0),
            ("previous_track", "Previous Track", 0xB2),
        )
    }
)


def _normalized_name(value: str) -> str:
    if not isinstance(value, str):
        raise ActionValidationError("Action identifiers must be strings")
    stripped = value.strip().casefold()
    if not stripped:
        raise ActionValidationError("Action identifiers cannot be empty")
    if len(stripped) == 1 and not stripped.isalnum():
        return stripped
    return "".join(character for character in stripped if character.isalnum())


def _alias_map(
    definitions: Mapping[str, KeyDefinition | ModifierDefinition | MediaDefinition],
) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for identifier, definition in definitions.items():
        aliases[_normalized_name(identifier)] = identifier
        aliases[_normalized_name(definition.label)] = identifier
    return aliases


_KEY_ALIASES = _alias_map(SINGLE_KEYS)
_KEY_ALIASES.update(
    {
        "esc": "escape",
        "return": "enter",
        "del": "delete",
        "ins": "insert",
        "pgup": "page_up",
        "pgdn": "page_down",
        "pagedn": "page_down",
        "printscreen": "print",
        "prtsc": "print",
        "apps": "application",
        "contextmenu": "application",
    }
)

_MODIFIER_ALIASES = _alias_map(MODIFIERS)
_MODIFIER_ALIASES.update(
    {
        "ctrl": "lctrl",
        "control": "lctrl",
        "lcontrol": "lctrl",
        "leftcontrol": "lctrl",
        "shift": "lshift",
        "alt": "lalt",
        "option": "lalt",
        "loption": "lalt",
        "leftoption": "lalt",
        "super": "lsuper",
        "win": "lsuper",
        "windows": "lsuper",
        "cmd": "lsuper",
        "command": "lsuper",
        "meta": "lsuper",
        "rcontrol": "rctrl",
        "rightcontrol": "rctrl",
        "roption": "ralt",
        "rightoption": "ralt",
        "rwin": "rsuper",
        "rwindows": "rsuper",
        "rcmd": "rsuper",
        "rcommand": "rsuper",
    }
)

_MEDIA_ALIASES = _alias_map(MEDIA_KEYS)


def _canonical_key(value: str) -> str:
    try:
        return _KEY_ALIASES[_normalized_name(value)]
    except KeyError as error:
        raise ActionValidationError(f"Unknown single key {value!r}") from error


def _canonical_modifier(value: str) -> str:
    try:
        return _MODIFIER_ALIASES[_normalized_name(value)]
    except KeyError as error:
        raise ActionValidationError(f"Unknown modifier {value!r}") from error


def _canonical_media_key(value: str) -> str:
    try:
        return _MEDIA_ALIASES[_normalized_name(value)]
    except KeyError as error:
        raise ActionValidationError(f"Unknown media key {value!r}") from error


def _require_object(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ActionValidationError("Serialized action must be a JSON object")
    if not value:
        raise ActionValidationError("Serialized action cannot be empty")
    return value


def _require_fields(
    value: Mapping[str, Any], required: set[str], action_type: str
) -> None:
    actual = set(value)
    missing = required - actual
    extra = actual - required
    if missing:
        raise ActionValidationError(
            f"{action_type!r} action is missing field(s): {', '.join(sorted(missing))}"
        )
    if extra:
        raise ActionValidationError(
            f"{action_type!r} action has unknown field(s): {', '.join(sorted(extra))}"
        )


ActionT = TypeVar("ActionT", bound="Action")


class Action:
    """Base class and registry for all serializable action types."""

    action_type: ClassVar[str]
    _registry: ClassVar[dict[str, type[Action]]] = {}

    @property
    def id(self) -> str:
        """Return the action's stable, HID-oriented identifier."""
        raise NotImplementedError

    @property
    def label(self) -> str:
        """Return the action's human-readable label."""
        raise NotImplementedError

    def validate(self: ActionT) -> ActionT:
        """Validate the action and return it for convenient call chaining."""
        raise NotImplementedError

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-serializable representation of the action."""
        raise NotImplementedError

    @classmethod
    def _from_json(cls: type[ActionT], value: Mapping[str, Any]) -> ActionT:
        raise NotImplementedError

    @classmethod
    def register_type(cls, action_class: type[ActionT]) -> type[ActionT]:
        """Register an action subclass by its string ``action_type`` namespace."""
        namespace = getattr(action_class, "action_type", None)
        if not isinstance(namespace, str) or not namespace.strip():
            raise ValueError("Registered action classes need a non-empty action_type")
        if namespace in cls._registry and cls._registry[namespace] is not action_class:
            raise ValueError(f"Action type {namespace!r} is already registered")
        cls._registry[namespace] = action_class
        return action_class

    @classmethod
    def from_json(cls, value: Any) -> Action:
        """Validate and restore an action through the registered type namespace."""
        payload = _require_object(value)
        action_type = payload.get("type")
        if not isinstance(action_type, str) or not action_type:
            raise ActionValidationError(
                "Serialized action field 'type' must be a non-empty string"
            )
        try:
            action_class = cls._registry[action_type]
        except KeyError as error:
            raise ActionValidationError(f"Unknown action type {action_type!r}") from error
        return action_class._from_json(payload)


def register_action_type(action_class: type[ActionT]) -> type[ActionT]:
    """Decorator/function form of :meth:`Action.register_type`."""
    return Action.register_type(action_class)


@register_action_type
@dataclass(frozen=True)
class SingleKeyAction(Action):
    """One key from the USB HID keyboard/keypad usage page."""

    key: str
    action_type: ClassVar[str] = "key"

    def __post_init__(self) -> None:
        object.__setattr__(self, "key", _canonical_key(self.key))

    @property
    def definition(self) -> KeyDefinition:
        return SINGLE_KEYS[self.key]

    @property
    def id(self) -> str:
        return f"key:{self.key}"

    @property
    def label(self) -> str:
        return self.definition.label

    @property
    def usage_id(self) -> int:
        return self.definition.usage_id

    def validate(self) -> SingleKeyAction:
        _canonical_key(self.key)
        return self

    def to_json(self) -> dict[str, Any]:
        return {"type": self.action_type, "key": self.key}

    @classmethod
    def _from_json(cls, value: Mapping[str, Any]) -> SingleKeyAction:
        _require_fields(value, {"type", "key"}, cls.action_type)
        return cls(value["key"])


@register_action_type
@dataclass(frozen=True)
class ModifierAction(Action):
    """A key-down or key-up event for one sided HID modifier."""

    modifier: str
    event: str = "down"
    action_type: ClassVar[str] = "modifier"

    def __post_init__(self) -> None:
        object.__setattr__(self, "modifier", _canonical_modifier(self.modifier))
        if self.event not in {"down", "up"}:
            raise ActionValidationError("Modifier event must be 'down' or 'up'")

    @property
    def definition(self) -> ModifierDefinition:
        return MODIFIERS[self.modifier]

    @property
    def id(self) -> str:
        suffix = "" if self.event == "down" else ":up"
        return f"mod:{self.modifier}{suffix}"

    @property
    def label(self) -> str:
        return f"{self.definition.label} {self.event.title()}"

    @property
    def usage_id(self) -> int:
        return self.definition.usage_id

    @property
    def bit_number(self) -> int:
        return self.definition.bit_number

    @property
    def bit_mask(self) -> int:
        return self.definition.bit_mask

    @property
    def is_key_down(self) -> bool:
        return self.event == "down"

    def validate(self) -> ModifierAction:
        _canonical_modifier(self.modifier)
        if self.event not in {"down", "up"}:
            raise ActionValidationError("Modifier event must be 'down' or 'up'")
        return self

    def to_json(self) -> dict[str, Any]:
        return {
            "type": self.action_type,
            "modifier": self.modifier,
            "event": self.event,
        }

    @classmethod
    def _from_json(cls, value: Mapping[str, Any]) -> ModifierAction:
        _require_fields(value, {"type", "modifier", "event"}, cls.action_type)
        return cls(value["modifier"], value["event"])


def _shortcut_id_modifier(modifier: str) -> str:
    return {
        "lctrl": "ctrl",
        "lshift": "shift",
        "lalt": "alt",
        "lsuper": "super",
    }.get(modifier, modifier)


@register_action_type
@dataclass(frozen=True)
class ShortcutAction(Action):
    """One to four sided modifiers held with exactly one keyboard key."""

    modifiers: tuple[str, ...]
    key: str
    action_type: ClassVar[str] = "shortcut"

    def __post_init__(self) -> None:
        if isinstance(self.modifiers, str):
            raise ActionValidationError("Shortcut modifiers must be a sequence")
        try:
            modifiers = tuple(_canonical_modifier(item) for item in self.modifiers)
        except TypeError as error:
            raise ActionValidationError("Shortcut modifiers must be a sequence") from error
        object.__setattr__(self, "modifiers", modifiers)
        object.__setattr__(self, "key", _canonical_key(self.key))
        self.validate()

    @property
    def id(self) -> str:
        parts = [_shortcut_id_modifier(item) for item in self.modifiers]
        return "combo:" + "+".join((*parts, self.key))

    @property
    def label(self) -> str:
        modifier_labels = [MODIFIERS[item].shortcut_label for item in self.modifiers]
        return "+".join((*modifier_labels, SINGLE_KEYS[self.key].label))

    @property
    def modifier_mask(self) -> int:
        mask = 0
        for modifier in self.modifiers:
            mask |= MODIFIERS[modifier].bit_mask
        return mask

    @property
    def usage_id(self) -> int:
        return SINGLE_KEYS[self.key].usage_id

    def validate(self) -> ShortcutAction:
        if not self.modifiers:
            raise ActionValidationError("Shortcut requires at least one modifier")
        if len(self.modifiers) > 4:
            raise ActionValidationError("Shortcut cannot contain more than 4 modifiers")
        if len(set(self.modifiers)) != len(self.modifiers):
            raise ActionValidationError("Shortcut cannot contain duplicate modifiers")
        for modifier in self.modifiers:
            _canonical_modifier(modifier)
        _canonical_key(self.key)
        return self

    def to_json(self) -> dict[str, Any]:
        return {
            "type": self.action_type,
            "modifiers": list(self.modifiers),
            "key": self.key,
        }

    @classmethod
    def _from_json(cls, value: Mapping[str, Any]) -> ShortcutAction:
        _require_fields(value, {"type", "modifiers", "key"}, cls.action_type)
        modifiers = value["modifiers"]
        if not isinstance(modifiers, (list, tuple)):
            raise ActionValidationError("Shortcut modifiers must be a JSON array")
        return cls(tuple(modifiers), value["key"])

    @classmethod
    def parse(cls, label: str) -> ShortcutAction:
        """Parse a case-insensitive label such as ``Ctrl+Shift+S``."""
        return parse_shortcut(label)


@register_action_type
@dataclass(frozen=True)
class MediaAction(Action):
    """One consumer-page media control, separate from keyboard actions."""

    media_key: str
    action_type: ClassVar[str] = "media"

    def __post_init__(self) -> None:
        object.__setattr__(self, "media_key", _canonical_media_key(self.media_key))

    @property
    def definition(self) -> MediaDefinition:
        return MEDIA_KEYS[self.media_key]

    @property
    def id(self) -> str:
        return f"media:{self.media_key}"

    @property
    def label(self) -> str:
        return self.definition.label

    @property
    def usage_id(self) -> int:
        return self.definition.usage_id

    def validate(self) -> MediaAction:
        _canonical_media_key(self.media_key)
        return self

    def to_json(self) -> dict[str, Any]:
        return {"type": self.action_type, "key": self.media_key}

    @classmethod
    def _from_json(cls, value: Mapping[str, Any]) -> MediaAction:
        _require_fields(value, {"type", "key"}, cls.action_type)
        return cls(value["key"])


def parse_shortcut(label: str) -> ShortcutAction:
    """Parse a shortcut label with 1--4 modifiers and one keyboard key.

    Unsided names (``Ctrl``, ``Shift``, ``Alt``, ``Super``) deterministically
    select their left-side HID variant. Explicit ``L``/``R`` names retain the
    requested side.
    """
    if not isinstance(label, str) or not label.strip():
        raise ActionValidationError("Shortcut label cannot be empty")
    parts = [part.strip() for part in label.split("+")]
    if any(not part for part in parts):
        raise ActionValidationError("Shortcut contains an empty component")
    if len(parts) < 2:
        raise ActionValidationError("Shortcut requires modifiers and one main key")

    modifier_parts = parts[:-1]
    if len(modifier_parts) > 4:
        raise ActionValidationError("Shortcut cannot contain more than 4 modifiers")
    modifiers = tuple(_canonical_modifier(part) for part in modifier_parts)

    main_key = parts[-1]
    normalized_main = _normalized_name(main_key)
    if normalized_main in _MEDIA_ALIASES:
        raise ActionValidationError("Media keys cannot be used inside a shortcut")
    if normalized_main in _MODIFIER_ALIASES:
        raise ActionValidationError("Shortcut requires exactly one non-modifier main key")
    return ShortcutAction(modifiers, _canonical_key(main_key))


def validate_action(value: Action | Any) -> Action:
    """Validate an action object or deserialize and validate a JSON value."""
    if isinstance(value, Action):
        return value.validate()
    return Action.from_json(value)


# A concise compatibility name for callers that prefer the HID term "key".
KeyAction = SingleKeyAction


__all__ = [
    "Action",
    "ActionValidationError",
    "KeyAction",
    "KeyDefinition",
    "MEDIA_KEYS",
    "MODIFIERS",
    "MediaAction",
    "MediaDefinition",
    "ModifierAction",
    "ModifierDefinition",
    "SINGLE_KEYS",
    "ShortcutAction",
    "SingleKeyAction",
    "parse_shortcut",
    "register_action_type",
    "validate_action",
]
