# Renovate auto-hébergé

Même modèle que les autres dépôts d'infrastructure : `renovate.json` couvre
récursivement toutes les stacks et images CI, `.gitlab-ci.yml` inclut
`.gitlab/renovate.gitlab-ci.yml` (socle identique aux autres dépôts) et
`.gitlab/tests.gitlab-ci.yml` (tests médias séparés). Managers complémentaires pour les images
interpolées et ancres `x-…image`. Une seule planification par dépôt.

## Activation sur le GitLab personnel

Le remote local pointe actuellement vers GitHub. Les fichiers GitLab sont
fournis à ta demande mais n'y lancent rien : publier sur le projet GitLab voulu
est un prérequis distinct. Aucun remote, push, projet ou paramètre GitLab n'est
modifié automatiquement.

1. Publier les fichiers après revue. Protéger la branche par défaut, interdire
   les push directs du bot et activer **Pipelines must succeed**, sans accepter
   les pipelines ignorés comme validation. Les MR non fiables ne doivent pas
   recevoir de variables ou runners protégés.
2. Prévoir un runner isolé sans privilèges, socket Docker ni DinD pour les
   validations de MR. Le bot peut utiliser un runner protégé distinct. Aucun
   tag de runner ou adresse d'infrastructure n'est inventé dans cette CI.
3. Utiliser un compte bot dédié ou project access token expirant, scope `api`,
   rôle minimal permettant branches/MR et fusion selon la protection GitLab.
   Stocker `RENOVATE_TOKEN` masqué **et protégé**, jamais dans Git. Ne pas le
   remplacer par `CI_JOB_TOKEN`.
4. Le runner doit déjà faire confiance à la PKI pour le clone et les images.
   Si nécessaire ajouter `RENOVATE_CA_BUNDLE`, variable **File** contenant un
   bundle PEM public + CA internes, sans clé privée. Le job le fournit à Node
   et Git, sans désactiver TLS. Les registres privés peuvent être configurés
   par `RENOVATE_HOST_RULES` protégé avec accès minimal.
5. Créer une planification sur la branche par défaut protégée, par exemple
   nocturne. Premier lancement avec `RENOVATE_DRY_RUN=full` : examiner les
   résultats avant de retirer cette variable. Le bot ne s'exécute jamais dans
   les pipelines de MR ; le lancement web demande une action manuelle.

## Politique et garde-fous

- `pinDigests: true` : conserver `image:version@sha256:digest`.
- Mineures, correctifs et renouvellements de SHA de tags complets : fusion par
  Renovate après CI verte (`platformAutomerge: false`, `ignoreTests: false`).
  Une exécution ultérieure du bot peut être nécessaire pour fusionner.
- Majeures, premiers épinglages et remplacements : revue/fusion humaines.
- Tags incomplets/flottants et mineures pré-1.0 : revue manuelle. Actuellement,
  Jellyfin `12.3`, TimescaleDB `pg18.4-ts2.29.1` et les formats LinuxServer
  Prowlarr/qBittorrent restent donc manuels avec le filtre commun, y compris
  pour leurs SHA. Vérifier séparément PostgreSQL, TimescaleDB et les migrations.
- Les exceptions communes PostgreSQL (versions complètes à deux nombres) et
  Hermes (renouvellement du volume source à revoir) restent présentes, même si
  ces images ne figurent pas ici. Les six règles sont ainsi identiques aux autres
  dépôts ; l'exception PostgreSQL ne s'applique pas à l'image TimescaleDB.
- Les images du bot et des validations sont suivies elles aussi, sans recopier
  les images Compose dans `example.env`. Revoir les éventuelles surcharges
  d'image Komodo sans lire ni publier les secrets.
- Aucun déploiement Docker/Komodo lancé par cette CI. Vérifier les éventuels
  webhooks préexistants ; fusion Git et déploiement restent deux opérations.
  Sauvegarde, compatibilité des volumes et restauration restent obligatoires.

## Validations

`compose-image-policy` contrôle YAML/ancres et versions + SHA des images sans
daemon ni `.env`. `stack-tests` contrôle notamment les montages en écriture,
utilisateurs et isolation. Les tests n'immobilisent pas les images au SHA du
commit initial : une mise à jour Renovate doit pouvoir passer la CI.
Ce job ne fournit pas de CLI Compose : le test de rendu est signalé comme
ignoré en CI ; il reste exécutable localement avec `COMPOSE_BIN` et fixtures
factices. `renovate-config-check` emploie le validateur officiel strict.

Ces contrôles ne valident ni migrations, runtime rootless, droits réels, GPU
ou TLS. Ne pas confondre CI verte et autorisation de déployer en production.
La configuration doit être validée dans le GitLab cible avant activation du bot.

## Désactivation / retour arrière

Désactiver la planification arrête le bot ; révoquer son token si nécessaire.
Une fusion se revient par commit après revue. Si un déploiement a migré les
données, restaurer les données compatibles, pas uniquement l'ancienne image.
Ne pas toucher aux volumes pour activer/désactiver Renovate.

Sources : [GitLab](https://docs.renovatebot.com/modules/platform/gitlab/),
[Compose](https://docs.renovatebot.com/modules/manager/docker-compose/),
[GitLab CI](https://docs.renovatebot.com/modules/manager/gitlabci/),
[configuration](https://docs.renovatebot.com/configuration-options/).
