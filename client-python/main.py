"""Punto de entrada y controlador principal de la aplicación de mensajería.

Coordina la máquina de estados (AUTH → LIVE → EXIT), la TUI, la sesión en
memoria, la persistencia local y la comunicación con el servidor.
"""

import curses
import os
import time
from config import load_config
from network import NetworkClient
from api_client import APIClient
from app_state import AppSession, AppState, AuthMode, LiveMode
from persistence import PersistenceManager
from tui import TUI
import images


class MessagingApp:
    """Controlador principal de la aplicación: gestiona estados, eventos y lógica de negocio."""

    def __init__(self, stdscr):
        """Inicializa la app: carga configuración, abre conexión TCP e instancia subsistemas."""
        self.stdscr = stdscr
        self.session = AppSession()
        self.persistence = PersistenceManager()

        curses.curs_set(0)
        stdscr.nodelay(1)

        ip, port = load_config()
        self.net = NetworkClient(ip, port)
        self.connected = False
        self.connect_error = ""
        self._try_connect()
        self.api = APIClient(self.net)

        self.tui = TUI(stdscr)
        self.state = AppState.AUTH
        self.auth_mode = AuthMode.MENU
        self.live_mode = LiveMode.NAVIGATION
        self.needs_redraw = True

    def run(self):
        """Bucle principal de la aplicación; despacha al manejador del estado actual."""
        while True:
            if self.state == AppState.AUTH:
                self.handle_auth()
            elif self.state == AppState.LIVE:
                self.handle_live()
            elif self.state == AppState.EXIT:
                break

    def cleanup(self):
        """Envía logout al servidor, vuelca conversaciones a disco y cierra el socket."""
        if self.session.is_authenticated():
            if self.connected:
                self.api.api_logout()
            self.persistence.save_user_conversations(self.session.username, self.session.messages)
        if hasattr(self, 'net'):
            self.net.close()

    def _try_connect(self) -> bool:
        """Intenta abrir la conexión TCP; guarda el error en `connect_error` si falla."""
        try:
            self.net.connect()
            self.connected = True
            self.connect_error = ""
            return True
        except Exception as e:
            self.connected = False
            self.connect_error = str(e)
            return False

    # ── Helpers de UI ────────────────────────────────────────────────────────

    def _draw_centered_box(self, h: int, w: int, title: str = "") -> tuple:
        """Borra la pantalla y dibuja un cuadro centrado. Devuelve (top_y, left_x)."""
        rows, cols = self.stdscr.getmaxyx()
        by = max(0, (rows - h) // 2)
        bx = max(0, (cols - w) // 2)
        inner = w - 2
        if title:
            pad  = max(0, (inner - len(title) - 2) // 2)
            rest = inner - pad - len(title) - 2
            top  = '╔' + '═' * pad + f' {title} ' + '═' * rest + '╗'
        else:
            top = '╔' + '═' * inner + '╗'
        self.stdscr.clear()
        try:
            self.stdscr.addstr(by,         bx, top)
            for row in range(1, h - 1):
                self.stdscr.addstr(by + row, bx, '║' + ' ' * inner + '║')
            self.stdscr.addstr(by + h - 1, bx, '╚' + '═' * inner + '╝')
        except curses.error:
            pass
        return by, bx

    def show_error_message(self, msg: str):
        """Muestra un cuadro de error centrado y espera una pulsación de tecla."""
        BOX_W = max(len(msg) + 8, 38)
        by, bx = self._draw_centered_box(6, BOX_W, "ERROR")
        err_attr = (curses.color_pair(1) | curses.A_BOLD) if curses.has_colors() else curses.A_BOLD
        try:
            self.stdscr.addstr(by + 2, bx + 2, msg[:BOX_W - 4], err_attr)
            self.stdscr.addstr(by + 4, bx + 2, "Presiona cualquier tecla...")
        except curses.error:
            pass
        self.stdscr.refresh()
        curses.curs_set(0)
        self.stdscr.nodelay(0)
        self.stdscr.getch()
        self.stdscr.nodelay(1)

    # ── AUTENTICACIÓN ────────────────────────────────────────────────────────

    def handle_auth(self):
        """Despacha al submanejador del estado de autenticación actual."""
        if self.auth_mode == AuthMode.MENU:
            self.show_auth_menu()
        elif self.auth_mode == AuthMode.LOGIN:
            self._show_auth_form("LOGIN", is_register=False)
        elif self.auth_mode == AuthMode.REGISTER:
            self._show_auth_form("REGISTRO", is_register=True)

    def show_auth_menu(self):
        """Dibuja el menú principal de autenticación y procesa la tecla pulsada."""
        curses.curs_set(0)
        self.stdscr.nodelay(1)
        by, bx = self._draw_centered_box(11, 28, "MENSAJERÍA")
        if self.connected:
            self.stdscr.addstr(by + 2, bx + 2, "● Conectado", curses.A_DIM)
        else:
            err = (curses.color_pair(1) | curses.A_BOLD) if curses.has_colors() else curses.A_BOLD
            self.stdscr.addstr(by + 2, bx + 2, "✗ Sin conexión", err)
        try:
            self.stdscr.addstr(by + 4, bx + 2, "(l)  Login")
            self.stdscr.addstr(by + 5, bx + 2, "(r)  Registrarse")
            self.stdscr.addstr(by + 6, bx + 2, "(q)  Salir")
            self.stdscr.addstr(by + 9, bx + 2, "Opción: ")
        except curses.error:
            pass
        self.stdscr.refresh()
        key = self.stdscr.getch()
        if key == ord('l'):
            self.auth_mode = AuthMode.LOGIN
        elif key == ord('r'):
            self.auth_mode = AuthMode.REGISTER
        elif key == ord('q'):
            self.state = AppState.EXIT
        time.sleep(0.05)

    def _get_password_input(self, row, col, hint_row, hint_col=2, max_len=32) -> str:
        """Lee la contraseña carácter a carácter con opción de mostrar/ocultar via Tab."""
        password = ""
        show = False
        while True:
            # Redibuja el campo sin borrar más allá del ancho del campo
            self.stdscr.addstr(row, col, ' ' * max_len)
            self.stdscr.addstr(row, col, password if show else '*' * len(password))
            hint = "(Tab para ocultar)" if show else "(Tab para mostrar)"
            self.stdscr.addstr(hint_row, hint_col, hint.ljust(22), curses.A_DIM)
            self.stdscr.move(row, col + len(password))
            self.stdscr.refresh()
            try:
                ch = self.stdscr.get_wch()
            except curses.error:
                continue
            if ch in ('\n', '\r'):
                break
            elif ch == '\t':
                show = not show
            elif ch in ('\x7f', '\x08') or ch == curses.KEY_BACKSPACE:
                password = password[:-1]
            elif isinstance(ch, str) and len(ch) == 1 and ord(ch) >= 32 and len(password) < max_len:
                password += ch
        return password

    def _show_auth_form(self, title: str, is_register: bool):
        """Muestra el formulario de login o registro, autentica al usuario y carga la sesión."""
        if not self.connected:
            by, bx = self._draw_centered_box(5, 36)
            self.stdscr.addstr(by + 2, bx + 2, "Conectando...", curses.A_DIM)
            self.stdscr.refresh()
            if not self._try_connect():
                self.show_error_message(f"Sin conexión: {self.connect_error}")
                self.auth_mode = AuthMode.MENU
                return

        curses.curs_set(1)
        self.stdscr.nodelay(0)

        BOX_W, BOX_H = 46, 9
        by, bx = self._draw_centered_box(BOX_H, BOX_W, title)

        label_x = bx + 2
        input_x = bx + 12
        uy, py, hy, sy = by + 2, by + 3, by + 4, by + 6

        try:
            self.stdscr.addstr(uy, label_x, "Usuario:  ")
        except curses.error:
            pass
        curses.echo()
        username = self.stdscr.getstr(uy, input_x, 28).decode('utf-8').strip()
        curses.noecho()

        try:
            self.stdscr.addstr(py, label_x, "Password: ")
        except curses.error:
            pass
        self.stdscr.refresh()
        password = self._get_password_input(py, input_x, hint_row=hy, hint_col=label_x).strip()

        if not username or not password:
            self.show_error_message("Usuario y contraseña obligatorios")
            self.auth_mode = AuthMode.MENU
            return

        try:
            self.stdscr.addstr(sy, label_x, "Registrando..." if is_register else "Autenticando...", curses.A_DIM)
        except curses.error:
            pass
        self.stdscr.refresh()

        success, msg, resp = self.api.api_authenticate(username, password, is_register)
        if not success:
            self.show_error_message(f"Error: {msg}")
            self.auth_mode = AuthMode.MENU
            return

        if is_register:
            try:
                self.stdscr.addstr(sy, label_x, "Registro exitoso. Iniciando sesión...", curses.A_BOLD)
            except curses.error:
                pass
            self.stdscr.refresh()
            time.sleep(1)
            # El servidor hace auto-login tras el registro y envía una segunda respuesta; la descartamos.
            self.api.net.recv(timeout=5)

        self.session.set_user(username)
        self._load_with_delta(username)
        self.state = AppState.LIVE
        curses.curs_set(0)
        self.stdscr.nodelay(1)

    # ── LIVE ─────────────────────────────────────────────────────────────────

    def _load_with_delta(self, username: str):
        """Sincroniza los chats locales con el servidor mediante una petición de delta.

        1. Carga los chats guardados en disco.
        2. Envía LOADMESSAGEDELTA con la fecha global de última sincronización.
        3. Añade todos los mensajes recibidos; los chats vacíos llegan como claves con [].
        4. Vuelca el resultado a disco.
        """
        since = self.persistence.load_last_sync(username)
        local_convs = {} if since == "1970-01-01 00:00:00" else self.persistence.load_user_conversations(username)

        while self.api.net.try_recv() is not None:
            pass

        success, _, delta = self.api.api_load_message_delta(username, since)
        if success:
            img_dir = self.persistence.images_dir(username)
            for chat, new_msgs in delta.items():
                if chat not in local_convs:
                    local_convs[chat] = []
                for m in new_msgs:
                    if isinstance(m, dict) and images.is_wire_format(m.get('contents', '')):
                        m = {**m, 'contents': images.decode_and_save(m['contents'], img_dir)}
                    local_convs[chat].append(m)

        self.session.load_conversations(local_convs)
        self.persistence.save_user_conversations(username, self.session.messages)

    def _strip_image(self, msg: dict) -> dict:
        """Si el mensaje contiene una imagen en formato wire, guarda el binario y devuelve la ref."""
        contents = msg.get('contents', '')
        if images.is_wire_format(contents):
            ref = images.decode_and_save(contents, self.persistence.images_dir(self.session.username))
            return {**msg, 'contents': ref}
        return msg

    def _apply_push(self, msg: dict):
        """Procesa un mensaje push recibido del servidor: lo guarda y marca el chat como no leído."""
        chat = msg.get('chatname')
        if not chat:
            return
        msg = self._strip_image(msg)
        author   = msg.get('author', '?')
        contents = msg.get('contents', '')
        if chat in self.session.messages and not images.is_image_ref(contents):
            try:
                self.session.messages[chat].remove(f"{author}: {contents}")
            except ValueError:
                pass
        self.session.add_message(chat, msg)
        self.persistence.update_user_chat(self.session.username, chat, self.session.messages[chat])
        if chat != self.session.active_chat:
            self.session.mark_unread(chat)
        self.needs_redraw = True

    def _apply_new_chat(self, msg: dict):
        """Registra un nuevo chat recibido por push si aún no existe en la sesión."""
        chat = msg.get('chatname')
        if not chat or chat in self.session.chats:
            return
        self.session.chats.insert(0, chat)
        self.session.messages[chat] = []
        self.persistence.update_user_chat(self.session.username, chat, [])
        self.needs_redraw = True

    def handle_live(self):
        """Ciclo del estado LIVE: repinta si es necesario y despacha al modo activo."""
        if self.needs_redraw:
            self.draw_live_ui()
            self.needs_redraw = False
        if self.live_mode == LiveMode.NAVIGATION:
            self.handle_navigation()
        elif self.live_mode == LiveMode.INPUT:
            self.handle_message_input()
        elif self.live_mode == LiveMode.NEW_CHAT:
            self.handle_new_chat()

    def draw_live_ui(self):
        """Actualiza todos los componentes de la TUI y fuerza el repintado."""
        self.tui.set_chats(self.session.chats)
        self.tui.set_active_chat(self.session.active_chat)
        self.tui.set_unread(self.session.unread_chats)
        if self.session.active_chat:
            self.tui.set_messages(self.session.get_chat_messages(self.session.active_chat))
        self.tui.set_status(
            f"Conectado como {self.session.username} | ↑↓: Navegar | ENTER: Enviar | n: Nuevo | o: Abrir imagen | q: Salir"
        )
        self.tui.draw()

    def handle_navigation(self):
        """Procesa teclas de navegación y mensajes push entrantes en modo NAVIGATION."""
        self.stdscr.nodelay(1)
        key = self.stdscr.getch()

        msg = self.api.net.try_recv()
        while msg is not None:
            if isinstance(msg, dict) and 'chatname' in msg:
                if 'author' in msg:
                    self._apply_push(msg)
                else:
                    self._apply_new_chat(msg)
            msg = self.api.net.try_recv()

        if key == -1:
            time.sleep(0.05)
            return

        if key == ord('q'):
            self.state = AppState.EXIT
        elif key in (curses.KEY_UP, curses.KEY_DOWN) and self.session.chats:
            idx = (
                self.session.chats.index(self.session.active_chat)
                if self.session.active_chat in self.session.chats else 0
            )
            idx = max(0, idx - 1) if key == curses.KEY_UP else min(len(self.session.chats) - 1, idx + 1)
            self.session.active_chat = self.session.chats[idx]
            self.session.mark_read(self.session.active_chat)
            self.needs_redraw = True
        elif key in (ord('\n'), ord(' ')) and self.session.active_chat:
            self.live_mode = LiveMode.INPUT
            self.needs_redraw = True
        elif key == ord('n'):
            self.live_mode = LiveMode.NEW_CHAT
            self.needs_redraw = True
        elif key == ord('o') and self.session.active_chat:
            self._select_and_open_image()

    def _select_and_open_image(self):
        """Muestra un selector de imágenes del chat activo y abre la elegida."""
        msgs = self.session.get_chat_messages(self.session.active_chat)
        img_msgs = [m for m in msgs
                    if isinstance(m, dict) and images.is_image_ref(m.get('contents', ''))]
        if not img_msgs:
            return

        img_dir = self.persistence.images_dir(self.session.username)
        selected = len(img_msgs) - 1
        rows, cols = self.stdscr.getmaxyx()
        box_h = min(len(img_msgs) + 4, rows - 2)
        box_w = min(64, cols - 4)

        self.stdscr.nodelay(0)
        while True:
            by, bx = self._draw_centered_box(box_h, box_w, "SELECCIONAR IMAGEN")
            visible_items = img_msgs[: box_h - 4]
            for i, m in enumerate(visible_items):
                filename = images.get_filename(m.get('contents', ''))
                author   = m.get('author', '?')
                text     = f"{author}: {filename}"[: box_w - 4]
                attr     = curses.A_REVERSE if i == selected else 0
                try:
                    self.stdscr.addstr(by + 2 + i, bx + 2, text.ljust(box_w - 4), attr)
                except curses.error:
                    pass
            try:
                self.stdscr.addstr(by + box_h - 2, bx + 2,
                                   "↑↓: Navegar | ENTER: Abrir | ESC: Cancelar"[: box_w - 4],
                                   curses.A_DIM)
            except curses.error:
                pass
            self.stdscr.refresh()

            key = self.stdscr.getch()
            if key == curses.KEY_UP:
                selected = max(0, selected - 1)
            elif key == curses.KEY_DOWN:
                selected = min(len(img_msgs) - 1, selected + 1)
            elif key in (ord('\n'), ord('\r')):
                images.open_image(img_msgs[selected]['contents'], img_dir)
                break
            elif key == 27:  # ESC
                break

        self.stdscr.nodelay(1)
        self.needs_redraw = True

    def handle_message_input(self):
        """Captura el mensaje del usuario, lo envía al servidor y lo persiste localmente."""
        curses.curs_set(1)
        self.stdscr.nodelay(0)
        self.tui.set_status("Escribiendo mensaje... (ENTER para enviar)")
        self.tui.draw()
        self.tui.get_input()

        msg = self.tui.input.strip()
        if msg:
            wire = images.encode_file(msg) if os.path.isfile(msg) else None
            payload = wire if wire else msg

            success, api_msg = self.api.api_send_message(
                self.session.active_chat, payload, self.session.username
            )
            if success:
                if wire:
                    ref = images.decode_and_save(wire, self.persistence.images_dir(self.session.username))
                    self.session.add_message(self.session.active_chat, {
                        'author': self.session.username,
                        'contents': ref,
                        'sent': '',
                        'chatname': self.session.active_chat,
                    })
                else:
                    self.session.add_message(self.session.active_chat, f"{self.session.username}: {msg}")
                self.persistence.update_user_chat(
                    self.session.username,
                    self.session.active_chat,
                    self.session.get_chat_messages(self.session.active_chat)
                )
                self.tui.set_status("✓ Mensaje enviado")
            else:
                self.session.add_message(self.session.active_chat, f"[FALLIDO] {self.session.username}: {msg}")
                self.tui.set_status(f"✗ Error: {api_msg}")

        self.live_mode = LiveMode.NAVIGATION
        curses.curs_set(0)
        self.stdscr.nodelay(1)
        self.needs_redraw = True

    def handle_new_chat(self):
        """Muestra el formulario de creación de chat, envía la petición y actualiza la sesión."""
        curses.curs_set(1)
        self.stdscr.nodelay(0)
        self.stdscr.clear()
        self.stdscr.addstr(2, 2, "╔═ CREAR NUEVO CHAT ═╗", curses.A_BOLD)

        self.stdscr.addstr(4, 2, "Nombre: ")
        curses.echo()
        chat_name = self.stdscr.getstr(4, 10, 30).decode('utf-8').strip()

        self.stdscr.addstr(5, 2, "Participantes (separados por comas): ")
        participants_str = self.stdscr.getstr(5, 37, 100).decode('utf-8').strip()
        curses.noecho()

        if chat_name and participants_str:
            others = [p.strip() for p in participants_str.split(',') if p.strip() and p.strip() != self.session.username]
            participants = [self.session.username] + others

            self.stdscr.addstr(7, 2, "Creando...", curses.A_DIM)
            self.stdscr.refresh()

            success, msg = self.api.api_create_group(chat_name, participants)
            if success:
                self.session.create_chat(chat_name)
                self.persistence.update_user_chat(self.session.username, chat_name, [])
                self.tui.set_status(f"✓ Chat '{chat_name}' creado")
            else:
                self.tui.set_status(f"✗ Error: {msg}")

        self.live_mode = LiveMode.NAVIGATION
        curses.curs_set(0)
        self.stdscr.nodelay(1)
        self.needs_redraw = True


def main(stdscr):
    """Función raíz pasada a curses.wrapper: construye la app y la ejecuta."""
    app = MessagingApp(stdscr)
    try:
        app.run()
    except KeyboardInterrupt:
        pass
    finally:
        app.cleanup()


if __name__ == "__main__":
    curses.wrapper(main)
