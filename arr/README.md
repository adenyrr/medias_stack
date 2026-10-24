# Arr — Prowlarr

Renseigner `PROWLARR_HOST` et suivre le [guide commun](../README.md).
Prowlarr conserve sa configuration dans `arr_prowlarr-config` et écoute sur 9696
uniquement dans Docker. L'interface est publiée en HTTPS par Traefik.

Terminer l'assistant d'authentification avant l'accès public, puis configurer les
indexeurs et les intégrations. qBittorrent est joignable sur
`http://qbittorrent:8080` avec ses identifiants via le réseau `traefik`.
Prowlarr n'a pas besoin de monter les répertoires de téléchargement.

Source : [image LinuxServer Prowlarr](https://docs.linuxserver.io/images/docker-prowlarr/).
