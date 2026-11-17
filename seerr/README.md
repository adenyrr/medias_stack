# Seerr

Renseigner `SEERR_HOST`, puis suivre le [guide commun](../README.md).
L'image officielle conserve son utilisateur `node` et sa configuration dans le
volume `seerr_seerr-config` ; `init: true` assure la gestion des processus.
Aucun port hôte n'est publié ; Traefik rejoint le service sur 5055.

Dans l'assistant, utiliser `http://jellyfin:8096` pour la connexion interne à
Jellyfin et `https://<JELLYFIN_HOST>` pour son adresse publique. Configurer
l'URL publique Seerr et les permissions des utilisateurs. Ajouter ensuite
Sonarr/Radarr si souhaité : ils ne sont pas inclus dans la stack Prowlarr.

Source : [Seerr — Docker](https://docs.seerr.dev/getting-started/docker/).
