#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <pthread.h>
#include <arpa/inet.h>

#define BUF_SIZE    4096
#define MAX_NAME    64
#define CONFIG_FILE "config.txt"
#define EOT         0x04  /* End of Transmission, separador de mensajes */

int  sockfd = -1;
char my_username[MAX_NAME];
char current_chat[MAX_NAME] = "";

/* ── Leer config ── */

static int load_config(char *ip, size_t ip_sz, int *port)
{
    FILE *f = fopen(CONFIG_FILE, "r");
    if (!f) {
        fprintf(stderr, "No se encontro %s\n", CONFIG_FILE);
        return -1;
    }

    char line[256];
    while (fgets(line, sizeof(line), f)) {
        char key[64], val[128];
        if (sscanf(line, " %63[^=] = %127s", key, val) != 2)
            continue;

        /* Quitar espacios del final de la clave */
        char *end = key + strlen(key) - 1;
        while (end > key && *end == ' ')
            *end-- = '\0';

        if (strcmp(key, "ip") == 0)
            strncpy(ip, val, ip_sz - 1);
        else if (strcmp(key, "puerto") == 0)
            *port = atoi(val);
    }

    fclose(f);
    return 0;
}

/* ── Pretty print JSON ── */

static void json_login(char *buf, size_t sz,
                       const char *username, const char *password)
{
    snprintf(buf, sz,
             "{\n"
             "    \"action\": \"login\",\n"
             "    \"username\": \"%s\",\n"
             "    \"password\": \"%s\"\n"
             "}\n",
             username, password);
}

static void json_create_user(char *buf, size_t sz,
                              const char *username, const char *password)
{
    snprintf(buf, sz,
             "{\n"
             "    \"action\": \"create_user\",\n"
             "    \"username\": \"%s\",\n"
             "    \"password\": \"%s\"\n"
             "}\n",
             username, password);
}

static void json_create_chat(char *buf, size_t sz,
                              const char *chat_name, const char *participants)
{
    snprintf(buf, sz,
             "{\n"
             "    \"action\": \"create_chat\",\n"
             "    \"chat_name\": \"%s\",\n"
             "    \"participants\": %s\n"
             "}\n",
             chat_name, participants);
}

static void json_send_msg(char *buf, size_t sz,
                          const char *chat, const char *msg)
{
    snprintf(buf, sz,
             "{\n"
             "    \"action\": \"send_msg\",\n"
             "    \"chat\": \"%s\",\n"
             "    \"msg\": \"%s\"\n"
             "}\n",
             chat, msg);
}

static void json_logout(char *buf, size_t sz, const char *username)
{
    snprintf(buf, sz,
             "{\n"
             "    \"action\": \"logout\",\n"
             "    \"username\": \"%s\"\n"
             "}\n",
             username);
}

/* ── Parseo JSON minimo ── */

static int extract_str(const char *json, const char *key,
                        char *out, size_t out_sz)
{
    char        search[128];
    const char *p;
    size_t      i = 0;

    snprintf(search, sizeof(search), "\"%s\"", key);
    p = strstr(json, search);
    if (!p)
        return 0;

    p += strlen(search);
    while (*p == ' ' || *p == ':' || *p == '\n') p++;
    if (*p != '"')
        return 0;
    p++;

    while (*p && *p != '"' && i < out_sz - 1)
        out[i++] = *p++;
    out[i] = '\0';
    return 1;
}

static int extract_code(const char *json)
{
    const char *p = strstr(json, "\"code\"");
    if (!p)
        return -1;
    p += strlen("\"code\"");
    while (*p == ' ' || *p == ':' || *p == '\n') p++;
    return atoi(p);
}

static int is_incoming(const char *j)
{
    return strstr(j, "\"action\"") && strstr(j, "\"incoming\"");
}

static int is_shutdown(const char *j)
{
    return strstr(j, "\"action\"") && strstr(j, "\"shutdown\"");
}

/* ── Enviar mensaje + EOT ── */

static int send_eot(const char *msg)
{
    size_t len  = strlen(msg);
    char  *tmp  = malloc(len + 2);
    int    ret  = 0;

    if (!tmp)
        return -1;

    memcpy(tmp, msg, len);
    tmp[len]     = EOT;
    tmp[len + 1] = '\0';

    if (send(sockfd, tmp, len + 1, 0) < 0) {
        perror("send");
        ret = -1;
    }

    free(tmp);
    return ret;
}

/* ── Recibir hasta EOT ── */

static int recv_eot(char *resp, size_t resp_sz)
{
    size_t  total = 0;
    ssize_t n;
    char    byte;

    while (total < resp_sz - 1) {
        n = recv(sockfd, &byte, 1, 0);
        if (n <= 0)
            return -1;
        if ((unsigned char)byte == EOT)
            break;
        resp[total++] = byte;
    }

    resp[total] = '\0';
    return 0;
}

/* ── Hilo receptor ── */

void *receiver(void *arg __attribute__((unused)))
{
    char buf[BUF_SIZE];

    while (recv_eot(buf, sizeof(buf)) == 0) {

        if (is_incoming(buf)) {
            char author[MAX_NAME];
            char content[BUF_SIZE];
            char chat[MAX_NAME];

            extract_str(buf, "author",  author,  sizeof(author));
            extract_str(buf, "msg",     content, sizeof(content));
            extract_str(buf, "chat",    chat,    sizeof(chat));

            printf("\r[%s][%s]: %s\n> ", chat, author, content);
            fflush(stdout);

        } else if (is_shutdown(buf)) {
            printf("\nEl servidor se ha cerrado\n");
            close(sockfd);
            sockfd = -1;
            exit(0);
        }
    }

    printf("\nConexion perdida\n");
    exit(0);
    return NULL;
}

/* ── send + recv sincronos ── */

static int send_recv(const char *msg, char *resp, size_t resp_sz)
{
    if (send_eot(msg) < 0)
        return -1;
    return recv_eot(resp, resp_sz);
}

/* ── MAIN ── */

int main(int argc, char *argv[])
{
    char      ip[64]      = "";
    int       port        = 0;
    char      password[128];
    char      buf[BUF_SIZE];
    char      resp[BUF_SIZE];
    char      line[BUF_SIZE];
    char      msg_err[256];
    int       code;
    pthread_t recv_tid;

    if (argc != 2) {
        fprintf(stderr, "Uso: %s <username>\n", argv[0]);
        return 1;
    }

    strncpy(my_username, argv[1], sizeof(my_username) - 1);

    /* Leer config */
    if (load_config(ip, sizeof(ip), &port) < 0)
        return 1;

    if (strlen(ip) == 0 || port == 0) {
        fprintf(stderr, "Config incompleta, revisa %s\n", CONFIG_FILE);
        return 1;
    }

    /* Socket y conexion */
    sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd < 0) {
        perror("socket");
        return 1;
    }

    struct sockaddr_in serv = {
        .sin_family = AF_INET,
        .sin_port   = htons(port)
    };

    if (inet_pton(AF_INET, ip, &serv.sin_addr) <= 0) {
        fprintf(stderr, "IP invalida en config: %s\n", ip);
        return 1;
    }

    if (connect(sockfd, (struct sockaddr *)&serv, sizeof(serv)) < 0) {
        perror("connect");
        return 1;
    }

    /* Login o registro */
    printf("(1) Login  (2) Registrarse: ");
    fflush(stdout);
    if (!fgets(line, sizeof(line), stdin))
        return 1;

    printf("Password: ");
    fflush(stdout);
    if (!fgets(password, sizeof(password), stdin))
        return 1;
    password[strcspn(password, "\n")] = '\0';

    if (line[0] == '2') {
        json_create_user(buf, sizeof(buf), my_username, password);
        if (send_recv(buf, resp, sizeof(resp)) < 0) {
            fprintf(stderr, "Error en registro\n");
            return 1;
        }
        code = extract_code(resp);
        if (code != 1) {
            extract_str(resp, "msg", msg_err, sizeof(msg_err));
            fprintf(stderr, "Registro fallido: %s\n", msg_err);
            close(sockfd);
            return 1;
        }
        printf("Usuario creado correctamente\n");
    }

    /* Login */
    json_login(buf, sizeof(buf), my_username, password);
    if (send_recv(buf, resp, sizeof(resp)) < 0) {
        fprintf(stderr, "Error en login\n");
        return 1;
    }

    code = extract_code(resp);
    if (code != 1) {
        extract_str(resp, "msg", msg_err, sizeof(msg_err));
        fprintf(stderr, "Login incorrecto: %s\n", msg_err);
        close(sockfd);
        return 1;
    }

    /* Mensajes perdidos desde ultimo login */
    if (strstr(resp, "\"new_chats\"")) {
        printf("\n--- Mensajes nuevos ---\n");
        const char *p = strstr(resp, "\"new_chats\"");
        printf("%s\n", p);
        printf("-----------------------\n");
    }

    /* Arrancar hilo receptor */
    if (pthread_create(&recv_tid, NULL, receiver, NULL) != 0) {
        perror("pthread_create");
        return 1;
    }
    pthread_detach(recv_tid);

    /* Bucle principal */
    printf("\nComandos:\n");
    printf("  /chat <nombre>            -> entrar en un chat\n");
    printf("  /new <nombre> <u1,u2,...> -> crear chat nuevo\n");
    printf("  /exit                     -> salir\n\n");

    while (1) {
        if (strlen(current_chat) > 0)
            printf("[%s]> ", current_chat);
        else
            printf("> ");
        fflush(stdout);

        if (!fgets(line, sizeof(line), stdin))
            break;
        line[strcspn(line, "\n")] = '\0';
        if (strlen(line) == 0)
            continue;

        if (strcmp(line, "/exit") == 0)
            break;

        if (strncmp(line, "/chat ", 6) == 0) {
            strncpy(current_chat, line + 6, sizeof(current_chat) - 1);
            printf("Ahora en: %s\n", current_chat);
            continue;
        }

        if (strncmp(line, "/new ", 5) == 0) {
            char chat_name[MAX_NAME];
            char participants_raw[BUF_SIZE];
            char participants_json[BUF_SIZE];
            char *tok;
            char *rest;
            int   first = 1;

            if (sscanf(line + 5, "%63s %4095s", chat_name, participants_raw) != 2) {
                printf("Uso: /new <nombre_chat> <user1,user2,...>\n");
                continue;
            }

            rest = participants_raw;
            strcpy(participants_json, "[");
            while ((tok = strtok_r(rest, ",", &rest)) != NULL) {
                if (!first)
                    strcat(participants_json, ", ");
                strcat(participants_json, "\"");
                strcat(participants_json, tok);
                strcat(participants_json, "\"");
                first = 0;
            }
            strcat(participants_json, "]");

            json_create_chat(buf, sizeof(buf), chat_name, participants_json);
            if (send_recv(buf, resp, sizeof(resp)) < 0) {
                fprintf(stderr, "Error creando chat\n");
                continue;
            }
            code = extract_code(resp);
            if (code != 1) {
                extract_str(resp, "msg", msg_err, sizeof(msg_err));
                printf("Error: %s\n", msg_err);
            } else {
                strncpy(current_chat, chat_name, sizeof(current_chat) - 1);
                printf("Chat '%s' creado\n", current_chat);
            }
            continue;
        }

        if (strlen(current_chat) == 0) {
            printf("Primero elige un chat con /chat <nombre>\n");
            continue;
        }

        if (sockfd < 0)
            break;

        json_send_msg(buf, sizeof(buf), current_chat, line);
        if (send_eot(buf) < 0)
            break;
    }

    if (sockfd >= 0) {
        json_logout(buf, sizeof(buf), my_username);
        send_eot(buf);
        close(sockfd);
    }

    printf("Desconectado\n");
    return 0;
}
