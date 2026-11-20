"""LANE: 게임 규칙과 메인 루프.

그리는 일은 ui.py, 오래 걸리는 일(분석 등)은 workers.py가 맡는다.
"""
import math
import random

import pygame

import config as C
from ui import Renderer


# ============================================================
# 플레이어: 이동(관성), 대시, 잔상
# ============================================================

KEY_ALIASES = {
    pygame.K_UP: "Up", pygame.K_KP8: "Up", pygame.K_w: "Up",
    pygame.K_DOWN: "Down", pygame.K_KP2: "Down", pygame.K_s: "Down",
    pygame.K_LEFT: "Left", pygame.K_KP4: "Left", pygame.K_a: "Left",
    pygame.K_RIGHT: "Right", pygame.K_KP6: "Right", pygame.K_d: "Right",
}


class Player:

    def __init__(self):
        self.reset()

    def reset(self):
        self.x = C.WIDTH / 2
        self.y = C.HEIGHT / 2
        self.visual_r = C.PLAYER_VISUAL_R
        self.hit_r = C.PLAYER_HIT_R

        self.vx = 0.0
        self.vy = 0.0
        self.keys = {"Up": False, "Down": False, "Left": False, "Right": False}
        self.last_dir = (0, -1)

        self.dash_cooldown = 0
        self.is_dashing = False
        self.dash_vx = 0.0
        self.dash_vy = 0.0
        self.dash_grace = 0
        self.dash_buffer = 0

        self.ghosts = []
        self.move_trails = []

    @property
    def invulnerable(self):
        return self.is_dashing or self.dash_grace > 0

    # ---------------- 입력 ----------------
    def press(self, name):
        self.keys[name] = True

    def release(self, name):
        self.keys[name] = False

    def try_dash(self):
        if self.dash_cooldown == 0:
            self._start_dash()
        elif self.dash_cooldown <= C.DASH_BUFFER:
            self.dash_buffer = C.DASH_BUFFER

    def _input_axis(self):
        mx = (1 if self.keys["Right"] else 0) - (1 if self.keys["Left"] else 0)
        my = (1 if self.keys["Down"] else 0) - (1 if self.keys["Up"] else 0)
        return mx, my

    def _start_dash(self):
        mx, my = self._input_axis()
        if mx == 0 and my == 0:
            mx, my = self.last_dir
        if mx != 0 or my != 0:
            length = math.hypot(mx, my)
            self.dash_vx = (mx / length) * C.DASH_SPEED
            self.dash_vy = (my / length) * C.DASH_SPEED
            self.is_dashing = True
            self.dash_grace = C.DASH_GRACE_AFTER_START
            self.dash_cooldown = C.DASH_COOLDOWN
            self.dash_buffer = 0

    # ---------------- 업데이트 ----------------
    def update(self):
        old_x, old_y = self.x, self.y
        was_dashing = self.is_dashing

        if self.is_dashing:
            self.ghosts.append({"x": self.x, "y": self.y, "life": C.DASH_GHOST_LIFE, "max": C.DASH_GHOST_LIFE})
            self.x += self.dash_vx
            self.y += self.dash_vy
            self.dash_vx *= C.DASH_DECAY
            self.dash_vy *= C.DASH_DECAY
            if abs(self.dash_vx) < 0.5 and abs(self.dash_vy) < 0.5:
                self.is_dashing = False
                self.dash_grace = C.DASH_GRACE_AFTER_END

        if not self.is_dashing:
            self._walk()

        self._clamp_to_box()

        if was_dashing:
            self._add_move_trail(old_x, old_y, self.x, self.y)

        if self.dash_cooldown > 0:
            self.dash_cooldown -= 1
            if self.dash_cooldown == 0 and self.dash_buffer > 0:
                self._start_dash()
        if self.dash_buffer > 0:
            self.dash_buffer -= 1
        if self.dash_grace > 0:
            self.dash_grace -= 1

    def _walk(self):
        mx, my = self._input_axis()
        length = math.hypot(mx, my)
        if length > 0:
            mx /= length
            my /= length
            self.vx += mx * C.PLAYER_ACCELERATION
            self.vy += my * C.PLAYER_ACCELERATION
            self.last_dir = (1 if mx > 0 else (-1 if mx < 0 else 0),
                             1 if my > 0 else (-1 if my < 0 else 0))
        else:
            self.vx *= C.PLAYER_FRICTION
            self.vy *= C.PLAYER_FRICTION

        speed = math.hypot(self.vx, self.vy)
        if speed > C.PLAYER_MAX_SPEED:
            scale = C.PLAYER_MAX_SPEED / speed
            self.vx *= scale
            self.vy *= scale
        if abs(self.vx) < 0.025:
            self.vx = 0
        if abs(self.vy) < 0.025:
            self.vy = 0

        self.x += self.vx
        self.y += self.vy

    def _clamp_to_box(self):
        r = self.visual_r
        if self.x < C.BOX_LEFT + r:
            self.x = C.BOX_LEFT + r
            self.vx = 0
        elif self.x > C.BOX_RIGHT - r:
            self.x = C.BOX_RIGHT - r
            self.vx = 0
        if self.y < C.BOX_TOP + r:
            self.y = C.BOX_TOP + r
            self.vy = 0
        elif self.y > C.BOX_BOTTOM - r:
            self.y = C.BOX_BOTTOM - r
            self.vy = 0

    def _add_move_trail(self, ox, oy, nx, ny):
        if math.hypot(nx - ox, ny - oy) < 0.5:
            return
        self.move_trails.append({"start": (ox, oy), "end": (nx, ny),
                                 "life": C.DASH_TRAIL_LIFE, "max": C.DASH_TRAIL_LIFE})

    def update_fx(self):
        for ghost in self.ghosts[:]:
            ghost["life"] -= 1
            if ghost["life"] <= 0:
                self.ghosts.remove(ghost)
        for trail in self.move_trails[:]:
            trail["life"] -= 1
            if trail["life"] <= 0:
                self.move_trails.remove(trail)

    # ---------------- 그리기 ----------------

# ============================================================
# 가로/세로 일반 레이저
# ============================================================

class LaserField:

    def __init__(self):
        self.reset()

    def reset(self):
        self.items = []
        self.last_axis = None
        self.streak = 0
        self.triple_batch_id = 0

    # ---------------- 위치/방향 선택 ----------------
    def choose_position(self, forced_type, player):
        margin = C.TRIPLE_WALL_MARGIN

        if forced_type == "H":
            if player.y < (C.BOX_TOP + C.BOX_BOTTOM) / 2:
                pos = (C.BOX_BOTTOM - margin) - random.uniform(C.LASER_OFFSET_MIN, C.LASER_OFFSET_MAX)
            else:
                pos = (C.BOX_TOP + margin) + random.uniform(C.LASER_OFFSET_MIN, C.LASER_OFFSET_MAX)
            return "H", max(C.BOX_TOP + margin, min(C.BOX_BOTTOM - margin, pos))

        if forced_type == "V":
            if player.x < (C.BOX_LEFT + C.BOX_RIGHT) / 2:
                pos = (C.BOX_RIGHT - margin) - random.uniform(C.LASER_OFFSET_MIN, C.LASER_OFFSET_MAX)
            else:
                pos = (C.BOX_LEFT + margin) + random.uniform(C.LASER_OFFSET_MIN, C.LASER_OFFSET_MAX)
            return "V", max(C.BOX_LEFT + margin, min(C.BOX_RIGHT - margin, pos))

        return self.choose_position(random.choice(["H", "V"]), player)

    def next_single_direction(self):
        if self.streak >= 3:
            direction = "V" if self.last_axis == "H" else "H"
        else:
            direction = random.choice(["H", "V"])
        if direction == self.last_axis:
            self.streak += 1
        else:
            self.last_axis = direction
            self.streak = 1
        return direction

    # ---------------- 생성 ----------------
    def spawn(self, laser_type, player, target_player=False,
              lifetime=C.SINGLE_LIFETIME, single=True):
        if target_player:
            pos = player.y if laser_type == "H" else player.x
        else:
            laser_type, pos = self.choose_position(laser_type, player)

        laser = {
            "type": laser_type, "pos": pos,
            "warn": True, "timer": C.LASER_WARNING_TIME,
            "life": lifetime, "single": single,
            "blink": False, "hit_grace": 0,
            "triple_batch": None, "remove_timer": None,
        }
        self.items.append(laser)
        return laser

    def spawn_single(self, player):
        self.spawn(self.next_single_direction(), player, target_player=True)

    def spawn_triple(self, player):
        for laser in self.items:
            if not laser["single"] and laser["remove_timer"] is None:
                laser["remove_timer"] = C.TRIPLE_REMOVE_DELAY

        self.triple_batch_id += 1
        directions = ["H", "H", "V"] if random.choice([True, False]) else ["H", "V", "V"]
        random.shuffle(directions)
        for direction in directions:
            laser = self.spawn(direction, player, lifetime=C.TRIPLE_LIFETIME,
                               single=False)
            laser["triple_batch"] = self.triple_batch_id

    def limit(self, max_count=C.MAX_LASERS):
        while len(self.items) > max_count:
            self.items.pop(0)

    # ---------------- 업데이트 ----------------
    def update(self, player):
        """플레이어가 맞으면 True."""
        for laser in self.items[:]:
            if laser["single"]:
                laser["life"] -= 1
                if laser["life"] <= 0:
                    self.items.remove(laser)
                    continue
            elif laser["remove_timer"] is not None:
                laser["remove_timer"] -= 1
                if laser["remove_timer"] <= 0:
                    self.items.remove(laser)
                    continue

            if laser["warn"]:
                laser["timer"] -= 1
                laser["blink"] = not laser["blink"]
                if laser["timer"] <= 0:
                    laser["warn"] = False
                    laser["blink"] = False
                    laser["hit_grace"] = C.LASER_HIT_GRACE
                continue

            if laser["hit_grace"] > 0:
                laser["hit_grace"] -= 1
                continue

            if player.invulnerable:
                continue
            if laser["type"] == "H" and abs(player.y - laser["pos"]) < player.hit_r:
                return True
            if laser["type"] == "V" and abs(player.x - laser["pos"]) < player.hit_r:
                return True
        return False

    # ---------------- 그리기 ----------------

# ============================================================
# 발사형 레이저
# ============================================================

class RamSystem:

    def __init__(self):
        self.reset()

    def reset(self):
        self.attack = None
        self.trails = []

    @property
    def active(self):
        return self.attack is not None

    @staticmethod
    def warning_time(score):
        step = score // C.RAM_WARNING_STEP_FRAMES
        return max(C.RAM_WARNING_MIN_TIME,
                   C.RAM_WARNING_TIME - step * C.RAM_WARNING_REDUCTION)

    # ---------------- 시작 ----------------
    def start(self, player, score):
        if self.attack is not None:
            return

        distances = {"left": player.x, "right": C.WIDTH - player.x,
                     "top": player.y, "bottom": C.HEIGHT - player.y}
        edge = max(distances, key=distances.get)
        d = C.RAM_SPAWN_DISTANCE

        if edge == "left":
            sx, sy = -d, random.uniform(C.RAM_SPAWN_MARGIN, C.HEIGHT - C.RAM_SPAWN_MARGIN)
        elif edge == "right":
            sx, sy = C.WIDTH + d, random.uniform(C.RAM_SPAWN_MARGIN, C.HEIGHT - C.RAM_SPAWN_MARGIN)
        elif edge == "top":
            sx, sy = random.uniform(C.RAM_SPAWN_MARGIN, C.WIDTH - C.RAM_SPAWN_MARGIN), -d
        else:
            sx, sy = random.uniform(C.RAM_SPAWN_MARGIN, C.WIDTH - C.RAM_SPAWN_MARGIN), C.HEIGHT + d

        dx, dy = player.x - sx, player.y - sy
        length = math.hypot(dx, dy) or 1
        warn = self.warning_time(score)

        self.attack = {
            "phase": "warning", "timer": warn, "warning_duration": warn,
            "dir_x": dx / length, "dir_y": dy / length,
            "source_x": sx, "source_y": sy,
            "beam_pos": 0, "hit_grace": 0,
        }

    # ---------------- 업데이트 ----------------
    def update(self, player, check_collision=True):
        """플레이어가 맞으면 True."""
        hit = self._update_attack(player, check_collision)

        for trail in self.trails[:]:
            trail["life"] -= 1
            if trail["life"] <= 0:
                self.trails.remove(trail)
        return hit

    def _update_attack(self, player, check_collision):
        a = self.attack
        if a is None:
            return False

        if a["phase"] == "warning":
            a["timer"] -= 1
            dx, dy = player.x - a["source_x"], player.y - a["source_y"]
            length = math.hypot(dx, dy)
            if length:
                a["dir_x"], a["dir_y"] = dx / length, dy / length
            if a["timer"] <= 0:
                a["phase"] = "fire"
                a["beam_pos"] = 0
                a["hit_grace"] = C.RAM_HIT_GRACE
            return False

        dx, dy = a["dir_x"], a["dir_y"]
        old_pos = a["beam_pos"]
        a["beam_pos"] += C.RAM_SPEED
        new_pos = a["beam_pos"]

        self.trails.append({
            "start": (a["source_x"] + dx * old_pos, a["source_y"] + dy * old_pos),
            "end": (a["source_x"] + dx * new_pos, a["source_y"] + dy * new_pos),
            "life": C.RAM_TRAIL_LIFETIME,
        })

        hit = False
        if a["hit_grace"] > 0:
            a["hit_grace"] -= 1
        elif check_collision and not player.invulnerable:
            rx, ry = player.x - a["source_x"], player.y - a["source_y"]
            along = rx * dx + ry * dy
            side = abs(rx * (-dy) + ry * dx)
            r = player.hit_r
            if (new_pos - r < along < new_pos + C.RAM_LENGTH + r
                    and side < C.RAM_THICKNESS / 2 + r):
                hit = True

        if a["beam_pos"] > math.hypot(C.WIDTH, C.HEIGHT) * 2:
            self.attack = None
        return hit

    # ---------------- 그리기 ----------------

# ============================================================
# 레이저 생성 담당 (지금은 랜덤 타이머, 나중에 패턴 기반으로 교체)
# ============================================================

class RandomSpawner:

    def __init__(self):
        self.reset()

    def reset(self):
        self.startup_delay = C.STARTUP_DELAY
        self.initial_triple_delay = None
        self.initial_ram_delay = None
        self.single_timer = 0
        self.triple_timer = 0
        self.ram_timer = 0

    @staticmethod
    def intervals(score):
        step = score // C.INTERVAL_STEP_FRAMES
        single = max(C.SINGLE_MIN_INTERVAL, C.SINGLE_START_INTERVAL - step * C.SINGLE_REDUCTION)
        triple = max(C.TRIPLE_MIN_INTERVAL, C.TRIPLE_START_INTERVAL - step * C.TRIPLE_REDUCTION)
        ram = max(C.RAM_MIN_INTERVAL, C.RAM_START_INTERVAL - step * C.RAM_REDUCTION)
        return single, triple, ram

    def update(self, score, player, lasers, ram):
        if self.startup_delay > 0:
            self.startup_delay -= 1
            if self.startup_delay == 0:
                lasers.spawn_single(player)
                self.initial_triple_delay = C.LASER_WARNING_TIME
                self.initial_ram_delay = None
                self.single_timer = 0
                self.triple_timer = 0
                self.ram_timer = 0
            return

        self.single_timer += 1
        self.ram_timer += 1
        single_iv, triple_iv, ram_iv = self.intervals(score)

        if self.initial_triple_delay is not None:
            self.initial_triple_delay -= 1
            if self.initial_triple_delay <= 0:
                lasers.spawn_triple(player)
                self.initial_triple_delay = None
                self.initial_ram_delay = C.LASER_WARNING_TIME
                self.triple_timer = 0
        elif self.initial_ram_delay is not None:
            self.initial_ram_delay -= 1
            if self.initial_ram_delay <= 0:
                ram.start(player, score)
                self.initial_ram_delay = None
                self.ram_timer = 0
        else:
            self.triple_timer += 1

        if self.single_timer >= single_iv:
            self.single_timer = 0
            lasers.spawn_single(player)

        opening_done = self.initial_triple_delay is None and self.initial_ram_delay is None

        if opening_done and self.triple_timer >= triple_iv:
            self.triple_timer = 0
            lasers.spawn_triple(player)

        if opening_done and self.ram_timer >= ram_iv and not ram.active:
            self.ram_timer = 0
            ram.start(player, score)

# ============================================================
# 사망 연출 상태 (그리기는 ui.py)
# ============================================================

class DeathFx:

    def __init__(self):
        self.reset()

    def reset(self):
        self.fragments = []
        self.sparks = []
        self.ring = None
        self.shake = 0.0
        self.hitstop = 0
        self.death_timer = 0
        self.can_restart = False

    def start(self):
        self.hitstop = C.HITSTOP_FRAMES
        self.death_timer = 0
        self.can_restart = False

    @property
    def ready_for_text(self):
        return self.death_timer >= C.RESTART_DELAY

    def _explode(self, player):
        x, y, r = player.x, player.y, player.visual_r
        n = C.DEATH_FRAGMENTS
        for i in range(n):
            a1 = math.pi * 2 * i / n
            a2 = math.pi * 2 * (i + 1) / n
            pts = [(0, 0), (r * math.cos(a1), r * math.sin(a1)),
                   (r * math.cos(a2), r * math.sin(a2))]
            gx = sum(p[0] for p in pts) / 3
            gy = sum(p[1] for p in pts) / 3
            mid = (a1 + a2) / 2
            sp = random.uniform(2.5, 6.5)
            self.fragments.append({
                "local": [(p[0] - gx, p[1] - gy) for p in pts],
                "cx": x + gx, "cy": y + gy,
                "vx": math.cos(mid) * sp, "vy": math.sin(mid) * sp,
                "angle": random.uniform(0, math.pi * 2),
                "spin": random.uniform(-0.4, 0.4),
                "life": 45, "max": 45})

        for _ in range(C.DEATH_SPARKS):
            a = random.uniform(0, math.pi * 2)
            sp = random.uniform(2, 9)
            self.sparks.append({
                "x": x, "y": y,
                "vx": math.cos(a) * sp, "vy": math.sin(a) * sp,
                "size": random.uniform(1.2, 3),
                "color": random.choice([C.CYAN, "#ffffff", C.DANGER]),
                "life": 28, "max": 28})

        self.ring = {"x": x, "y": y, "r": 6, "dr": 6.0, "life": 18, "max": 18}
        self.shake = C.DEATH_SHAKE

    def update(self, player):
        if self.hitstop > 0:
            self.hitstop -= 1
            if self.hitstop == 0:
                self._explode(player)
            return

        for f in self.fragments[:]:
            f["cx"] += f["vx"]
            f["cy"] += f["vy"]
            f["vx"] *= 0.96
            f["vy"] = f["vy"] * 0.96 + 0.12
            f["angle"] += f["spin"]
            f["life"] -= 1
            if f["life"] <= 0:
                self.fragments.remove(f)

        for p in self.sparks[:]:
            p["x"] += p["vx"]
            p["y"] += p["vy"]
            p["vx"] *= 0.9
            p["vy"] *= 0.9
            p["life"] -= 1
            if p["life"] <= 0:
                self.sparks.remove(p)

        if self.ring:
            r = self.ring
            r["r"] += r["dr"]
            r["dr"] *= 0.9
            r["life"] -= 1
            if r["life"] <= 0:
                self.ring = None

        if self.shake > 0.5:
            self.shake *= 0.85
        elif self.shake:
            self.shake = 0

        self.death_timer += 1
        if self.death_timer >= C.RESTART_DELAY:
            self.can_restart = True

    def shake_offset(self, game_over):
        if self.shake > 0.5 and game_over:
            return (random.uniform(-self.shake, self.shake),
                    random.uniform(-self.shake, self.shake))
        return 0, 0

# ============================================================
# 게임 본체: 부품을 연결하고 입력과 루프를 돈다
# ============================================================

class Game:

    def __init__(self, spawner=None):
        pygame.init()
        self.ui = Renderer()
        self.clock = pygame.time.Clock()

        self.player = Player()
        self.lasers = LaserField()
        self.ram = RamSystem()
        self.fx = DeathFx()
        self.spawner = spawner or RandomSpawner()

        self.running = True
        self.reset_game()

    def reset_game(self):
        self.player.reset()
        self.lasers.reset()
        self.ram.reset()
        self.fx.reset()
        self.spawner.reset()
        self.score = 0
        self.started = False
        self.game_over = False

    # ---------------- 입력 ----------------
    def on_keydown(self, event):
        name = KEY_ALIASES.get(event.key)
        if name:
            self.player.press(name)
            self.started = True
        elif event.key == pygame.K_SPACE:
            if self.started and not self.game_over:
                self.player.try_dash()
        elif event.key == pygame.K_RETURN and self.game_over and self.fx.can_restart:
            self.reset_game()
            self.started = True

    def on_keyup(self, event):
        name = KEY_ALIASES.get(event.key)
        if name:
            self.player.release(name)

    # ---------------- 업데이트 ----------------
    def die(self):
        if self.game_over:
            return
        self.game_over = True
        self.fx.start()

    def update_death(self):
        self.ram.update(self.player, check_collision=False)
        self.fx.update(self.player)

    def update_game(self):
        p = self.player
        p.update()
        self.score += 1

        self.spawner.update(self.score, p, self.lasers, self.ram)

        if self.ram.update(p) or self.lasers.update(p):
            self.die()
            return

        self.lasers.limit()
        p.update_fx()

    # ---------------- 메인 루프 ----------------
    def run(self):
        while self.running:
            self.clock.tick(C.FPS)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    self.on_keydown(event)
                elif event.type == pygame.KEYUP:
                    self.on_keyup(event)

            if self.game_over:
                self.update_death()
            elif self.started:
                self.update_game()

            self.ui.draw(self)

        pygame.quit()


if __name__ == "__main__":
    Game().run()