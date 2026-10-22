"""Attribution des tours à un compartiment de posture : tâche 2.3."""
import unittest

from fixtures_book_usage import Base, Transcript, hit, simple_turn


class Attribution(Base):
    def buckets(self, transcript):
        self.put(transcript)
        self.collect()
        return sorted(r["bucket"] for r in self.records())

    def test_une_posture_balise_anglaise(self):
        self.assertEqual(self.buckets(simple_turn(Transcript(), "[Posture: Delivery]\nTexte.")), ["Delivery"])

    def test_une_posture_balise_francaise(self):
        self.assertEqual(self.buckets(simple_turn(Transcript(), "[Posture : Scaling]\nTexte.")), ["Scaling"])

    def test_bascule(self):
        t = simple_turn(Transcript(), "[Posture: Delivery]\nTexte.\n\n[Switch to Scaling]\nSuite.")
        self.assertEqual(self.buckets(t), ["plusieurs postures"])

    def test_bascule_francaise_et_deux_balises(self):
        t = simple_turn(Transcript(), "[Posture : Discovery]\nUn.\n[Bascule vers Facilitation]\nDeux.")
        self.assertEqual(self.buckets(t), ["plusieurs postures"])
        self.setUp()
        t = simple_turn(Transcript(), "[Posture: Discovery]\nUn.\n[Posture: Delivery]\nDeux.")
        self.assertEqual(self.buckets(t), ["plusieurs postures"])

    def test_critic_sous_agent_compte_a_part(self):
        t = Transcript()
        t.user()
        t.search([hit("flux-et-valeur.md")])
        t.launch_critic()
        t.search([hit("equipes-reseau.md"), hit("equipes-reseau.md")], sidechain=True)
        t.say("Critic : Équipes en réseau est cité.", sidechain=True)
        t.say("[Posture: Delivery]\nRéponse.\n\n[Posture: Critic]\nObjections.\n\nMa lecture de cette critique")
        self.put(t)
        self.collect()
        par_bucket = {r["bucket"]: r for r in self.records()}
        self.assertEqual(sorted(par_bucket), ["Critic", "Delivery"])
        self.assertEqual(list(par_bucket["Delivery"]["books"]), ["flux-et-valeur.md"])
        self.assertEqual(list(par_bucket["Critic"]["books"]), ["equipes-reseau.md"])
        self.assertEqual(par_bucket["Critic"]["books"]["equipes-reseau.md"]["returned"], 2)
        self.assertEqual(par_bucket["Critic"]["books"]["equipes-reseau.md"]["cited"], 1)
        self.assertNotEqual(par_bucket["Critic"]["turn"], par_bucket["Delivery"]["turn"])

    def critic_record(self, content):
        t = Transcript()
        t.user()
        launch = t.launch_critic()
        t.search([hit("equipes-reseau.md")], sidechain=True)
        t.say("   ", sidechain=True)
        t.text_result(launch, content)
        t.say("[Posture: Delivery]\nRéponse.\n\n[Posture: Critic]\nObjections.")
        self.put(t)
        self.collect()
        return {r["bucket"]: r for r in self.records()}["Critic"]

    def test_critic_lit_le_resultat_de_l_appel_agent(self):
        record = self.critic_record("Critic : Équipes en réseau est cité. Hypothèse non sourcée : hors bibliothèque.")
        self.assertEqual(record["books"]["equipes-reseau.md"]["cited"], 1)
        self.assertEqual(record["outside_library"], 1)

    def test_critic_resultat_en_liste_de_blocs_text(self):
        record = self.critic_record(["Premier bloc.", "Équipes en réseau est cité, hors bibliothèque."])
        self.assertEqual(record["books"]["equipes-reseau.md"]["cited"], 1)
        self.assertEqual(record["outside_library"], 1)

    def test_critic_sans_resultat_repli_sur_le_sous_agent(self):
        t = Transcript()
        t.user()
        t.launch_critic()
        t.search([hit("equipes-reseau.md")], sidechain=True)
        t.say("Équipes en réseau, hors bibliothèque.", sidechain=True)
        t.say("[Posture: Delivery]\nRéponse.")
        self.put(t)
        self.collect()
        record = {r["bucket"]: r for r in self.records()}["Critic"]
        self.assertEqual(record["books"]["equipes-reseau.md"]["cited"], 1)
        self.assertEqual(record["outside_library"], 1)

    def test_sous_agent_non_critic_non_compte(self):
        t = Transcript()
        t.user()
        t.launch_other()
        t.search([hit("equipes-reseau.md")], sidechain=True)
        t.say("[Posture: Delivery]\nRéponse.")
        self.assertEqual(self.buckets(t), ["Delivery"])
        self.assertEqual(self.records()[0]["books"], {})

    def test_sous_agent_dans_un_autre_fichier(self):
        t = Transcript("sess-a")
        t.user()
        t.launch_critic()
        t.say("[Posture: Delivery]\nRéponse.")
        side = Transcript("sess-a")
        side.minute = 1       # même séance, enregistrements entre le message et la réponse (horodatage)
        side.search([hit("ateliers-vivants.md")], sidechain=True)
        self.put(t, "sess-a.jsonl")
        self.put(side, "sess-a/subagents/agent-1.jsonl")
        self.collect()
        par_bucket = {r["bucket"]: r for r in self.records()}
        self.assertEqual(sorted(par_bucket), ["Critic", "Delivery"])

    def test_sans_balise(self):
        self.assertEqual(self.buckets(simple_turn(Transcript(), "Réponse sans balise.")), ["sans posture"])

    def test_balise_mal_ecrite(self):
        for balise in ("[Posture: Découverte]", "[Posture: discovery]", "[Posture: DISCOVERY]", "[Posture : Delivery]\n[Posture: Livraison]"):
            self.setUp()
            attendu = ["Delivery"] if "Delivery" in balise else ["sans posture"]
            self.assertEqual(self.buckets(simple_turn(Transcript(), balise + "\nTexte.")), attendu, balise)

    def test_balise_critic_seule_dans_la_reponse_principale(self):
        self.assertEqual(self.buckets(simple_turn(Transcript(), "[Posture: Critic]\nTexte.")), ["sans posture"])

    def test_pas_de_devinette_sur_le_contenu(self):
        t = simple_turn(Transcript(), "Voici un atelier de rétrospective et un plan de Discovery.", user="Quel atelier ?")
        self.assertEqual(self.buckets(t), ["sans posture"])

    def test_balise_anglaise_avec_espace_avant_deux_points_non_reconnue(self):
        # le format français a l'espace, l'anglais n'en a pas : « [Posture : X] » est la balise française, déjà reconnue
        self.assertEqual(self.buckets(simple_turn(Transcript(), "[Posture:Delivery]\nTexte.")), ["Delivery"])


if __name__ == "__main__":
    unittest.main()
