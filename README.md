# Stacks médias — Docker rootless / Traefik

Toutes les stacks doivent utiliser le **même moteur Docker rootless**, exécuté
par `deploy` (UID 1001), et le réseau `traefik` créé par
[internal_traefik](https://github.com/adenyrr/internal_traefik).

| Dossier | Services | Variable du domaine | Port HTTP interne |
| --- | --- | --- | --- |
| `jellyfin` | Jellyfin + NVIDIA | `JELLYFIN_HOST` | 8096 |
| `torrents` | qBittorrent, qui | `QBITTORRENT_HOST`, `QUI_HOST` | 8080, 7476 |
| `arr` | Prowlarr | `PROWLARR_HOST` | 9696 |
| `tracearr` | Tracearr, TimescaleDB, Redis | `TRACEARR_HOST` | 3000 |
| `seerr` | Seerr | `SEERR_HOST` | 5055 |

Aucune interface HTTP n'est publiée sur l'hôte. Traefik utilise `websecure` et
`letsencrypt`. Seuls les ports BitTorrent 6881 TCP/UDP sont publiés par
qBittorrent : le proxy HTTP ne transporte pas ces échanges entre pairs.
Jellyfin ne publie aucun port, y compris pour la découverte et DLNA.

## Préparer le serveur

Dans une session du compte `deploy` :

```sh
id -u                                      # attendu : 1001
export DOCKER_HOST=unix:///run/user/1001/docker.sock
docker info --format '{{json .SecurityOptions}}'  # doit contenir rootless
docker compose version
docker network inspect traefik             # démarrer internal_traefik avant
```

Docker rootless nécessite `newuidmap`, `newgidmap` et au moins 65536 UID/GID
subordonnés dans `/etc/subuid` et `/etc/subgid` pour `deploy`.
L'administrateur peut activer `loginctl enable-linger deploy` afin que le service
utilisateur continue après déconnexion. Komodo doit utiliser ce même socket.

Dans cet espace de noms, **UID 0 du conteneur = UID 1001 sur l'hôte** ; mettre
`user: 1001` dans les conteneurs ne sélectionne pas le compte hôte `deploy`.
Jellyfin et qui utilisent `user: "0:0"`. qBittorrent et Prowlarr conservent
l'initialisation LinuxServer et utilisent `PUID=0`, `PGID=0`.
Le GID 0 correspond au groupe primaire de `deploy` (à vérifier avec `id deploy`).

Les répertoires bind de `torrents` et les médias Jellyfin doivent exister et être
accessibles à `deploy` : traversée des parents, lecture et écriture selon l'usage.
Les bind mounts refusent de créer silencieusement un chemin absent.
Ne pas appliquer les anciens exemples `chown 1000:1000` sur l'hôte.
Si SELinux est actif, les chemins doivent également avoir une étiquette autorisant
les conteneurs ; pour un chemin partagé utiliser un label partagé, pas privé.

Seerr, Tracearr et les bases gardent les utilisateurs définis par leurs images.
Leurs volumes nommés sont initialisés avec les propriétaires internes appropriés.
Leurs UID internes sont des UID subordonnés sur l'hôte : ne pas les remplacer
par 1001 et ne pas appliquer de `chown -R deploy` aux données PostgreSQL.
Les configurations et volumes d'un ancien moteur rootful ne sont pas visibles
dans le moteur rootless : sauvegarder puis migrer avant de démarrer les stacks.

## Domaines et déploiement

Dans chaque dossier, copier `example.env` en `.env` et renseigner les valeurs,
ou les définir dans les variables de la stack Komodo. Les domaines sont des noms
DNS seuls, sans protocole ni chemin. Tracearr exige aussi des secrets et les
adresses des proxys : voir son README.

Pour chaque domaine, configurer le DNS vers BunkerWeb puis un upstream BunkerWeb
vers `https://<IP privée Traefik>:8443` (ou le port HTTPS choisi). Préserver Host,
SNI et les en-têtes X-Forwarded, vérifier le certificat, autoriser les WebSockets
et les flux longs. Le HTTP public est redirigé selon la configuration du proxy.

Depuis chaque dossier :

```sh
docker compose config --quiet
docker compose up -d
docker compose ps
docker compose logs --tail=100
```

Terminer les assistants et configurer les comptes d'accès via un accès restreint
côté BunkerWeb avant de rendre les nouveaux domaines publics. Les applications
utilisent leur authentification native ; le middleware Authentik de l'API Traefik
n'est pas appliqué à ces routes.

## Vérification

Le parsing Compose valide la structure et les variables, pas les droits du
serveur ni ses pilotes. Après déploiement, vérifier la connexion HTTPS à chaque
service, la connexion de qui à qBittorrent, les recherches Prowlarr, la liaison de
Seerr/Tracearr avec Jellyfin et un transcodage NVIDIA (guide Jellyfin).

Sources : [Docker rootless](https://docs.docker.com/engine/security/rootless/),
[qui Docker](https://getqui.com/docs/getting-started/docker/),
[LinuxServer qBittorrent](https://docs.linuxserver.io/images/docker-qbittorrent/),
[LinuxServer Prowlarr](https://docs.linuxserver.io/images/docker-prowlarr/).
