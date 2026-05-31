# Ejemplos de Peticiones y Respuestas del Backend

Basado en los DTOs del backend-java. Estos son los streams que recibe y devuelve el servidor.

---

## 1. ADD USER - Crear nuevo usuario

### PETICIÓN (Lo que envía el cliente al backend)
```
AddUserRequest{
  "username": "juanperez",
  "password": "MiPassword123"
}0x04
```

Donde `[0x04]` es el carácter EOT (End of Transmission)

### RESPUESTA (Lo que devuelve el backend)
```json
{"processed":true}
```
o en caso de error:
```json
{"processed":false}
```

**Estructura de la petición:**
- `username` (String): Nombre de usuario único
- `password` (String): Contraseña en texto plano

**Estructura de la respuesta:**
- `processed` (boolean): `true` si se creó correctamente, `false` si hubo error

---

## 2. ADD CHAT - Crear nuevo chat con participantes

### PETICIÓN (Lo que envía el cliente al backend)
```
CreateChatRequest{
  "chatname": "Grupo-Amigos",
  "usernames": [
    "juanperez",
    "maria",
    "carlos"
  ]
}0x04
```

Donde `[0x04]` es el carácter EOT (End of Transmission)

### RESPUESTA (Lo que devuelve el backend)
```json
{"processed":true}
```
o en caso de error:
```json
{"processed":false}
```

**Estructura de la petición:**
- `chatname` (String): Nombre del chat (debe ser único)
- `usernames` (Array<String>): Lista de nombres de usuarios participantes

**Estructura de la respuesta:**
- `processed` (boolean): `true` si se creó correctamente, `false` si hubo error

---

## 3. ADD MESSAGE - Agregar mensaje a un chat

### PETICIÓN (Lo que envía el cliente al backend)
```
SendMessageRequest{
  "username": "juanperez",
  "chatname": "Grupo-Amigos",
  "message": "Hola a todos!",
  "date": "2026-05-04 10:30:00"
}[0x04]
```

Donde `[0x04]` es el carácter EOT (End of Transmission)

### RESPUESTA (Lo que devuelve el backend)
```json
{"processed":true}
```
o en caso de error:
```json
{"processed":false}
```

**Estructura de la petición:**
- `username` (String): Nombre del usuario que envía el mensaje
- `chatname` (String): Nombre del chat donde se envía
- `message` (String): Contenido del mensaje
- `date` (String): Fecha en formato "YYYY-MM-DD HH:MM:SS"

**Estructura de la respuesta:**
- `
AuthRequest{
  "username": "juanperez",
  "password": "MiPassword123"
}0x04
```

Donde `[0x04]` es el carácter EOT (End of Transmission)

## 4. CHECK PASSWORD - Verificar credenciales de usuario

### PETICIÓN (Lo que envía el cliente al backend)
```json
{"username":"juanperez","password":"MiPassword123"}
```

### RESPUESTA (Lo que devuelve el backend)
```json
{"authorized":true}
```
o si las credenciales son incorrectas:
```json
{"authorized":false}
```

**Estructura de la petición:**
- `username` (String): Nombre de usuario
- `password` (String): Contraseña a verificar

**Estructura de la respuesta:**
- `authorized` (boolean): `true` si las credenciales son válidas, `false` en caso contrario

---
LoadConversationsRequest{
  "username": "juanperez"
}[0x04]
```

Donde `[0x04]` es el carácter EOT (End of Transmission)5. LOAD CONVERSATIONS - Cargar todas las conversaciones de un usuario

### PETICIÓN (Lo que envía el cliente al backend)
```json
{"username":"juanperez"}
```

### RESPUESTA (Lo que devuelve el backend)
```json
{
  "conversations": {
    "Grupo-Amigos": [
      {
        "author": "juanperez",
        "content": "Hola a todos!",
        "date": "2026-05-04 10:30:00"
      },
      {
        "author": "maria",
        "content": "Hola Juan!",
        "date": "2026-05-04 10:31:15"
      }
    ],
    "Chat-Personal": [
      {
        "author": "carlos",
        "content": "¿Cómo estás?",
        "date": "2026-05-04 14:00:00"
      }
    ]
  }
}
```
o si el usuario no existe o no tiene conversaciones:
```json
{
  "conversations": {}
}
```

**Estructura de la petición:**
- `username` (String): Nombre del usuario

**Estructura de la respuesta:**
- `conversations` (Map<String, List<MessageDTO>>): 
  - Clave: Nombre del chat (String)
  - Valor: Lista de mensajes en ese chat
    - `author` (String): Autor del mensaje
    - `content` (String): Contenido del mensaje
    - `date` (String): Fecha en formato "YYYY-MM-DD HH:MM:SS"

---

printf 'AddUserRequest{\n  "username": "juanperez",\n  "password": "MiPassword123"\n}\x04' | nc localhost 6767

# 2. Crear chat
printf 'CreateChatRequest{\n  "chatname": "Grupo-Amigos",\n  "usernames": ["juanperez", "maria", "carlos"]\n}\x04' | nc localhost 6767

# 3. Agregar mensaje
printf 'SendMessageRequest{\n  "username": "juanperez",\n  "chatname": "Grupo-Amigos",\n  "message": "Hola a todos!",\n  "date": "2026-05-04 10:30:00"\n}\x04' | nc localhost 6767

# 4. Verificar contraseña
printf 'AuthRequest{\n  "username": "juanperez",\n  "password": "MiPassword123"\n}\x04' | nc localhost 6767

# 5. Cargar conversaciones
printf 'LoadConversationsRequest{\n  "username": "juanperez"\n}\x04
echo -n '{"username":"juanperez","password":"MiPassword123"}' | nc localhost 6767

# 5. Cargar conversaciones
echo -n '{"username":"juanperez"}' | nc localhost 6767
```

---Header**: Cada petición comienza con el nombre del tipo de request (AddUserRequest, CreateChatRequest, etc.)
- **JSON Pretty-printed**: El JSON viene formateado con indentación
- **Terminación**: Termina con el carácter `0x04` (EOT - End of Transmission)
- **Formato completo**: `[HeaderName]{JSON formateado}[0x04]`
## Notas Importantes

- **Serialización**: Los JSON se envían directamente como bytes sin ningún delimitador previo
- **Finalización**: No hay delimitador explícito, el servidor espera que se cierre la conexión
- **Timestamps**: Las fechas deben estar en formato "YYYY-MM-DD HH:MM:SS"
- **Caracteres especiales**: Se soportan acentos, emojis y caracteres especiales en mensajes
- **Puerto**: Las pruebas se hacen conectando a `localhost:6767`
