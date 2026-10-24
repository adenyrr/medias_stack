# Jellyfin — Traefik et NVIDIA rootless

Jellyfin est accessible uniquement via `https://<JELLYFIN_HOST>` et le réseau
Docker `traefik`. Aucun port hôte n'est publié : découverte UDP et DLNA ne sont
pas exposés. L'image conserve les volumes `jellyfin_jellyfin-config` et
`jellyfin_jellyfin-cache`, le montage `/media` et la réservation du GPU NVIDIA.

Lire d'abord les prérequis du [guide commun](../README.md). Le `user: "0:0"`
correspond au compte hôte `deploy` (UID 1001) en Docker rootless. Renseigner
`JELLYFIN_HOST` et `MEDIAS` dans `.env` ou Komodo. En cas de migration depuis un
autre moteur Docker, sauvegarder et restaurer les volumes avant démarrage ;
leur nom seul ne transfère aucune donnée.

## Préparation NVIDIA sur le serveur

Installer le pilote NVIDIA compatible avec le GPU et NVIDIA Container Toolkit
selon la documentation officielle. Vérifier `nvidia-smi` depuis la session
`deploy`. Configurer le runtime **dans cette session utilisateur**, pas dans la
configuration du daemon rootful :

```sh
nvidia-ctk runtime configure --runtime=docker --config="$HOME/.config/docker/daemon.json"
systemctl --user restart docker
```

L'administrateur doit aussi configurer le toolkit pour le mode rootless :

```sh
sudo nvidia-ctk config --set nvidia-container-cli.no-cgroups --in-place
```

Ce dernier réglage concerne `/etc/nvidia-container-runtime/config.toml` sur
l'hôte. Il est global : tenir compte des autres workloads GPU éventuels. `deploy`
doit pouvoir accéder aux périphériques `/dev/nvidia*`, y compris `nvidia-uvm`.
Une simple appartenance à un groupe supplémentaire sur l'hôte ne garantit pas
l'accès dans le user namespace ; vérifier le test conteneur ci-dessous et les
droits/ACL des périphériques si celui-ci échoue. Ne pas contourner le problème
avec `privileged: true`.

Le Compose sélectionne explicitement `runtime: nvidia`, réserve tous les GPU et
demande les capacités NVIDIA `compute,video,utility` pour CUDA, NVENC/NVDEC et
`nvidia-smi`.

## Validation puis démarrage

Depuis ce dossier, en tant que `deploy`, avec son moteur rootless :

```sh
export DOCKER_HOST=unix:///run/user/1001/docker.sock
docker info --format '{{json .SecurityOptions}}'
docker info --format '{{json .Runtimes}}'   # doit contenir nvidia
docker network inspect traefik
docker compose config --quiet
docker compose run --rm --no-deps --entrypoint nvidia-smi jellyfin
# Test d'encodage NVENC de 30 images synthétiques, sans fichier de sortie.
docker compose run --rm --no-deps --entrypoint /usr/lib/jellyfin-ffmpeg/ffmpeg jellyfin \
  -hide_banner -f lavfi -i testsrc2=size=1280x720:rate=30 \
  -frames:v 30 -c:v h264_nvenc -f null -
docker compose up -d
```

Dans Jellyfin, activer NVIDIA NVENC dans les paramètres de transcodage et ne
cocher que les codecs pris en charge par le GPU. Tester une lecture qui force
le transcodage, puis vérifier les logs FFmpeg et l'activité via `nvidia-smi`.
Le succès de `nvidia-smi` seul ne valide pas l'encodage/décodage vidéo.

Dans Réseau, autoriser les connexions distantes et ajouter l'adresse Docker de
Traefik aux **Known Proxies / proxys connus** :

```sh
docker inspect --format '{{(index .NetworkSettings.Networks "traefik").IPAddress}}' traefik
```

Actualiser cette valeur si l'adresse change ; laisser l'URL de base vide.

La configuration est adaptée à rootless, mais sa validation matérielle exige
les commandes ci-dessus sur le serveur disposant du GPU.

Sources : [NVIDIA — configuration rootless](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html#rootless-mode),
[Jellyfin — NVIDIA](https://jellyfin.org/docs/general/post-install/transcoding/hardware-acceleration/nvidia/),
[Jellyfin — Traefik](https://jellyfin.org/docs/general/post-install/networking/reverse-proxy/traefik/).
