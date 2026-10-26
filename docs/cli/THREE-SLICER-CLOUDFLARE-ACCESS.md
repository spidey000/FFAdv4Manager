# Acceso remoto protegido para Three_Slicer

Este documento describe la configuración prevista para `https://slicerweb.gg0099.top`.
Estado verificado el 2026-10-25: DNS proxied, ingress del túnel y app Access
con política humana `Allow` configurados; el bridge exige JWT de Access. La
política `Service Auth` del bot queda pendiente de rotar el token expuesto. El
inicio de sesión humano autorizado aún requiere verificación desde navegador.

## Configurar Cloudflare

1. Añade una regla al túnel `slicer-home` para `slicerweb.gg0099.top`. Conserva
   las reglas existentes para `slicer.gg0099.top` y `vault.gg0099.top`; no
   cambies las rutas del túnel de Immich.
2. Publica `slicerweb.gg0099.top` hacia
   `http://127.0.0.1:8765`. Conserva el `Host` público y no reescribas `Host` u
   `Origin` a `127.0.0.1`.
3. Habilita Cloudflare Access en la cuenta propietaria de `gg0099.top`, crea
   una aplicación self-hosted para el hostname completo, sin excepciones por
   ruta, y crea el Service Token en esa misma organización de Zero Trust. No
   presupongas que un token de otra cuenta/organización sirve para esta app.
4. Añade una política `Allow` para el email exacto del usuario autorizado y una
   política `Service Auth` limitada al Service Token del bot. Activa `Strict
   Service Token Authentication` si está disponible. No añadas políticas
   `Bypass`.
5. Comprueba que no hay otro hostname, listener o ruta pública que permita
   evitar Access. El bridge debe seguir enlazado exclusivamente a loopback.

Si automatizas la configuración por API, usa un token dedicado y limitado a los
recursos necesarios: `Cloudflare Tunnel Write` y `Access: Apps and Policies
Write` en la cuenta correspondiente, y `DNS Write` solo en la zona `gg0099.top`.
No uses un token de cuenta completa ni guardes el token en el repositorio.
Revoca cualquier token que se haya compartido en chat antes de crear uno nuevo.

## Iniciar el bridge en modo Access

Entrega estas variables al proceso mediante el gestor de servicios local; no las
guardes en el código ni en este documento:

```sh
CF_ACCESS_TEAM_DOMAIN=<equipo>.cloudflareaccess.com
CF_ACCESS_AUD=<AUD de la aplicación Access>
CF_ACCESS_EMAIL=<email exacto permitido>
CF_ACCESS_PUBLIC_ORIGIN=https://slicerweb.gg0099.top
CF_ACCESS_SERVICE_TOKEN_ID=<Client ID configurado para el bot; opcional>
```

`CF_ACCESS_SERVICE_TOKEN_ID` es únicamente el Client ID público configurado para
el bot; no es el secreto. Si no se configura, las aserciones de bots no se
aceptan. Los cuatro ajustes humanos siguen siendo obligatorios para habilitar
Access.

## Solicitudes del bot

Configura el bot para enviar la solicitud a la URL pública protegida por Access e
incluye en cada solicitud los encabezados que Cloudflare exige para un Service
Token:

```http
CF-Access-Client-Id: <Client ID del bot>
CF-Access-Client-Secret: <secreto del Service Token>
```

Cloudflare valida esas credenciales y añade `Cf-Access-Jwt-Assertion`. El bridge
verifica la firma, issuer, audiencia y expiración de la aserción, y acepta el bot
solo cuando `common_name` coincide exactamente con
`CF_ACCESS_SERVICE_TOKEN_ID`. El bridge no lee ni almacena
`CF-Access-Client-Secret`: guárdalo exclusivamente en el gestor de secretos del
servidor/cliente bot y nunca lo incluyas en el repositorio, la UI ni código
JavaScript del navegador. **El secreto del Service Token nunca debe enviarse ni
empaquetarse en código de navegador.**

Después de construir la UI (`cd web && npm ci && npm run build`) inicia:

```sh
ffadv4manager slicer --require-access
```

El proceso se niega a iniciar si falta alguno de los cuatro valores obligatorios
o si la configuración es parcial, y conserva el listener en `127.0.0.1:8765`.
En modo Access no abre la URL local: abre `https://slicerweb.gg0099.top` en un
navegador autorizado. El bridge valida la aserción JWT de Cloudflare en las
solicitudes públicas de la UI y de `/api/print`; para la API también valida el
`Host`, `Origin` y el token efímero de la instancia.

## Verificación y límites

- Sin sesión de Access, la UI y `/api/print` deben ser denegados en el borde;
  la validación del JWT en el origen añade una segunda comprobación.
- Valida el flujo con solicitudes no mutantes y logs del túnel/origen. Las pruebas
  automatizadas usan callbacks simulados; no envíes G-code de prueba ni una orden
  real de impresión para comprobar el acceso.
- Una persona autenticada puede subir G-code y solicitar el inicio de una
  impresión. Access limita quién llega al sitio, pero no vuelve inocua una sesión
  autorizada comprometida. Supervisa las primeras operaciones y conserva el
  control local de la impresora.
- La confirmación HTTP solo demuestra que el bridge aceptó el comando; no prueba
  que el archivo se guardara correctamente ni que la impresora comenzara a
  imprimir físicamente.
