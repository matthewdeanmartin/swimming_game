import pygame
import sys

# Initialize Pygame
pygame.init()
pygame.font.init()  # Initialize the font module

# --- Constants ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
FPS = 60

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (0, 0, 255)
LIGHT_BLUE = (173, 216, 230)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
PURPLE = (128, 0, 128)
PINK = (255, 192, 203)
GRAY = (128, 128, 128)
BUTTON_COLOR = (100, 100, 200)
BUTTON_HOVER_COLOR = (150, 150, 220)
TEXT_COLOR = WHITE

# Fonts
DEFAULT_FONT_SIZE = 30
LARGE_FONT_SIZE = 50
SMALL_FONT_SIZE = 20
try:
    DEFAULT_FONT = pygame.font.SysFont("Arial", DEFAULT_FONT_SIZE)
    LARGE_FONT = pygame.font.SysFont("Arial", LARGE_FONT_SIZE)
    SMALL_FONT = pygame.font.SysFont("Arial", SMALL_FONT_SIZE)
except pygame.error:
    DEFAULT_FONT = pygame.font.Font(None, DEFAULT_FONT_SIZE)  # Fallback font
    LARGE_FONT = pygame.font.Font(None, LARGE_FONT_SIZE)
    SMALL_FONT = pygame.font.Font(None, SMALL_FONT_SIZE)

# Game States
STATE_MAIN_MENU = "main_menu"
STATE_PLAYER_SELECT = "player_select"
STATE_PLAYER_SETUP = "player_setup"
STATE_SHOP = "shop"
STATE_RACE = "race"
STATE_RACE_END = "race_end"

# Player Configuration
# Easily change key bindings here
# Each player dict: 'move' = key for swimming, 'exit' = key for exiting water (finishing)
PLAYER_CONTROLS_CONFIG = [
    {'name': 'Player 1', 'move': pygame.K_p, 'exit': pygame.K_v, 'color': RED},
    {'name': 'Player 2', 'move': pygame.K_j, 'exit': pygame.K_n, 'color': GREEN},
    {'name': 'Player 3', 'move': pygame.K_f, 'exit': pygame.K_w, 'color': YELLOW},
    {'name': 'Player 4', 'move': pygame.K_q, 'exit': pygame.K_o, 'color': PURPLE},
]

# Shop Items
# Structure: { "id": {"name": "Item Name", "price": 0, "type": "flipper/goggles/snack/swimsuit", "effect_value": 0, "tier": 0 (0=basic, 1=better, 2=best)}}
# Effect value: speed boost for flippers/goggles, duration/intensity for snacks
SHOP_ITEMS = {
    "flipper_basic": {"name": "Basic Flippers", "price": 30, "type": "flipper", "effect_value": 0.1, "tier": 0},
    "flipper_pro": {"name": "Pro Flippers", "price": 60, "type": "flipper", "effect_value": 0.2, "tier": 1},
    "goggles_basic": {"name": "Basic Goggles", "price": 15, "type": "goggles", "effect_value": 0.05, "tier": 0},
    "goggles_good": {"name": "Good Goggles", "price": 30, "type": "goggles", "effect_value": 0.1, "tier": 1},
    "goggles_best": {"name": "Best Goggles", "price": 50, "type": "goggles", "effect_value": 0.15, "tier": 2},
    # Best goggles
    "snack_small": {"name": "Small Snack", "price": 10, "type": "snack", "effect_value": 5, "tier": 0},
    # 5 seconds boost
    "snack_medium": {"name": "Medium Snack", "price": 20, "type": "snack", "effect_value": 10, "tier": 1},
    "snack_large": {"name": "Large Snack", "price": 30, "type": "snack", "effect_value": 15, "tier": 2},  # Best snack
    "swimsuit_red": {"name": "Red Swimsuit", "price": 5, "type": "swimsuit", "color_value": RED, "tier": 0},
    "swimsuit_blue": {"name": "Blue Swimsuit", "price": 5, "type": "swimsuit", "color_value": BLUE, "tier": 0},
    "swimsuit_yellow": {"name": "Yellow Swimsuit", "price": 5, "type": "swimsuit", "color_value": YELLOW, "tier": 0},
    "swimsuit_green": {"name": "Green Swimsuit", "price": 5, "type": "swimsuit", "color_value": GREEN, "tier": 0},
    "swimsuit_purple": {"name": "Purple Swimsuit", "price": 5, "type": "swimsuit", "color_value": PURPLE, "tier": 0},
    "swimsuit_pink": {"name": "Pink Swimsuit", "price": 5, "type": "swimsuit", "color_value": PINK, "tier": 0},
    "swimsuit_black": {"name": "Black Swimsuit", "price": 5, "type": "swimsuit", "color_value": BLACK, "tier": 0},
}

# Race Configuration
RACE_LENGTH = SCREEN_WIDTH - 100  # Pixels to cover
LANE_HEIGHT = 100
LANE_PADDING = 10
START_X = 50
FINISH_LINE_X = START_X + RACE_LENGTH

# --- Global Variables ---
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Swimming Race Mania")
clock = pygame.time.Clock()
current_state = STATE_MAIN_MENU
num_players_selected = 0
players_data = []  # List to store Player objects
active_input_player_index = 0  # For name input
input_text = ""
shop_current_player_idx = 0  # Which player is currently shopping
race_winner = None


# --- Helper Functions ---
def draw_text(text, font, color, surface, x, y, center=False):
    textobj = font.render(text, True, color)
    textrect = textobj.get_rect()
    if center:
        textrect.center = (x, y)
    else:
        textrect.topleft = (x, y)
    surface.blit(textobj, textrect)
    return textrect


def create_button(text, rect_pos_size, base_color, hover_color, font, action=None):
    mouse_pos = pygame.mouse.get_pos()
    clicked = pygame.mouse.get_pressed()[0] == 1  # Left click

    rect = pygame.Rect(rect_pos_size)

    if rect.collidepoint(mouse_pos):
        pygame.draw.rect(screen, hover_color, rect, border_radius=10)
        if clicked and action:
            pygame.time.wait(200)  # Debounce click
            return action()  # Call the action function
    else:
        pygame.draw.rect(screen, base_color, rect, border_radius=10)

    draw_text(text, font, TEXT_COLOR, screen, rect.centerx, rect.centery, center=True)
    return None  # No action triggered or no action defined


# --- Player Class ---
class Player:
    def __init__(self, player_id, name, controls, color, start_coins=50):
        self.id = player_id
        self.name = name
        self.controls = controls  # {'move': key, 'exit': key}
        self.color = color
        self.coins = start_coins
        self.gear = {  # Item IDs from SHOP_ITEMS
            "flipper": None,
            "goggles": None,
            "snack": None,  # Snacks are consumed per race
            "swimsuit": None
        }
        self.x = START_X
        self.y = 0  # Will be set based on lane
        self.base_speed = 2  # Pixels per frame
        self.current_speed = self.base_speed
        self.snack_active_time = 0  # Countdown for snack effect
        self.finished_race = False
        self.finish_time = 0

    def update_speed(self):
        self.current_speed = self.base_speed
        if self.gear["flipper"]:
            self.current_speed += SHOP_ITEMS[self.gear["flipper"]]["effect_value"] * 10  # Scale effect
        if self.gear["goggles"]:
            self.current_speed += SHOP_ITEMS[self.gear["goggles"]]["effect_value"] * 10  # Scale effect

        if self.snack_active_time > 0:
            if self.gear["snack"]:  # Assuming snack gives a temporary flat boost
                self.current_speed += SHOP_ITEMS[self.gear["snack"]]["effect_value"] * 0.2  # Smaller, temporary boost
            self.snack_active_time -= 1 / FPS
            if self.snack_active_time <= 0:
                self.gear["snack"] = None  # Consume snack

    def move(self):
        if not self.finished_race:
            self.x += self.current_speed
            if self.x >= FINISH_LINE_X:
                self.x = FINISH_LINE_X
                self.finished_race = True
                # Record finish time (simple frame count for now)
                self.finish_time = pygame.time.get_ticks()

    def draw(self, surface, lane_y):
        self.y = lane_y + LANE_HEIGHT // 2
        player_rect = pygame.Rect(self.x - 15, self.y - 10, 30, 20)  # Simple rectangle for player

        player_color = self.color
        if self.gear["swimsuit"] and SHOP_ITEMS[self.gear["swimsuit"]]["type"] == "swimsuit":
            player_color = SHOP_ITEMS[self.gear["swimsuit"]]["color_value"]

        pygame.draw.rect(surface, player_color, player_rect, border_radius=5)
        draw_text(self.name[0], SMALL_FONT, BLACK, surface, self.x, self.y - 25, center=True)  # Initial

    def buy_item(self, item_id):
        item = SHOP_ITEMS[item_id]
        if self.coins >= item["price"]:
            # Constraint: Cannot have best goggles and best snack at the same time
            if item["type"] == "goggles" and item["tier"] == 2:  # Trying to buy best goggles
                if self.gear["snack"] and SHOP_ITEMS[self.gear["snack"]]["tier"] == 2:
                    print(f"{self.name} cannot buy best goggles with best snack equipped.")
                    return False  # Purchase failed
            if item["type"] == "snack" and item["tier"] == 2:  # Trying to buy best snack
                if self.gear["goggles"] and SHOP_ITEMS[self.gear["goggles"]]["tier"] == 2:
                    print(f"{self.name} cannot buy best snack with best goggles equipped.")
                    return False  # Purchase failed

            self.coins -= item["price"]
            if item["type"] in self.gear:  # flipper, goggles, swimsuit
                self.gear[item["type"]] = item_id
            elif item["type"] == "snack":  # Snacks are equipped for next race
                self.gear["snack"] = item_id  # Overwrite previous snack if any
            print(f"{self.name} bought {item['name']}. Coins left: {self.coins}")
            return True
        else:
            print(f"{self.name} has not enough coins for {item['name']}.")
            return False

    def use_snack(self):
        if self.gear["snack"] and not self.snack_active_time > 0:  # Can only use if not already active
            self.snack_active_time = SHOP_ITEMS[self.gear["snack"]]["effect_value"]  # Duration in seconds
            print(f"{self.name} used {SHOP_ITEMS[self.gear['snack']]['name']}")
            # Snack is consumed after its effect wears off (handled in update_speed)


# --- Game State Functions ---
def main_menu():
    global current_state, num_players_selected, players_data
    screen.fill(LIGHT_BLUE)
    draw_text("Swimming Race Mania!", LARGE_FONT, BLACK, screen, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4, center=True)

    if create_button("Start Game", (SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 - 50, 200, 50), BUTTON_COLOR,
                     BUTTON_HOVER_COLOR, DEFAULT_FONT, lambda: STATE_PLAYER_SELECT):
        current_state = STATE_PLAYER_SELECT
        return  # Exit to avoid processing other buttons in same frame

    if create_button("Shop", (SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 + 20, 200, 50), BUTTON_COLOR,
                     BUTTON_HOVER_COLOR, DEFAULT_FONT, lambda: STATE_SHOP if players_data else None):
        if players_data:  # Can only go to shop if players exist
            current_state = STATE_SHOP
            global shop_current_player_idx
            shop_current_player_idx = 0  # Reset to first player for shopping
        else:
            # Optionally, display a message "Set up players first"
            print("Please set up players before visiting the shop.")
        return

    if create_button("Quit", (SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT // 2 + 90, 200, 50), BUTTON_COLOR,
                     BUTTON_HOVER_COLOR, DEFAULT_FONT, pygame.quit):
        pygame.quit()
        sys.exit()


def player_select_screen():
    global current_state, num_players_selected
    screen.fill(LIGHT_BLUE)
    draw_text("Select Number of Players", LARGE_FONT, BLACK, screen, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 4, center=True)

    button_y_start = SCREEN_HEIGHT // 2 - 60
    button_height = 50
    button_spacing = 10

    def set_players_and_start_setup(num):
        global num_players_selected, current_state, active_input_player_index, input_text
        num_players_selected = num
        active_input_player_index = 0
        input_text = ""
        current_state = STATE_PLAYER_SETUP

    if create_button("2 Players", (SCREEN_WIDTH // 2 - 100, button_y_start, 200, button_height), BUTTON_COLOR,
                     BUTTON_HOVER_COLOR, DEFAULT_FONT, lambda: set_players_and_start_setup(2)): return
    if create_button("3 Players",
                     (SCREEN_WIDTH // 2 - 100, button_y_start + button_height + button_spacing, 200, button_height),
                     BUTTON_COLOR, BUTTON_HOVER_COLOR, DEFAULT_FONT, lambda: set_players_and_start_setup(3)): return
    if create_button("4 Players", (SCREEN_WIDTH // 2 - 100, button_y_start + 2 * (button_height + button_spacing), 200,
                                   button_height), BUTTON_COLOR, BUTTON_HOVER_COLOR, DEFAULT_FONT,
                     lambda: set_players_and_start_setup(4)): return

    if create_button("Back", (SCREEN_WIDTH // 2 - 100, button_y_start + 3 * (button_height + button_spacing) + 20, 200,
                              button_height), GRAY, BUTTON_HOVER_COLOR, DEFAULT_FONT, lambda: STATE_MAIN_MENU):
        current_state = STATE_MAIN_MENU


def player_setup_screen():
    global current_state, players_data, active_input_player_index, input_text, num_players_selected
    screen.fill(LIGHT_BLUE)

    if active_input_player_index >= num_players_selected:
        # All players named, initialize Player objects
        players_data = []  # Clear previous player data if any
        for i in range(num_players_selected):
            # This assumes names were stored somewhere, or we use default names if input_text was per player
            # For simplicity, let's assume input_text holds the last entered name, and we need a list of names.
            # This part needs refinement if we want individual name entry.
            # For now, let's just use default names from PLAYER_CONTROLS_CONFIG
            player_name = temp_player_names[i] if i < len(temp_player_names) else PLAYER_CONTROLS_CONFIG[i]['name']
            controls = PLAYER_CONTROLS_CONFIG[i]
            players_data.append(Player(player_id=i, name=player_name, controls=controls, color=controls['color']))
        print(f"Players created: {[p.name for p in players_data]}")
        current_state = STATE_MAIN_MENU  # Or go to shop, or directly to race
        return

    draw_text(f"Enter Name for {PLAYER_CONTROLS_CONFIG[active_input_player_index]['name']}", DEFAULT_FONT, BLACK,
              screen, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3, center=True)

    # Simple text input box
    input_box_rect = pygame.Rect(SCREEN_WIDTH // 2 - 150, SCREEN_HEIGHT // 2 - 25, 300, 50)
    pygame.draw.rect(screen, WHITE, input_box_rect)
    pygame.draw.rect(screen, BLACK, input_box_rect, 2)  # Border
    draw_text(input_text, DEFAULT_FONT, BLACK, screen, input_box_rect.x + 10, input_box_rect.y + 10)

    # "Next" or "Done" button
    button_text = "Next Player" if active_input_player_index < num_players_selected - 1 else "Done"

    def process_name_input():
        global active_input_player_index, input_text, temp_player_names
        if 'temp_player_names' not in globals():  # Initialize if not exists
            globals()['temp_player_names'] = []

        if input_text.strip():  # Ensure name is not empty
            temp_player_names.append(input_text.strip())
            input_text = ""  # Reset for next player
            active_input_player_index += 1
        else:
            # Show error: name cannot be empty
            print("Name cannot be empty.")

    if create_button(button_text, (SCREEN_WIDTH // 2 - 75, SCREEN_HEIGHT * 2 // 3, 150, 50), BUTTON_COLOR,
                     BUTTON_HOVER_COLOR, DEFAULT_FONT, process_name_input):
        pass  # Action handled by process_name_input

    if create_button("Back to Menu", (20, SCREEN_HEIGHT - 60, 200, 40), GRAY, BUTTON_HOVER_COLOR, SMALL_FONT,
                     lambda: STATE_MAIN_MENU):
        current_state = STATE_MAIN_MENU
        # Reset player setup progress
        active_input_player_index = 0
        input_text = ""
        if 'temp_player_names' in globals(): del globals()['temp_player_names']


def shop_screen():
    global current_state, shop_current_player_idx
    screen.fill(LIGHT_BLUE)

    if not players_data:
        draw_text("No players configured. Go to Main Menu.", DEFAULT_FONT, RED, screen, SCREEN_WIDTH // 2,
                  SCREEN_HEIGHT // 2, center=True)
        if create_button("Main Menu", (SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT * 3 // 4, 200, 50), BUTTON_COLOR,
                         BUTTON_HOVER_COLOR, DEFAULT_FONT, lambda: STATE_MAIN_MENU):
            current_state = STATE_MAIN_MENU
        return

    player = players_data[shop_current_player_idx]
    draw_text(f"Shop - {player.name}", LARGE_FONT, BLACK, screen, SCREEN_WIDTH // 2, 50, center=True)
    draw_text(f"Coins: {player.coins}", DEFAULT_FONT, BLACK, screen, SCREEN_WIDTH - 150, 20)

    item_y_start = 120
    item_height = 30
    item_spacing = 5
    item_x_start = 50
    item_width = SCREEN_WIDTH - 100

    # Display items
    idx = 0
    for item_id, item_details in SHOP_ITEMS.items():
        item_rect = pygame.Rect(item_x_start, item_y_start + idx * (item_height + item_spacing), item_width,
                                item_height)

        # Highlight owned items or current selection
        display_color = GRAY if player.gear.get(item_details["type"]) == item_id or (
                    item_details["type"] == "swimsuit" and player.gear.get("swimsuit") == item_id) else BUTTON_COLOR

        # Check if item is affordable
        affordable = player.coins >= item_details["price"]
        button_text_color = TEXT_COLOR if affordable else RED

        # Create a button for each item
        mouse_pos = pygame.mouse.get_pos()
        clicked = pygame.mouse.get_pressed()[0] == 1

        final_button_color = display_color
        if item_rect.collidepoint(mouse_pos):
            final_button_color = BUTTON_HOVER_COLOR if affordable else (255, 100,
                                                                        100)  # Different hover if not affordable
            if clicked and affordable:
                pygame.time.wait(200)  # debounce
                player.buy_item(item_id)
                # No return here, allow multiple buys per screen visit

        pygame.draw.rect(screen, final_button_color, item_rect, border_radius=5)
        draw_text(f"{item_details['name']} - ${item_details['price']} (Effect: {item_details['effect_value']})",
                  SMALL_FONT, button_text_color, screen, item_rect.x + 10, item_rect.y + 5)
        idx += 1
        if item_y_start + idx * (item_height + item_spacing) > SCREEN_HEIGHT - 150:  # crude pagination
            draw_text("More items below (scrolling not implemented)", SMALL_FONT, BLACK, screen, item_x_start,
                      item_y_start + idx * (item_height + item_spacing))
            break

    # Navigation for shop
    if create_button("Next Player", (SCREEN_WIDTH - 200, SCREEN_HEIGHT - 60, 180, 40), BUTTON_COLOR, BUTTON_HOVER_COLOR,
                     SMALL_FONT,
                     lambda: (shop_current_player_idx + 1) % len(players_data) if players_data else 0):
        if players_data:
            shop_current_player_idx = (shop_current_player_idx + 1) % len(players_data)

    if create_button("Main Menu", (20, SCREEN_HEIGHT - 60, 180, 40), BUTTON_COLOR, BUTTON_HOVER_COLOR, SMALL_FONT,
                     lambda: STATE_MAIN_MENU):
        current_state = STATE_MAIN_MENU


def race_screen_init():
    """Initialize or reset players for the race."""
    global race_winner
    race_winner = None
    for i, player in enumerate(players_data):
        player.x = START_X
        player.y = (i * (LANE_HEIGHT + LANE_PADDING)) + LANE_PADDING + LANE_HEIGHT // 2
        player.finished_race = False
        player.finish_time = 0
        player.update_speed()  # Apply gear effects to speed
        # player.use_snack() # Snacks are typically used during the race by player action, or automatically at start
        # For simplicity, let's assume snacks are activated by the 'move' key for now if available
    print("Race initialized. Players reset.")


def race_screen():
    global current_state, race_winner
    screen.fill(BLUE)  # Water color

    # Draw lanes
    for i in range(num_players_selected):
        lane_y_start = i * (LANE_HEIGHT + LANE_PADDING) + LANE_PADDING
        pygame.draw.rect(screen, LIGHT_BLUE, (0, lane_y_start, SCREEN_WIDTH, LANE_HEIGHT))
        # Draw lane lines (buoys) - simplified
        for j in range(START_X, FINISH_LINE_X, 50):
            pygame.draw.circle(screen, YELLOW, (j, lane_y_start), 5)
            pygame.draw.circle(screen, YELLOW, (j, lane_y_start + LANE_HEIGHT), 5)

    # Draw Finish Line
    pygame.draw.line(screen, RED, (FINISH_LINE_X, 0), (FINISH_LINE_X, SCREEN_HEIGHT), 5)

    # Update and draw players
    all_finished = True
    for i, player in enumerate(players_data):
        lane_y_start = i * (LANE_HEIGHT + LANE_PADDING) + LANE_PADDING
        player.draw(screen, lane_y_start)
        player.update_speed()  # Keep updating speed for snack countdowns etc.
        if not player.finished_race:
            all_finished = False

    # Check for winner
    if not race_winner:
        finished_players = [p for p in players_data if p.finished_race]
        if finished_players:
            # Sort by finish time (lower is better)
            finished_players.sort(key=lambda p: p.finish_time)
            if not race_winner:  # First one to finish
                race_winner = finished_players[0]
                print(f"Race winner: {race_winner.name}")
                race_winner.coins += 10  # Award coins
                print(f"{race_winner.name} awarded 10 coins. Total: {race_winner.coins}")

    if all_finished or (
            race_winner and pygame.time.get_ticks() > race_winner.finish_time + 3000):  # All finished or 3s after winner
        current_state = STATE_RACE_END
        return

    # Back to menu button during race (optional)
    if create_button("End Race Early", (SCREEN_WIDTH - 220, SCREEN_HEIGHT - 60, 200, 40), GRAY, BUTTON_HOVER_COLOR,
                     SMALL_FONT, lambda: STATE_MAIN_MENU):
        current_state = STATE_MAIN_MENU  # Or STATE_RACE_END
        # Reset player positions if going back to menu without finishing
        race_screen_init()


def race_end_screen():
    global current_state
    screen.fill(LIGHT_BLUE)
    if race_winner:
        draw_text(f"{race_winner.name} Wins!", LARGE_FONT, GREEN, screen, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3,
                  center=True)
        draw_text(f"Awarded 10 coins.", DEFAULT_FONT, BLACK, screen, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, center=True)
    else:
        draw_text("Race Over!", LARGE_FONT, BLACK, screen, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 3, center=True)
        draw_text("No winner declared (or race ended early).", DEFAULT_FONT, BLACK, screen, SCREEN_WIDTH // 2,
                  SCREEN_HEIGHT // 2, center=True)

    # Display all player times/positions (optional)
    y_offset = SCREEN_HEIGHT // 2 + 60
    sorted_players = sorted(players_data,
                            key=lambda p: (not p.finished_race, p.finish_time if p.finished_race else float('inf')))
    for i, p in enumerate(sorted_players):
        time_text = f"{(p.finish_time - (pygame.time.get_ticks() - 3000)) / 1000 :.2f}s" if p.finished_race and race_winner else (
            "Finished" if p.finished_race else "DNF")
        # The time calculation above is a bit off, should be simpler: (p.finish_time - race_start_time) / 1000
        # For now, just display name and if finished
        status = "Finished" if p.finished_race else "Did not finish"
        draw_text(f"{i + 1}. {p.name}: {status}", SMALL_FONT, BLACK, screen, SCREEN_WIDTH // 2, y_offset + i * 25,
                  center=True)

    if create_button("Main Menu", (SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT * 3 // 4, 200, 50), BUTTON_COLOR,
                     BUTTON_HOVER_COLOR, DEFAULT_FONT, lambda: STATE_MAIN_MENU):
        current_state = STATE_MAIN_MENU
        race_screen_init()  # Reset for next potential race


# --- Main Game Loop ---
running = True
is_race_initialized = False  # Flag to initialize race screen once

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if current_state == STATE_PLAYER_SETUP:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    # This logic is now handled by the "Next/Done" button's action
                    pass
                elif event.key == pygame.K_BACKSPACE:
                    input_text = input_text[:-1]
                else:
                    if len(input_text) < 20:  # Max name length
                        input_text += event.unicode

        if current_state == STATE_RACE:
            if event.type == pygame.KEYDOWN:
                for player in players_data:
                    if not player.finished_race:
                        if event.key == player.controls['move']:
                            player.move()
                            # Activate snack if player has one and presses move key
                            if player.gear["snack"] and player.snack_active_time <= 0:
                                player.use_snack()
                        elif event.key == player.controls['exit']:
                            # This key is for finishing, which is now handled by reaching FINISH_LINE_X
                            # Could be repurposed for something else, or just signifies the intent to finish
                            # For now, let's make it an explicit action to cross the line if very close
                            if player.x >= FINISH_LINE_X - player.current_speed * 2:  # If within 2 moves of finish
                                player.x = FINISH_LINE_X
                                player.finished_race = True
                                player.finish_time = pygame.time.get_ticks()
                                print(f"{player.name} used exit key to finish.")

    # State Management & Drawing
    if current_state == STATE_MAIN_MENU:
        main_menu()
    elif current_state == STATE_PLAYER_SELECT:
        player_select_screen()
    elif current_state == STATE_PLAYER_SETUP:
        player_setup_screen()
    elif current_state == STATE_SHOP:
        shop_screen()
    elif current_state == STATE_RACE:
        if not is_race_initialized:
            race_screen_init()
            is_race_initialized = True
        race_screen()
    elif current_state == STATE_RACE_END:
        is_race_initialized = False  # Reset for next race
        race_end_screen()

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
sys.exit()
