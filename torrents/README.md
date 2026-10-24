# Torrents — qBittorrent et qui

Les deux services utilisent le même `${MEDIAS}` hôte monté en `/downloads`, ce
qui préserve les anciens chemins qBittorrent et permet à qui de manipuler les
mêmes fichiers. Leurs configurations `/config` restent séparées.

Les interfaces HTTPS utilisent `QBITTORRENT_HOST` et `QUI_HOST` via Traefik.
Seuls les ports des pairs 6881 TCP/UDP restent publiés. Pour que les connexions
BitTorrent entrantes fonctionnent, acheminer ces ports vers l'hôte dans le
routeur/pare-feu ; ils ne passent pas par BunkerWeb. Le port d'écoute configuré
dans qBittorrent doit rester 6881.

## Migration des anciennes stacks

1. Sauvegarder les configurations qBittorrent et qui, y compris `qui.db`, ses
   fichiers WAL éventuels et `config.toml` (secret de session).
2. Relever les **chemins absolus** réellement montés par les anciens conteneurs :

   ```sh
   docker inspect qbittorrent qui --format '{{.Name}} {{json .Mounts}}'
   ```

3. Copier `example.env` en `.env` et renseigner `QBITTORRENT_CONFIG` avec l'ancien
   `CONFIG`, `QUI_CONFIG` avec l'ancien dossier `qui/qui`, et `MEDIAS` avec le même
   dossier que précédemment. Les répertoires doivent déjà exister et être
   accessibles à `deploy`. Ne pas créer une configuration vierge pour remplacer
   une configuration existante. Pour une installation neuve, créer les dossiers
   sous le compte `deploy` avant de déployer.
4. Arrêter et retirer les anciens conteneurs avant de lancer la nouvelle stack
   (mêmes noms `qbittorrent` et `qui`). Désactiver leurs anciens déploiements Komodo
   et pointer la nouvelle stack vers `torrents/compose.yaml`. Ne pas supprimer les
   données ni utiliser `down -v` pour la migration. Si le moteur change, transférer
   les données à l'arrêt et adapter leurs droits au compte `deploy`.
5. Appliquer les étapes du [guide commun](../README.md).

Dans qui, ajouter l'instance `http://qbittorrent:8080` avec les identifiants
qBittorrent, puis activer **Local Filesystem Access** si nécessaire.
Le réseau privé de stack `torrents` permet cette communication. Les chemins
internes doivent être `/downloads/...` dans les deux applications, sans remapping.

Conserver l'authentification qBittorrent et ses protections CSRF/Host. Si le proxy
est refusé, autoriser explicitement le domaine public et le nom `qbittorrent`
dans les domaines serveur de la Web UI ; renseigner les proxys de confiance
selon les adresses réellement utilisées. Ne pas désactiver globalement ces
protections. Vérifier connexion et ajout d'un torrent via qui et via la Web UI.

Source : [qui — Docker et accès aux fichiers](https://getqui.com/docs/getting-started/docker/).
