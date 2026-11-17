# Tracearr

Stack composée de l'image officielle Tracearr, de TimescaleDB/PostgreSQL 18 et
de Redis. Seul Tracearr rejoint `traefik` ; les bases sont sur le réseau interne
`backend`, sans port publié. Les données utilisent des volumes nommés adaptés
aux utilisateurs des images en Docker rootless.

Copier `example.env` vers `.env` ou définir les variables dans Komodo.
Générer séparément `DB_PASSWORD`, `JWT_SECRET`, `COOKIE_SECRET` et
`BETTER_AUTH_SECRET` avec `openssl rand -hex 32`. Conserver ces valeurs : leur
rotation affecte les sessions et, pour PostgreSQL, modifier la variable ne
modifie pas le mot de passe d'une base déjà initialisée. Le mot de passe généré
en hexadécimal peut être inséré sans échappement dans `DATABASE_URL`.

Renseigner `TRACEARR_HOST` et `TRUST_PROXY` : adresses IP/CIDR explicites de
Traefik et BunkerWeb dans la chaîne proxy, séparées par des virgules. Relever
l'adresse de Traefik avec :

```sh
docker inspect --format '{{(index .NetworkSettings.Networks "traefik").IPAddress}}' traefik
```

Pour BunkerWeb, tenir compte de l'adresse source réellement vue après le NAT
rootless et de la configuration `EXTERNAL_PROXY` de Traefik. Mettre à jour les
valeurs si les adresses changent. Éviter une confiance globale dans tous les
proxys. L'origine CORS est limitée à `https://<TRACEARR_HOST>`.

Suivre le [guide commun](../README.md), puis connecter Jellyfin à
`http://jellyfin:8096` avec sa clé API. Vérifier l'ouverture d'une session et la
remontée d'une lecture Jellyfin.

Prévoir les ressources pour les trois services, notamment 512 Mio de mémoire
partagée pour PostgreSQL et environ 1 Gio pour Tracearr. Le service utilisateur
Docker doit autoriser une limite de 65536 descripteurs de fichiers pour la base.

Cette configuration PostgreSQL 18 est destinée à une nouvelle installation ;
ne pas y monter directement des données PostgreSQL d'une autre version majeure.
Utiliser les fonctions de sauvegarde/restauration de Tracearr pour les données,
pas une copie des fichiers d'une base en fonctionnement.

Sources : [installation officielle](https://docs.tracearr.com/getting-started/installation),
[Compose PostgreSQL 18](https://github.com/connorgallopo/Tracearr/blob/main/docker/examples/docker-compose.pg18.yml).
