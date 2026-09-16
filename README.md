# Latros

Latros est un projet de recherche et de conception pour une application médicale locale, *offline first*, d'aide à l'orientation clinique.

Le projet vise un moteur de diagnostic différentiel structuré et explicable, fondé sur des connaissances médicales versionnées. Un LLM peut assister la compréhension du langage, la formulation des questions et l'explication, mais ne remplace pas le moteur clinique.

> Statut : phase de conception. Aucun moteur diagnostique, importateur de données ou interface n'est encore implémenté.

## Principes

- Le moteur clinique doit fonctionner sans LLM.
- Les signes présents, absents et inconnus sont distincts.
- Chaque assertion médicale conserve sa source, sa version et sa provenance.
- Le triage des drapeaux rouges est séparé du diagnostic différentiel.
- Les résultats sont des hypothèses et de l'aide à l'orientation, jamais un diagnostic médical certain.
- Les données patient, poids de modèles et sources médicales brutes ne sont pas versionnés dans ce dépôt.

## Documentation

La conception détaillée est disponible dans [projet.md](projet.md). Elle couvre notamment :

- le modèle de données médical ;
- la fusion des sources et la gestion des identifiants ;
- le moteur différentiel et les questions adaptatives ;
- l'explicabilité, la provenance et la reproductibilité ;
- les rôles de MedGemma et de TxGemma ;
- le protocole d'évaluation et les limites scientifiques.

Les décisions d'architecture seront ajoutées dans [docs/decisions](docs/decisions/README.md).

## Organisation du dépôt

```text
Latros/
├── projet.md                # conception générale
├── README.md                # point d'entrée du dépôt
├── CONTRIBUTING.md          # règles de contribution
├── docs/
│   └── decisions/           # journal des décisions d'architecture
└── .github/                 # modèles d'issues et de pull requests
```

Les futurs dossiers de code, de données et de modèles seront créés seulement après les décisions de phase 0.

## Démarrer

Après publication du dépôt privé :

```bash
git clone git@github.com:GaetanAff/Latros.git
cd Latros
```

Pour récupérer les évolutions :

```bash
git pull --ff-only
```

## Sécurité et confidentialité

Ne jamais ajouter au dépôt :

- données patient ou enregistrements identifiants ;
- mots de passe, clés ou jetons ;
- modèles téléchargés ;
- bases médicales brutes soumises à une licence, une authentification ou des restrictions de redistribution.

## Licence

Aucune licence de redistribution n'est définie à ce stade. Le dépôt est prévu comme privé ; une licence sera choisie avant toute ouverture ou distribution.

