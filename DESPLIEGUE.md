# Guía de despliegue — Soporte TI

Dos opciones: **Docker Compose** (recomendado) o instalación manual en Ubuntu 24.04.

---

## Opción A · Docker Compose (recomendado)

### 1. Instalar Docker en Ubuntu 24.04

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER   # para no necesitar sudo en cada comando
```

### 2. Subir el proyecto al servidor

```bash
# Desde tu máquina local:
scp -r ticketing/ usuario@tu-servidor:/opt/ticketing/

# O en el servidor directamente si tienes git:
# git clone <repo> /opt/ticketing
```

### 3. Configurar variables de entorno

```bash
cd /opt/ticketing
cp .env.example .env
nano .env          # Rellena SECRET_KEY, MAIL_*, ADMIN_EMAIL, APP_URL
```

**Genera una SECRET_KEY segura:**
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 4. Arrancar

```bash
cd /opt/ticketing
docker compose up -d --build
```

La aplicación estará disponible en `http://IP-DEL-SERVIDOR`.

### 5. Primer admin

Regístrate en la aplicación y luego ejecuta:

```bash
docker compose exec app python3 -c "
from app import app, db
from models import User
with app.app_context():
    u = User.query.filter_by(email='tu@correo.com').first()
    u.rol = 'admin'
    db.session.commit()
    print('Listo —', u.nombre, 'es ahora admin')
"
```

### 6. Comandos útiles

```bash
docker compose logs -f app        # Ver logs en tiempo real
docker compose restart app        # Reiniciar la app
docker compose down               # Parar todo
docker compose up -d --build      # Reconstruir y arrancar (tras cambios en el código)
```

### 7. HTTPS con Let's Encrypt

```bash
# Instala certbot en el HOST (no dentro del contenedor)
sudo apt install -y certbot

# Detén Nginx temporalmente para obtener el certificado
docker compose stop nginx
sudo certbot certonly --standalone -d tu-dominio.com
docker compose start nginx

# Edita nginx.conf: descomenta el bloque HTTPS y ajusta el dominio
# Luego recarga:
docker compose restart nginx
```

---

## Opción B · Instalación manual (sin Docker)

### 1. Preparar el servidor

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3 python3-pip python3-venv nginx -y
```

### 2. Subir el proyecto

```bash
sudo mkdir -p /var/www/ticketing
# scp -r ticketing/ usuario@tu-servidor:/var/www/ticketing/
```

### 3. Entorno virtual

```bash
cd /var/www/ticketing
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Variables de entorno

```bash
cp .env.example .env
nano .env
```

### 5. Servicio systemd

Crea `/etc/systemd/system/ticketing.service`:

```ini
[Unit]
Description=Soporte TI — Sistema de tickets
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/ticketing
EnvironmentFile=/var/www/ticketing/.env
ExecStart=/var/www/ticketing/venv/bin/gunicorn \
    --workers 3 \
    --bind unix:/var/www/ticketing/ticketing.sock \
    --timeout 60 \
    app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ticketing
sudo systemctl status ticketing
```

### 6. Nginx

Crea `/etc/nginx/sites-available/ticketing`:

```nginx
server {
    listen 80;
    server_name tu-dominio.com;

    location /static/ {
        alias /var/www/ticketing/static/;
        expires 7d;
    }

    location / {
        proxy_pass http://unix:/var/www/ticketing/ticketing.sock;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/ticketing /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 7. HTTPS

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d tu-dominio.com
```

---

## Estructura del proyecto

```
ticketing/
├── app.py                  # Aplicación Flask (rutas, lógica, email)
├── models.py               # Modelos SQLAlchemy
├── requirements.txt        # Dependencias Python
├── Dockerfile              # Imagen Docker
├── docker-compose.yml      # Orquestación (app + nginx)
├── nginx.conf              # Configuración de Nginx
├── .env.example            # Plantilla de variables de entorno
├── DESPLIEGUE.md           # Esta guía
├── static/
│   └── style.css
└── templates/
    ├── base.html
    ├── login.html
    ├── registro.html
    ├── dashboard.html
    ├── nuevo_ticket.html
    ├── ticket_detalle.html
    ├── admin_panel.html
    ├── admin_estadisticas.html
    └── admin_usuarios.html
```

## Notificaciones por correo

Se envían automáticamente en tres casos:
- **Nuevo ticket** → llega un correo a `ADMIN_EMAIL`
- **Admin responde** → llega un correo al usuario que creó el ticket
- **Estado cambia** → llega un correo al usuario con el nuevo estado

Si no configuras las variables `MAIL_*`, la aplicación funciona igual pero sin enviar correos.
