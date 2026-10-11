"""
PMZilla Lab — table de classement des livres : domaines et MAPPING.

Module commun à sort_by_domain.py (copie des livres par domaine) et à convert_books.py (--redo-figures retrouve
par cette table un Markdown dont le nom diffère de sa source). Une seule table : jamais de copie.

MAPPING : « chemin du Markdown, relatif au dossier qui contient Bibliotheque-MD/Livres - Ressources » -> codes de
domaine (chaîne vide = livre écarté). Les commentaires de MAPPING sont lus par dashboard.py (livres absents).
"""
import unicodedata

DOMAINS = {
    "P": "produit",
    "D": "flow",
    "O": "organisation",
    "F": "facilitation",
    "T": "tech",
}

R = "Livres - Ressources/"

MAPPING = {
    # Agile & Scrum
    R + "Agile & Scrum/2022-16th-Annual-State-Of-Agile-Report.md": "O",
    R + "Agile & Scrum/Graham Shaw - The Art of Business Communication.md": "F",
    R + "Agile & Scrum/Kent Beck, Cynthia Andres - Extreme Programming Explained (2nd ed).md": "DT",
    R + "Agile & Scrum/agile-fluency-french-version.md": "",  # doublon : on garde l'original anglais
    R + "Agile & Scrum/agile-fluency-project-ebook-rtw-1.md": "OD",
    R + "Agile & Scrum/Building the Agile Business through Digital Transformation_ How to Lead Digital Transformation in Your Workplace.md": "O",
    R + "Agile & Scrum/Clean Agile Back to Basics by Robert C. Martin.md": "D",
    R + "Agile & Scrum/Lyssa Adkins - Coaching Agile Teams.md": "FO",
    R + "Agile & Scrum/The_Art_of_Agile_Development.md": "DT",
    R + "Agile & Scrum/The.Lean-Agile.Way.md": "D",
    R + "Agile & Scrum/un_guide_de_survie_à_l_adoption_ou_transformation_agile___travailler_avec_la_culture_d_une_organisation.md": "",  # doublon FR d'Agile Survival Guide
    # AI & Machine Learning
    R + "AI & Machine Learning/Concevoir des applications avec des agents - Michael Albada.md": "T",
    R + "AI & Machine Learning/Large Language Models - Stephan Raaijmakers (The MIT Press Essential Knowledge series) 2025.md": "T",
    # Communication & Social Skills (deux livres distincts, pas un doublon)
    R + "Communication & Social Skills/(Le Livre de Poche) Dale Carnegie, Didier Weyne - Comment se faire des amis-Hachette (1990).md": "F",
    R + "Communication & Social Skills/Dale Carnegie - Comment se faire des amis à l_ère numérique-Presses du Châtelet (2013).md": "F",
    # DevOps & Platform Engineering
    R + "DevOps & Platform Engineering/Decoding Platform Engineering Patterns.md": "TO",
    R + "DevOps & Platform Engineering/Fundamentals of DevOps and Software Delivery A Hands-On Guide to Deploying and Managing Software in Production O reilly 2025 .md": "TD",
    R + "DevOps & Platform Engineering/Platform Engineering for Architects - Max Krbcher Andreas Grabner Hil.md": "T",
    R + "Hyper-Agile Testing Delivering Software in an AI-Accelerated World 2026.md": "TD",
    # Leadership & Management
    R + "Leadership & Management/Carol S. Dweck - Mindset.md": "F",
    R + "Leadership & Management/La boîte à outils de la méthode OKR Objectifs et.md": "OP",
    R + "Leadership & Management/Leadership agilité bonheur au travail...bullshit.md": "O",
    R + "Leadership & Management/Lencioni-The Five Dysfunctions of a Team.md": "F",
    R + "Leadership & Management/Management Divided Contradictions of Labor Management  Matt Vida 2022.md": "O",
    R + "Leadership & Management/The OKRs Field Book Ben Lamorte 2021.md": "OP",
    R + "Leadership & Management/Travailler en equipe - Krogerus Mikael, Tschappeler Roman 2024.md": "F",
    R + "Leadership & Management/Daniel H. Pink - Drive.md": "OF",
    # Lean & Continuous Improvement
    R + "Lean & Continuous Improvement/Gemba Kaizen_ A Commonsense Approach to a Continuous Improvement Strategy 2_E.md": "D",
    R + "Lean & Continuous Improvement/Hôpital apprenant, L’ - Michael Ballé, Guillaume Couillard & Anne-Lise Seltzer.md": "OD",
    R + "Lean & Continuous Improvement/Kaizen.md": "",  # pas un livre : courte présentation sans auteur, retirée de la bibliothèque (R-9)
    R + "Lean & Continuous Improvement/Le Lean management au cœur des services (French Edition).md": "D",
    R + "Lean & Continuous Improvement/Lean en ingénierie_ Guide de voyage - Les meilleurs itinéraires pour développer vos nouveaux produits et satisfaire vos clients (Management Lean) (French Edition).md": "DP",
    R + "Lean & Continuous Improvement/Lean et leadership (Management Lean) (French Edition).md": "O",
    R + "Lean & Continuous Improvement/Mike Cohn - Agile Estimating and Planning.md": "DP",
    R + "Lean & Continuous Improvement/The Lean Tech Manifesto - Fabrice Bernhard 2024.md": "OT",
    # Miscellaneous
    R + "Miscellaneous/Crossing the Chasm, 3rd Edition_ Marketing and Selling Disruptive Products to Mainstream Customers.md": "P",
    R + "Miscellaneous/Gaming - sociologie du jeu vidéo Jean-Philippe Dubrulle 2024.md": "F",  # serious games
    # Organizational Change & Transformation
    R + "Organizational Change & Transformation/Designing Organizations Stefan Kühl, Judith Muster  2025.md": "O",
    R + "Organizational Change & Transformation/Digital Business Transformation - Nigel Vaz.md": "O",
    R + "Organizational Change & Transformation/Leading Change.md": "O",
    R + "Organizational Change & Transformation/OCTO_Culture_CHANGE_Web.md": "O",
    R + "Organizational Change & Transformation/OCTO_CULTURE_SCALING_KAIZEN_WEB.md": "",  # doublon : on garde la version EPUB, plus propre
    R + "Organizational Change & Transformation/Org-topologies-the-primer.md": "O",
    R + "Organizational Change & Transformation/OrgTopologies.md": "O",
    R + "Organizational Change & Transformation/the-fifth-discipline.md": "O",
    R + "Organizational Change & Transformation/To Accelerate Change in 2015 - Kotter International.md": "O",
    # Personal Development & Mindset
    R + "Personal Development & Mindset/Mark McKergow, Helen Bailey - Host.md": "F",
    R + "Personal Development & Mindset/Origgi Quest-ce que la confiance 2008.md": "F",
    # Product Management & Discovery
    R + "Product Management & Discovery/Discovery Discipline_ La méthode radicale pour exceller en Product Discovery (French Edition).md": "P",
    R + "Product Management & Discovery/INSPIRED_ How to Create Tech Products Customers Love.md": "P",
    R + "Product Management & Discovery/Jeff Patton - Le story mapping (2015).md": "",  # doublon FR : on garde l'édition O'Reilly
    R + "Product Management & Discovery/Product Leadership_ How Top Product Managers Launch Awesome Products and Build Successful Teams.md": "PO",
    R + "Product Management & Discovery/Project to Product - Mik Kersten.md": "OPD",
    R + "Product Management & Discovery/The Principles of Product Development Flow_ Second Generation Lean Product Development.md": "DP",
    R + "Product Management & Discovery/The Product-Minded Engineer Building Impactful Software for Your Users Drew Hoskins O reilly 2025.md": "PT",
    R + "Product Management & Discovery/User Story Mapping Jeffe Patton O reilly 2014.md": "PD",
    # Software Engineering & Architecture
    R + "Software Engineering & Architecture/Alberto Brandolini - Introducing EventStorming-Leanpub (2018).md": "TPF",
    R + "Software Engineering & Architecture/Architecture for Flow Susanne Kaiser Addison-Wesley 2026.md": "TOD",
    R + "Software Engineering & Architecture/Balancing Coupling in Software Design 2026 Vlad Khononov Addison-Wesley 2026.md": "T",
    R + "Software Engineering & Architecture/bddbooks-discovery.md": "TP",
    R + "Software Engineering & Architecture/bddbooks-formulation.md": "T",
    R + "Software Engineering & Architecture/dddvitefait.md": "T",
    R + "Software Engineering & Architecture/Vaughn Vernon - Domain-Driven Design Distilled-Addison-Wesley Professional (2016).md": "T",
    # UX & Design
    R + "UX & Design/04_Cours_MethodoUX_MDulot_Organisation.md": "P",
    R + "UX & Design/Lean UX_ Applying Lean Principles to Improve User Experience.md": "",  # doublon : on garde la version EPUB, plus propre
    R + "UX & Design/Rachel Davies, Liz Sedley - Agile Coaching.md": "F",
    R + "UX & Design/Michael Sahota - An Agile Adoption and Transformation Survival Guide.md": "OF",

    # À re-télécharger d'une autre source (le fichier portait un autre livre ; seconde remise en ordre du 5 octobre 2026),
    # avec les domaines de leur ancienne entrée :
    #   Practices for Scaling Lean & Agile Development (Larman, Vodde) OD ;
    #   Behind Closed Doors (Rothman, Derby) FO ;
    #   The Sketchnote Handbook et The Sketchnote Workbook (Rohde) F ; Leadership Agility (Joiner, Josephs) OF.

    # Livres absents de la bibliothèque (fichiers mal nommés, remis en ordre le 5 octobre 2026) : à re-télécharger.
    #   Switch (Heath).

    # --- Ajouts du 3 octobre 2026 (livres issus des EPUB) ---
    R + "AI Agents - Nicole Koenigstein O reilly october 2026.md": "T",
    R + "Latency Reduce delay in software systems Manning 2026.md": "T",
    R + "Agile & Scrum/Ryan Ripley, Todd Miller - Fixing Your Scrum.md": "DF",
    R + "Agile & Scrum/Malcolm Gladwell - Blink.md": "",  # écarté : hors sujet
    R + "Agile & Scrum/Mike Cohn - User Stories Applied.md": "PD",
    R + "Agile & Scrum/SAFe(R) Coaches Handbook Proven tips and techniques for launching and running SAFe(R) Teams, ARTs, and Portfolios in an Agile Enterprise by Darren Wilmshurst, Lindy Quick 2023.md": "OD",
    R + "Agile & Scrum/cfd.md": "D",  # à vérifier : supposé porter sur le Cumulative Flow Diagram
    R + "Communication & Social Skills/BookHabits - Summary of Principles by Ray Dalio.md": "",  # écarté : doublon du livre complet (Ray Dalio - Principles)
    R + "DevOps & Platform Engineering/Accelerate.md": "DTO",
    R + "DevOps & Platform Engineering/The Platform Engineering Playbook 2025 Early access.md": "TO",
    R + "Leadership & Management/Sharon L. Bowman - Training from the Back of the Room (DE).md": "F",
    R + "Leadership & Management/Robert Greene - The Laws of Human Nature.md": "F",
    R + "Leadership & Management/Johanna Rothman - Practical Ways to Manage Yourself.md": "OF",
    R + "Miscellaneous/RocketGuide1.01noIllustrations.md": "OD",  # Agile Rocket Guide, collectif, booksprint 2016 (CC BY-NC-ND)
    R + "Organizational Change & Transformation/Ray Dalio - Principles.md": "O",
    R + "Organizational Change & Transformation/culture-scaling-kaizen-version-epub.md": "OD",  # version EPUB d'OCTO Culture Scaling Kaizen
    R + "Personal Development & Mindset/Joe Navarro - Narcissists Among Us.md": "",  # écarté : hors sujet
    R + "Personal Development & Mindset/Robert Greene - Mastery (concise).md": "",  # écarté : version concise, hors sujet
    R + "Product Management & Discovery/Marty Cagan_Chris Jones_ Empowered_ Ordinary People, Extraordinary Products (2020).md": "PO",
    R + "Product Management & Discovery/Teresa Torres - Continuous Discovery Habits_ Discover Products that Create Customer Value and Business Value (2021, Product Talk LLC).md": "P",
    R + "UX & Design/Lean UX_ Applying Lean Principles to Improve User Experience .md": "P",  # version EPUB de Lean UX
    R + "UX & Design/atomic-design.md": "PT",
    R + "Team Topologies - Matthew Skelton 2nd ed.md": "ODT",
    # Books (ajout d'octobre 2026)
    R + "Books/Gamestorming_A_Playbook_for_Innovators,_Rulebreakers,_and_Changemakers.md": "FP",
    R + "Books/Kanban PDF.md": "",  # remplacé par le livre complet d'Anderson
    R + "Books/Measure-What-Matters-John-Doerr.md": "PO",
    R + "Books/Radical_Focus_Achieving_Your_Most_Important_Goals_with_Objectives_and_Key_Results_Christina_Wodtke_Marty_Cagan.md": "PO",
    R + "Books/Testing_Business_Ideas.md": "P",
    R + "Books/The_Fearless_Organization_Creating_Psychological_Safety_in_the_Workplace.md": "FO",
    R + "Books/The_Goal_A_Process_Of_Ongoing_Improvement_Eliyahu_M_Goldratt,_Jeff.md": "DO",
    R + "Books/competing-against-luck-the-story-of-innovation-and-customer-choice.md": "P",
    R + "Books/jobs_to_be_done_book.md": "P",

    # --- Ajouts du 5 octobre 2026 (livres vérifiés) ---
    R + "Books/Geoff Watts - Scrum Mastery.md": "FD",
    R + "Books/Stacia Viscardi - The Professional ScrumMaster's Handbook.md": "FD",
    R + "Books/Opelt, Gloger, Pfarl, Mittermayr - Agile Contracts.md": "O",

    # --- Ajouts du 5 octobre 2026 (livres vérifiés par audit) ---
    R + "Books/Kanban Successful Evolutionary Change for Your Technology Business by David J. Anderson.md": "DO",
    R + "Books/Cardon-Coaching-d-Equipe.md": "FO",
    R + "Books/Coaching for meaning the culture and practice of coaching Lenhardt, Vincent Responsables porteurs de sens.md": "FO",
    R + "Books/mots sont des fenetres (ou bien s), Les - Rosenberg, Marshall B_.md": "F",

    # --- Ajouts du 6 octobre 2026 (livres vérifiés par audit) ---
    R + "Books/Patterns, Principles and Practices of Domain-Driven Design.md": "T",
    R + "Books/Platform Engineering - Camille Fournier.md": "TO",  # EPUB gardé, PDF ignoré (même ISBN)
    R + "Books/funretrospectives.md": "FD",
    # --- Ajout du 6 octobre 2026 (livre jamais converti ; domaine proposé, à valider) ---
    R + "Books/The Surprising Power of Liberating Structures - Henri Lipmanowicz, Keith McCandless.md": "F",
    # --- Ajout du 9 octobre 2026 (domaines proposés, à valider) ---
    R + "Books/Impact-first_Product_Teams_-_Matt_LeMay.md": "P",
    R + "Books/The_Lean_Startup__How_Todays_Entrepreneur_-_Eric_Ries.md": "P",
    R + "Books/Agile_Retrospectives_2nd_Ed_A_Practical_Guide_-_Esther_Derby.md": "FD",
    R + "Books/Accelerate_-_John_P_Kotter.md": "O",
    R + "Books/Adaptive_Leadership_Accelerating_Enterprise_Agility_-_Jim_Highsmith.md": "O",
    R + "Books/Rethinking_Agile_Why_Agile_Teams_Have_Nothing_To_Do_With_Business_Agility_-_Klaus_Leopold.md": "OD",
    R + "Books/Practical_Ways_to_Lead_an_Innovative_Organ_-_Johanna_Rothman.md": "OF",
    R + "Books/Actionable_Agile_Metrics_for_Predictability_An_Introduction_-_Daniel_S_Vacanti.md": "D",
    R + "Books/Product_Management_-_SA_Chunawalla.md": "P",
    R + "Books/Zombie_Scrum_Survival_Guide_-_Barry_Overeem.md": "DF",
    R + "Books/Lean_Analytics_-_Alistair_Croll_Benjamin_Yoskovitz.md": "P",
    # --- Ajouts du 11 octobre 2026 (domaines validés par l'utilisateur) ---
    R + "Books/Human_Robot_Agent_-_Jurgen_Appelo.md": "OT",
    R + "Books/Louder_Than_Words_-_Joe_Navarro.md": "F",
    R + "Books/Management_30_Leading_Agile_Developers_Developing_Agile_Leaders_-_Jurgen_Appelo.md": "OF",
    R + "Books/Output_to_Outcome_-_Mik_Kersten.md": "OPD",
    R + "Books/Peopleware_-_Tom_DeMarco.md": "OF",
    R + "Books/Startup_Scaleup_Screwup_-_Jurgen_Appelo.md": "OP",
    R + "Books/The_ART_of_Avoiding_a_Train_Wreck_Practical_Tips_and_Tricks_for_Launching_and_Operating_SAFe_Agile_Release_Trains_-_Em_Campbell-Pretty.md": "OD",
    R + "Books/The_Nexus_Framework_for_Scaling_Scrum_-_Kurt_Bittner.md": "OD",
    R + "Books/The_Secrets_of_Consulting_-_Gerald_M_Weinberg.md": "F",
    R + "Books/Turn_the_Ship_Around__A_True_Story_of_Tur_-_David_Marquet.md": "OF",
    R + "Books/Workout_-_Jurgen_Appelo.md": "FO",
    # Écartés comme doublons : Team Topologies 2nd ed. (déjà ci-dessus, fichier à titre ISBN), Introducing Eventstorming (version Leanpub de 2017, celle de 2018 est au catalogue).
}


# Correspondance explicite source -> Markdown, pour les livres que ni le nom de fichier ni MAPPING ne relient à leur
# Markdown (nom de fichier différent de la source, Markdown renommé à la main). Clé : chemin du livre source relatif
# au dossier des livres (« Livres - Ressources » de Téléchargements), avec son extension. Valeur : le Markdown, comme
# une clé de MAPPING (R + chemin). Utilisée par convert_books.py --redo-figures avant la recherche par nom et par
# MAPPING ; un Markdown absent arrête tout avant la moindre conversion.
SOURCES = {
    "05 Organization, Transformation & Scaling/Team Topologies, 2nd Edition Organizing Business and Technology for "
    "Fast Flow of Value by Matthew Skelton, Manuel Pais 2025.pdf": R + "Team Topologies - Matthew Skelton 2nd ed.md",
    "06 Leadership, Management & Teams/The Fearless Organization  Amy C Edmondson 2018.epub":
        R + "Books/The_Fearless_Organization_Creating_Psychological_Safety_in_the_Workplace.md",
    "01 Agile & Scrum/Stacia Viscardi - The Professional ScrumMaster_s Handbook.pdf":
        R + "Books/Stacia Viscardi - The Professional ScrumMaster's Handbook.md",
    "03 Lean, Flow & Kanban/The Goal A Process of Ongoing Improvement By Eliyahu M. Goldratt, Jeff Cox.epub":
        R + "Books/The_Goal_A_Process_Of_Ongoing_Improvement_Eliyahu_M_Goldratt,_Jeff.md",
    "04 Product, Discovery & UX/Competing Against Luck The Story of Innovation and Customer Choice By Clayton M. "
    "Christensen, Karen Dillon, Taddy Hall, David S. Duncan.epub":
        R + "Books/competing-against-luck-the-story-of-innovation-and-customer-choice.md",
    "04 Product, Discovery & UX/Radical Focus Wodtke.epub":
        R + "Books/Radical_Focus_Achieving_Your_Most_Important_Goals_with_Objectives_and_Key_Results_Christina_Wodtke_Marty_Cagan.md",
    # même livre d'Ulwick (confirmé par book_catalog.yaml, validé par l'utilisateur) : le Markdown vient du PDF
    # jobs_to_be_done_book.pdf diffusé par Strategyn, la société d'Ulwick ; son « © 2018 » est celui de cette diffusion,
    # pas une autre édition. La reconversion le réécrit depuis l'EPUB (l'ancien reste en .md.avant-figures).
    "04 Product, Discovery & UX/Jobs to Be Done Theory to Practice Anthony W_ Ulwick 2016.epub":
        R + "Books/jobs_to_be_done_book.md",
    # même livre que le PDF « 03 Lean, Flow & Kanban/The Lean Tech Manifesto - Fabrice Bernhard 2024.pdf » : l'EPUB
    # remplace le PDF (le PDF est en EXCLUSIONS), comme pour Ulwick ; le Markdown garde son entrée de MAPPING.
    "03 Lean, Flow & Kanban/The_Lean_Tech_Manifesto_-_Fabrice_Bernhard.epub":
        R + "Lean & Continuous Improvement/The Lean Tech Manifesto - Fabrice Bernhard 2024.md",
}

# Sources que la conversion normale ignore (ni convertie, ni listée « sans Markdown »). Clé : chemin du livre source
# relatif au dossier des livres, avec son extension. Valeur : la raison. --redo-figures refuse un livre exclu et le dit.
EXCLUSIONS = {
    "02 Coaching, Facilitation & Training/Gamestorming.Jouer pour innover.Sunni Brown.epub":
        "édition française de Gamestorming (Jouer pour innover) : une édition différente de l'édition anglaise "
        "dont le Markdown est dans Books/ ; ne pas les relier, pour ne pas écraser le Markdown anglais",
    "03 Lean, Flow & Kanban/The Lean Tech Manifesto - Fabrice Bernhard 2024.pdf":
        "remplacé par l'EPUB du même livre (voir SOURCES)",
    "11 Reports, White Papers & Slides/Kaizen.pdf":
        "pas un livre : courte présentation, sans auteur au catalogue ; retirée de la bibliothèque (Gemba Kaizen et Culture Scaling Kaizen restent)",
    "11 Reports, White Papers & Slides/La_révolution_des_pratiques_agiles_à_lère_de_lIA_-_livret.docx.pdf":
        "pas un livre : livret court",
    "04 Product, Discovery & UX/Continuous_Discovery_Habits_-_Teresa_Torres.epub":
        "doublon de l'EPUB déjà converti (04 Product, Discovery & UX)",
}


def norm(text: str) -> str:
    # macOS écrit les accents des noms de fichiers en Unicode NFD (é = e + ´) : on compare en NFC.
    return unicodedata.normalize("NFC", text)


def fold(text: str) -> str:
    """Forme comparable d'un nom : sans accents ni casse (« Équipes » = « equipes »)."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()
