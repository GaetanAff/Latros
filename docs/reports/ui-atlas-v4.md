# Atlas de navigation v4 — série locale

28 septembre 2026. Les illustrations sont **générées et non validées anatomiquement** ; elles
servent à la navigation UX, jamais à déduire une localisation clinique ou une assertion.

L'arbre `src/latros/ui/assets/anatomy/navigation.json` v3 possède 47 nœuds. Le manifeste
`illustrations.json` recense 37 illustrations locales (sept antérieures et trente nouvelles)
avec fichier, SHA-256, statut et famille de prompt. Les nouveaux visuels cohérents couvrent
thorax, poumons, cœur ; abdomen, estomac, foie, intestins ; système urinaire, reins, uretères,
vessie ; épaule, bras, coude, avant-bras, poignet, main ; hanche, cuisse, genou, jambe, cheville,
pied ; dos, colonne et régions cervicale, thoracique et lombaire. La génération est originale,
sans image distante au runtime. Un prompt ne garantit pas une reproduction byte pour byte : les
fichiers versionnés et leurs hashes sont la référence visuelle.

L'image bitmap, les zones SVG transparentes et les labels HTML restent trois couches séparées.
Le bouton d'une région et sa zone sur l'image partagent un seul état hover/focus/sélection :
survoler l'un teinte l'autre, sans logique médicale dans le navigateur. Toutes les entrées du
catalogue anatomique sont des IDs potentiels explicites ; le backend les résout dans le snapshot
actif et masque les codes absents/ambigus. Une sélection crée la même observation canonique que
la recherche et `present` par défaut, modifiable ensuite. Aucun `body_site` n'est inféré.

Le script `uv run --offline --no-sync python scripts/audit_ui_anatomy.py` audite les références
sur le vrai snapshot. Exemples de liens supportés : sinus 7/7, thorax 10/10, poumons 11/11,
cœur 7/8, abdomen 12/13, intestins 6/8, urinaire 11/11, dos 4/4. Les références non résolues
sont cachées, non remplacées par analogie. Une planche n'est pas un atlas de référence : revue
anatomique humaine et extensions des mappings UI resteront nécessaires avant toute prétention
de précision pédagogique.
