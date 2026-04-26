from __future__ import annotations

import argparse
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass


DEFAULT_ATTACK_SPEED = 1.6
DEFAULT_ATTACK_SAFETY_SECONDS = 0.0
DEFAULT_EAT_HOLD_SECONDS = 2.2
DEFAULT_EAT_AT_FOOD = 12.0
DEFAULT_INITIAL_FOOD = 20.0
DEFAULT_INITIAL_SATURATION = 0.0
DEFAULT_STACK_SIZE = 64
DEFAULT_SWORD_SLOT = 1
DEFAULT_FOOD_SLOTS = (2, 3, 4, 5, 6, 7, 8, 9)
EXHAUSTION_PER_ATTACK = 0.1
EXHAUSTION_PER_POINT = 4.0
COOKED_PORKCHOP_FOOD = 8.0
COOKED_PORKCHOP_SATURATION = 12.8
MIN_SWEEP_INTERVAL_SECONDS = 0.55


class AutomationState:
    def __init__(self, start_active: bool) -> None:
        self._lock = threading.Lock()
        self._active = start_active
        self._resume_requested = start_active

    def toggle(self) -> bool:
        with self._lock:
            self._active = not self._active
            if self._active:
                self._resume_requested = True
            return self._active

    def is_active(self) -> bool:
        with self._lock:
            return self._active

    def set_active(self, active: bool) -> None:
        with self._lock:
            self._active = active
            if active:
                self._resume_requested = True

    def consume_resume_requested(self) -> bool:
        with self._lock:
            requested = self._resume_requested
            self._resume_requested = False
            return requested


def normalize_food_slots(slots: list[int] | tuple[int, ...]) -> tuple[int, ...]:
    seen: set[int] = set()
    normalized: list[int] = []
    for slot in slots:
        slot_number = int(slot)
        if slot_number in seen:
            continue
        seen.add(slot_number)
        normalized.append(slot_number)
    return tuple(normalized)


def validate_slot_selection(sword_slot: int, food_slots: list[int] | tuple[int, ...]) -> tuple[int, ...]:
    if sword_slot not in range(1, 10):
        raise ValueError("Sword slot must be between 1 and 9.")

    normalized_food_slots = normalize_food_slots(food_slots)
    if not normalized_food_slots:
        raise ValueError("At least one food slot must be selected.")

    invalid_slots = [slot for slot in normalized_food_slots if slot not in range(1, 10)]
    if invalid_slots:
        raise ValueError("Food slots must be between 1 and 9.")

    if sword_slot in normalized_food_slots:
        raise ValueError("Sword slot must not also be in food slots.")

    return normalized_food_slots


@dataclass
class FoodState:
    slots: tuple[int, ...]
    attempts_per_slot: int
    slot_index: int = 0
    attempts_in_slot: int = 0
    full_cycles: int = 0

    @property
    def current_slot(self) -> int:
        return self.slots[self.slot_index]

    def record_eat_attempt(self) -> None:
        self.attempts_in_slot += 1
        if self.attempts_in_slot < self.attempts_per_slot:
            return

        self.attempts_in_slot = 0
        self.slot_index += 1
        if self.slot_index >= len(self.slots):
            self.slot_index = 0
            self.full_cycles += 1


@dataclass
class HungerModel:
    food: float
    saturation: float
    exhaustion: float = 0.0

    def add_attack(self) -> None:
        self.exhaustion += EXHAUSTION_PER_ATTACK
        while self.exhaustion >= EXHAUSTION_PER_POINT:
            self.exhaustion -= EXHAUSTION_PER_POINT
            if self.saturation > 0:
                self.saturation = max(0.0, self.saturation - 1.0)
            else:
                self.food = max(0.0, self.food - 1.0)

    def should_eat(self, eat_at_food: float) -> bool:
        return self.food <= eat_at_food

    def record_eat_attempt(self, food_points: float, saturation: float) -> None:
        if self.food >= 20.0:
            return
        self.food = min(20.0, self.food + food_points)
        self.saturation = min(self.food, self.saturation + saturation)


@dataclass(frozen=True)
class FoodProfile:
    name: str
    food_points: float
    saturation: float
    consume_seconds: float
    stack_size: int


DEFAULT_FOOD_PROFILE = FoodProfile(
    name="Cooked Porkchop",
    food_points=COOKED_PORKCHOP_FOOD,
    saturation=COOKED_PORKCHOP_SATURATION,
    consume_seconds=1.6,
    stack_size=DEFAULT_STACK_SIZE,
)


class Controller:
    def __init__(self, dry_run: bool) -> None:
        self.dry_run = dry_run
        self.pyautogui = None
        if not dry_run:
            try:
                import pyautogui
            except ImportError as exc:
                raise SystemExit(
                    "pyautogui is not installed. Run this inside the conda environment: "
                    "conda run -n mc-afk-automation python mc_afk_attack.py"
                ) from exc

            pyautogui.PAUSE = 0.04
            pyautogui.FAILSAFE = True
            self.pyautogui = pyautogui

    def press_slot(self, slot: int) -> None:
        if self.dry_run:
            print(f"[dry-run] press hotbar slot {slot}")
            return
        self.pyautogui.press(str(slot))

    def left_click(self) -> None:
        if self.dry_run:
            print("[dry-run] left click")
            return
        self.pyautogui.click(button="left")

    def hold_right_click(self, seconds: float) -> None:
        if self.dry_run:
            print(f"[dry-run] hold right click for {seconds:.2f}s")
            time.sleep(min(seconds, 0.2))
            return

        self.pyautogui.mouseDown(button="right")
        try:
            time.sleep(seconds)
        finally:
            self.pyautogui.mouseUp(button="right")

    def release_buttons(self) -> None:
        if self.dry_run or self.pyautogui is None:
            return
        self.pyautogui.mouseUp(button="left")
        self.pyautogui.mouseUp(button="right")


def start_hotkey_listener(
    state: AutomationState,
    controller: Controller,
    on_toggle: Callable[[bool], None] | None = None,
):
    try:
        from pynput import keyboard
    except ImportError as exc:
        raise SystemExit(
            "pynput is not installed. Run this inside the conda environment: "
            "conda run -n mc-afk-automation python mc_afk_attack.py"
        ) from exc

    def toggle() -> None:
        is_active = state.toggle()
        if is_active:
            print("Alt+C pressed: automation running.", flush=True)
        else:
            controller.release_buttons()
            print("Alt+C pressed: automation paused.", flush=True)
        if on_toggle is not None:
            on_toggle(is_active)

    listener = keyboard.GlobalHotKeys({"<alt>+c": toggle})
    listener.start()
    return listener


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Minecraft Java AFK attack and cooked porkchop eating automation."
    )
    parser.add_argument(
        "--attack-interval",
        type=float,
        default=None,
        help=(
            "Seconds between left-click attacks. Default: 1 / attack speed + safety, "
            "which is 0.625s for a 1.6 attack-speed sword."
        ),
    )
    parser.add_argument(
        "--attack-speed",
        type=float,
        default=DEFAULT_ATTACK_SPEED,
        help="Sword attack speed shown by Minecraft. Default: 1.6",
    )
    parser.add_argument(
        "--attack-safety",
        type=float,
        default=DEFAULT_ATTACK_SAFETY_SECONDS,
        help="Extra seconds added to the theoretical full cooldown. Default: 0.0",
    )
    parser.add_argument(
        "--eat-at-food",
        type=float,
        default=DEFAULT_EAT_AT_FOOD,
        help="Estimated hunger value at or below which to eat. Default: 12.0",
    )
    parser.add_argument(
        "--eat-hold",
        type=float,
        default=DEFAULT_EAT_HOLD_SECONDS,
        help="Seconds to hold right click for eating. Default: 2.2",
    )
    parser.add_argument(
        "--initial-food",
        type=float,
        default=DEFAULT_INITIAL_FOOD,
        help="Estimated starting hunger points. Default: 20.0",
    )
    parser.add_argument(
        "--initial-saturation",
        type=float,
        default=DEFAULT_INITIAL_SATURATION,
        help=(
            "Estimated hidden starting saturation. Default: 0.0, a conservative value "
            "that eats earlier."
        ),
    )
    parser.add_argument(
        "--sword-slot",
        type=int,
        default=DEFAULT_SWORD_SLOT,
        choices=range(1, 10),
        metavar="1-9",
        help="Hotbar slot containing the sword. Default: 1",
    )
    parser.add_argument(
        "--food-slots",
        type=int,
        nargs="+",
        default=list(DEFAULT_FOOD_SLOTS),
        choices=range(1, 10),
        metavar="1-9",
        help="Hotbar slots containing cooked porkchops. Default: 2 3 4 5 6 7 8 9",
    )
    parser.add_argument(
        "--stack-size",
        type=int,
        default=DEFAULT_STACK_SIZE,
        help="Eating attempts before rotating to the next food slot. Default: 64",
    )
    parser.add_argument(
        "--eat-on-start",
        action="store_true",
        help="Make one eating attempt whenever automation is started or resumed.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without sending keyboard or mouse input.",
    )
    parser.add_argument(
        "--start-active",
        action="store_true",
        help="Start automation immediately. Intended for testing; default is paused.",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help="Optional number of seconds to run after startup, mainly for testing.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.attack_speed <= 0:
        raise SystemExit("--attack-speed must be positive.")
    if args.attack_safety < 0:
        raise SystemExit("--attack-safety must be non-negative.")
    if args.attack_interval is not None and args.attack_interval < MIN_SWEEP_INTERVAL_SECONDS:
        raise SystemExit("--attack-interval must be at least 0.55 seconds for sweep attacks.")
    if not 0 <= args.eat_at_food <= 19:
        raise SystemExit("--eat-at-food must be between 0 and 19.")
    if args.eat_hold < 1.8:
        raise SystemExit("--eat-hold must be at least 1.8 seconds.")
    if not 0 <= args.initial_food <= 20:
        raise SystemExit("--initial-food must be between 0 and 20.")
    if not 0 <= args.initial_saturation <= 20:
        raise SystemExit("--initial-saturation must be between 0 and 20.")
    if args.stack_size <= 0:
        raise SystemExit("--stack-size must be positive.")
    if args.duration is not None and args.duration <= 0:
        raise SystemExit("--duration must be positive.")
    try:
        args.food_slots = list(validate_slot_selection(args.sword_slot, args.food_slots))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def get_attack_interval(args: argparse.Namespace) -> float:
    if args.attack_interval is not None:
        return args.attack_interval
    return (1.0 / args.attack_speed) + args.attack_safety


def do_attack(controller: Controller) -> None:
    controller.left_click()


def do_eat(
    controller: Controller,
    food_state: FoodState,
    hunger_model: HungerModel,
    sword_slot: int,
    food_profile: FoodProfile,
    hold_seconds: float,
    reason: str,
    is_active: Callable[[], bool],
    logger: Callable[[str], None] = print,
) -> bool:
    food_slot = food_state.current_slot
    logger(
        f"Eating attempt ({reason}): slot {food_slot} "
        f"({food_state.attempts_in_slot + 1}/{food_state.attempts_per_slot}), "
        f"model food={hunger_model.food:.1f}, saturation={hunger_model.saturation:.1f}"
    )
    controller.press_slot(food_slot)
    time.sleep(0.12)
    if not is_active():
        return False
    controller.hold_right_click(hold_seconds)
    if not is_active():
        return False
    time.sleep(0.12)
    if not is_active():
        return False
    food_state.record_eat_attempt()
    hunger_model.record_eat_attempt(food_profile.food_points, food_profile.saturation)
    controller.press_slot(sword_slot)
    if food_state.attempts_in_slot == 0:
        logger(
            f"Rotated food slot. Current slot is now {food_state.current_slot}; "
            f"completed cycles: {food_state.full_cycles}"
        )
    return True


def run_automation_loop(
    args: argparse.Namespace,
    controller: Controller,
    state: AutomationState,
    stop_event: threading.Event | None = None,
    logger: Callable[[str], None] = print,
    attack_interval_provider: Callable[[], float] | None = None,
    slot_selection_provider: Callable[[], tuple[int, tuple[int, ...]]] | None = None,
    food_profile_provider: Callable[[], FoodProfile] | None = None,
    eat_hold_provider: Callable[[], float] | None = None,
) -> int:
    def resolve_attack_interval() -> float:
        attack_interval = (
            attack_interval_provider() if attack_interval_provider is not None else get_attack_interval(args)
        )
        if attack_interval < MIN_SWEEP_INTERVAL_SECONDS:
            raise SystemExit("Computed attack interval is below 0.55 seconds; increase --attack-safety.")
        return attack_interval

    def resolve_slot_selection() -> tuple[int, tuple[int, ...]]:
        if slot_selection_provider is None:
            sword_slot = args.sword_slot
            food_slots = tuple(args.food_slots)
        else:
            sword_slot, food_slots = slot_selection_provider()

        normalized_food_slots = validate_slot_selection(sword_slot, food_slots)
        return sword_slot, normalized_food_slots

    def resolve_food_profile() -> FoodProfile:
        if food_profile_provider is not None:
            return food_profile_provider()
        return FoodProfile(
            name=DEFAULT_FOOD_PROFILE.name,
            food_points=DEFAULT_FOOD_PROFILE.food_points,
            saturation=DEFAULT_FOOD_PROFILE.saturation,
            consume_seconds=DEFAULT_FOOD_PROFILE.consume_seconds,
            stack_size=args.stack_size,
        )

    def resolve_eat_hold_seconds(food_profile: FoodProfile) -> float:
        if eat_hold_provider is not None:
            return eat_hold_provider()
        return args.eat_hold
    attack_interval = resolve_attack_interval()
    current_sword_slot, current_food_slots = resolve_slot_selection()
    current_food_profile = resolve_food_profile()
    food_state = FoodState(current_food_slots, current_food_profile.stack_size)
    hunger_model = HungerModel(args.initial_food, args.initial_saturation)

    now = time.monotonic()
    end_at = None if args.duration is None else now + args.duration
    next_attack = now + attack_interval

    try:
        while True:
            if stop_event is not None and stop_event.is_set():
                return 0

            now = time.monotonic()
            if end_at is not None and now >= end_at:
                logger("Duration reached; stopping.")
                return 0

            if not state.is_active():
                time.sleep(0.05)
                continue

            if state.consume_resume_requested():
                try:
                    attack_interval = resolve_attack_interval()
                    current_sword_slot, current_food_slots = resolve_slot_selection()
                    current_food_profile = resolve_food_profile()
                except ValueError as exc:
                    controller.release_buttons()
                    state.set_active(False)
                    logger(str(exc))
                    time.sleep(0.05)
                    continue

                if (
                    food_state.slots != current_food_slots
                    or food_state.attempts_per_slot != current_food_profile.stack_size
                ):
                    food_state = FoodState(current_food_slots, current_food_profile.stack_size)

                controller.release_buttons()
                controller.press_slot(current_sword_slot)
                now = time.monotonic()
                next_attack = now + attack_interval
                if args.eat_on_start:
                    do_eat(
                        controller,
                        food_state,
                        hunger_model,
                        current_sword_slot,
                        current_food_profile,
                        resolve_eat_hold_seconds(current_food_profile),
                        "start/resume",
                        state.is_active,
                        logger,
                    )
                    next_attack = time.monotonic() + attack_interval
                continue

            if hunger_model.should_eat(args.eat_at_food):
                completed_eat = do_eat(
                    controller,
                    food_state,
                    hunger_model,
                    current_sword_slot,
                    current_food_profile,
                    resolve_eat_hold_seconds(current_food_profile),
                    "hunger model",
                    state.is_active,
                    logger,
                )
                if not completed_eat:
                    continue
                now = time.monotonic()
                next_attack = now + attack_interval

            if now >= next_attack:
                do_attack(controller)
                hunger_model.add_attack()
                next_attack = time.monotonic() + attack_interval

            time.sleep(max(0.01, min(0.2, next_attack - time.monotonic())))
    except KeyboardInterrupt:
        logger("\nStopped by Ctrl+C.")
        return 0
    finally:
        controller.release_buttons()


def run() -> int:
    args = parse_args()
    validate_args(args)

    attack_interval = get_attack_interval(args)
    if attack_interval < MIN_SWEEP_INTERVAL_SECONDS:
        raise SystemExit("Computed attack interval is below 0.55 seconds; increase --attack-safety.")

    controller = Controller(dry_run=args.dry_run)
    state = AutomationState(args.start_active)
    hotkey_listener = start_hotkey_listener(state, controller)

    print("Minecraft AFK automation ready.")
    print(f"Attack interval: {attack_interval:.3f}s")
    print(f"Eating model: eat at food <= {args.eat_at_food:.1f}")
    print(f"Sword slot: {args.sword_slot}; food slots: {list(args.food_slots)}")
    initial_state = "running" if args.start_active else "paused"
    print(f"Initial state: {initial_state}. Press Alt+C to start/pause. Ctrl+C stops.")
    print("Move the mouse to the upper-left screen corner to trigger PyAutoGUI fail-safe.")

    try:
        return run_automation_loop(args, controller, state)
    finally:
        hotkey_listener.stop()


if __name__ == "__main__":
    sys.exit(run())
