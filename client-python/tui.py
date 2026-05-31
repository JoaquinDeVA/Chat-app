"""Capa de presentación basada en curses.

TUI gestiona el pintado de la pantalla principal (lista de chats + mensajes +
barra de entrada) y la captura de texto del usuario. No contiene lógica de
negocio: recibe datos desde MessagingApp y devuelve la entrada del usuario.
"""

import curses
import curses.textpad
import locale
import images

locale.setlocale(locale.LC_ALL, '')

FAILED_PREFIX = '[FALLIDO]'


class TUI:
    """Componente de interfaz de usuario basado en curses."""

    def __init__(self, stdscr):
        """Inicializa la TUI y configura los pares de color disponibles."""
        self.stdscr = stdscr
        self.height, self.width = stdscr.getmaxyx()
        self.chat_list = []
        self.messages = []
        self.input = ''
        self.status = ''
        self.active_chat = None
        self.unread_chats: set = set()
        self.scroll = 0
        self.chat_selection = 0

        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_RED,   -1)
            curses.init_pair(2, curses.COLOR_GREEN, -1)

    def set_unread(self, unread: set):
        """Actualiza el conjunto de chats con mensajes no leídos (para el indicador ◆)."""
        self.unread_chats = unread

    def draw(self):
        """Repinta la pantalla completa: lista de chats, mensajes y barra de entrada."""
        self.stdscr.clear()
        self.height, self.width = self.stdscr.getmaxyx()

        chat_w = max(25, self.width // 4)

        # ── Chat list ────────────────────────────────────────────────────────
        try:
            self.stdscr.addstr(0, 0, '═ CHATS ═', curses.A_BOLD)
        except curses.error:
            pass

        if not self.chat_list:
            try:
                self.stdscr.addstr(1, 0, '(sin chats)', curses.A_DIM)
            except curses.error:
                pass
        else:
            for i, chat in enumerate(self.chat_list):
                if i + 1 >= self.height - 1:
                    break
                is_active   = (chat == self.active_chat)
                is_selected = (i == self.chat_selection)
                is_unread   = (chat in self.unread_chats)

                if is_active and is_selected:
                    attr   = curses.A_REVERSE | curses.A_BOLD
                    prefix = "► "
                elif is_active:
                    attr   = curses.A_BOLD
                    prefix = "● "
                elif is_selected:
                    attr   = curses.A_REVERSE
                    prefix = "  "
                else:
                    attr   = 0
                    prefix = "  "

                display = prefix + chat[:chat_w - 4]
                try:
                    self.stdscr.addstr(i + 1, 0, display.ljust(chat_w - 1), attr)
                    if is_unread:
                        green = curses.color_pair(2) | curses.A_BOLD
                        self.stdscr.addstr(i + 1, chat_w - 2, "◆", green)
                except curses.error:
                    pass

        # ── Vertical divider ─────────────────────────────────────────────────
        for row in range(self.height - 1):
            try:
                self.stdscr.addstr(row, chat_w, '│')
            except curses.error:
                pass

        # ── Messages area ────────────────────────────────────────────────────
        msg_x = chat_w + 2
        msg_w = self.width - msg_x - 1
        msg_h = self.height - 5

        active_name = self.active_chat or "(ningún chat seleccionado)"
        try:
            self.stdscr.addstr(0, msg_x, f"╔ {active_name[:msg_w - 4]} ╗"[:msg_w], curses.A_BOLD)
        except curses.error:
            pass

        visible = (
            self.messages[-msg_h - self.scroll : len(self.messages) - self.scroll]
            if self.scroll else self.messages[-msg_h:]
        )
        for i, msg in enumerate(visible):
            try:
                if isinstance(msg, dict):
                    contents = msg.get('contents', '')
                    author   = msg.get('author', '?')
                    if images.is_image_ref(contents) or images.is_wire_format(contents):
                        text = f"{author}: [imagen: {images.get_filename(contents)}]"
                        attr = curses.color_pair(2) | curses.A_BOLD
                    else:
                        text = f"{author}: {contents}"
                        attr = 0
                else:
                    text = str(msg)
                    attr = (curses.color_pair(1) | curses.A_BOLD) if text.startswith(FAILED_PREFIX) else 0
                self.stdscr.addstr(i + 1, msg_x, text[:msg_w], attr)
            except curses.error:
                pass

        # ── Input bar ────────────────────────────────────────────────────────
        try:
            self.stdscr.addstr(self.height - 3, 0, '─' * (self.width - 1))
            self.stdscr.addstr(self.height - 2, 0, 'Mensaje: ')
            self.stdscr.addstr(self.height - 2, 9, self.input[:self.width - 10])
            self.stdscr.addstr(self.height - 1, 0, self.status[:self.width - 1], curses.A_DIM)
        except curses.error:
            pass

        self.stdscr.refresh()

    def get_input(self):
        """Lee una línea de texto del usuario desde la barra de entrada y la devuelve.

        Soporta backspace y caracteres Unicode. Deja el resultado en `self.input`.
        """
        start_x = 9
        input_y = self.height - 2
        curses.curs_set(1)
        self.input = ""
        while True:
            self.stdscr.move(input_y, start_x)
            self.stdscr.clrtoeol()
            self.stdscr.addstr(input_y, start_x, self.input)
            try:
                ch = self.stdscr.get_wch()
            except curses.error:
                continue
            if ch in ('\n', '\r'):
                break
            elif ch in ('\x7f', '\x08') or ch == curses.KEY_BACKSPACE:
                self.input = self.input[:-1]
            elif isinstance(ch, str):
                self.input += ch
        curses.curs_set(0)
        return self.input

    def set_status(self, msg):
        """Establece el texto de la barra de estado (última línea de la pantalla)."""
        self.status = msg

    def set_chats(self, chats):
        """Reemplaza la lista de chats y reinicia la selección al primero."""
        self.chat_list = chats
        self.chat_selection = 0
        if self.active_chat not in chats and chats:
            self.active_chat = chats[0]

    def set_messages(self, messages):
        """Reemplaza los mensajes visibles y reinicia el scroll al final."""
        self.messages = messages
        self.scroll = 0

    def set_active_chat(self, chat):
        """Marca `chat` como activo y sincroniza el índice de selección."""
        self.active_chat = chat
        if chat in self.chat_list:
            self.chat_selection = self.chat_list.index(chat)

    def scroll_up(self):
        """Desplaza la vista de mensajes hacia atrás (mensajes más antiguos)."""
        if self.scroll < len(self.messages) - 1:
            self.scroll += 1
        self.draw()

    def scroll_down(self):
        """Desplaza la vista de mensajes hacia adelante (mensajes más recientes)."""
        if self.scroll > 0:
            self.scroll -= 1
        self.draw()
