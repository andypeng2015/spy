#!/usr/bin/env python3
"""Corridor racer game using the raytracer"""

import math
import time
import sys
import os
import random
from raytracer import Vec3, Ray, Sphere, Plane, trace_ray
from dataclasses import dataclass
from typing import List, Optional

# Game state
@dataclass
class GameObject:
    pos: Vec3  # Position relative to player
    type: str  # 'coin' or 'obstacle'

@dataclass
class GameState:
    player_x: float = 0.0  # Horizontal position (-2 to 2)
    player_z: float = 0.0  # Forward position (always 0, objects move)
    speed: float = 5.0  # Units per second
    score: int = 0
    game_over: bool = False
    objects: List[GameObject] = None

    def __post_init__(self):
        if self.objects is None:
            self.objects = []


class CheckeredPlane:
    """Plane with animated checkerboard pattern"""
    def __init__(self, point: Vec3, normal: Vec3, base_color, alt_color, checker_size: float, offset_z: float = 0):
        self.point = point
        self.normal = normal.normalize()
        self.base_color = base_color
        self.alt_color = alt_color
        self.checker_size = checker_size
        self.offset_z = offset_z

    def intersect(self, ray: Ray):
        from raytracer import HitRecord

        denom = self.normal.dot(ray.direction)
        if abs(denom) < 0.0001:
            return None

        t = (self.point - ray.origin).dot(self.normal) / denom
        if t < 0.001:
            return None

        point = ray.origin + ray.direction * t

        # Animated checkerboard
        z_adjusted = point.z + self.offset_z
        checker_x = int(point.x / self.checker_size)
        checker_z = int(z_adjusted / self.checker_size)

        if (checker_x + checker_z) % 2 == 0:
            color = self.base_color
        else:
            color = self.alt_color

        return HitRecord(point, self.normal, t, color)


def render_frame(width: int, height: int, state: GameState, z_offset: float) -> str:
    """Render game frame"""
    camera_pos = Vec3(state.player_x, 0, state.player_z)

    # Create corridor walls and floor
    objects = [
        # Floor - moving checkerboard
        CheckeredPlane(
            Vec3(0, -1.5, 0),
            Vec3(0, 1, 0),
            (0.3, 0.3, 0.3),
            (0.6, 0.6, 0.6),
            1.5,
            z_offset
        ),
        # Left wall - vertical stripes
        CheckeredPlane(
            Vec3(-3, 0, 0),
            Vec3(1, 0, 0),
            (0.4, 0.2, 0.2),
            (0.6, 0.3, 0.3),
            1.0,
            z_offset
        ),
        # Right wall - vertical stripes
        CheckeredPlane(
            Vec3(3, 0, 0),
            Vec3(-1, 0, 0),
            (0.2, 0.2, 0.4),
            (0.3, 0.3, 0.6),
            1.0,
            z_offset
        ),
        # Ceiling
        CheckeredPlane(
            Vec3(0, 1.5, 0),
            Vec3(0, -1, 0),
            (0.2, 0.2, 0.2),
            (0.3, 0.3, 0.3),
            1.0,
            z_offset
        ),
    ]

    # Add player representation - green sphere centered at bottom of view
    player_sphere = Sphere(Vec3(state.player_x, -0.8, -1.5), 0.35, (0.2, 1.0, 0.3))
    objects.append(player_sphere)

    # Add game objects (coins and obstacles)
    for obj in state.objects:
        if obj.type == 'coin':
            # Gold coins
            objects.append(Sphere(obj.pos, 0.3, (1.0, 0.9, 0.2)))
        elif obj.type == 'obstacle':
            # Red dangerous balls
            objects.append(Sphere(obj.pos, 0.4, (1.0, 0.2, 0.2)))

    light_dir = Vec3(0.3, 1, -0.5).normalize()

    aspect_ratio = width / height
    fov = math.pi / 3

    # Build frame
    buffer = []
    for y in range(height):
        line = []
        for x in range(width):
            px = (2 * (x + 0.5) / width - 1) * aspect_ratio * math.tan(fov / 2)
            py = (1 - 2 * (y + 0.5) / height) * math.tan(fov / 2)

            direction = Vec3(px, py, -1).normalize()
            ray = Ray(camera_pos, direction)

            r, g, b = trace_ray(ray, objects, light_dir)

            r_int = int(min(255, r * 255))
            g_int = int(min(255, g * 255))
            b_int = int(min(255, b * 255))

            line.append(f'\033[48;2;{r_int};{g_int};{b_int}m ')

        line.append('\033[0m\n')
        buffer.append(''.join(line))

    return ''.join(buffer)


def spawn_objects(state: GameState, spawn_z: float):
    """Spawn new coins or obstacles"""
    if random.random() < 0.3:  # 30% chance to spawn something
        obj_type = 'coin' if random.random() < 0.7 else 'obstacle'
        # Random x position in corridor
        x_pos = random.uniform(-2, 2)
        # Spawn ahead at spawn_z
        state.objects.append(GameObject(
            Vec3(x_pos, 0, spawn_z),
            obj_type
        ))


def update_game(state: GameState, dt: float, player_input: Optional[str]):
    """Update game state"""
    if state.game_over:
        return

    # Handle player input
    if player_input == 'left':
        state.player_x = max(-2.5, state.player_x - 5 * dt)
    elif player_input == 'right':
        state.player_x = min(2.5, state.player_x + 5 * dt)

    # Move objects toward player
    new_objects = []
    for obj in state.objects:
        obj.pos.z += state.speed * dt

        # Check collision
        if obj.pos.z > -0.5:  # Object reached player
            dist = math.sqrt((obj.pos.x - state.player_x) ** 2 + obj.pos.z ** 2)
            if dist < 0.5:  # Collision
                if obj.type == 'coin':
                    state.score += 10
                    continue  # Remove coin
                elif obj.type == 'obstacle':
                    state.game_over = True
                    return

        # Keep object if still visible
        if obj.pos.z < 20:
            new_objects.append(obj)

    state.objects = new_objects

    # Spawn new objects
    spawn_objects(state, -20)

    # Increase speed over time
    state.speed += 0.5 * dt


def read_input():
    """Non-blocking input reading"""
    import select
    if select.select([sys.stdin], [], [], 0)[0]:
        char = sys.stdin.read(1)
        if char == '\x1b':  # ESC sequence
            sys.stdin.read(1)  # [
            arrow = sys.stdin.read(1)
            if arrow == 'D':
                return 'left'
            elif arrow == 'C':
                return 'right'
        elif char == 'q':
            return 'quit'
    return None


def game_loop():
    """Main game loop"""
    # Get terminal size
    term_size = os.get_terminal_size()
    width = term_size.columns
    height = term_size.lines - 2

    state = GameState()

    # Setup terminal
    print('\033[?1049h', end='')  # Alternate screen
    print('\033[?25l', end='')     # Hide cursor

    # Set terminal to raw mode for immediate input
    import tty
    import termios
    old_settings = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())

    last_time = time.time()
    z_offset = 0.0

    try:
        while not state.game_over:
            current_time = time.time()
            dt = current_time - last_time
            last_time = current_time

            # Read player input
            player_input = read_input()
            if player_input == 'quit':
                break

            # Update game
            update_game(state, dt, player_input)

            # Update z offset for moving texture
            z_offset += state.speed * dt

            # Render
            frame = render_frame(width, height, state, z_offset)

            # Display
            info = f"\n\033[1;33mScore: {state.score}\033[0m | Speed: {state.speed:.1f} | \033[1;32mArrows\033[0m: move | \033[1;31mq\033[0m: quit"
            sys.stdout.write('\033[H' + frame + info)
            sys.stdout.flush()

            # Cap frame rate
            time.sleep(0.016)  # ~60 FPS

        # Game over
        if state.game_over:
            game_over_msg = f"\n\n\033[1;31m=== GAME OVER ===\033[0m\n\033[1;33mFinal Score: {state.score}\033[0m\n\nPress any key to exit..."
            sys.stdout.write(game_over_msg)
            sys.stdout.flush()
            sys.stdin.read(1)

    finally:
        # Restore terminal
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print('\033[?25h', end='')     # Show cursor
        print('\033[?1049l', end='')   # Exit alternate screen
        print(f"\nGame ended. Final score: {state.score}")


if __name__ == '__main__':
    game_loop()
