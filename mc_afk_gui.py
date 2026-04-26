from __future__ import annotations

import argparse
import re
import sys
import threading
import tkinter as tk
import webbrowser
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from mc_afk_attack import (
    DEFAULT_ATTACK_SAFETY_SECONDS,
    DEFAULT_ATTACK_SPEED,
    DEFAULT_EAT_AT_FOOD,
    DEFAULT_INITIAL_FOOD,
    DEFAULT_INITIAL_SATURATION,
    DEFAULT_SWORD_SLOT,
    AutomationState,
    Controller,
    FoodProfile,
    run_automation_loop,
    validate_slot_selection,
)


WINDOW_TITLE = "Minecraft AFK 自动横扫"
ATTACK_SPEED_MIN = 0.50
ATTACK_SPEED_MAX = 4.00
ATTACK_SPEED_RESOLUTION = 0.05
EAT_HOLD_PADDING_SECONDS = 0.20
BASE_FONT_FAMILY = "Microsoft YaHei UI"
BASE_FONT_SIZE = 13
TITLE_FONT_SIZE = 20
STATUS_FONT_SIZE = 14
LINK_FONT_SIZE = 12

SUPPORTED_FOODS: dict[str, FoodProfile] = {
    "熟猪排": FoodProfile("熟猪排", 8.0, 12.8, 1.6, 64),
    "牛排": FoodProfile("牛排", 8.0, 12.8, 1.6, 64),
    "金胡萝卜": FoodProfile("金胡萝卜", 6.0, 14.4, 1.6, 64),
    "熟羊肉": FoodProfile("熟羊肉", 6.0, 9.6, 1.6, 64),
    "熟鸡肉": FoodProfile("熟鸡肉", 6.0, 7.2, 1.6, 64),
    "熟鲑鱼": FoodProfile("熟鲑鱼", 6.0, 9.6, 1.6, 64),
    "面包": FoodProfile("面包", 5.0, 6.0, 1.6, 64),
    "烤土豆": FoodProfile("烤土豆", 5.0, 6.0, 1.6, 64),
    "熟鳕鱼": FoodProfile("熟鳕鱼", 5.0, 6.0, 1.6, 64),
    "苹果": FoodProfile("苹果", 4.0, 2.4, 1.6, 64),
    "胡萝卜": FoodProfile("胡萝卜", 3.0, 3.6, 1.6, 64),
    "西瓜片": FoodProfile("西瓜片", 2.0, 1.2, 1.6, 64),
    "甜菜根": FoodProfile("甜菜根", 1.0, 1.2, 1.6, 64),
    "干海带": FoodProfile("干海带", 1.0, 0.6, 0.865, 64),
}

DEFAULT_FOOD_NAME = "熟猪排"
DEFAULT_FOOD_SLOTS = tuple(range(2, 10))


class MinecraftAfkGui:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.configure_fonts()

        self.controller = Controller(dry_run=False)
        self.state = AutomationState(start_active=False)
        self.stop_event = threading.Event()
        self.runtime_lock = threading.Lock()
        self.closing = False

        default_profile = SUPPORTED_FOODS[DEFAULT_FOOD_NAME]
        self.runtime_attack_interval = self.interval_for_speed(DEFAULT_ATTACK_SPEED)
        self.runtime_sword_slot = DEFAULT_SWORD_SLOT
        self.runtime_food_slots = DEFAULT_FOOD_SLOTS
        self.runtime_food_profile = default_profile
        self.runtime_eat_hold_seconds = self.eat_hold_seconds_for_profile(default_profile)

        self.attack_speed_var = tk.DoubleVar(value=DEFAULT_ATTACK_SPEED)
        self.attack_speed_text_var = tk.StringVar(value=f"{DEFAULT_ATTACK_SPEED:.2f}")
        self.food_name_var = tk.StringVar(value=DEFAULT_FOOD_NAME)
        self.sword_slot_var = tk.IntVar(value=DEFAULT_SWORD_SLOT)
        self.food_slot_vars = {slot: tk.BooleanVar(value=slot in DEFAULT_FOOD_SLOTS) for slot in range(1, 10)}

        self.status_var = tk.StringVar(value="状态：已暂停")
        self.summary_var = tk.StringVar()
        self.message_var = tk.StringVar(value="等待 Alt+C。关闭窗口会立即停止自动操作。")

        self.build_ui()
        self.refresh_summary()

        self.hotkey_listener = self.start_hotkey_listener()
        self.worker = threading.Thread(target=self.worker_main, name="mc-afk-worker", daemon=True)
        self.worker.start()

    def configure_fonts(self) -> None:
        for font_name in (
            "TkDefaultFont",
            "TkTextFont",
            "TkMenuFont",
            "TkCaptionFont",
            "TkHeadingFont",
            "TkIconFont",
            "TkTooltipFont",
        ):
            font_obj = tkfont.nametofont(font_name)
            font_obj.configure(family=BASE_FONT_FAMILY, size=BASE_FONT_SIZE)

        self.root.option_add("*TCombobox*Listbox*Font", (BASE_FONT_FAMILY, BASE_FONT_SIZE))

    def build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.grid(row=0, column=0, sticky="nsew")
        outer.columnconfigure(0, weight=1)

        title = ttk.Label(outer, text=WINDOW_TITLE, font=(BASE_FONT_FAMILY, TITLE_FONT_SIZE, "bold"))
        title.grid(row=0, column=0, sticky="w")

        intro_text = (
            "默认配置适配攻击速度 1.6 的剑，按满冷却节奏自动横扫。\n"
            "只支持能放在快捷栏里，长按右键直接吃下去的常规食物。\n"
            "修改设置后，会在下次 Alt+C 重新启动自动化时生效。"
        )
        intro = ttk.Label(outer, text=intro_text, justify="left")
        intro.grid(row=1, column=0, sticky="w", pady=(10, 12))

        usage_frame = ttk.LabelFrame(outer, text="使用说明", padding=12)
        usage_frame.grid(row=2, column=0, sticky="ew")
        usage_text = (
            "1. 先在窗口里设置剑格、食物格、食物类型和攻击速度。\n"
            "2. 切回 Minecraft，按 Alt+C 开始自动化。\n"
            "3. 再按一次 Alt+C 暂停；关闭窗口会直接停止程序。\n"
            "4. 当前运行中的参数不会中途变更，新的设置会在下次 Alt+C 启动时生效。"
        )
        usage = ttk.Label(usage_frame, text=usage_text, justify="left")
        usage.grid(row=0, column=0, sticky="w")

        status = ttk.Label(outer, textvariable=self.status_var, font=(BASE_FONT_FAMILY, STATUS_FONT_SIZE, "bold"))
        status.grid(row=3, column=0, sticky="w", pady=(12, 10))

        config_frame = ttk.LabelFrame(outer, text="自动化配置", padding=12)
        config_frame.grid(row=4, column=0, sticky="ew")

        speed_label = ttk.Label(config_frame, text="剑的攻击速度")
        speed_label.grid(row=0, column=0, sticky="w")

        self.speed_scale = tk.Scale(
            config_frame,
            from_=ATTACK_SPEED_MIN,
            to=ATTACK_SPEED_MAX,
            resolution=ATTACK_SPEED_RESOLUTION,
            orient="horizontal",
            variable=self.attack_speed_var,
            length=300,
            font=(BASE_FONT_FAMILY, BASE_FONT_SIZE),
            command=self.on_attack_speed_changed,
        )
        self.speed_scale.grid(row=1, column=0, sticky="w", pady=(6, 0))

        speed_value = ttk.Label(config_frame, textvariable=self.attack_speed_text_var)
        speed_value.grid(row=1, column=1, sticky="w", padx=(12, 0))

        speed_hint = ttk.Label(config_frame, text="攻击速度越高，脚本攻击越频繁。")
        speed_hint.grid(row=1, column=2, sticky="w", padx=(12, 0))

        food_label = ttk.Label(config_frame, text="食物类型")
        food_label.grid(row=2, column=0, sticky="w", pady=(12, 0))

        food_combo = ttk.Combobox(
            config_frame,
            textvariable=self.food_name_var,
            values=list(SUPPORTED_FOODS.keys()),
            state="readonly",
            width=16,
        )
        food_combo.grid(row=3, column=0, sticky="w", pady=(6, 0))
        food_combo.bind("<<ComboboxSelected>>", lambda _event: self.refresh_summary())

        food_hint = ttk.Label(
            config_frame,
            text="按当前食物的恢复量、进食时长和堆叠上限进行估算。",
        )
        food_hint.grid(row=3, column=1, columnspan=2, sticky="w", padx=(12, 0), pady=(6, 0))

        slot_frame = ttk.LabelFrame(outer, text="快捷栏布局", padding=12)
        slot_frame.grid(row=5, column=0, sticky="ew", pady=(12, 0))

        sword_label = ttk.Label(slot_frame, text="哪个格子放剑")
        sword_label.grid(row=0, column=0, sticky="w")

        sword_buttons = ttk.Frame(slot_frame)
        sword_buttons.grid(row=1, column=0, sticky="w", pady=(6, 10))
        for slot in range(1, 10):
            button = ttk.Radiobutton(
                sword_buttons,
                text=str(slot),
                value=slot,
                variable=self.sword_slot_var,
                command=self.refresh_summary,
            )
            button.grid(row=0, column=slot - 1, padx=(0, 8))

        food_slots_label = ttk.Label(slot_frame, text="哪些格子放食物")
        food_slots_label.grid(row=2, column=0, sticky="w")

        food_buttons = ttk.Frame(slot_frame)
        food_buttons.grid(row=3, column=0, sticky="w", pady=(6, 0))
        for slot in range(1, 10):
            button = ttk.Checkbutton(
                food_buttons,
                text=str(slot),
                variable=self.food_slot_vars[slot],
                command=self.refresh_summary,
            )
            button.grid(row=0, column=slot - 1, padx=(0, 8))

        summary = ttk.Label(outer, textvariable=self.summary_var, justify="left", wraplength=680)
        summary.grid(row=6, column=0, sticky="w", pady=(12, 0))

        message = ttk.Label(outer, textvariable=self.message_var, justify="left", wraplength=680)
        message.grid(row=7, column=0, sticky="w", pady=(12, 0))

        self.build_footer(outer)

    def build_footer(self, parent: ttk.Frame) -> None:
        footer = ttk.Frame(parent)
        footer.grid(row=8, column=0, pady=(16, 0))

        link_font = tkfont.Font(family=BASE_FONT_FAMILY, size=LINK_FONT_SIZE, underline=True)

        author_label = tk.Label(
            footer,
            text="作者 Nanoberry",
            fg="#0a66c2",
            cursor="hand2",
            font=link_font,
            borderwidth=0,
        )
        author_label.pack(side="left")
        author_label.bind("<Button-1>", lambda _event: webbrowser.open("https://github.com/LeoWang0814"))

        separator = ttk.Label(footer, text=" | ")
        separator.pack(side="left")

        repo_label = tk.Label(
            footer,
            text="Github 仓库",
            fg="#0a66c2",
            cursor="hand2",
            font=link_font,
            borderwidth=0,
        )
        repo_label.pack(side="left")
        repo_label.bind("<Button-1>", lambda _event: webbrowser.open("https://github.com/LeoWang0814/mc-afk"))

    def on_attack_speed_changed(self, _value: str) -> None:
        value = round(self.attack_speed_var.get() / ATTACK_SPEED_RESOLUTION) * ATTACK_SPEED_RESOLUTION
        self.attack_speed_var.set(value)
        self.attack_speed_text_var.set(f"{value:.2f}")
        self.refresh_summary()

    def selected_food_slots(self) -> tuple[int, ...]:
        return tuple(slot for slot in range(1, 10) if self.food_slot_vars[slot].get())

    def selected_food_profile(self) -> FoodProfile:
        return SUPPORTED_FOODS[self.food_name_var.get()]

    def interval_for_speed(self, speed: float) -> float:
        interval = 1.0 / speed + DEFAULT_ATTACK_SAFETY_SECONDS
        if interval < 0.55:
            raise ValueError("攻击速度过高，计算出的攻击间隔小于 0.55 秒，无法稳定触发横扫。")
        return interval

    def eat_hold_seconds_for_profile(self, food_profile: FoodProfile) -> float:
        return food_profile.consume_seconds + EAT_HOLD_PADDING_SECONDS

    def describe_current_config(
        self,
        speed: float,
        interval: float,
        sword_slot: int,
        food_slots: tuple[int, ...],
        food_profile: FoodProfile,
    ) -> str:
        food_slot_text = "、".join(str(slot) for slot in food_slots)
        return (
            f"当前配置：剑在第 {sword_slot} 格；食物在第 {food_slot_text} 格；食物类型为 {food_profile.name}；"
            f"攻击速度 {speed:.2f}；攻击间隔 {interval:.3f} 秒/次；"
            f"单次进食按住右键 {self.eat_hold_seconds_for_profile(food_profile):.3f} 秒。"
        )

    def translate_error_message(self, message: str) -> str:
        translations = {
            "Sword slot must be between 1 and 9.": "剑所在格子必须在 1 到 9 之间。",
            "At least one food slot must be selected.": "请至少选择一个食物格。",
            "Food slots must be between 1 and 9.": "食物格子必须在 1 到 9 之间。",
            "Sword slot must not also be in food slots.": "剑所在格子不能同时作为食物格。",
            "Computed attack interval is below 0.55 seconds; increase --attack-safety.": (
                "计算出的攻击间隔低于 0.55 秒，无法稳定触发横扫。"
            ),
        }
        return translations.get(message, message)

    def refresh_summary(self) -> None:
        try:
            speed = self.attack_speed_var.get()
            interval = self.interval_for_speed(speed)
            sword_slot = self.sword_slot_var.get()
            food_slots = validate_slot_selection(sword_slot, self.selected_food_slots())
            food_profile = self.selected_food_profile()
            self.summary_var.set(
                self.describe_current_config(speed, interval, sword_slot, food_slots, food_profile)
            )
        except ValueError as exc:
            self.summary_var.set(f"当前配置无效：{self.translate_error_message(str(exc))}")

    def apply_runtime_config(self) -> bool:
        try:
            speed = self.attack_speed_var.get()
            interval = self.interval_for_speed(speed)
            sword_slot = self.sword_slot_var.get()
            food_slots = validate_slot_selection(sword_slot, self.selected_food_slots())
            food_profile = self.selected_food_profile()
            eat_hold_seconds = self.eat_hold_seconds_for_profile(food_profile)
        except ValueError as exc:
            translated = self.translate_error_message(str(exc))
            self.message_var.set(f"无法启动：{translated}")
            messagebox.showerror("配置无效", translated, parent=self.root)
            return False

        with self.runtime_lock:
            self.runtime_attack_interval = interval
            self.runtime_sword_slot = sword_slot
            self.runtime_food_slots = food_slots
            self.runtime_food_profile = food_profile
            self.runtime_eat_hold_seconds = eat_hold_seconds

        self.summary_var.set(
            self.describe_current_config(speed, interval, sword_slot, food_slots, food_profile)
        )
        return True

    def get_attack_interval(self) -> float:
        with self.runtime_lock:
            return self.runtime_attack_interval

    def get_slot_selection(self) -> tuple[int, tuple[int, ...]]:
        with self.runtime_lock:
            return self.runtime_sword_slot, self.runtime_food_slots

    def get_food_profile(self) -> FoodProfile:
        with self.runtime_lock:
            return self.runtime_food_profile

    def get_eat_hold_seconds(self) -> float:
        with self.runtime_lock:
            return self.runtime_eat_hold_seconds

    def start_hotkey_listener(self):
        try:
            from pynput import keyboard
        except ImportError as exc:
            messagebox.showerror("缺少依赖", "未安装 pynput，无法监听 Alt+C。", parent=self.root)
            raise SystemExit(1) from exc

        def on_hotkey() -> None:
            if not self.closing:
                self.root.after(0, self.toggle_automation)

        listener = keyboard.GlobalHotKeys({"<alt>+c": on_hotkey})
        listener.start()
        return listener

    def toggle_automation(self) -> None:
        if self.closing:
            return

        if self.state.is_active():
            self.state.set_active(False)
            self.controller.release_buttons()
            self.status_var.set("状态：已暂停")
            self.message_var.set("已暂停。按 Alt+C 继续。新的设置会在下次 Alt+C 启动自动化时生效。")
            return

        if not self.apply_runtime_config():
            return

        self.state.set_active(True)
        self.status_var.set("状态：运行中")
        self.message_var.set("运行中。按 Alt+C 暂停。当前这次运行会沿用启动时的配置。")

    def make_args(self) -> argparse.Namespace:
        default_profile = SUPPORTED_FOODS[DEFAULT_FOOD_NAME]
        return argparse.Namespace(
            attack_interval=None,
            attack_speed=DEFAULT_ATTACK_SPEED,
            attack_safety=DEFAULT_ATTACK_SAFETY_SECONDS,
            eat_at_food=DEFAULT_EAT_AT_FOOD,
            eat_hold=self.eat_hold_seconds_for_profile(default_profile),
            initial_food=DEFAULT_INITIAL_FOOD,
            initial_saturation=DEFAULT_INITIAL_SATURATION,
            sword_slot=DEFAULT_SWORD_SLOT,
            food_slots=list(DEFAULT_FOOD_SLOTS),
            stack_size=default_profile.stack_size,
            eat_on_start=False,
            dry_run=False,
            start_active=False,
            duration=None,
        )

    def translate_worker_message(self, message: str) -> str:
        eat_match = re.search(r"slot (\d+)", message)
        rotate_match = re.search(r"Current slot is now (\d+)", message)

        if message.startswith("Eating attempt") and eat_match:
            return f"正在自动进食：使用第 {eat_match.group(1)} 格中的 {self.get_food_profile().name}。"
        if message.startswith("Rotated food slot") and rotate_match:
            return f"当前食物格已轮换，下一格是第 {rotate_match.group(1)} 格。"
        translated = self.translate_error_message(message)
        if translated != message:
            return f"配置无效：{translated}"
        return message

    def worker_main(self) -> None:
        try:
            run_automation_loop(
                self.make_args(),
                self.controller,
                self.state,
                stop_event=self.stop_event,
                logger=self.log_from_worker,
                attack_interval_provider=self.get_attack_interval,
                slot_selection_provider=self.get_slot_selection,
                food_profile_provider=self.get_food_profile,
                eat_hold_provider=self.get_eat_hold_seconds,
            )
        except Exception as exc:
            if not self.closing:
                self.root.after(0, self.show_worker_error, str(exc))

    def log_from_worker(self, message: str) -> None:
        if not self.closing:
            translated = self.translate_worker_message(message)
            self.root.after(0, self.message_var.set, translated)

    def show_worker_error(self, message: str) -> None:
        translated = self.translate_worker_message(message)
        self.status_var.set("状态：已停止")
        self.message_var.set(translated)
        messagebox.showerror("自动化已停止", translated, parent=self.root)

    def close(self) -> None:
        self.closing = True
        self.state.set_active(False)
        self.stop_event.set()
        self.controller.release_buttons()
        self.hotkey_listener.stop()
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    try:
        MinecraftAfkGui(root)
    except SystemExit as exc:
        return int(exc.code or 0)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
