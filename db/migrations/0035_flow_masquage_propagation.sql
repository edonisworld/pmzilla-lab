-- Schéma touché : flow (vue flow.v_version_quality_photo ; fonctions flow.propager_bornes, flow.photo_masque et flow.masking_version).
-- R-144, groupe 6, conception D15 (propagation des bornes de la photo), D9 et D12 : le marqueur du masquage passe à la version 2. Aucune donnée, aucun mot
-- de passe, aucun rôle créé, modifié ou supprimé, aucune table changée. Cette migration suit celle du masquage des sommes (0022), déjà fusionnée : elle ne la
-- modifie pas en place (D12, tâche 6.5). Les colonnes de la vue sont celles qu'elle avait : CREATE OR REPLACE VIEW suffit.
--
-- Remplace : les CTE libre_serie, produit_libre_brut (en tant que règle), produit_serie et produit_libre de la vue de la photo (0022) et leurs appels à
-- flow.photo_serie, que flow.photo_masque reprend en entier (D3, la boucle de D5-d et D2 jusqu'au point fixe, puis la propagation de D15). Retrait :
-- flow.photo_serie reste créée par 0022 (une migration fusionnée ne se modifie pas) mais n'est plus appelée par aucune vue ; elle tombe avec la première
-- migration qui supprime les fonctions de 0022 (le groupe 7, quand la fonction du partage et du retard remplace flow.retard_d2).
--
-- flow.propager_bornes (D15, « Propagation ») : la propagation de bornes (bounds consistency) sur des relations linéaires entières à coefficients +1 ou -1.
-- Entrées : les bornes de départ des variables (hi NULL : sans borne haute), les relations (sorte 1 : égalité, sorte 2 : inférieure ou égale ; second
-- membre ; termes à plat, rangés par relation), la borne finie maximale M et la limite de balayages. Sortie : l'intervalle de chaque variable et un drapeau
-- « vide » quand un intervalle est vide. Une borne finie au-dessus de M, ou plus de `limite` balayages : le drapeau « limite_atteinte » (aucune exception, pour rester PARALLEL SAFE) ; flow.photo_masque lève alors, dans chacune des quatre lectures de l'excès (échec fermé, M2 a). Pure : aucune table lue.
--
-- Limite de balayages : au plus V x (2M + 3) balayages qui changent (une borne basse prend au plus M + 1 valeurs, une borne haute au plus M + 2, l'infini
-- compris, sous le contrôle d'exécution « aucune borne finie au-dessus de M »), plus un balayage stable ; la valeur est calculée par flow.photo_masque :
-- PROPAGATION-MAX 1 + V x (2M + 3)
-- Limite de balayages de chaque lecture de pari par ligne (« m = 0 », « U = 0 », « U = 0 et m = 0 » ; D15, M2 a et M7 a de la fiche R-20261104-6) : un pari
-- que les cellules publiées contredisent ne se resserre jamais, les bornes montent jusqu'à M (des dizaines de milliers de balayages) ; la limite atteinte est une
-- erreur, rien n'est publié (échec fermé). Replaces: nothing in D15 (borne neuve des seules lectures par ligne, que PROPAGATION-MAX bornait avant). Condition de
-- retrait (M9 a, R-20261104-12, amendée par R-20261104-50) : une exception comptée par la mesure 17.1 (plancher et seuil relevé 10) revient à l'auteur avant
-- tout retrait ; la limite tombe avec la mesure 17.1, une fois ses exceptions tranchées ; ces lectures reprennent alors PROPAGATION-MAX :
-- PROPAGATION-ZERO-MAX 4 x (V + R) + 10
-- Limite de la boucle externe de flow.photo_masque : chaque passe qui ne s'arrête pas masque exactement une cellule publiée, C étant le nombre de cellules de
-- comptage publiées de l'unité au début de la boucle : au plus C passes qui masquent, une dernière stable :
-- LOOP-MAX C + 1
-- Limite de passes de la boucle de la ligne sans version de chaque série (D5-d puis D2, comme 0022) :
-- PASSES-MAX 2 x W + 1
--
-- flow.photo_masque (D15) : toute la photo en une seule fonction pure. Entrées, une valeur par ligne (tableaux rangés par la clé « rang de ligne : 0 pour
-- les équipes, 1 pour le produit ; semaine ; équipe, texte comparé octet par octet (COLLATE "C") ; version, la ligne sans version d'abord ») : la semaine, le
-- nom de l'équipe ('(produit)' pour le produit), le numéro de version (NULL : ligne sans version), les neuf comptes à plat (found, found_open,
-- corrected_at_week, corrected_now, reopened, defects_created, defects_without_affects, resolved_week, resolved_week_defects ; une ligne de version n'a que
-- les cinq premiers, une ligne sans version que les quatre derniers), et le nombre de termes non retenus de la ligne sans version (écart (d) de D4 : la vue
-- les voit, le lecteur Python non). Sortie : la visibilité de chacun des neuf comptes de chaque ligne, dans l'ordre d'entrée.
--   1. règles existantes (D13) : les séries d'équipe jusqu'à leur point fixe (D5-d sur les seules cellules publiées, puis D2 sur chaque semaine, sauf pour une ligne sans ligne de version, que D2 ne touche pas (écart de photo_serie de 0022, aligné sur Python), la règle
--      appliquée avec les termes masqués publiés puis avec tous les termes cachés, le plus strict décidant), D3 sur la ligne du produit, puis la série du
--      produit ;
--   2. variables et relations : chaque cellule de comptage est une variable (publiée : [v, v] ; masquée : [0, borne] selon la première règle qui l'a masquée,
--      B15), plus D_r, m_r et U_r de chaque ligne sans version qui a des lignes de version (U_r >= 0 sans borne haute : les versions non retenues, D4 (d),
--      M1 a de la fiche R-20261104-6 ; D_r + m_r = somme des trouvés retenus + U_r) ; relations P1 (paires), P2 (ligne à compléter), P3 (chaîne de D5-d),
--      P4 (ligne du produit), P5 (défauts distincts du produit, redondante : D_P = somme des D_t, avec un D_t latent et créés - sans affects - D_t = 0 pour
--      une ligne sans D_r ; R-20261104-49, Q1 e ; la relation des sommes n'est pas traversée par la règle du voisin) ; une voisine qui était la seule candidate
--      part sans borne haute (reg_a NULL, B15 ; R-20261104-49, Q2 a) ;
--   3. propagation dans les lectures de l'excès (décision 14) : « m libre » (un intervalle vide : exception), puis, par ligne, les lectures « m_r = 0 »,
--      « U_r = 0 » et « U_r = 0 et m_r = 0 » dont le pari peut encore tenir (M2 a, M7 a ; un intervalle vide écarte la lecture, une limite atteinte
--      est une exception) ;
--   4. une cellule masquée dont l'intervalle n'a qu'une valeur dans une lecture non écartée est épinglée ; un excès m_r fixé sous le seuil dans la lecture « U_r = 0 »
--      de sa ligne l'est aussi (D5-e, X10), sauf pour une ligne à un seul terme retenu ; la première, dans l'ordre des clés, masque sa voisine (la plus petite cellule publiée liée à elle, les termes
--      latents étant transparents ; à égalité, la première de l'ordre des clés) et tout recommence au point 1.
-- Le plancher (5) est une constante : les vues masquent au plancher, le lecteur relève le seuil en Python. EXECUTE est accordé au seul rôle des vues.

SET LOCAL ROLE pmzilla_owner;

CREATE FUNCTION flow.propager_bornes(lo bigint[], hi bigint[], rel_kind smallint[], rel_rhs bigint[], term_rel integer[], term_var integer[],
                                     term_coef smallint[], borne_m bigint, limite bigint)
    RETURNS TABLE (rang integer, borne_lo bigint, borne_hi bigint, vide boolean, limite_atteinte boolean)
    LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    n integer := coalesce(array_length(lo, 1), 0);
    nr integer := coalesce(array_length(rel_kind, 1), 0);
    nt integer := coalesce(array_length(term_rel, 1), 0);
    l bigint[] := lo;
    h bigint[] := hi;
    debut integer[] := ARRAY[]::integer[];
    fin integer[] := ARRAY[]::integer[];
    balayage bigint := 0;
    change boolean;
    est_vide boolean := false;
    hors_limite boolean := false;
    r integer;
    k integer;
    j integer;
    i integer;
    x integer;
    somme_max bigint;
    somme_min bigint;
    max_inf boolean;
    min_inf boolean;
    t_max bigint;
    t_min bigint;
    haut_t bigint;
    bas_t bigint;
    nlo bigint;
    nhi bigint;
BEGIN
    FOR i IN 1..nt LOOP                                      -- les termes d'une relation se suivent : début et fin de chaque relation
        IF term_rel[i] > coalesce(array_length(debut, 1), 0) THEN
            debut[term_rel[i]] := i;
        END IF;
        fin[term_rel[i]] := i;
    END LOOP;
    <<balayages>>
    LOOP
        IF balayage >= limite THEN
            hors_limite := true;                             -- pas de balayage stable dans la limite : drapeau rendu, l'appelante décide
            EXIT balayages;
        END IF;
        balayage := balayage + 1;
        change := false;
        FOR r IN 1..nr LOOP
            FOR k IN debut[r]..fin[r] LOOP
                somme_max := 0;
                somme_min := 0;
                max_inf := false;
                min_inf := false;
                FOR j IN debut[r]..fin[r] LOOP
                    CONTINUE WHEN j = k;
                    IF term_coef[j] = 1 THEN
                        t_max := h[term_var[j]];
                        t_min := l[term_var[j]];
                    ELSE
                        t_max := -l[term_var[j]];
                        t_min := CASE WHEN h[term_var[j]] IS NULL THEN NULL ELSE -h[term_var[j]] END;
                    END IF;
                    IF t_max IS NULL THEN max_inf := true; ELSE somme_max := somme_max + t_max; END IF;
                    IF t_min IS NULL THEN min_inf := true; ELSE somme_min := somme_min + t_min; END IF;
                END LOOP;
                haut_t := CASE WHEN min_inf THEN NULL ELSE rel_rhs[r] - somme_min END;                       -- a_k x_k <= second membre - somme des plus petits
                bas_t := CASE WHEN rel_kind[r] <> 1 OR max_inf THEN NULL ELSE rel_rhs[r] - somme_max END;    -- égalité : a_k x_k >= second membre - somme des plus grands
                x := term_var[k];
                IF term_coef[k] = 1 THEN
                    nlo := bas_t;
                    nhi := haut_t;
                ELSE
                    nlo := CASE WHEN haut_t IS NULL THEN NULL ELSE -haut_t END;
                    nhi := CASE WHEN bas_t IS NULL THEN NULL ELSE -bas_t END;
                END IF;
                IF nlo IS NOT NULL AND nlo > l[x] THEN
                    l[x] := nlo;
                    change := true;
                END IF;
                IF nhi IS NOT NULL AND (h[x] IS NULL OR nhi < h[x]) THEN
                    h[x] := nhi;
                    change := true;
                END IF;
                IF l[x] > borne_m OR (h[x] IS NOT NULL AND h[x] > borne_m) THEN
                    hors_limite := true;                     -- une borne finie au-dessus de M : drapeau rendu
                    EXIT balayages;
                END IF;
                IF h[x] IS NOT NULL AND l[x] > h[x] THEN
                    est_vide := true;
                    EXIT balayages;
                END IF;
            END LOOP;
        END LOOP;
        IF NOT change THEN
            EXIT balayages;
        END IF;
    END LOOP;
    FOR i IN 1..n LOOP
        rang := i;
        borne_lo := l[i];
        borne_hi := h[i];
        vide := est_vide;
        limite_atteinte := hors_limite;
        RETURN NEXT;
    END LOOP;
END
$$;

-- Les deux derniers paramètres, par défaut NULL, abaissent la limite de la boucle externe et la limite de balayages : seuls les tests les donnent (limite
-- atteinte : exception, aucune ligne) ; les vues appellent la fonction avec cinq arguments et les limites déclarées plus haut.
CREATE FUNCTION flow.photo_masque(sem date[], eq text[], ver integer[], val bigint[], extra bigint[],
                                  lim_boucle integer DEFAULT NULL, lim_balayages bigint DEFAULT NULL)
    RETURNS TABLE (rang integer, v_found boolean, v_found_open boolean, v_corrected_at_week boolean, v_corrected_now boolean, v_reopened boolean,
                   v_dc boolean, v_dwa boolean, v_rw boolean, v_rwd boolean)
    LANGUAGE plpgsql IMMUTABLE PARALLEL SAFE SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    t constant integer := 5;                                 -- le plancher
    prod constant text := '(produit)';
    n integer := coalesce(array_length(sem, 1), 0);
    paire_de integer[] := ARRAY[0, 1, 4, 0, 4, 0, 6, 0, 8];  -- colonne -> colonne du tout de sa paire (0 : aucune), PAIRES_PHOTO de tools/flow_views.py
    vis boolean[];                                           -- visibilité de chaque compte, à plat : (ligne - 1) x 9 + colonne
    regle smallint[];                                        -- première règle qui a masqué : 1 primaire, 2 paire, 3 D3, 4 D5-d, 5 D2 ou D5-e, 6 D15, 7 inconnue
    reg_a bigint[];                                          -- D5-d : la ligne d'ancrage ; D15 : la borne haute de départ
    termine boolean[];
    serie integer[];
    iter integer := 0;
    limite_b integer;
    phase integer;
    i integer;
    j integer;
    q integer;
    k integer;
    c integer;
    c_deb integer;
    c_fin integer;
    ix integer;
    ix_dc integer;
    ix_dwa integer;
    v integer;
    v2 integer;
    t_i integer;
    pj integer;
    premier boolean;
    y integer;
    r integer;
    w integer;
    m bigint;
    np bigint;
    sv bigint;
    crees bigint;
    sans bigint;
    dernier bigint;
    ancre integer;
    besoin boolean;
    change_s boolean;
    limite_s integer;
    passe_s integer;
    -- variables, relations
    nv integer;
    nr integer;
    var_ix integer[];
    var_d integer[];
    var_m integer[];
    var_u integer[];
    var_dt integer[];                                        -- P5 : D_t latent des lignes sans version d'une semaine de P5 qui n'ont pas de D_r (colonne 10, comme D_r)
    p5_ok boolean[];                                         -- P5 : la ligne sans version (équipe ou produit) appartient à une semaine où P5 est construite
    ok5 boolean;
    hors_anneau boolean[];                                   -- par relation : vrai pour la relation P5 des sommes, que la règle du voisin ne traverse pas
    nb_termes integer[];                                    -- par ligne sans version : le nombre de ses termes retenus (écart 3 de M5)
    pin_zero boolean[];                                      -- cellule épinglée dans l'une des lectures « m = 0 » par ligne
    pin_exces boolean[];                                     -- excès m fixé sous le seuil dans la lecture « U = 0 » de sa ligne (hors exemption)
    v_row integer[];
    v_col integer[];
    avec_termes boolean;
    nterms integer;
    lo0 bigint[];
    hi0 bigint[];
    publiee boolean[];
    valeur bigint[];
    somme_pub bigint;
    rk smallint[];
    rr bigint[];
    tr integer[];
    tv integer[];
    tc smallint[];
    r_deb integer[];
    r_fin integer[];
    borne_m bigint;
    limite_p bigint;
    rec record;
    lo1 bigint[];
    hi1 bigint[];
    vide1 boolean;
    hors1 boolean;
    hors3 boolean;
    lo2 bigint[];
    hi2 bigint[];
    lo3 bigint[];
    hi3 bigint[];
    vide3 boolean;
    epingle integer;
    -- voisine
    vus boolean[];
    front boolean[];
    anneau boolean[];
    progres boolean;
    touche boolean;
    trouve boolean;
    meilleure integer;
    plus_petite_autre bigint;
    haut bigint;
    pub_n integer;
BEGIN
    IF n = 0 THEN
        RETURN;
    END IF;
    vis := array_fill(false, ARRAY[n * 9]);
    regle := array_fill(0::smallint, ARRAY[n * 9]);
    reg_a := array_fill(0::bigint, ARRAY[n * 9]);
    FOR i IN 1..n LOOP                                       -- visibilité de départ : primaire et paires (D11) ; un nul est « inconnue »
        c_deb := CASE WHEN ver[i] IS NULL THEN 6 ELSE 1 END;
        c_fin := CASE WHEN ver[i] IS NULL THEN 9 ELSE 5 END;
        FOR c IN c_deb..c_fin LOOP
            ix := (i - 1) * 9 + c;
            IF val[ix] IS NULL THEN
                regle[ix] := 7;
            ELSIF val[ix] < t THEN
                regle[ix] := 1;
            ELSIF paire_de[c] > 0 AND (val[(i - 1) * 9 + paire_de[c]] IS NULL OR val[(i - 1) * 9 + paire_de[c]] - val[ix] < t) THEN
                regle[ix] := 2;
            ELSE
                vis[ix] := true;
            END IF;
        END LOOP;
    END LOOP;

    <<externe>>
    LOOP
        -- 1. les règles existantes, dans leur ordre : les séries d'équipe (phase 1), D3 (phase 2), la série du produit (phase 3)
        FOR phase IN 1..3 LOOP
            IF phase = 2 THEN
                FOR i IN 1..n LOOP                           -- D3 : une cellule du produit n'est publiée que si toutes les cellules d'équipe de sa colonne le sont
                    IF eq[i] = prod THEN
                        c_deb := CASE WHEN ver[i] IS NULL THEN 6 ELSE 1 END;
                        c_fin := CASE WHEN ver[i] IS NULL THEN 9 ELSE 5 END;
                        FOR c IN c_deb..c_fin LOOP
                            ix := (i - 1) * 9 + c;
                            IF vis[ix] THEN
                                FOR j IN 1..n LOOP
                                    IF eq[j] <> prod AND sem[j] = sem[i] AND ver[j] IS NOT DISTINCT FROM ver[i] AND NOT vis[(j - 1) * 9 + c] THEN
                                        vis[ix] := false;
                                        regle[ix] := 3;
                                        EXIT;
                                    END IF;
                                END LOOP;
                            END IF;
                        END LOOP;
                    END IF;
                END LOOP;
                CONTINUE;
            END IF;
            termine := array_fill(false, ARRAY[n]);
            FOR i IN 1..n LOOP
                IF ver[i] IS NULL AND NOT termine[i] AND ((phase = 1 AND eq[i] <> prod) OR (phase = 3 AND eq[i] = prod)) THEN
                    serie := ARRAY[]::integer[];             -- une série : les lignes sans version d'une équipe (ou du produit), dans l'ordre des semaines
                    FOR j IN i..n LOOP
                        IF ver[j] IS NULL AND eq[j] = eq[i] THEN
                            serie := serie || j;
                            termine[j] := true;
                        END IF;
                    END LOOP;
                    w := cardinality(serie);
                    limite_s := 2 * w + 1;
                    passe_s := 0;
                    LOOP
                        IF passe_s >= limite_s THEN
                            RAISE EXCEPTION 'v_version_quality_photo : le masquage de la ligne sans version ne se stabilise pas en % passes', limite_s;
                        END IF;
                        passe_s := passe_s + 1;
                        change_s := false;
                        FOR c IN 6..7 LOOP                   -- D5-d sur les seules cellules encore publiées
                            dernier := NULL;
                            ancre := NULL;
                            FOR k IN 1..w LOOP
                                j := serie[k];
                                ix := (j - 1) * 9 + c;
                                IF vis[ix] THEN
                                    IF dernier IS NOT NULL AND abs(val[ix] - dernier) BETWEEN 1 AND t - 1 THEN
                                        vis[ix] := false;
                                        regle[ix] := 4;
                                        reg_a[ix] := ancre;
                                        change_s := true;
                                    ELSE
                                        dernier := val[ix];
                                        ancre := j;
                                    END IF;
                                END IF;
                            END LOOP;
                        END LOOP;
                        FOR k IN 1..w LOOP                   -- D2 sur chaque semaine (même règle que flow.photo_serie, sauf pour une ligne sans ligne de version, que D2 ne touche pas : écart de photo_serie de 0022, aligné sur Python)
                            j := serie[k];
                            ix_dc := (j - 1) * 9 + 6;
                            ix_dwa := (j - 1) * 9 + 7;
                            IF vis[ix_dc] THEN
                                np := 0;
                                sv := 0;
                                nterms := 0;
                                FOR q IN 1..n LOOP           -- termes de la ligne : les versions de l'équipe et de la semaine ; cachés : cellule masquée
                                    IF ver[q] IS NOT NULL AND eq[q] = eq[j] AND sem[q] = sem[j] THEN
                                        nterms := nterms + 1;
                                        IF vis[(q - 1) * 9 + 1] THEN
                                            sv := sv + val[(q - 1) * 9 + 1];
                                        ELSE
                                            np := np + 1;
                                        END IF;
                                    END IF;
                                END LOOP;
                                crees := val[ix_dc];
                                sans := val[ix_dwa];
                                besoin := false;
                                -- aucune ligne de version dans la semaine : pas de relation à compléter (D15, P2 ; comme completer de flow_views.py)
                                IF nterms > 0 THEN
                                FOREACH m IN ARRAY ARRAY[np, np + coalesce(extra[j], 0)] LOOP
                                    besoin := besoin OR coalesce(CASE WHEN vis[ix_dwa]
                                        THEN ((m >= 1 AND (m < 2 OR crees - sans - sv < 5 OR crees - sans - sv = 4 * m))
                                              OR (m = 0 AND sv - (crees - sans) < 5))
                                        ELSE (1 + m < 2 OR crees - sv < 5 OR crees - sv = 4 * (1 + m))
                                        END, false);
                                END LOOP;
                                END IF;
                                IF besoin THEN
                                    IF vis[ix_dwa] THEN
                                        vis[ix_dwa] := false;
                                        regle[ix_dwa] := 5;
                                    ELSE
                                        vis[ix_dc] := false;
                                        regle[ix_dc] := 5;
                                    END IF;
                                    change_s := true;
                                END IF;
                            END IF;
                        END LOOP;
                        EXIT WHEN NOT change_s;
                    END LOOP;
                END IF;
            END LOOP;
        END LOOP;

        -- P5 (R-20261104-49, Q1 e) : les lignes sans version des semaines où le produit a des lignes d'équipe sans version (les deux comptes y sont toujours là)
        p5_ok := array_fill(false, ARRAY[n]);
        FOR i IN 1..n LOOP
            IF eq[i] = prod AND ver[i] IS NULL THEN
                ok5 := false;
                FOR j IN 1..n LOOP
                    IF eq[j] <> prod AND ver[j] IS NULL AND sem[j] = sem[i] THEN
                        ok5 := true;
                        p5_ok[j] := true;
                    END IF;
                END LOOP;
                IF ok5 THEN
                    p5_ok[i] := true;
                END IF;
            END IF;
        END LOOP;

        -- 2. variables : les cellules de comptage dans l'ordre des clés, puis D_r et m_r après les cellules de leur ligne
        nv := 0;
        var_ix := array_fill(0, ARRAY[n * 9]);
        var_d := array_fill(0, ARRAY[n]);
        var_m := array_fill(0, ARRAY[n]);
        var_u := array_fill(0, ARRAY[n]);
        var_dt := array_fill(0, ARRAY[n]);
        nb_termes := array_fill(0, ARRAY[n]);
        v_row := ARRAY[]::integer[];
        v_col := ARRAY[]::integer[];
        FOR i IN 1..n LOOP
            c_deb := CASE WHEN ver[i] IS NULL THEN 6 ELSE 1 END;
            c_fin := CASE WHEN ver[i] IS NULL THEN 9 ELSE 5 END;
            FOR c IN c_deb..c_fin LOOP
                nv := nv + 1;
                var_ix[(i - 1) * 9 + c] := nv;
                v_row[nv] := i;
                v_col[nv] := c;
            END LOOP;
            IF ver[i] IS NULL THEN
                avec_termes := false;
                FOR j IN 1..n LOOP
                    IF ver[j] IS NOT NULL AND eq[j] = eq[i] AND sem[j] = sem[i] THEN
                        avec_termes := true;
                        EXIT;
                    END IF;
                END LOOP;
                IF avec_termes THEN
                    nv := nv + 1;
                    var_d[i] := nv;
                    v_row[nv] := i;
                    v_col[nv] := 10;
                    nv := nv + 1;
                    var_m[i] := nv;
                    v_row[nv] := i;
                    v_col[nv] := 11;
                    nv := nv + 1;                            -- U : terme latent des versions non retenues (D4 (d), M1 a), sans borne haute
                    var_u[i] := nv;
                    v_row[nv] := i;
                    v_col[nv] := 12;
                ELSIF p5_ok[i] THEN
                    nv := nv + 1;                            -- D_t de P5 : sans borne haute, comme D_r, à la même place dans l'ordre des clés
                    var_dt[i] := nv;
                    v_row[nv] := i;
                    v_col[nv] := 10;
                END IF;
            END IF;
        END LOOP;
        lo0 := array_fill(0::bigint, ARRAY[nv]);
        hi0 := array_fill(NULL::bigint, ARRAY[nv]);
        publiee := array_fill(false, ARRAY[nv]);
        valeur := array_fill(NULL::bigint, ARRAY[nv]);
        somme_pub := 0;
        pub_n := 0;
        FOR v IN 1..nv LOOP                                  -- bornes de départ (B15)
            IF v_col[v] <= 9 THEN
                i := v_row[v];
                c := v_col[v];
                ix := (i - 1) * 9 + c;
                IF vis[ix] THEN
                    publiee[v] := true;
                    valeur[v] := val[ix];
                    lo0[v] := val[ix];
                    hi0[v] := val[ix];
                    somme_pub := somme_pub + val[ix];
                    pub_n := pub_n + 1;
                ELSIF regle[ix] = 1 THEN
                    hi0[v] := t - 1;
                ELSIF regle[ix] = 2 THEN
                    IF vis[(i - 1) * 9 + paire_de[c]] THEN
                        hi0[v] := greatest(t - 1, val[(i - 1) * 9 + paire_de[c]]);
                    END IF;
                ELSIF regle[ix] = 6 THEN
                    IF reg_a[ix] IS NOT NULL THEN            -- voisine qui était la seule candidate : reg_a NULL, pas de borne haute (B15) ; greatest ignorerait le NULL
                        hi0[v] := greatest(t - 1, reg_a[ix]);
                    END IF;
                END IF;                                    -- inconnue, D3, D5-d (P3), D2 et D5-e : pas de borne haute
            END IF;
        END LOOP;
        IF iter = 0 THEN
            limite_b := coalesce(lim_boucle, pub_n + 1);     -- LOOP-MAX C + 1, C : les cellules publiées au début de la boucle
        END IF;

        rk := ARRAY[]::smallint[];
        rr := ARRAY[]::bigint[];
        tr := ARRAY[]::integer[];
        tv := ARRAY[]::integer[];
        tc := ARRAY[]::smallint[];
        nr := 0;
        FOR i IN 1..n LOOP                                   -- P1 : partie <= tout, sur une ligne
            c_deb := CASE WHEN ver[i] IS NULL THEN 6 ELSE 1 END;
            c_fin := CASE WHEN ver[i] IS NULL THEN 9 ELSE 5 END;
            FOR c IN c_deb..c_fin LOOP                       -- termes dans l'ordre des clés, relations rangées par leur premier terme (comme _construire de Python)
                IF paire_de[c] > c THEN                      -- c est une partie dont le tout vient après : la partie d'abord
                    nr := nr + 1;
                    rk := rk || 2::smallint;
                    rr := rr || 0::bigint;
                    tr := tr || nr || nr;
                    tv := tv || var_ix[(i - 1) * 9 + c] || var_ix[(i - 1) * 9 + paire_de[c]];
                    tc := tc || 1::smallint || (-1)::smallint;
                END IF;
                FOR q IN c + 1..c_fin LOOP                   -- c est le tout d'une partie qui vient après : le tout d'abord
                    IF paire_de[q] = c THEN
                        nr := nr + 1;
                        rk := rk || 2::smallint;
                        rr := rr || 0::bigint;
                        tr := tr || nr || nr;
                        tv := tv || var_ix[(i - 1) * 9 + c] || var_ix[(i - 1) * 9 + q];
                        tc := tc || (-1)::smallint || 1::smallint;
                    END IF;
                END LOOP;
            END LOOP;
        END LOOP;
        FOR i IN 1..n LOOP                                   -- P2 : ligne à compléter de chaque ligne sans version qui a des lignes de version
            IF ver[i] IS NULL AND var_d[i] > 0 THEN
                nr := nr + 1;                                -- créés = sans affects + D
                rk := rk || 1::smallint;
                rr := rr || 0::bigint;
                tr := tr || nr || nr || nr;
                tv := tv || var_ix[(i - 1) * 9 + 6] || var_ix[(i - 1) * 9 + 7] || var_d[i];
                tc := tc || 1::smallint || (-1)::smallint || (-1)::smallint;
                FOR j IN 1..n LOOP                           -- D >= chaque trouvé (D d'abord : sa clé précède celle des lignes de version ; avant D + m, à premier terme égal)
                    IF ver[j] IS NOT NULL AND eq[j] = eq[i] AND sem[j] = sem[i] THEN
                        nr := nr + 1;
                        rk := rk || 2::smallint;
                        rr := rr || 0::bigint;
                        tr := tr || nr || nr;
                        tv := tv || var_d[i] || var_ix[(j - 1) * 9 + 1];
                        tc := tc || (-1)::smallint || 1::smallint;
                    END IF;
                END LOOP;
                nr := nr + 1;                                -- D + m = somme des trouvés retenus + U (U : les versions non retenues, M1 a)
                rk := rk || 1::smallint;
                rr := rr || 0::bigint;
                tr := tr || nr || nr || nr;
                tv := tv || var_d[i] || var_m[i] || var_u[i];
                tc := tc || 1::smallint || 1::smallint || (-1)::smallint;
                nb_termes[i] := 0;
                FOR j IN 1..n LOOP
                    IF ver[j] IS NOT NULL AND eq[j] = eq[i] AND sem[j] = sem[i] THEN
                        tr := tr || nr;
                        tv := tv || var_ix[(j - 1) * 9 + 1];
                        tc := tc || (-1)::smallint;
                        nb_termes[i] := nb_termes[i] + 1;
                    END IF;
                END LOOP;
            END IF;
        END LOOP;
        FOR v IN 1..nv LOOP                                  -- P3 : chaîne de D5-d, x <= ancre + (T - 1) ; termes dans l'ordre des clés, rangées par premier terme
            IF v_col[v] <= 9 THEN
                FOR passe_p IN 1..2 LOOP                        -- passe 1 : v est l'ancre (coefficient -1) ; passe 2 : v est la cellule x (coefficient +1)
                    FOR v2 IN v + 1..nv LOOP
                        IF v_col[v2] <= 9 THEN
                            -- passe 1 : x = v2, ancre = v ; passe 2 : x = v, ancre = v2
                            ix := CASE WHEN passe_p = 1 THEN (v_row[v2] - 1) * 9 + v_col[v2] ELSE (v_row[v] - 1) * 9 + v_col[v] END;
                            IF NOT vis[ix] AND regle[ix] = 4
                               AND var_ix[(reg_a[ix]::integer - 1) * 9 + (CASE WHEN passe_p = 1 THEN v_col[v2] ELSE v_col[v] END)]
                                   = (CASE WHEN passe_p = 1 THEN v ELSE v2 END)
                               AND v_col[v] = v_col[v2] THEN
                                nr := nr + 1;
                                rk := rk || 2::smallint;
                                rr := rr || (t - 1)::bigint;
                                tr := tr || nr || nr;
                                tv := tv || v || v2;
                                tc := tc || (CASE WHEN passe_p = 1 THEN (-1) ELSE 1 END)::smallint || (CASE WHEN passe_p = 1 THEN 1 ELSE (-1) END)::smallint;
                            END IF;
                        END IF;
                    END LOOP;
                END LOOP;
            END IF;
        END LOOP;
        FOR t_i IN 1..n LOOP                                 -- P4 : cellule du produit = somme des cellules d'équipe de la semaine et de la version
            IF eq[t_i] <> prod THEN                          -- rangées par leur premier terme : la première ligne d'équipe de la semaine et de la version
                premier := true;
                FOR j IN 1..t_i - 1 LOOP
                    IF eq[j] <> prod AND sem[j] = sem[t_i] AND ver[j] IS NOT DISTINCT FROM ver[t_i] THEN
                        premier := false;
                        EXIT;
                    END IF;
                END LOOP;
                pj := 0;
                IF premier THEN
                    FOR j IN 1..n LOOP
                        IF eq[j] = prod AND sem[j] = sem[t_i] AND ver[j] IS NOT DISTINCT FROM ver[t_i] THEN
                            pj := j;
                            EXIT;
                        END IF;
                    END LOOP;
                END IF;
                IF pj > 0 THEN
                    c_deb := CASE WHEN ver[t_i] IS NULL THEN 6 ELSE 1 END;
                    c_fin := CASE WHEN ver[t_i] IS NULL THEN 9 ELSE 5 END;
                    FOR c IN c_deb..c_fin LOOP
                        nr := nr + 1;
                        rk := rk || 1::smallint;
                        rr := rr || 0::bigint;
                        FOR j IN 1..n LOOP                   -- les cellules d'équipe d'abord (clés plus petites), la cellule du produit en dernier
                            IF eq[j] <> prod AND sem[j] = sem[t_i] AND ver[j] IS NOT DISTINCT FROM ver[t_i] THEN
                                tr := tr || nr;
                                tv := tv || var_ix[(j - 1) * 9 + c];
                                tc := tc || (-1)::smallint;
                            END IF;
                        END LOOP;
                        tr := tr || nr;
                        tv := tv || var_ix[(pj - 1) * 9 + c];
                        tc := tc || 1::smallint;
                    END LOOP;
                END IF;
            END IF;
        END LOOP;
        -- P5 (R-20261104-49, Q1 e), après P4 : les défauts distincts du produit D_P = somme des D_t, redondante (conséquence de P4 sur créés et sans affects), et,
        -- pour une ligne sans D_r de P2, créés - sans affects - D_t = 0. Relations rangées par premier terme croissant, comme le tri de Python ; la relation des
        -- sommes n'est pas traversée par la règle du voisin (hors_anneau). Replaces: nothing (relation neuve). Removal: falls with P5.
        hors_anneau := ARRAY[]::boolean[];
        FOR v IN 1..nv LOOP
            i := v_row[v];
            IF v_col[v] = 6 AND var_dt[i] > 0 THEN
                nr := nr + 1;
                rk := rk || 1::smallint;
                rr := rr || 0::bigint;
                tr := tr || nr || nr || nr;
                tv := tv || var_ix[(i - 1) * 9 + 6] || var_ix[(i - 1) * 9 + 7] || var_dt[i];
                tc := tc || 1::smallint || (-1)::smallint || (-1)::smallint;
            END IF;
            IF v_col[v] = 10 AND p5_ok[i] AND eq[i] <> prod THEN
                premier := true;                             -- la somme est rangée par la première ligne d'équipe sans version de la semaine
                FOR j IN 1..i - 1 LOOP
                    IF eq[j] <> prod AND ver[j] IS NULL AND sem[j] = sem[i] THEN
                        premier := false;
                        EXIT;
                    END IF;
                END LOOP;
                IF premier THEN
                    nr := nr + 1;
                    rk := rk || 1::smallint;
                    rr := rr || 0::bigint;
                    hors_anneau[nr] := true;
                    FOR j IN 1..n LOOP                       -- les D_t d'équipe d'abord (clés plus petites), le D_P du produit en dernier
                        IF eq[j] <> prod AND ver[j] IS NULL AND sem[j] = sem[i] THEN
                            tr := tr || nr;
                            tv := tv || CASE WHEN var_d[j] > 0 THEN var_d[j] ELSE var_dt[j] END;
                            tc := tc || (-1)::smallint;
                        END IF;
                    END LOOP;
                    FOR j IN 1..n LOOP
                        IF eq[j] = prod AND ver[j] IS NULL AND sem[j] = sem[i] THEN
                            tr := tr || nr;
                            tv := tv || CASE WHEN var_d[j] > 0 THEN var_d[j] ELSE var_dt[j] END;
                            tc := tc || 1::smallint;
                            EXIT;
                        END IF;
                    END LOOP;
                END IF;
            END IF;
        END LOOP;
        r_deb := ARRAY[]::integer[];
        r_fin := ARRAY[]::integer[];
        FOR k IN 1..coalesce(array_length(tr, 1), 0) LOOP
            IF tr[k] > coalesce(array_length(r_deb, 1), 0) THEN
                r_deb[tr[k]] := k;
            END IF;
            r_fin[tr[k]] := k;
        END LOOP;

        -- 3. propagation dans les quatre lectures de l'excès
        borne_m := (somme_pub + t) * (nv + 1);
        limite_p := coalesce(lim_balayages, 1 + nv * (2 * borne_m + 3));     -- PROPAGATION-MAX 1 + V x (2M + 3)
        lo1 := ARRAY[]::bigint[];
        hi1 := ARRAY[]::bigint[];
        vide1 := false;
        hors1 := false;
        FOR rec IN SELECT * FROM flow.propager_bornes(lo0, hi0, rk, rr, tr, tv, tc, borne_m, limite_p) LOOP
            lo1[rec.rang] := rec.borne_lo;
            hi1[rec.rang] := rec.borne_hi;
            vide1 := rec.vide;
            hors1 := rec.limite_atteinte;
        END LOOP;
        IF hors1 THEN                                        -- limite de balayages ou borne au-dessus de M : erreur, rien n'est publié (comme MasquageInstable)
            RAISE EXCEPTION 'v_version_quality_photo : la propagation atteint sa limite de balayages ou une borne au-dessus de M';
        END IF;
        IF vide1 THEN                                       -- la lecture « m libre » n'est jamais écartée : un intervalle vide est une erreur
            RAISE EXCEPTION 'v_version_quality_photo : la propagation donne un intervalle vide dans la lecture où m est libre';
        END IF;
        pin_zero := array_fill(false, ARRAY[nv]);
        pin_exces := array_fill(false, ARRAY[nv]);
        FOR i IN 1..n LOOP                                   -- par ligne (M2 a, M7 a) : lectures « m_r = 0 », « U_r = 0 » et « U_r = 0 et m_r = 0 », les autres lignes libres
            IF var_m[i] > 0 THEN
              FOR lect IN 1..3 LOOP                          -- 1 : m = 0 ; 2 : U = 0 ; 3 : U = 0 et m = 0
                IF (lect = 1 AND lo1[var_m[i]] = 0) OR (lect = 2 AND lo1[var_u[i]] = 0)
                   OR (lect = 3 AND lo1[var_m[i]] = 0 AND lo1[var_u[i]] = 0) THEN     -- le pari tient encore (sinon : lecture vide, écartée)
                    lo2 := lo0;
                    hi2 := hi0;
                    IF lect <> 2 THEN
                        lo2[var_m[i]] := 0;
                        hi2[var_m[i]] := 0;
                    END IF;
                    IF lect >= 2 THEN
                        lo2[var_u[i]] := 0;
                        hi2[var_u[i]] := 0;
                    END IF;
                    lo3 := ARRAY[]::bigint[];
                    hi3 := ARRAY[]::bigint[];
                    vide3 := false;
                    hors3 := false;
                    FOR rec IN SELECT * FROM flow.propager_bornes(lo2, hi2, rk, rr, tr, tv, tc, borne_m,
                                                                  least(limite_p, 4 * (nv + nr) + 10)) LOOP         -- PROPAGATION-ZERO-MAX 4 x (V + R) + 10
                        lo3[rec.rang] := rec.borne_lo;
                        hi3[rec.rang] := rec.borne_hi;
                        vide3 := rec.vide;
                        hors3 := rec.limite_atteinte;
                    END LOOP;
                    -- une limite atteinte (PROPAGATION-ZERO-MAX) ou une borne au-dessus de M : erreur, rien n'est publié (échec fermé, M2 a, comme
                    -- MasquageInstable) ; seul un intervalle vide écarte la lecture de cette ligne (le pari est contredit par les cellules publiées)
                    IF hors3 THEN
                        RAISE EXCEPTION 'v_version_quality_photo : une lecture par ligne (m = 0, U = 0 ou les deux) atteint sa limite de balayages ou une borne au-dessus de M';
                    END IF;
                    IF NOT vide3 THEN
                        FOR v IN 1..nv LOOP
                            IF v_col[v] <= 9 AND NOT publiee[v] AND hi3[v] IS NOT NULL AND lo3[v] = hi3[v] THEN
                                pin_zero[v] := true;
                            END IF;
                        END LOOP;
                        -- D15, étape 4 : l'excès m_r fixé sous le seuil dans la lecture « U_r = 0 » de sa ligne est épinglé, sauf pour une ligne à un seul
                        -- terme retenu (exemption : m = 0 par structure) ; ni « m = 0 » ni « U = 0 et m = 0 », où m = 0 est le pari lui-même
                        IF lect = 2 AND hi3[var_m[i]] IS NOT NULL AND lo3[var_m[i]] = hi3[var_m[i]] AND lo3[var_m[i]] < t
                           AND nb_termes[i] <> 1 THEN
                            pin_exces[var_m[i]] := true;
                        END IF;
                    END IF;
                END IF;
              END LOOP;
            END IF;
        END LOOP;

        -- 4. la première variable épinglée, dans l'ordre des clés
        epingle := 0;
        FOR v IN 1..nv LOOP
            IF v_col[v] <= 9 THEN
                IF NOT publiee[v] THEN
                    IF (hi1[v] IS NOT NULL AND lo1[v] = hi1[v]) OR pin_zero[v] THEN
                        epingle := v;
                        EXIT;
                    END IF;
                END IF;
            ELSIF v_col[v] = 11 THEN
                IF pin_exces[v] THEN                         -- excès fixé sous le seuil dans la lecture « U = 0 » de sa ligne (D5-e, X10), hors exemption
                    epingle := v;
                    EXIT;
                END IF;
            END IF;
        END LOOP;
        IF epingle = 0 THEN
            FOR i IN 1..n LOOP
                rang := i;
                v_found := vis[(i - 1) * 9 + 1];
                v_found_open := vis[(i - 1) * 9 + 2];
                v_corrected_at_week := vis[(i - 1) * 9 + 3];
                v_corrected_now := vis[(i - 1) * 9 + 4];
                v_reopened := vis[(i - 1) * 9 + 5];
                v_dc := vis[(i - 1) * 9 + 6];
                v_dwa := vis[(i - 1) * 9 + 7];
                v_rw := vis[(i - 1) * 9 + 8];
                v_rwd := vis[(i - 1) * 9 + 9];
                RETURN NEXT;
            END LOOP;
            RETURN;
        END IF;
        iter := iter + 1;
        IF iter >= limite_b THEN
            RAISE EXCEPTION 'v_version_quality_photo : la propagation des bornes ne se stabilise pas en % passes', limite_b;
        END IF;

        -- 5. la voisine : la plus petite cellule publiée liée à la variable épinglée, anneau après anneau ; les termes latents sont transparents
        vus := array_fill(false, ARRAY[nv]);
        front := array_fill(false, ARRAY[nv]);
        vus[epingle] := true;
        front[epingle] := true;
        y := 0;
        LOOP
            anneau := array_fill(false, ARRAY[nv]);
            LOOP
                progres := false;
                FOR r IN 1..nr LOOP
                    CONTINUE WHEN coalesce(hors_anneau[r], false);       -- la relation P5 des sommes n'est pas traversée par les anneaux
                    touche := false;
                    FOR k IN r_deb[r]..r_fin[r] LOOP
                        IF front[tv[k]] OR (anneau[tv[k]] AND v_col[tv[k]] > 9) THEN
                            touche := true;
                            EXIT;
                        END IF;
                    END LOOP;
                    IF touche THEN
                        FOR k IN r_deb[r]..r_fin[r] LOOP
                            IF NOT vus[tv[k]] AND NOT front[tv[k]] AND NOT anneau[tv[k]] THEN
                                anneau[tv[k]] := true;
                                IF v_col[tv[k]] > 9 THEN
                                    progres := true;
                                END IF;
                            END IF;
                        END LOOP;
                    END IF;
                END LOOP;
                EXIT WHEN NOT progres;
            END LOOP;
            meilleure := 0;
            plus_petite_autre := NULL;
            FOR v IN 1..nv LOOP                              -- candidates : cellules de comptage publiées de l'anneau ; la plus petite valeur, à égalité la première clé
                IF anneau[v] AND v_col[v] <= 9 AND publiee[v] THEN
                    IF meilleure = 0 THEN
                        meilleure := v;
                    ELSIF valeur[v] < valeur[meilleure] THEN
                        plus_petite_autre := CASE WHEN plus_petite_autre IS NULL THEN valeur[meilleure] ELSE least(plus_petite_autre, valeur[meilleure]) END;
                        meilleure := v;
                    ELSE
                        plus_petite_autre := CASE WHEN plus_petite_autre IS NULL THEN valeur[v] ELSE least(plus_petite_autre, valeur[v]) END;
                    END IF;
                END IF;
            END LOOP;
            IF meilleure > 0 THEN
                y := meilleure;
                EXIT;
            END IF;
            trouve := false;
            FOR v IN 1..nv LOOP
                IF anneau[v] THEN
                    vus[v] := true;
                    trouve := true;
                END IF;
            END LOOP;
            IF NOT trouve THEN
                RAISE EXCEPTION 'v_version_quality_photo : une cellule épinglée sans cellule publiée à masquer';
            END IF;
            front := anneau;
        END LOOP;
        haut := CASE WHEN plus_petite_autre IS NULL THEN NULL ELSE greatest(t - 1, plus_petite_autre) END;      -- voisine seule candidate : NULL, sans borne haute (B15)
        ix := (v_row[y] - 1) * 9 + v_col[y];
        vis[ix] := false;
        regle[ix] := 6;
        reg_a[ix] := haut;
    END LOOP externe;
END
$$;

-- Le marqueur du masquage passe à 2 (D9, décision 15 : la propagation des bornes de la photo est installée) ; les versions sont croissantes. adopt-n attend 3
-- dès le groupe 6 (R-20261104-45 (1)) : il refuse 1 et 2, code 3, sans rien écrire, jusqu'à la migration des groupes 7 et 8 qui posera 3 (tâche 7.0b).
CREATE OR REPLACE FUNCTION flow.masking_version() RETURNS integer
    LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$ SELECT 2 $$;

CREATE OR REPLACE VIEW flow.v_version_quality_photo AS
WITH RECURSIVE adoptions AS (
    SELECT weeks, adopted_on, row_number() OVER (ORDER BY id DESC) AS rang FROM flow.version_photo_n
),
courante AS (
    SELECT weeks AS n_weeks, adopted_on AS n_adopted_on FROM adoptions WHERE rang = 1
),
etat_n AS (
    SELECT (SELECT count(*) FROM adoptions) > 0 AS adopte,
           (SELECT count(*) FROM adoptions) > 1 AS modifie,
           (SELECT weeks FROM adoptions WHERE rang = 2) AS n_previous_weeks,
           (SELECT adopted_on FROM adoptions WHERE rang = 2) AS n_previous_adopted_on
),
couverture AS (
    SELECT r.id AS run_id, r.source, w.coverage, w.week_start, r.taken_at
    FROM flow.version_photo_weeks w JOIN flow.version_photo_runs r ON r.id = w.run_id
),
retenues AS (       -- vide tant que N n'est pas adopté (jointure avec « courante ») et pour une version sans date de sortie
    SELECT v.version_no, v.release_date, v.released,
           (v.release_date - (extract(isodow FROM v.release_date)::int - 1) - 7 * c.n_weeks) AS week_start,
           c.n_weeks, c.n_adopted_on
    FROM flow.version_photo_versions v CROSS JOIN courante c
    WHERE v.release_date IS NOT NULL
),
equipe_version AS (
    SELECT x.run_id, x.source, x.coverage, x.week_start, x.taken_at, e.team, e.version_no,
           rt.release_date, rt.released, rt.n_weeks, rt.n_adopted_on,
           e.found, e.found_open, e.corrected_at_week, e.corrected_now, e.reopened
    FROM flow.version_photo_rows e
    JOIN retenues rt ON rt.version_no = e.version_no AND rt.week_start = e.week_start
    JOIN couverture x ON x.week_start = e.week_start
),
produit_version AS (
    -- Sommes brutes des cellules d'équipe par semaine et version : la règle D3 et toutes les autres sont dans flow.photo_masque.
    SELECT week_start, version_no,
           min(run_id) AS run_id, min(source) AS source, min(coverage) AS coverage, min(taken_at) AS taken_at,
           min(release_date) AS release_date, bool_or(released) AS released, min(n_weeks) AS n_weeks, min(n_adopted_on) AS n_adopted_on,
           sum(found)::bigint AS found, sum(found_open)::bigint AS found_open, sum(corrected_at_week)::bigint AS corrected_at_week,
           sum(corrected_now)::bigint AS corrected_now, sum(reopened)::bigint AS reopened
    FROM equipe_version
    GROUP BY week_start, version_no
),
libre_base AS (
    -- Défauts sans affects : la relation réelle est « défauts créés = sans affects + défauts distincts avec au moins une affects version ». Les termes
    -- sont les versions qui ont une ligne dans l'équipe et la semaine ; n_caches - n_publies est le nombre de termes dont la version n'est pas retenue cette
    -- semaine (écart (d) : le SQL les voit et pas le Python) ; flow.photo_masque compte lui-même les termes retenus dont la cellule est masquée.
    SELECT x.run_id, x.source, x.coverage, x.week_start, x.taken_at, e.team, c.n_weeks, c.n_adopted_on,
           e.defects_created, e.defects_without_affects, e.resolved_week, e.resolved_week_defects,
           nv.n_caches, nv.n_publies
    FROM flow.version_photo_rows e
    JOIN (SELECT DISTINCT week_start FROM retenues) s ON s.week_start = e.week_start
    JOIN couverture x ON x.week_start = e.week_start
    CROSS JOIN courante c
    CROSS JOIN LATERAL (
        SELECT count(*) FILTER (WHERE NOT (ev.found >= 5
                                           AND EXISTS (SELECT 1 FROM retenues rt WHERE rt.version_no = ev.version_no AND rt.week_start = ev.week_start)))
                   AS n_caches,
               count(*) FILTER (WHERE ev.found < 5
                                AND EXISTS (SELECT 1 FROM retenues rt WHERE rt.version_no = ev.version_no AND rt.week_start = ev.week_start))
                   AS n_publies
        FROM flow.version_photo_rows ev
        WHERE ev.week_start = e.week_start AND ev.team = e.team AND ev.version_no IS NOT NULL    -- un trouvé nul est un terme caché, comme en Python
    ) nv
    WHERE e.version_no IS NULL
),
produit_libre_brut AS (
    SELECT week_start,
           min(run_id) AS run_id, min(source) AS source, min(coverage) AS coverage, min(taken_at) AS taken_at,
           min(n_weeks) AS n_weeks, min(n_adopted_on) AS n_adopted_on,
           sum(defects_created)::bigint AS defects_created, sum(defects_without_affects)::bigint AS defects_without_affects,
           sum(resolved_week)::bigint AS resolved_week, sum(resolved_week_defects)::bigint AS resolved_week_defects
    FROM libre_base
    GROUP BY week_start
),
termes_produit AS (
    -- Termes du produit non retenus cette semaine : une version qui a une ligne dans la semaine sans cellule du produit retenue.
    SELECT t.week_start, count(*) FILTER (WHERE pv.version_no IS NULL) AS extra
    FROM (SELECT DISTINCT week_start, version_no
          FROM flow.version_photo_rows
          WHERE version_no IS NOT NULL AND week_start IN (SELECT week_start FROM retenues)) t
    LEFT JOIN produit_version pv ON pv.week_start = t.week_start AND pv.version_no = t.version_no
    GROUP BY t.week_start
),
lignes_unite AS (
    -- L'unité de la propagation (D15) : toute la photo, une ligne par semaine retenue, équipe (ou produit) et version, rangée par la clé (rang de ligne :
    -- équipes 0, produit 1 ; semaine ; équipe en ordre d'octets ; version, la ligne sans version d'abord).
    SELECT u.*, row_number() OVER (ORDER BY u.rang_t, u.week_start, u.team COLLATE "C", u.vno NULLS FIRST) AS rn
    FROM (
        SELECT 0 AS rang_t, 'ev'::text AS genre, e.run_id, e.source, e.coverage, e.week_start, e.taken_at, e.team, e.version_no AS vno,
               e.release_date, e.released, e.n_weeks, e.n_adopted_on,
               e.found, e.found_open, e.corrected_at_week, e.corrected_now, e.reopened,
               NULL::bigint AS dc, NULL::bigint AS dwa, NULL::bigint AS rw, NULL::bigint AS rwd, 0::bigint AS extra
        FROM equipe_version e
        UNION ALL
        SELECT 1, 'pv'::text, p.run_id, p.source, p.coverage, p.week_start, p.taken_at, '(produit)'::text, p.version_no,
               p.release_date, p.released, p.n_weeks, p.n_adopted_on,
               p.found, p.found_open, p.corrected_at_week, p.corrected_now, p.reopened,
               NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint, 0::bigint
        FROM produit_version p
        UNION ALL
        SELECT 0, 'el'::text, l.run_id, l.source, l.coverage, l.week_start, l.taken_at, l.team, NULL::integer,
               NULL::date, NULL::boolean, l.n_weeks, l.n_adopted_on,
               NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint,
               l.defects_created, l.defects_without_affects, l.resolved_week, l.resolved_week_defects, (l.n_caches - l.n_publies)::bigint
        FROM libre_base l
        UNION ALL
        SELECT 1, 'pl'::text, q.run_id, q.source, q.coverage, q.week_start, q.taken_at, '(produit)'::text, NULL::integer,
               NULL::date, NULL::boolean, q.n_weeks, q.n_adopted_on,
               NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint,
               q.defects_created, q.defects_without_affects, q.resolved_week, q.resolved_week_defects, coalesce(tp.extra, 0)::bigint
        FROM produit_libre_brut q LEFT JOIN termes_produit tp ON tp.week_start = q.week_start
    ) u
),
tableaux AS (
    SELECT (SELECT array_agg(u.week_start ORDER BY u.rn) FROM lignes_unite u) AS sem,
           (SELECT array_agg(u.team ORDER BY u.rn) FROM lignes_unite u) AS eq,
           (SELECT array_agg(u.vno ORDER BY u.rn) FROM lignes_unite u) AS ver,
           (SELECT array_agg(c.x ORDER BY u.rn, c.k)
            FROM lignes_unite u
            CROSS JOIN LATERAL (VALUES (1, u.found), (2, u.found_open), (3, u.corrected_at_week), (4, u.corrected_now), (5, u.reopened),
                                       (6, u.dc), (7, u.dwa), (8, u.rw), (9, u.rwd)) AS c(k, x)) AS val,
           (SELECT array_agg(u.extra ORDER BY u.rn) FROM lignes_unite u) AS extra
),
masque AS (
    SELECT m.* FROM tableaux a CROSS JOIN LATERAL flow.photo_masque(a.sem, a.eq, a.ver, a.val, a.extra) m
)
-- 1. lignes de couverture
SELECT x.run_id, x.source, x.coverage, x.week_start, x.taken_at,
       n.adopte AS n_adopted, n.modifie AS n_modified_after_reading, n.n_previous_weeks, n.n_previous_adopted_on,
       NULL::integer AS n_weeks, NULL::date AS n_adopted_on, NULL::text AS team, NULL::integer AS version_no,
       NULL::date AS release_date, NULL::boolean AS released,
       NULL::bigint AS found, NULL::bigint AS found_open, NULL::bigint AS corrected_at_week, NULL::bigint AS corrected_now,
       NULL::bigint AS reopened, NULL::bigint AS defects_created, NULL::bigint AS defects_without_affects,
       NULL::bigint AS resolved_week, NULL::bigint AS resolved_week_defects,
       NULL::numeric AS correction_share_percent, NULL::numeric AS without_affects_share_percent
FROM couverture x CROSS JOIN etat_n n
UNION ALL
-- 2. équipe et version
SELECT u.run_id, u.source, u.coverage, u.week_start, u.taken_at,
       n.adopte, n.modifie, n.n_previous_weeks, n.n_previous_adopted_on,
       u.n_weeks, u.n_adopted_on, u.team, u.vno, u.release_date, u.released,
       CASE WHEN m.v_found THEN u.found END, CASE WHEN m.v_found_open THEN u.found_open END,
       CASE WHEN m.v_corrected_at_week THEN u.corrected_at_week END, CASE WHEN m.v_corrected_now THEN u.corrected_now END,
       CASE WHEN m.v_reopened THEN u.reopened END, NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint,
       NULL::numeric, NULL::numeric
FROM lignes_unite u JOIN masque m ON m.rang = u.rn CROSS JOIN etat_n n
WHERE u.genre = 'ev'
UNION ALL
-- 3. produit et version
SELECT u.run_id, u.source, u.coverage, u.week_start, u.taken_at,
       n.adopte, n.modifie, n.n_previous_weeks, n.n_previous_adopted_on,
       u.n_weeks, u.n_adopted_on, '(produit)'::text, u.vno, u.release_date, u.released,
       CASE WHEN m.v_found THEN u.found END, CASE WHEN m.v_found_open THEN u.found_open END,
       CASE WHEN m.v_corrected_at_week THEN u.corrected_at_week END, CASE WHEN m.v_corrected_now THEN u.corrected_now END,
       CASE WHEN m.v_reopened THEN u.reopened END, NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint, NULL::numeric, NULL::numeric
FROM lignes_unite u JOIN masque m ON m.rang = u.rn CROSS JOIN etat_n n
WHERE u.genre = 'pv'
UNION ALL
-- 4. équipe, sans version
SELECT u.run_id, u.source, u.coverage, u.week_start, u.taken_at,
       n.adopte, n.modifie, n.n_previous_weeks, n.n_previous_adopted_on,
       u.n_weeks, u.n_adopted_on, u.team, NULL::integer, NULL::date, NULL::boolean,
       NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint,
       CASE WHEN m.v_dc THEN u.dc END, CASE WHEN m.v_dwa THEN u.dwa END,
       CASE WHEN m.v_rw THEN u.rw END, CASE WHEN m.v_rwd THEN u.rwd END,
       CASE WHEN m.v_rwd AND m.v_rw THEN round(100.0 * u.rwd / u.rw, 1) END,
       CASE WHEN m.v_dwa AND m.v_dc THEN round(100.0 * u.dwa / u.dc, 1) END
FROM lignes_unite u JOIN masque m ON m.rang = u.rn CROSS JOIN etat_n n
WHERE u.genre = 'el'
UNION ALL
-- 5. produit, sans version
SELECT u.run_id, u.source, u.coverage, u.week_start, u.taken_at,
       n.adopte, n.modifie, n.n_previous_weeks, n.n_previous_adopted_on,
       u.n_weeks, u.n_adopted_on, '(produit)'::text, NULL::integer, NULL::date, NULL::boolean,
       NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint, NULL::bigint,
       CASE WHEN m.v_dc THEN u.dc END, CASE WHEN m.v_dwa THEN u.dwa END,
       CASE WHEN m.v_rw THEN u.rw END, CASE WHEN m.v_rwd THEN u.rwd END,
       CASE WHEN m.v_rwd AND m.v_rw THEN round(100.0 * u.rwd / u.rw, 1) END,
       CASE WHEN m.v_dwa AND m.v_dc THEN round(100.0 * u.dwa / u.dc, 1) END
FROM lignes_unite u JOIN masque m ON m.rang = u.rn CROSS JOIN etat_n n
WHERE u.genre = 'pl';

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits : retirés d'abord (les droits par défaut du schéma s'appliquent à tout nouvel objet du propriétaire), puis accordés, comme 0022.
REVOKE ALL ON flow.v_version_quality_photo FROM PUBLIC, pmzilla_flow, pmzilla_flow_ro, pmzilla_quality_views;
GRANT SELECT ON flow.v_version_quality_photo TO pmzilla_flow_views;

-- Les deux fonctions de la propagation : EXECUTE au seul rôle des vues. En PostgreSQL, le droit EXECUTE d'une fonction appelée dans une vue est vérifié
-- pour l'utilisateur qui lit la vue, non pour son propriétaire : sans lui, pmzilla_flow_views ne pourrait plus lire la photo. Elles ne lisent aucune table.
REVOKE ALL ON FUNCTION flow.propager_bornes(bigint[], bigint[], smallint[], bigint[], integer[], integer[], smallint[], bigint, bigint)
    FROM PUBLIC, pmzilla_flow, pmzilla_flow_views, pmzilla_flow_ro, pmzilla_quality_views;
GRANT EXECUTE ON FUNCTION flow.propager_bornes(bigint[], bigint[], smallint[], bigint[], integer[], integer[], smallint[], bigint, bigint)
    TO pmzilla_flow_views;
REVOKE ALL ON FUNCTION flow.photo_masque(date[], text[], integer[], bigint[], bigint[], integer, bigint)
    FROM PUBLIC, pmzilla_flow, pmzilla_flow_views, pmzilla_flow_ro, pmzilla_quality_views;
GRANT EXECUTE ON FUNCTION flow.photo_masque(date[], text[], integer[], bigint[], bigint[], integer, bigint) TO pmzilla_flow_views;
-- flow.photo_masque appelle flow.propager_bornes : sous le rôle des vues, l'appel est vérifié pour ce rôle, qui a les deux droits.

-- Marqueur (D9) : exécutable par le seul rôle d'import ; ni PUBLIC, ni le rôle des vues, ni la lecture seule, ni les vues de la qualité.
REVOKE ALL ON FUNCTION flow.masking_version() FROM PUBLIC, pmzilla_flow_views, pmzilla_flow_ro, pmzilla_quality_views;
GRANT EXECUTE ON FUNCTION flow.masking_version() TO pmzilla_flow;
