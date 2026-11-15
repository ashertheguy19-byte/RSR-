import math
import random
import sys
import pygame

# =====================================================================
# RSR — MEDIEVAL PIXEL ART CASTLE SIEGE & MULTI-LAYER ELEVATION ENGINE
# =====================================================================

WIDTH, HEIGHT = 1024, 640
FPS = 60
PIXEL_SCALE = 3

# Elevation Layers (0 = Down-Down, 1 = Down, 2 = Up, 3 = Up-Up)
LAYERS = [
    {"id": 0, "code": "DOWN-DOWN", "name": "Subterranean Dungeon Tunnels", "bg": (24, 20, 32)},
    {"id": 1, "code": "DOWN", "name": "Outer Gates & Royal Courtyard", "bg": (58, 92, 52)},
    {"id": 2, "code": "UP", "name": "Castle Battlements & Towers", "bg": (74, 118, 152)},
    {"id": 3, "code": "UP-UP", "name": "High Sky Tactical Airspace", "bg": (34, 66, 128)},
]

# Pixel Art Sprite Matrices (1 = primary, 2 = secondary/armor, 3 = accent/gold/fire, 4 = dark)
PALETTES = {
    "defender": {1: (220, 185, 150), 2: (65, 115, 210), 3: (240, 205, 65), 4: (30, 35, 50)},
    "attacker": {1: (210, 175, 145), 2: (195, 55, 55), 3: (150, 155, 165), 4: (35, 25, 25)},
    "sapper":   {1: (185, 155, 125), 2: (95, 75, 55), 3: (245, 130, 40), 4: (25, 20, 20)},
    "heli":     {1: (75, 95, 75), 2: (45, 60, 45), 3: (245, 210, 65), 4: (20, 25, 20)},
}

KNIGHT_ART = [
    "....2222....",
    "...233332...",
    "...211112...",
    "...214142...",
    "..22222222..",
    ".3222332223.",
    ".3222222223.",
    "..4.2222.4..",
    "....22.22...",
    "...44...44..",
]

HELI_ART = [
    "..444444444444..",
    ".......44.......",
    "....1111111.....",
    ".441113331111...",
    "44411133311111..",
    "....111111111...",
    "     22...22    ",
    "    2222.2222   ",
]


def bake_sprite(art, palette, scale=PIXEL_SCALE):
    h = len(art)
    w = len(art[0])
    surf = pygame.Surface((w * scale, h * scale), pygame.SRCALPHA)
    for r, row in enumerate(art):
        for c, ch in enumerate(row):
            if ch != "." and int(ch) in palette:
                pygame.draw.rect(
                    surf,
                    palette[int(ch)],
                    (c * scale, r * scale, scale, scale),
                )
    return surf


class Unit:
    def __init__(self, team, x, y, layer, kind="knight"):
        self.team = team
        self.x = float(x)
        self.y = float(y)
        self.layer = layer
        self.kind = kind
        self.hp = 140 if kind == "heli" else (70 if kind == "sapper" else 100)
        self.max_hp = self.hp
        self.speed = 2.4 if kind == "heli" else (1.3 if kind == "sapper" else 1.1)
        self.damage = 28 if kind == "heli" else 14
        self.cooldown = 0

    def update(self, game):
        if self.cooldown > 0:
            self.cooldown -= 1

        direction = 1 if self.team == "attacker" else -1
        target_unit = None

        for other in game.units:
            if other.team != self.team and other.layer == self.layer and other.hp > 0:
                if abs(other.x - self.x) < 38 and abs(other.y - self.y) < 42:
                    target_unit = other
                    break

        if target_unit:
            if self.cooldown == 0:
                target_unit.hp -= self.damage
                self.cooldown = 35
                game.spawn_particles(target_unit.x, target_unit.y, (255, 90, 70), 5)
            return

        if self.team == "attacker":
            if self.layer in (0, 1) and game.outer_gate_hp > 0 and self.x >= 530:
                if self.cooldown == 0:
                    dmg = self.damage * (2 if self.kind == "sapper" else 1)
                    game.outer_gate_hp = max(0, game.outer_gate_hp - dmg)
                    self.cooldown = 40
                    game.spawn_particles(560, self.y, (235, 190, 90), 6)
                return

            if self.x >= 850:
                if self.cooldown == 0:
                    game.keep_hp = max(0, game.keep_hp - self.damage)
                    self.cooldown = 40
                    game.spawn_particles(880, self.y, (255, 70, 70), 8)
                return

        self.x += direction * self.speed
        if self.x < 40 or self.x > WIDTH - 40:
            self.hp = 0


class Particle:
    def __init__(self, x, y, color):
        self.x = float(x)
        self.y = float(y)
        self.vx = random.uniform(-2.5, 2.5)
        self.vy = random.uniform(-3.0, 1.0)
        self.life = random.randint(18, 35)
        self.color = color

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= 1


class RSRGame:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("RSR — Medieval Pixel Castle Defense")
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        self.clock = pygame.time.Clock()
        self.font_sm = pygame.font.SysFont("consolas", 16, bold=True)
        self.font_md = pygame.font.SysFont("consolas", 22, bold=True)
        self.font_lg = pygame.font.SysFont("consolas", 38, bold=True)

        self.sprites = {
            "defender": bake_sprite(KNIGHT_ART, PALETTES["defender"]),
            "attacker": bake_sprite(KNIGHT_ART, PALETTES["attacker"]),
            "sapper": bake_sprite(KNIGHT_ART, PALETTES["sapper"]),
            "heli": bake_sprite(HELI_ART, PALETTES["heli"], scale=4),
        }

        self.state = "MENU"
        self.mode = "defender"
        self.current_layer = 1

        self.admin_unlocked = False
        self.console_open = False
        self.console_text = ""
        self.status_banner = ""
        self.banner_timer = 0
        self.nuke_flash = 0

        self.reset_battle("defender")

    def reset_battle(self, mode):
        self.mode = mode
        self.current_layer = 1
        self.gold = 300 if mode != "tutorial" else 999
        self.outer_gate_hp = 500
        self.keep_hp = 800
        self.units = []
        self.particles = []
        self.spawn_timer = 0
        self.tutorial_step = 0
        self.winner = None

        if mode == "tutorial":
            self.notify("TUTORIAL: Press UP/DOWN arrows to switch elevation layers!")

    def notify(self, msg, duration=210):
        self.status_banner = msg
        self.banner_timer = duration

    def spawn_particles(self, x, y, color, count=10):
        for _ in range(count):
            self.particles.append(Particle(x, y, color))

    def spawn_unit(self, team, kind="knight", layer=None, x=None, y=None):
        if layer is None:
            layer = self.current_layer
        if x is None:
            x = 90 if team == "attacker" else 810
        if y is None:
            y = random.randint(240, 480)
        self.units.append(Unit(team, x, y, layer, kind))

    def execute_command(self, raw):
        cmd = raw.strip()
        parts = cmd.split()
        if not parts:
            return

        head = parts[0].lower()

        if head == "/admin":
            secret = " ".join(parts[1:])
            if secret == "Sigma 18":
                self.admin_unlocked = True
                self.notify("ADMIN ACCESS GRANTED [Sigma 18]: /heli and /nuke unlocked!")
            else:
                self.notify("ACCESS DENIED: Invalid Admin Passcode.")
            return

        if not self.admin_unlocked:
            self.notify("LOCKED: Admin Commands required (/admin <password>).")
            return

        if head == "/gold":
            self.gold += 1000
            self.notify("ADMIN: +1000 Royal Gold added.")

        elif head == "/heli":
            if self.current_layer != 3:
                self.notify("ELEVATION ERROR: You must go UP-UP (High Sky) to deploy a Helicopter!")
            else:
                team = "defender" if self.mode in ("defender", "tutorial") else "attacker"
                start_x = 840 if team == "defender" else 110
                self.spawn_unit(team, kind="heli", layer=3, x=start_x, y=280)
                self.notify("ADMIN AIR SUPPORT: Tactical Helicopter deployed in High Sky!")

        elif head == "/nuke":
            if self.current_layer != 3:
                self.notify("ELEVATION ERROR: You must go UP-UP (High Sky) to launch a Nuke!")
            else:
                self.nuke_flash = 45
                enemy_team = "attacker" if self.mode in ("defender", "tutorial") else "defender"
                wiped = 0
                for u in self.units:
                    if u.team == enemy_team and u.hp > 0:
                        u.hp = 0
                        wiped += 1
                if self.mode == "attacker":
                    self.outer_gate_hp = 0
                    self.keep_hp = max(0, self.keep_hp - 400)
                self.spawn_particles(WIDTH // 2, HEIGHT // 2, (255, 220, 90), 65)
                self.notify(f"TACTICAL NUKE DETONATED FROM UP-UP! Eliminated {wiped} enemy forces!")
        else:
            self.notify(f"Unknown command: {head}. Try /admin Sigma 18, /heli, /nuke, /gold")

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if self.state == "MENU":
                    if event.key == pygame.K_1:
                        self.reset_battle("defender")
                        self.state = "PLAYING"
                    elif event.key == pygame.K_2:
                        self.reset_battle("attacker")
                        self.state = "PLAYING"
                    elif event.key == pygame.K_3:
                        self.reset_battle("tutorial")
                        self.state = "PLAYING"
                    continue

                if self.state == "GAMEOVER":
                    if event.key == pygame.K_r:
                        self.state = "MENU"
                    continue

                if self.console_open:
                    if event.key == pygame.K_RETURN:
                        self.execute_command(self.console_text)
                        self.console_text = ""
                        self.console_open = False
                    elif event.key == pygame.K_ESCAPE:
                        self.console_open = False
                    elif event.key == pygame.K_BACKSPACE:
                        self.console_text = self.console_text[:-1]
                    else:
                        if event.unicode and len(self.console_text) < 42:
                            self.console_text += event.unicode
                    continue

                if event.key in (pygame.K_SLASH, pygame.K_BACKQUOTE):
                    self.console_open = True
                    self.console_text = "/"
                    continue

                if event.key in (pygame.K_UP, pygame.K_w):
                    if self.current_layer < 3:
                        self.current_layer += 1
                        if self.mode == "tutorial" and self.tutorial_step == 0:
                            self.tutorial_step = 1
                            self.notify("TUTORIAL: Great! Press SPACE to deploy troops on this layer.")
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    if self.current_layer > 0:
                        self.current_layer -= 1
                        if self.mode == "tutorial" and self.tutorial_step == 0:
                            self.tutorial_step = 1
                            self.notify("TUTORIAL: Great! Press SPACE to deploy troops on this layer.")

                elif event.key == pygame.K_SPACE:
                    if self.current_layer == 3 and not self.admin_unlocked:
                        self.notify("High Sky (UP-UP) requires Admin Helicopters or Nukes!")
                    elif self.gold >= 50:
                        self.gold -= 50
                        team = "attacker" if self.mode == "attacker" else "defender"
                        kind = "sapper" if (team == "attacker" and self.current_layer == 0) else "knight"
                        self.spawn_unit(team, kind=kind, layer=self.current_layer)
                        if self.mode == "tutorial" and self.tutorial_step == 1:
                            self.tutorial_step = 2
                            self.notify("TUTORIAL: Awesome! Press '/' to open the Command Console.")

                elif event.key == pygame.K_e and self.mode in ("defender", "tutorial"):
                    if self.gold >= 75 and self.current_layer in (1, 2):
                        self.gold -= 75
                        for u in self.units:
                            if u.team == "attacker" and u.layer == 1 and 490 <= u.x <= 610:
                                u.hp -= 65
                        self.spawn_particles(555, 360, (255, 130, 30), 25)
                        self.notify("BOILING OIL POURED AT THE OUTER GATE!")

    def update(self):
        if self.banner_timer > 0:
            self.banner_timer -= 1
        if self.nuke_flash > 0:
            self.nuke_flash -= 1

        if self.state != "PLAYING":
            return

        self.spawn_timer += 1
        if self.spawn_timer % 90 == 0:
            self.gold += 25

        if self.mode != "tutorial" and self.spawn_timer % 180 == 0:
            ai_team = "attacker" if self.mode == "defender" else "defender"
            ai_layer = random.choice([0, 1, 1, 2])
            ai_kind = "sapper" if (ai_team == "attacker" and ai_layer == 0) else "knight"
            self.spawn_unit(ai_team, kind=ai_kind, layer=ai_layer)

        for u in self.units:
            if u.hp > 0:
                u.update(self)
        self.units = [u for u in self.units if u.hp > 0]

        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0]

        if self.keep_hp <= 0:
            self.winner = "ATTACKERS BREACHED THE ROYAL KEEP!"
            self.state = "GAMEOVER"
        elif self.mode == "defender" and self.spawn_timer > 5400 and not any(u.team == "attacker" for u in self.units):
            self.winner = "DEFENDERS HELD THE CASTLE!"
            self.state = "GAMEOVER"

    def draw_environment(self):
        layer_info = LAYERS[self.current_layer]
        self.screen.fill(layer_info["bg"])

        if self.current_layer == 0:
            pygame.draw.rect(self.screen, (38, 32, 48), (0, 210, WIDTH, 310))
            for x in range(0, WIDTH, 64):
                pygame.draw.rect(self.screen, (52, 44, 66), (x + 4, 214, 56, 40), 2)
                pygame.draw.rect(self.screen, (52, 44, 66), (x + 4, 476, 56, 40), 2)
            if self.outer_gate_hp > 0:
                pygame.draw.rect(self.screen, (110, 85, 60), (545, 210, 30, 310))

        elif self.current_layer == 1:
            pygame.draw.rect(self.screen, (124, 102, 74), (0, 220, 560, 290))
            pygame.draw.rect(self.screen, (135, 138, 145), (560, 210, 320, 310))
            for gx in range(560, 880, 40):
                for gy in range(210, 520, 40):
                    pygame.draw.rect(self.screen, (112, 115, 122), (gx, gy, 40, 40), 1)
            if self.outer_gate_hp > 0:
                pygame.draw.rect(self.screen, (85, 88, 96), (540, 180, 40, 360))
                pygame.draw.rect(self.screen, (135, 88, 42), (548, 250, 24, 220))
            pygame.draw.rect(self.screen, (95, 98, 108), (880, 150, 144, 420))
            pygame.draw.rect(self.screen, (185, 45, 45), (900, 180, 26, 65))

        elif self.current_layer == 2:
            pygame.draw.rect(self.screen, (62, 105, 58), (0, 430, WIDTH, 210))
            pygame.draw.rect(self.screen, (115, 118, 128), (520, 220, 440, 280))
            for cx in range(520, 960, 40):
                pygame.draw.rect(self.screen, (145, 148, 158), (cx, 195, 24, 25))

        elif self.current_layer == 3:
            for cloud_x in (140, 430, 760):
                pygame.draw.rect(self.screen, (215, 228, 248), (cloud_x, 160, 120, 28))
                pygame.draw.rect(self.screen, (235, 242, 255), (cloud_x + 20, 145, 80, 24))
            pygame.draw.rect(self.screen, (55, 78, 115), (540, 500, 380, 90))

    def draw_hud(self):
        layer_info = LAYERS[self.current_layer]
        pygame.draw.rect(self.screen, (18, 20, 28), (0, 0, WIDTH, 86))
        pygame.draw.line(self.screen, (210, 175, 65), (0, 86), (WIDTH, 86), 2)

        elev_surf = self.font_md.render(
            f"ELEVATION [{layer_info['code']}]: {layer_info['name']}",
            True,
            (245, 210, 75),
        )
        self.screen.blit(elev_surf, (18, 12))

        stats = (
            f"GOLD: {self.gold}  |  OUTER GATE: {self.outer_gate_hp}  |  "
            f"ROYAL KEEP: {self.keep_hp}  |  ADMIN: {'UNLOCKED' if self.admin_unlocked else 'LOCKED'}"
        )
        stat_surf = self.font_sm.render(stats, True, (220, 225, 235))
        self.screen.blit(stat_surf, (18, 48))

        for idx, lyr in enumerate(reversed(LAYERS)):
            real_idx = 3 - idx
            box_y = 110 + idx * 36
            active = real_idx == self.current_layer
            col = (245, 205, 65) if active else (95, 105, 120)
            pygame.draw.rect(self.screen, (20, 24, 34), (WIDTH - 165, box_y, 148, 28))
            pygame.draw.rect(self.screen, col, (WIDTH - 165, box_y, 148, 28), 2)
            lbl = self.font_sm.render(f"{'> ' if active else '  '}{lyr['code']}", True, col)
            self.screen.blit(lbl, (WIDTH - 156, box_y + 6))

        pygame.draw.rect(self.screen, (18, 20, 28), (0, HEIGHT - 36, WIDTH, 36))
        controls = "[UP/DOWN] Change Layer  |  [SPACE] Deploy Unit (50g)  |  [E] Boiling Oil (75g)  |  [/] Command Console"
        ctrl_surf = self.font_sm.render(controls, True, (185, 195, 210))
        self.screen.blit(ctrl_surf, (18, HEIGHT - 26))

        if self.banner_timer > 0 and self.status_banner:
            b_surf = self.font_sm.render(self.status_banner, True, (255, 245, 140))
            bx = WIDTH // 2 - b_surf.get_width() // 2
            pygame.draw.rect(self.screen, (25, 28, 40), (bx - 12, 96, b_surf.get_width() + 24, 28))
            self.screen.blit(b_surf, (bx, 102))

        if self.console_open:
            pygame.draw.rect(self.screen, (12, 14, 20), (40, HEIGHT - 82, WIDTH - 80, 36))
            pygame.draw.rect(self.screen, (95, 225, 125), (40, HEIGHT - 82, WIDTH - 80, 36), 2)
            c_surf = self.font_md.render(f"CMD> {self.console_text}_", True, (95, 225, 125))
            self.screen.blit(c_surf, (52, HEIGHT - 75))

    def draw_menu(self):
        self.screen.fill((22, 24, 34))
        title = self.font_lg.render("R S R", True, (245, 205, 65))
        sub = self.font_md.render("MEDIEVAL PIXEL ART CASTLE SIEGE", True, (200, 210, 225))
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 130))
        self.screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 185))

        options = [
            "[1] DEFENDER MODE — Hold the Gates, Courtyard & Keep",
            "[2] ATTACKER MODE — Breach the Gates & Capture the Keep",
            "[3] TUTORIAL MODE — Learn Elevation Layers & Admin Commands",
        ]
        for i, opt in enumerate(options):
            surf = self.font_md.render(opt, True, (235, 240, 250))
            self.screen.blit(surf, (WIDTH // 2 - surf.get_width() // 2, 280 + i * 52))

    def run(self):
        while True:
            self.handle_events()
            self.update()

            if self.state == "MENU":
                self.draw_menu()
            else:
                self.draw_environment()
                for u in self.units:
                    if u.layer == self.current_layer:
                        spr = self.sprites[u.kind if u.kind in self.sprites else u.team]
                        self.screen.blit(spr, (int(u.x - spr.get_width() // 2), int(u.y - spr.get_height() // 2)))
                        hp_w = int(32 * (u.hp / u.max_hp))
                        pygame.draw.rect(self.screen, (40, 40, 40), (int(u.x - 16), int(u.y - 26), 32, 4))
                        pygame.draw.rect(self.screen, (80, 220, 95), (int(u.x - 16), int(u.y - 26), hp_w, 4))

                for p in self.particles:
                    pygame.draw.rect(self.screen, p.color, (int(p.x), int(p.y), 4, 4))

                if self.nuke_flash > 0:
                    flash = pygame.Surface((WIDTH, HEIGHT))
                    flash.fill((255, 245, 200))
                    flash.set_alpha(min(220, self.nuke_flash * 5))
                    self.screen.blit(flash, (0, 0))

                self.draw_hud()

                if self.state == "GAMEOVER":
                    over = self.font_lg.render(self.winner, True, (255, 215, 75))
                    rst = self.font_md.render("Press [R] to return to Main Menu", True, (240, 240, 240))
                    self.screen.blit(over, (WIDTH // 2 - over.get_width() // 2, HEIGHT // 2 - 30))
                    self.screen.blit(rst, (WIDTH // 2 - rst.get_width() // 2, HEIGHT // 2 + 25))

            pygame.display.flip()
            self.clock.tick(FPS)


if __name__ == "__main__":
    RSRGame().run()
