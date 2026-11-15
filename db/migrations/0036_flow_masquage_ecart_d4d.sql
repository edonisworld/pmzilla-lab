-- Schéma touché : flow (fonction flow.photo_masque ; la vue flow.v_version_quality_photo et ses colonnes ne changent pas). Aucune donnée, aucun mot de passe,
-- aucun rôle créé, modifié ou supprimé, aucune table changée, le marqueur du masquage (flow.masking_version) reste à 2.
-- R-20261106-22 (décision de l'auteur du 2026-11-06, qui remplace R-20261105-6 Q4 (a) ; revue des chemins de démasquage de 0035, C1 et C1') : l'écart D4 (d) est
-- rétabli. Une ligne d'équipe sans ligne de version retenue cette semaine-là, et la ligne du produit sous la même condition, fait de nouveau masquer ses défauts
-- créés et sans affects (D2 et D5-e), comme le faisait flow.photo_serie de 0022 (l. 192-196 : m = n_publies = 0, l'excès étant sous 5 : sans affects est masqué, puis
-- créés à la passe suivante). Cette migration suit celle de la propagation (0035), déjà appliquée sur la vraie base : elle ne la modifie pas en place, elle
-- remplace la seule fonction flow.photo_masque (CREATE OR REPLACE, même signature).
--
-- Remplace : le garde-fou `IF nterms > 0` de flow.photo_masque dans 0035 (la lecture de m dans D2 ne se faisait que si la ligne avait au moins un terme, version
-- retenue de l'équipe et de la semaine), et son commentaire. Sans ce garde-fou, la boucle sur m = np et m = np + extra tourne aussi pour une ligne sans terme
-- (np = 0) : la cellule sans affects visible est masquée (l'excès créés - sans affects - 0 est sous 5 ou négatif), puis les créés, à la passe suivante. Le corps
-- de la fonction est par ailleurs celui de 0035, mot pour mot (un test les compare). Même règle dans tools/flow_views.py (completer), pour la parité.
-- Retrait : aucune condition de retrait, la règle est le masquage de la ligne sans version de la photo ; elle ne change que sur une nouvelle décision de l'auteur.
-- La fonction tombe, comme celle de 0035 qu'elle remplace, avec la migration qui remplacera flow.photo_masque.
--
-- Conséquence : la cascade C1' de la revue. Une semaine sans ligne de version que 0035 publiait servait d'ancre à D5-d (0035, l. 335-353) pour les semaines suivantes
-- et pouvait en masquer ou en démasquer ; elle est de nouveau masquée comme dans 0022 et ces ancres reviennent à celles de 0022. Aucune cellule n'est publiée
-- de plus que dans 0022 (cas d'oracle de tests/oracle_masquage, balayage 0 <= w <= c <= 30). Les limites déclarées de 0035 (PROPAGATION-MAX, PROPAGATION-ZERO-MAX,
-- LOOP-MAX, PASSES-MAX) sont inchangées.

SET LOCAL ROLE pmzilla_owner;

CREATE OR REPLACE FUNCTION flow.photo_masque(sem date[], eq text[], ver integer[], val bigint[], extra bigint[],
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
                        FOR k IN 1..w LOOP                   -- D2 sur chaque semaine (même règle que flow.photo_serie de 0022, y compris pour une ligne sans ligne de version : m = 0, R-20261106-22)
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
                                -- aucune ligne de version dans la semaine : pas de garde-fou (écart D4 (d) rétabli, R-20261106-22), m = np = 0 comme flow.photo_serie de 0022
                                FOREACH m IN ARRAY ARRAY[np, np + coalesce(extra[j], 0)] LOOP
                                    besoin := besoin OR coalesce(CASE WHEN vis[ix_dwa]
                                        THEN ((m >= 1 AND (m < 2 OR crees - sans - sv < 5 OR crees - sans - sv = 4 * m))
                                              OR (m = 0 AND sv - (crees - sans) < 5))
                                        ELSE (1 + m < 2 OR crees - sv < 5 OR crees - sv = 4 * (1 + m))
                                        END, false);
                                END LOOP;
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

RESET ROLE;     -- l'exécuteur écrit ensuite dans public.schema_migrations avec son propre rôle

-- Droits : retirés d'abord puis accordés au seul rôle des vues, comme 0035 (un CREATE OR REPLACE conserve les droits ; on les redit pour que le fichier se lise seul).
REVOKE ALL ON FUNCTION flow.photo_masque(date[], text[], integer[], bigint[], bigint[], integer, bigint)
    FROM PUBLIC, pmzilla_flow, pmzilla_flow_views, pmzilla_flow_ro, pmzilla_quality_views;
GRANT EXECUTE ON FUNCTION flow.photo_masque(date[], text[], integer[], bigint[], bigint[], integer, bigint) TO pmzilla_flow_views;
