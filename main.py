import json
import hashlib
import os
import random
from enum import Enum, auto

import arcade

SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
SCREEN_TITLE = "StickyCubes"

PLAYER_SIZE = 26

OBSTACLE_WIDTH = 30
OBSTACLE_MIN_HEIGHT = 50
OBSTACLE_MAX_HEIGHT = 110
OBSTACLE_SPEED = 120
OBSTACLE_SPAWN_INTERVAL = 2.4

GRAVITY_TOP_Y = SCREEN_HEIGHT - PLAYER_SIZE / 2 - 10
GRAVITY_BOTTOM_Y = PLAYER_SIZE / 2 + 10
PHYSICS_GRAVITY = 1.4


class GameState(Enum):
    MENU = auto()
    GAME = auto()
    GAME_OVER = auto()
    PAUSE = auto()
    SKINS = auto()


class GravityDirection(Enum):
    DOWN = auto()
    UP = auto()


class GravityCubeGame(arcade.Window):
    def __init__(self):
        super().__init__(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE, resizable=False)
        arcade.set_background_color(arcade.color.DARK_MIDNIGHT_BLUE)

        self.state = GameState.MENU
        self.gravity = GravityDirection.DOWN

        self.player_sprite = arcade.SpriteSolidColor(PLAYER_SIZE, PLAYER_SIZE, arcade.color.BRIGHT_GREEN)
        self.player_x = SCREEN_WIDTH // 3
        self.player_y = GRAVITY_BOTTOM_Y
        self.obstacles = []
        self.wall_list = arcade.SpriteList()
        self.physics_engine = None

        self.time_since_last_spawn = 0.0
        self.score = 0

        self.switch_cooldown = 0.35
        self.time_since_switch = 0.0
        self.coins = 0
        self.best_score = 0
        self.skins = [
            {"name": "Классический", "color": arcade.color.BRIGHT_GREEN, "price": 0, "owned": True, "rarity": 0},
            {"name": "Ледяной", "color": arcade.color.CYAN, "price": 20, "owned": False, "rarity": 1},
            {"name": "Тёмный", "color": arcade.color.DARK_BLUE, "price": 35, "owned": False, "rarity": 1},
            {"name": "Золотой", "color": arcade.color.GOLD, "price": 350, "owned": False, "rarity": 2},
        ]
        self.current_skin_index = 0

        self.menu_buttons = {
            "start": {"x": 0, "y": 0, "w": 220, "h": 60},
            "skins": {"x": 0, "y": 0, "w": 220, "h": 60},
            "quit": {"x": 0, "y": 0, "w": 220, "h": 60},
        }

        self._setup_menu_layout()
        self._load_progress()
        self.click_sound = arcade.load_sound(":resources:sounds/upgrade4.wav")

    def setup_game(self):
        self.state = GameState.GAME
        self.gravity = GravityDirection.DOWN
        self.time_since_last_spawn = 0.0
        self.score = 0
        self.time_since_switch = 0.0
        self.player_x = SCREEN_WIDTH // 3
        self.player_y = GRAVITY_BOTTOM_Y
        self.player_sprite.center_x = self.player_x
        self.player_sprite.center_y = self.player_y
        self.obstacles = []

        if len(self.wall_list) == 0:
            floor_height = 4
            floor = arcade.SpriteSolidColor(SCREEN_WIDTH, floor_height, (0, 0, 0, 0))
            bottom_line = GRAVITY_BOTTOM_Y - PLAYER_SIZE / 2
            floor.center_x = SCREEN_WIDTH / 2
            floor.center_y = bottom_line - floor_height / 2
            self.wall_list.append(floor)

            ceil_height = 4
            ceil = arcade.SpriteSolidColor(SCREEN_WIDTH, ceil_height, (0, 0, 0, 0))
            top_line = GRAVITY_TOP_Y + PLAYER_SIZE / 2
            ceil.center_x = SCREEN_WIDTH / 2
            ceil.center_y = top_line + ceil_height / 2
            self.wall_list.append(ceil)

        self.physics_engine = arcade.PhysicsEnginePlatformer(
            self.player_sprite,
            gravity_constant=PHYSICS_GRAVITY,
            walls=self.wall_list,
        )

    def _setup_menu_layout(self):
        center_x = SCREEN_WIDTH // 2
        center_y = SCREEN_HEIGHT // 2

        self.menu_buttons["start"]["x"] = center_x
        self.menu_buttons["start"]["y"] = center_y + 70

        self.menu_buttons["skins"]["x"] = center_x
        self.menu_buttons["skins"]["y"] = center_y

        self.menu_buttons["quit"]["x"] = center_x
        self.menu_buttons["quit"]["y"] = center_y - 70

    def _save_path(self):
        return os.path.join(os.path.dirname(__file__), "save.dat")

    def _save_progress(self):
        data = {
            "coins": self.coins,
            "owned": [s["owned"] for s in self.skins],
            "current": self.current_skin_index,
            "best": self.best_score,
        }
        raw = json.dumps(data, separators=(",", ":"), sort_keys=True)
        secret = "sticky_cubes_secret_v1"
        checksum = hashlib.sha256((secret + raw).encode("utf-8")).hexdigest()
        try:
            with open(self._save_path(), "w", encoding="utf-8") as f:
                f.write(checksum + "\n" + raw)
        except OSError:
            pass

    def _load_progress(self):
        path = self._save_path()
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                first = f.readline().strip()
                raw = f.read().strip()
        except OSError:
            return
        if not first or not raw:
            return
        secret = "sticky_cubes_secret_v1"
        expected = hashlib.sha256((secret + raw).encode("utf-8")).hexdigest()
        if expected != first:
            return
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return
        coins = data.get("coins")
        owned = data.get("owned")
        current = data.get("current", 0)
        best = data.get("best", 0)
        if isinstance(coins, int) and coins >= 0:
            self.coins = coins
        if isinstance(owned, list):
            for s, flag in zip(self.skins, owned):
                if isinstance(flag, bool):
                    s["owned"] = flag
        if isinstance(current, int) and 0 <= current < len(self.skins):
            self.current_skin_index = current
        if isinstance(best, int) and best >= 0:
            self.best_score = best

    def on_update(self, delta_time):
        if self.state != GameState.GAME:
            return

        self.time_since_switch += delta_time

        if self.physics_engine is not None:
            self.physics_engine.update()
            self.player_x = self.player_sprite.center_x
            self.player_y = self.player_sprite.center_y

            snap_eps = 2.0
            if self.gravity == GravityDirection.DOWN:
                target_y = GRAVITY_BOTTOM_Y
            else:
                target_y = GRAVITY_TOP_Y
            if abs(self.player_y - target_y) <= snap_eps:
                self.player_y = target_y
                self.player_sprite.center_y = target_y
                self.player_sprite.change_y = 0

        self.time_since_last_spawn += delta_time
        if self.time_since_last_spawn >= OBSTACLE_SPAWN_INTERVAL:
            self.time_since_last_spawn = 0.0
            self.spawn_obstacles_pair()

        new_obstacles = []
        for ob in self.obstacles:
            ob_x = ob["x"] - OBSTACLE_SPEED * delta_time
            ob["x"] = ob_x
            if ob_x + ob["w"] / 2 >= 0:
                new_obstacles.append(ob)
            else:
                self.score += 1
        self.obstacles = new_obstacles

        hitbox_scale = 0.7
        half_w = PLAYER_SIZE * hitbox_scale / 2
        half_h = PLAYER_SIZE * hitbox_scale / 2
        player_left = self.player_x - half_w
        player_right = self.player_x + half_w
        player_bottom = self.player_y - half_h
        player_top = self.player_y + half_h

        for ob in self.obstacles:
            ob_half_w = ob["w"] * hitbox_scale / 2
            ob_half_h = ob["h"] * hitbox_scale / 2
            ob_left = ob["x"] - ob_half_w
            ob_right = ob["x"] + ob_half_w
            ob_bottom = ob["y"] - ob_half_h
            ob_top = ob["y"] + ob_half_h
            if not (player_right < ob_left or player_left > ob_right or player_top < ob_bottom or player_bottom > ob_top):
                if self.score > self.best_score:
                    self.best_score = self.score
                self.coins += self.score
                self._save_progress()
                self.state = GameState.GAME_OVER
                break

    def spawn_obstacles_pair(self):
        height = random.randint(OBSTACLE_MIN_HEIGHT, OBSTACLE_MAX_HEIGHT)
        side_top = random.choice([False, True])

        if side_top:
            obstacle = {
                "x": SCREEN_WIDTH + OBSTACLE_WIDTH / 2,
                "y": SCREEN_HEIGHT - height / 2,
                "w": OBSTACLE_WIDTH,
                "h": height,
                "top": True,
            }
        else:
            obstacle = {
                "x": SCREEN_WIDTH + OBSTACLE_WIDTH / 2,
                "y": height / 2,
                "w": OBSTACLE_WIDTH,
                "h": height,
                "top": False,
            }

        self.obstacles.append(obstacle)

    def on_draw(self):
        self.clear()

        if self.state == GameState.MENU:
            self.draw_menu()
        elif self.state == GameState.GAME:
            self.draw_game()
        elif self.state == GameState.PAUSE:
            self.draw_game()
            self.draw_pause_overlay()
        elif self.state == GameState.SKINS:
            self.draw_skins_menu()
        elif self.state == GameState.GAME_OVER:
            self.draw_game()
            self.draw_game_over_overlay()

    def draw_menu(self):
        arcade.draw_text(
            "StickyCubes",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT - 120,
            arcade.color.WHITE,
            font_size=40,
            anchor_x="center",
        )

        for key, rect in self.menu_buttons.items():
            x = rect["x"]
            y = rect["y"]
            w = rect["w"]
            h = rect["h"]
            left = x - w / 2
            right = x + w / 2
            bottom = y - h / 2
            top = y + h / 2
            color = arcade.color.DARK_SLATE_GRAY
            arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, color)
            arcade.draw_lrbt_rectangle_outline(left, right, bottom, top, arcade.color.WHITE, 2)

            if key == "start":
                label = "Начать игру"
            elif key == "skins":
                label = "Скины"
            else:
                label = "Выход"
            arcade.draw_text(
                label,
                x,
                y - 10,
                arcade.color.WHITE,
                font_size=18,
                anchor_x="center",
            )

        arcade.draw_text(
            "Управление: ЛКМ - сменить гравитацию, ESC - меню",
            SCREEN_WIDTH / 2,
            40,
            arcade.color.LIGHT_GRAY,
            font_size=14,
            anchor_x="center",
        )
        arcade.draw_text(
            f"Монеты: {self.coins}",
            SCREEN_WIDTH / 2,
            80,
            arcade.color.GOLD,
            font_size=16,
            anchor_x="center",
        )

    def draw_game(self):
        arcade.draw_line(0, GRAVITY_BOTTOM_Y - PLAYER_SIZE / 2, SCREEN_WIDTH, GRAVITY_BOTTOM_Y - PLAYER_SIZE / 2, arcade.color.GRAY, 2)
        arcade.draw_line(0, GRAVITY_TOP_Y + PLAYER_SIZE / 2, SCREEN_WIDTH, GRAVITY_TOP_Y + PLAYER_SIZE / 2, arcade.color.GRAY, 2)

        for ob in self.obstacles:
            x = ob["x"]
            y = ob["y"]
            w = ob["w"]
            h = ob["h"]
            left = x - w / 2
            right = x + w / 2
            bottom = y - h / 2
            top = y + h / 2
            arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, arcade.color.CADMIUM_RED if not ob.get("top") else arcade.color.CADMIUM_ORANGE)

        player_left = self.player_x - PLAYER_SIZE / 2
        player_right = self.player_x + PLAYER_SIZE / 2
        player_bottom = self.player_y - PLAYER_SIZE / 2
        player_top = self.player_y + PLAYER_SIZE / 2
        color = self.skins[self.current_skin_index]["color"]
        arcade.draw_lrbt_rectangle_filled(player_left, player_right, player_bottom, player_top, color)

        arcade.draw_text(
            f"Счёт: {self.score}",
            10,
            SCREEN_HEIGHT - 30,
            arcade.color.WHITE,
            font_size=18,
        )
        arcade.draw_text(
            f"Рекорд: {self.best_score}",
            10,
            SCREEN_HEIGHT - 55,
            arcade.color.LIGHT_GRAY,
            font_size=16,
        )

    def draw_game_over_overlay(self):
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT, (0, 0, 0, 180))

        arcade.draw_text(
            "Вы разбились!",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT / 2 + 60,
            arcade.color.WHITE,
            font_size=32,
            anchor_x="center",
        )
        arcade.draw_text(
            f"Итоговый счёт: {self.score}",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT / 2 + 20,
            arcade.color.LIGHT_GRAY,
            font_size=20,
            anchor_x="center",
        )
        arcade.draw_text(
            f"Монеты всего: {self.coins}",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT / 2 - 10,
            arcade.color.GOLD,
            font_size=18,
            anchor_x="center",
        )
        arcade.draw_text(
            f"Рекорд: {self.best_score}",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT / 2 - 40,
            arcade.color.GOLD,
            font_size=18,
            anchor_x="center",
        )

        arcade.draw_text(
            "ЛКМ - начать заново   |   ESC - в меню",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT / 2 - 70,
            arcade.color.WHITE,
            font_size=18,
            anchor_x="center",
        )

    def draw_pause_overlay(self):
        arcade.draw_lrbt_rectangle_filled(0, SCREEN_WIDTH, 0, SCREEN_HEIGHT, (0, 0, 0, 140))
        arcade.draw_text(
            "Пауза",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT / 2 + 40,
            arcade.color.WHITE,
            font_size=32,
            anchor_x="center",
        )
        arcade.draw_text(
            "ESC - продолжить   |   M - меню",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT / 2 - 10,
            arcade.color.LIGHT_GRAY,
            font_size=18,
            anchor_x="center",
        )
        arcade.draw_text(
            "Внимание: выход в меню сбросит текущую попытку (очки не добавятся к монетам).",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT / 2 - 50,
            arcade.color.ORANGE,
            font_size=14,
            anchor_x="center",
        )

    def draw_skins_menu(self):
        arcade.draw_text(
            "Скины куба",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT - 80,
            arcade.color.WHITE,
            font_size=34,
            anchor_x="center",
        )
        arcade.draw_text(
            f"Монеты: {self.coins}",
            SCREEN_WIDTH / 2,
            SCREEN_HEIGHT - 130,
            arcade.color.GOLD,
            font_size=18,
            anchor_x="center",
        )
        start_y = SCREEN_HEIGHT - 190
        row_h = 70
        box_w = 380
        box_h = 55
        order = sorted(range(len(self.skins)), key=lambda i: self.skins[i]["rarity"])
        for row, idx in enumerate(order):
            skin = self.skins[idx]
            y = start_y - row * row_h
            x = SCREEN_WIDTH / 2
            left = x - box_w / 2
            right = x + box_w / 2
            bottom = y - box_h / 2
            top = y + box_h / 2
            bg = arcade.color.DARK_SLATE_GRAY if idx != self.current_skin_index else arcade.color.DARK_GREEN
            arcade.draw_lrbt_rectangle_filled(left, right, bottom, top, bg)
            arcade.draw_lrbt_rectangle_outline(left, right, bottom, top, arcade.color.WHITE, 2)
            cube_left = left + 20
            cube_right = cube_left + 40
            cube_bottom = y - 20
            cube_top = y + 20
            arcade.draw_lrbt_rectangle_filled(cube_left, cube_right, cube_bottom, cube_top, skin["color"])
            name = skin["name"]
            status = "Куплен" if skin["owned"] else f"{skin['price']} монет"
            arcade.draw_text(
                name,
                cube_right + 20,
                y + 8,
                arcade.color.WHITE,
                font_size=16,
                anchor_x="left",
            )
            arcade.draw_text(
                status,
                cube_right + 20,
                y - 18,
                arcade.color.LIGHT_GRAY,
                font_size=14,
                anchor_x="left",
            )
        arcade.draw_text(
            "ESC - назад в меню",
            SCREEN_WIDTH / 2,
            40,
            arcade.color.LIGHT_GRAY,
            font_size=16,
            anchor_x="center",
        )

    def on_mouse_press(self, x, y, button, modifiers):
        if button != arcade.MOUSE_BUTTON_LEFT:
            return

        if self.state == GameState.MENU:
            self.handle_menu_click(x, y)
        elif self.state == GameState.SKINS:
            self.handle_skins_click(x, y)
        elif self.state == GameState.GAME:
            ground_snap = 4
            on_bottom = abs(self.player_y - GRAVITY_BOTTOM_Y) <= ground_snap
            on_top = abs(self.player_y - GRAVITY_TOP_Y) <= ground_snap
            if self.time_since_switch >= self.switch_cooldown and (on_bottom or on_top):
                self.gravity = GravityDirection.UP if self.gravity == GravityDirection.DOWN else GravityDirection.DOWN
                if self.physics_engine is not None:
                    if self.gravity == GravityDirection.DOWN:
                        self.physics_engine.gravity_constant = abs(self.physics_engine.gravity_constant)
                    else:
                        self.physics_engine.gravity_constant = -abs(self.physics_engine.gravity_constant)
                self.time_since_switch = 0.0
        elif self.state == GameState.GAME_OVER:
            self.setup_game()

    def handle_menu_click(self, x, y):
        for key, rect in self.menu_buttons.items():
            left = rect["x"] - rect["w"] / 2
            right = rect["x"] + rect["w"] / 2
            bottom = rect["y"] - rect["h"] / 2
            top = rect["y"] + rect["h"] / 2
            if left <= x <= right and bottom <= y <= top:
                if hasattr(self, "click_sound") and self.click_sound:
                    arcade.play_sound(self.click_sound)
                if key == "start":
                    self.setup_game()
                elif key == "skins":
                    self.state = GameState.SKINS
                elif key == "quit":
                    arcade.close_window()

    def handle_skins_click(self, x, y):
        start_y = SCREEN_HEIGHT - 190
        row_h = 70
        box_w = 380
        box_h = 55
        order = sorted(range(len(self.skins)), key=lambda i: self.skins[i]["rarity"])
        for row, idx in enumerate(order):
            skin = self.skins[idx]
            row_y = start_y - row * row_h
            cx = SCREEN_WIDTH / 2
            left = cx - box_w / 2
            right = cx + box_w / 2
            bottom = row_y - box_h / 2
            top = row_y + box_h / 2
            if left <= x <= right and bottom <= y <= top:
                if hasattr(self, "click_sound") and self.click_sound:
                    arcade.play_sound(self.click_sound)
                if skin["owned"]:
                    self.current_skin_index = idx
                else:
                    if self.coins >= skin["price"]:
                        self.coins -= skin["price"]
                        skin["owned"] = True
                        self.current_skin_index = idx
                        self._save_progress()
                self._save_progress()
                break

    def on_key_press(self, symbol, modifiers):
        if symbol == arcade.key.ESCAPE:
            if self.state == GameState.GAME:
                self.state = GameState.PAUSE
            elif self.state == GameState.PAUSE:
                self.state = GameState.GAME
            elif self.state == GameState.GAME_OVER:
                self.state = GameState.MENU
            elif self.state == GameState.SKINS:
                self.state = GameState.MENU
        if symbol == arcade.key.M and self.state == GameState.PAUSE:
            self.state = GameState.MENU


def main():
    window = GravityCubeGame()
    arcade.run()


if __name__ == "__main__":
    main()

