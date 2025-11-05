import socket
import threading
import pygame
import random
import base64
import cv2
import numpy as np

HOST, PORT = "localhost", 9999
current_x = 0
game_started = False
face_surface = None
face_lock = threading.Lock()

def socket_listener():
    global current_x, game_started, face_surface
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(1)
    print(f"🎮 Serveur en écoute sur {HOST}:{PORT}")

    client_socket, addr = server.accept()
    print(f"✅ Client connecté depuis {addr}")

    buffer = ""
    try:
        while True:
            data = client_socket.recv(65536).decode()
            if not data:
                break
            buffer += data

            while "\n" in buffer:
                message, buffer = buffer.split("\n", 1)
                if message.startswith("x:"):
                    current_x = int(message.split(":")[1])
                elif message.lower() == "start":
                    game_started = True
                    print("🎮 Jeu démarré !")
                elif message.startswith("face:"):
                    threading.Thread(target=process_face, args=(message,), daemon=True).start()

    except Exception as e:
        print("❌ Erreur socket :", e)
    finally:
        client_socket.close()
        server.close()

def process_face(message):
    global face_surface
    try:
        face_data = message.split("face:")[1]
        img_bytes = base64.b64decode(face_data)
        img_array = np.frombuffer(img_bytes, np.uint8)
        face_img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        if face_img is not None:
            face_img = cv2.cvtColor(face_img, cv2.COLOR_BGR2RGB)
            surface = pygame.image.frombuffer(face_img.tobytes(), face_img.shape[1::-1], "RGB")
            with face_lock:
                face_surface = surface
    except Exception as e:
        print("⚠️ Erreur traitement visage:", e)

threading.Thread(target=socket_listener, daemon=True).start()

pygame.init()
WIDTH, HEIGHT = 1280,800 
win = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("⚽ Catch Game")

# === AJOUT MUSIQUE ===
pygame.mixer.init()
pygame.mixer.music.load("musique.mp3")  
pygame.mixer.music.play(-1) 
print("🎵 Musique lancée !")

background = pygame.image.load("background.jpg").convert()
background = pygame.transform.scale(background, (WIDTH, HEIGHT))

start_img = pygame.image.load("start_animation.png").convert_alpha()
player_img = pygame.image.load("player.png").convert_alpha()
face_size = (100, 100)
player_img = pygame.transform.scale(player_img, face_size)
ball_img = pygame.image.load("ball.png").convert_alpha()
ball_img = pygame.transform.scale(ball_img, (50, 50))
player = pygame.Rect(0, 0, *face_size)

class FallingObject:
    def __init__(self):
        self.x = random.randint(15, WIDTH - 15)
        self.y = 0
        self.speed = random.randint(4, 7)
    def move(self):
        self.y += self.speed
    def draw(self, surface):
        surface.blit(ball_img, (self.x - 15, self.y - 15))
    def rect(self):
        return pygame.Rect(self.x - 15, self.y - 15, 30, 30)

objects, spawn_timer, score = [], 0, 0
font = pygame.font.SysFont(None, 32)
clock = pygame.time.Clock()

anim_scale = 1.0
anim_direction = 1
anim_speed = 0.0005

running = True
while running:
    clock.tick(60)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    if not game_started:
        anim_scale += anim_direction * anim_speed
        if anim_scale > 1.05:
            anim_direction = -1
        elif anim_scale < 0.95:
            anim_direction = 1
        scaled_img = pygame.transform.smoothscale(start_img, (int(WIDTH * anim_scale), int(HEIGHT * anim_scale)))
        img_rect = scaled_img.get_rect(center=(WIDTH // 2, HEIGHT // 2))
        win.fill((0, 0, 0))
        win.blit(scaled_img, img_rect)
        pygame.display.update()
        continue

    win.blit(background, (0, 0))
    player.x = max(0, min(WIDTH - player.width, current_x))
    player.y = HEIGHT - face_size[1]

    spawn_timer += 1
    if spawn_timer >= 30:
        objects.append(FallingObject())
        spawn_timer = 0

    new_objects = []
    for obj in objects:
        obj.move()
        if player.colliderect(obj.rect()):
            score += 1
        elif obj.y < HEIGHT:
            new_objects.append(obj)
    objects = new_objects

    with face_lock:
        if face_surface:
            win.blit(pygame.transform.scale(face_surface, face_size), (player.x, player.y))
        else:
            win.blit(player_img, (player.x, player.y))

    for obj in objects:
        obj.draw(win)

    win.blit(font.render(f"Score : {score}", True, (255, 255, 255)), (10, 10))
    pygame.display.update()

pygame.quit()
