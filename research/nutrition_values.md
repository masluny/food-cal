# Nutrition values and g/cm² for food-cal — source research report

Prepared: 2026-10-12. This report replaces the "from memory" values in `configs/nutrition.yaml` with sourced values; **no project file other than this report was changed** by the research. (Translated from the original Polish report; class names follow the current English names in `configs/classes.yaml`.)

## 0. How this was done and what could NOT be done

- **NIZP-PZH "Tabele składu i wartości odżywczej żywności" (Polish food composition tables, Kunachowicz et al., 4th ed. 2017) — not available.** The full database is distributed only under a license agreement as an .XLSX file (quote from the PZH page: "Baza udostępniana jest na podstawie umowy licencyjnej w formacie pliku .XLSX" — "The database is provided under a license agreement as an .XLSX file", 1045 products and dishes; orders: biurosprzedazy@pzh.gov.pl). Only the cover/description (PDF) is public. No number in this report comes from NIZP-PZH. For Polish values you would need to buy the license or the PZWL book.
- **kcal/protein/fat/carbs values come from USDA FoodData Central**: CSV files downloaded from the official `fdc.nal.usda.gov/fdc-datasets/` page:
  - **SR Legacy** (`FoodData_Central_sr_legacy_food_csv_2018-04.zip`, 6.07 MB) — marked "SR <fdcId>",
  - **FNDDS / Survey** (`FoodData_Central_survey_food_csv_2022-10-28.zip`, 4.43 MB) — marked "FNDDS <fdcId>".
  Every value was read directly from `food_nutrient.csv` (energy: nutrient id 1008 in SR, no. 208 in FNDDS; protein 203; fat 204; carbohydrate "by difference" 205). Some SR values were additionally checked via the API (`/foods/search`, same numbers: e.g. SR 170317 = 268/10.4/12.3/29.0; SR 174924 = 266/8.85/3.33/49.4). USDA energy is kcal by Atwater factors (no fiber correction as in the new NIZP edition).
- **Densities: FAO/INFOODS Density Database v2.0** (Excel file, sheet "Density DB"; the sheet row number is given) and "cup/slice" weights from USDA `food_portion.csv` (1 cup = 236.588 ml; 1 fl oz = 29.5735 ml).
- **Thickness/height on the plate**: sources exist only for some items (pizza — whole-pizza mass and diameter; cutlet — thickness after pounding; bread slice — slicing thickness; sausage/potato/apple — dimensions from USDA). For piles (pasta, rice, salad, fries, vegetables…) **the pile height is an ASSUMPTION** and is marked as such. I found no published measurements of "typical height of a pasta pile on a plate".
- The `factual-research` tool is geared toward scientific literature (PubMed, arXiv etc.) and has no connector for food tables; verification was done by hand by reading the CSV/Excel files and quoting web pages verbatim. Web pages were read through a tool that summarizes content — key quotes were checked, and the quality of each source is marked in the tables.
- Confidence legend: **H** = high (a direct USDA/FAO entry for this dish), **M** = medium (mean of several USDA entries or a proxy), **L** = low (assumptions or a proxy far from the Polish dish).

## 1. Values per 100 g (kcal / protein / fat / carbs)

### 1.1 Composite dishes (pizza, toast, zapiekanka, bread)

| Class | kcal | protein | fat | carbs | Source and item | Confidence |
|---|---|---|---|---|---|---|
| pizza | 261 | 11.1 | 10.6 | 29.7 | Mean of 3 items: SR 170373 "Pizza, cheese topping, thin crust, frozen, cooked" (263/11.91/11.07/28.8); SR 173292 "Fast Food, Pizza Chain, 14" pizza, cheese topping, regular crust" (266/11.39/9.69/33.33); Dr. Oetker Ristorante Pizza Margherita label (CZ, rohlik.cz): 253 kcal/10 P/11 F/27 C | M |
| toast | 299 | 14.6 | 14.6 | 27.2 | **Computed** from a recipe (ASSUMED weights): 44 g toasted white bread (SR 174925 "Bread, white, commercially prepared, toasted": 290/9.0/4.0/54.5; 2 slices of 22 g per the SR "slice" 22 g), 25 g gouda (SR 171241 "Cheese, gouda": 356/24.94/27.44/2.22), 20 g ham (SR 173864 "Ham, sliced, regular (approximately 11% fat)": 164/16.6/8.8/3.63), 4 g butter (SR 173410 "Butter, salted": 717/0.85/81.11/0.06). Total 93 g, 278 kcal | M (USDA composition reliable, proportions assumed) |
| zapiekanka | 205 | 10.5 | 6.5 | 27.5 | **Computed** (ASSUMED weights): 140 g baguette (SR 172675 "Bread, french or vienna (includes sourdough)": 272/10.75/2.42/51.88), 80 g fried mushrooms (SR 169253 "Mushrooms, white, stir-fried": 26/3.58/0.33/4.04), 60 g cheese (mean of SR 170846 "Cheese, mozzarella, whole milk, low moisture": 318/21.6/24.64/2.47 and SR 171241 gouda), 25 g ketchup (SR 168556 "Catsup": 101/1.04/0.1/27.4). Total 305 g: mozzarella variant 202.5/10.2/6.1/27.6; gouda variant 210/10.9/6.6/27.6. Cross-check — labels/user entries (weak source): 175 kcal/8 P/5.4 F/23.4 C (Biedronka, kalkulatorkalorii.net), range 185–259 kcal on FatSecret | M/L |
| bread | 266 | 9.3 | 3.7 | 48.4 | Mean: SR 174924 "Bread, white, commercially prepared (includes soft bread crumbs)" (266/8.85/3.33/49.42); SR 172686 "Bread, wheat" (274/10.67/4.53/47.54); SR 172684 "Bread, rye" (259/8.5/3.3/48.3) | M |

### 1.2 Starches, sauces, dairy

| Class | kcal | protein | fat | carbs | Source and item | Confidence |
|---|---|---|---|---|---|---|
| pasta (cooked) | 158 | 5.8 | 0.9 | 30.9 | SR 169737 "Pasta, cooked, enriched, without added salt" (158/5.8/0.93/30.86). Note: kcal depends on how long it is cooked (water uptake); USDA "al dente" pasta is "drier" than overcooked | H |
| sauce — tomato | 70 | 3.7 | 3.0 | 7.0 | Mean: SR 171192 "Sauce, pasta, spaghetti/marinara, ready-to-serve" (50/1.39/1.61/7.43) and FNDDS 2341894 "Spaghetti sauce with meat" (90/5.94/4.36/6.54). Sauce alone without meat = 50 kcal | M |
| sauce — cream | 156 | 4.3 | 12.9 | 5.8 | Mean: FNDDS 2341213 "Alfredo sauce" (150/2.37/15.16/1.48); FNDDS 2341106 "White sauce or gravy" (144/3.84/10.2/9.21); SR 171191 "Sauce, cheese, ready-to-serve" (174/6.71/13.29/6.83) | M |
| **sauce — mix** | **104** | **3.9** | **6.9** | **6.5** | 0.6 × tomato + 0.4 × cream (**60/40 weights ASSUMED**) | L |
| cheese_butter (cheese) | 337 | 24.0 | 26.0 | 2.0 | Mean: SR 171241 "Cheese, gouda" (356/24.94/27.44/2.22); SR 173419 "Cheese, edam" (357/24.99/28.57/1.43); SR 170845 "Cheese, mozzarella, whole milk" (299/22.17/22.14/2.4) | H |
| butter (separately) | 717 | 0.85 | 81.1 | 0.06 | SR 173410 "Butter, salted" (717/0.85/81.11/0.06); identical to SR 173430 "Butter, without salt" | H |
| potatoes (boiled) | 86 | 1.7 | 0.1 | 20.0 | SR 170440 "Potatoes, boiled, cooked without skin, flesh, without salt" (86/1.71/0.1/20.0); in skin: SR 170438 87/1.87/0.1/20.1 | H |
| fries | 275 | 3.1 | 14.3 | 34.0 | Mean of 3: FNDDS 2344955 "Potato, french fries, fast food" (312/3.43/14.73/41.44, = SR 170698); FNDDS 2344956 "…restaurant" (289/3.49/14.04/37.2); FNDDS 2344957 "…from frozen, fried" (225/2.5/14.07/23.23). Range: oven-baked (FNDDS 2344954) 158 kcal — oven fries give very different kcal | M |
| rice (cooked, white) | 130 | 2.7 | 0.3 | 28.2 | SR 168878 "Rice, white, long-grain, regular, enriched, cooked" (130/2.69/0.28/28.17) | H |

### 1.3 Meat, fish, eggs

| Class | kcal | protein | fat | carbs | Source and item | Confidence |
|---|---|---|---|---|---|---|
| meat (pork/beef) | 247 | 26.6 | 14.9 | 0 | Mean: SR 167821 "Pork, fresh, loin, whole, separable lean and fat, cooked, roasted" (248/27.09/14.65/0); SR 168663 "Beef, composite of trimmed retail cuts, separable lean and fat, trimmed to 1/8" fat, select, cooked" (245/26.06/15.09/0). Lean tenderloin/loin without fat: 143–200 kcal | M |
| chicken | 190 | 28.9 | 7.4 | 0 | SR 171054 "Chicken, broilers or fryers, meat only, cooked, roasted" (190/28.93/7.41/0). Skinless breast only: SR 171477 = 165/31.02/3.57; with skin: SR 171450 = 239/27.3/13.6 | H |
| breaded_cutlet | 252 | 24.6 | 13.2 | 7.2 | Mean: FNDDS 2341275 "Pork, chop, coated, lean and fat eaten" (229/25.06/10.58/7.16); FNDDS 2341281 "Pork, steak, coated" (275/24.16/15.8/7.2). **Caveat:** this is a proxy (USDA has no schabowy); the USDA coating is ~10% of the mass (7.2 g carbs/100 g), a Polish cutlet with a thick coating fried in lard/oil may have more carbs and fat and less protein — see section 4 | L |
| sausage | 330 | 13.2 | 29.1 | 3.2 | Mean: SR 174577 "Polish sausage, pork" (326/14.1/28.72/1.63); SR 173878 "Kielbasa, fully cooked, pan-fried" (333/12.36/29.43/4.78). Other: SR 172954 "Sausage, Polish, pork and beef, smoked" 301/12.07/26.56/1.98 | M |
| fish | 159 | 23.1 | 6.7 | 0 | Mean of 5 species (cooked, dry heat): SR 171956 cod (105/22.83/0.86/0); SR 173681 Alaska pollock (111/23.48/1.18/0); SR 175117 Atlantic herring (203/23.03/11.59/0); SR 175168 farmed salmon (206/22.1/12.35/0); SR 173718 farmed trout (168/23.8/7.38/0). Lean (cod) ≈ 105, fatty (salmon) ≈ 206 kcal — wide spread | M |
| egg | 176 | 13.1 | 12.7 | 1.0 | Mean: SR 173424 "Egg, whole, cooked, hard-boiled" (155/12.58/10.61/1.12); SR 173423 "Egg, whole, cooked, fried" (196/13.61/14.84/0.83) | H |

### 1.4 Vegetables, fruit, soups, sweets, drinks, nuts, other

| Class | kcal | protein | fat | carbs | Source and item | Confidence |
|---|---|---|---|---|---|---|
| salad | 73 | 1.1 | 4.7 | 7.5 | Mean: FNDDS 2345335 "Coleslaw" (113/1.14/7.89/10.02); FNDDS 2345339 "Cucumber salad, made with sour cream dressing" (66/1.15/5.51/3.92, the equivalent of Polish mizeria); FNDDS 2345336 "Cabbage salad, NFS" (41/0.99/0.71/8.5). Range 41–159 (fast-food coleslaw = 159): depends on the amount of mayonnaise/oil | M/L |
| vegetables | 33 | 1.3 | 0.2 | 7.2 | Mean of 5: SR 170472 "Vegetables, mixed, frozen, cooked, boiled, drained, without salt" (65/2.86/0.15/13.09); SR 170393 raw carrot (41/0.93/0.24/9.58); SR 170457 tomato (18/0.88/0.2/3.89); SR 168409 cucumber with peel (15/0.65/0.11/3.63); SR 169975 raw cabbage (25/1.28/0.1/5.8). Vegetables with butter/oil will have more kcal | M |
| fruit | 58 | 0.7 | 0.2 | 14.9 | Mean of 6: SR 171688 apple (52/0.26/0.17/13.81); SR 173944 banana (89/1.09/0.33/22.84); SR 169097 orange (47/0.94/0.12/11.75); SR 174683 grapes (69/0.72/0.16/18.1); SR 167762 strawberries (32/0.67/0.3/7.68); SR 169118 pear (57/0.36/0.14/15.23) | M |
| soup | 46 | 2.7 | 1.5 | 5.8 | Mean of 5 (FNDDS): 2345634 "Borscht" (38/1.19/1.81/4.67); 2342593 "Chicken or turkey vegetable soup, home recipe" (48/4.52/1.7/4.14); 2344639 "Chicken or turkey noodle soup, home recipe" (61/5.56/2.22/4.93); 2345272 "Tomato soup, NFS" (33/0.74/0.22/7.72); 2345050 "Potato soup, NS as to made with milk or water" (50/1.6/1.49/7.66). Żurek/krupnik/pea soup will be denser (SR 171554 pea soup 125 kcal etc.) | L |
| sweets (cakes/cookies) | 404 | 5.5 | 15.6 | 61.8 | Mean of 6 (SR): 172716 "Cookies, chocolate chip, commercially prepared, regular, higher fat, enriched" (492/5.1/24.72/65.36); 172725 "Cookies, oatmeal, commercially prepared, regular" (450/6.2/18.1/68.7); 172819 "Cookies, butter, commercially prepared, unenriched" (467/6.1/18.8/68.9); 172704 "Cake, pound, commercially prepared, butter" (353/5/13.96/53.64); 172706 "Cake, sponge, commercially prepared" (290/5.4/2.7/61); 172697 "Cake, chocolate, prepared from recipe without frosting" (371/5.3/15.1/53.4) | M/L |
| drink | 39 | 0.8 | 0.8 | 7.4 | Mean of 5 (SR): 174852 regular cola (42/0/0.25/10.36); 169098 orange juice (45/0.7/0.2/10.4); 167771 apple juice (46/0.1/0.13/11.3); 171265 milk 3.25% (61/3.15/3.25/4.8); 171890 brewed coffee (1/0.12/0.02/0). The result depends heavily on what you drink (water = 0, cola ≈ 42) | L |
| nuts | 607 | 19.8 | 53.7 | 21.7 | Mean: SR 170587 "Nuts, mixed nuts, oil roasted, with peanuts, without salt added" (607/20.04/53.95/21.05); SR 170585 "…dry roasted, with peanuts, without salt added" (607/19.5/53.5/22.42). Carbs "by difference" (include fiber) | H |
| other | 184 | 12.4 | 6.6 | 18.3 | **ASSUMPTION (not sourced):** unweighted mean of 12 main-meal classes from this report (pizza, toast, zapiekanka, bread, pasta, potatoes, rice, meat, chicken, fish, egg, vegetables) | L |

## 2. Densities (FAO/INFOODS Density Database v2.0 and USDA)

Sheet "Density DB" of the file `density_DB_v2_0_final-1__1_.xlsx` (FAO/INFOODS Density Database Version 2.0, 2012). Value = bulk/mass density in g/ml; row = sheet row number. The codes in the "Source in the database" column (KEN, RC, FNDDS 4.1, S&W, TB, ASI, DK…) are copied as they appear in the BiblioID column of the sheet; their expansions are in the "BiblioID_Bibliography" sheet and the FAO guide (I did not check them, so I do not expand them).

| FAO item (row) | g/ml | Source in the database | Used for |
|---|---|---|---|
| Pasta, short macaroni style, boiled (355) | 0.55 | RC | pasta |
| Pasta/ noodles, boiled (357) | 0.59 | KEN | pasta |
| Noodles/pasta with fat (633) | 0.80 | KEN | pasta with fat/sauce |
| Rice, boiled (364) / Rice, white, boiled (371) | 0.73 / 0.73 | KEN / RC | rice |
| Potato, english, boiled (409) | 0.59 | KEN | potatoes |
| Bread, white, sliced, prepacked (290) / Bread (286) | 0.29 | FNDDS 4.1 | bread, toast |
| Bread, white (289) | 0.42 | KEN | bread (denser) |
| Egg, chicken, boiled/poached (499) | 0.60 | FNDDS 4.1 | egg (chopped — bulk) |
| Butter (208) | 0.911 | TB | butter |
| Cheese, emmentaler, grated (212) | 0.34 | RC | grated cheese (bulk) |
| Nuts (422) / Almonds (418) / Peanuts, shelled (424) | 0.63 / 0.46 / 0.69 | FNDDS 4.1 / ASI / ASI | nuts |
| Carrot, raw, grated (443) / chopped (442) | 0.71 / 0.54 | KEN | salad |
| Salad, green, leaves, raw (459) | 0.06 | RC | green lettuce (very light) |
| Salad dressing (548) / Mayonnaise, traditional (269) | 1.10 / 0.91 | FNDDS 4.1 / TB | dressing |
| Soup, vegetable (570) / Tomato soup (571) / Chicken noodle soup (564) / Soup, thick (squash, potato) (569) | 0.99 / 1.017 / 1.0 / 1.09 | KEN / S&W / S&W / RC | soup (~1.0) |
| Orange juice (27) / Fruit juice (11) / Coffee, brewed (48) / Milk, liquid, whole (205) | 1.038 / 1.06 / 1.0 / 1.03 | S&W / FNDDS 4.1 / FNDDS 4.1 / TB | drinks (~1.04) |
| Cake (305) / Biscuits (284) | 0.415 / 0.41–0.53 | S&W / FNDDS 4.1 | sweets |
| Cow, lean, no bone, raw (507) / Pork, medium, with bone, boiled (513) | 0.96 / 0.70 | KEN | meat (density of pieces in a volumetric measurement; actual tissue density ~1.0–1.05 — assumption) |

**Missing from FAO:** pizza, fries, sausage, cooked fish, breaded cutlet, fresh fruit, mushrooms. These are replaced with USDA measurements (below) or marked as assumptions.

Densities from USDA portion weights (`food_portion.csv`, 1 cup = 236.588 ml):

| USDA item | portion weight | g/ml |
|---|---|---|
| SR 169737 cooked pasta, spaghetti "cup not packed" | 124 g | 0.524 (elbows 120 g → 0.507; penne 107 g → 0.452) |
| SR 168878 cooked white rice | 158 g/cup | 0.668 |
| SR 170440 boiled potatoes | 78 g / ½ cup (118.3 ml) | 0.659 |
| FNDDS 2344956 restaurant fries | 60 g/cup | 0.254 |
| FNDDS 2345335 coleslaw / 2345336 cabbage salad | 220 g/cup | 0.930 |
| FNDDS 2345339 cucumber salad with sour cream (mizeria) | 133 g/cup | 0.562 |
| SR 170472 cooked mixed vegetables | 91 g/½ cup | 0.769 |
| SR 169975 raw cabbage | 89 g/cup chopped (70 g shredded) | 0.376 (0.296) |
| SR 170587 mixed nuts | 134 g/cup | 0.566 |
| SR 171176 tomato soup | 248 g/cup | 1.048 |
| SR 174852 cola | 370 g / 12 fl oz | 1.043 |
| SR 169098 orange juice | 248 g/cup | 1.048 |
| FNDDS 2345258 spaghetti sauce / 2341213 alfredo | 260 g/cup | 1.099 |
| SR 171287 raw egg | 243 g/cup | 1.027 |

## 3. Deriving g_cm² (g/cm² = thickness or height [cm] × density [g/cm³], or mass/area from source data)

### 3.1 Pizza — whole-pizza mass and diameter (best documented)

Area: ⌀14" = 35.56 cm → 993.1 cm²; ⌀31 cm → 754.8 cm²; ⌀24.5 cm → 471.4 cm².

| Pizza | mass | area | g/cm² | Source |
|---|---|---|---|---|
| 14" chain, thin crust | 590 g | 993 cm² | 0.594 | SR 173294 (portion "pizza" 590 g) |
| 14" chain, regular | 853 g | 993 cm² | 0.859 | SR 173292 (107 g/slice × 8 = 856 g; consistent) |
| 14" chain, thick | 922 g | 993 cm² | 0.928 | SR 173293 |
| FNDDS "surface inch": thin, restaurant | 4.5 g/in² | 6.4516 cm²/in² | 0.697 | FNDDS 2344099 portion "1 surface inch" |
| FNDDS "surface inch": restaurant, unspecified | 6.2 g/in² | | 0.961 | FNDDS 2344098 |
| Neapolitan pizza 31 cm (pizzeria, margherita) | 366 g | 755 cm² | 0.485 | scattidigusto.it: "366 grammi", "360-370 grammi per un diametro 31 centimetri" |
| Dr. Oetker Ristorante Margherita (CZ) | 295 g | 471 cm² | 0.626 | rohlik.cz: weight 295 g, diameter 24.5 cm |

Median of the seven values = 0.697 → **g_cm2 = 0.70**; range 0.49–0.96, so uncertainty ±0.20 (thin Italian ≈ 0.5–0.6, American/thick ≈ 0.86–0.96). This is the value for the whole visible circle (including the crust edge); a single slice has the same value.

### 3.2 Bread and toast

- Sliced bread: density 0.29 g/ml (FAO row 290) × slice thickness 1.0–1.3 cm (Dan Cake toast bread: "grubosc krojenia: ok. 10 mm" — "slicing thickness about 10 mm", chefsculinar.pl; an equipment guide says 12–13 mm — weak source, an online shop) = **0.29–0.38 g/cm²**. Check: SR 174924 slice = 29 g; area = 29 / (0.29 × 1.0) = 100 cm² (≈10 × 10 cm) — consistent with the blog (about 10 × 13 cm for Indian bread).
- Denser/rustic bread: 0.42 g/ml (FAO row 289) × 1.5 cm = 0.63. A roll seen from above (thick) ≈ 1.0 (assumption).
- **bread: g_cm2 = 0.40** (middle of the 0.3–0.6 range; uncertainty 0.30).
- **toast** (2 slices + cheese + ham + butter): mass 93 g (see 1.1) / 100 cm² = **0.93 → 0.95**; if a slice is 83 cm² (1.2 cm thick) → 1.12; uncertainty 0.20. The cheese/ham weights are assumed, not sourced.

### 3.3 Zapiekanka

Wikipedia: half a baguette, "may be up to 50 centimetres (20 in) long", mushrooms + cheese, ketchup. Assumptions: length 30 cm, width 8 cm = 240 cm²; mass ≈ 305 g (recipe from 1.1, the 140 g baguette is an ASSUMPTION) → 305/240 = 1.27; at 405 g (Biedronka per kalkulatorkalorii.net, weak source) and 30 × 9 cm → 1.5. **g_cm2 = 1.3**, uncertainty 0.25.

### 3.4 Pasta, rice, potatoes, fries (piles — height ASSUMED)

- **pasta:** mean bulk density of 0.524 (USDA), 0.55 and 0.59 (FAO) = 0.555 g/ml; mean pile height **2.3 cm (ASSUMPTION; a ~220 g portion on ~180 cm²)** → 0.555 × 2.3 = 1.28 → **1.3**, uncertainty 0.35. With sauce (FAO 0.80 "pasta with fat") the value rises to ~1.8.
- **rice:** (0.668 USDA; 0.73 FAO) → 0.71 g/ml × 1.8 cm (ASSUMPTION) = 1.28 → **1.3**, uncertainty 0.35.
- **potatoes:** USDA geometry — SR 170438 "potato (2-1/2" dia, sphere)" = 136 g; a ⌀6.35 cm sphere has a volume of 134 cm³ → density 1.01 g/cm³; projection = 31.7 cm² → a whole potato is 4.3 g/cm²; a half lying flat side down = half of that (2.15); cut/mashed: 0.66 g/ml × 2.5 cm (ASSUMPTION) = 1.65. A typical plate (halves and quarters) → **2.4**, uncertainty 0.35 (range 1.6–4.3).
- **fries:** bulk density 0.254 g/ml (FNDDS 2344956: 60 g/cup) × layer height 3.5 cm (ASSUMPTION: 2–3 layers of 1 cm fries) = 0.89 → **0.9**, uncertainty 0.40.

### 3.5 Meat, chicken, cutlet, sausage, fish, egg

- **breaded_cutlet:** thickness after pounding ¼ inch = 0.64 cm (whollytasteful.com: "pound to about ¼ inch thick"; polishyourkitchen.com: "¼ inch / 0.5 centimeter") + coating and puffing during frying ≈ +0.25 cm (ASSUMPTION) ≈ 0.9 cm × density ≈ 1.0 (ASSUMPTION; tissue ~1.05, porous coating) = 0.9; check: FNDDS 2341275 "regular" breaded chop 120 g on about 165 cm² (15 × 11 cm, ASSUMPTION) = 0.73. **g_cm2 = 0.85**, uncertainty 0.25. A thicker restaurant cutlet (1.5 cm) ≈ 1.5.
- **meat (a piece of steak/chop/roast):** density 0.96–1.05 × thickness 1.5 cm (ASSUMPTION) = **1.5**, uncertainty 0.25.
- **chicken (fillet):** 1.05 × mean thickness 1.4 cm (ASSUMPTION; a fillet tapers) = **1.5**; SR 171477 "½ breast, bone and skin removed" = 86 g (so a whole fillet ~172 g), uncertainty 0.30.
- **sausage:** USDA geometry — SR 174577 "sausage (10" long x 1-1/4" dia)" = 227 g: length 25.4 cm, ⌀3.175 cm → volume 201 cm³, density 1.13 g/cm³; mass / projected area (25.4 × 3.175 = 80.6 cm²) = **2.81 g/cm²** for a whole sausage. Lying slices 1 cm thick: 1.13 × 1.0 × 0.8 (coverage) ≈ 0.9. A 60% whole / 40% sliced mix → 0.6 × 2.81 + 0.4 × 0.9 = 2.05 → **2.0**, uncertainty 0.35. (The previous value of 1.9 was close but too low for a whole sausage.)
- **fish (fillet):** 1.05 (ASSUMPTION) × 1.3 cm = ~1.4; SR 171956 "1 fillet" cod = 180 g; for a 20 × 7 cm fillet (ASSUMPTION) = 1.29 → **1.3**, uncertainty 0.25.
- **egg:** fried: 55 g (FNDDS 2342630 "1 egg") on ⌀12–15 cm (ASSUMPTION) = 0.3–0.5; a whole boiled egg lying down: 50 g (SR 173424 "large") on a ~19.7 cm² projection (egg 5.7 × 4.4 cm, ASSUMPTION) = 2.5; scrambled/pile ≈ 1.0–1.5. Middle **1.2**, uncertainty 0.45 (strongly depends on the form).

### 3.6 Vegetables, fruit, soups, drinks, sweets, nuts, cheese, sauce

- **salad:** bulk density 0.56–0.93 g/ml (USDA coleslaw/mizeria), 0.54–0.71 (FAO carrot) → ~0.7 × height 1.4 cm (ASSUMPTION) = ~1.0 → **1.0**, uncertainty 0.40.
- **vegetables:** cooked 0.77 g/ml (USDA frozen mix), raw chopped 0.38–0.54 → ~0.6–0.7 × height 1.5 cm (ASSUMPTION) = ~1.0 → **1.0**, uncertainty 0.40.
- **fruit:** a medium apple "medium (3" dia)" = 182 g (SR 171688); a ⌀7.62 cm sphere, projection 45.6 cm² → 4.0 g/cm² (whole fruit); a "medium" banana 118 g (SR 173944; ~3.5 × 19 cm → ~1.8); cut slices ~1.2–1.5 → mix **2.0**, uncertainty 0.40.
- **soup:** density 1.0–1.05 g/ml (FAO/USDA); a typical serving is about 300 g (FNDDS: Borscht "Quantity not specified" 301 g, chicken soup 299 g); the soup surface in a deep plate ⌀~18 cm = 254 cm² (ASSUMPTION) → 300/254 = 1.2; in a ⌀13 cm bowl (133 cm²) → 2.3 → **1.6**, uncertainty 0.40.
- **drink:** density 1.04 g/ml; a 250 ml glass with a ⌀7.5 cm opening (44 cm², ASSUMPTION) → height 5.7 cm → **6.0**, uncertainty 0.40 (mug/glass: 5–7). A cola can 370 g/12 fl oz with ⌀6.6 cm → ~10.8.
- **sweets:** cake: density 0.415 g/ml (FAO row 305) × slice height 3.5 cm (ASSUMPTION) = 1.45; cookies (thin) ≈ 0.5–0.9 → **1.2**, uncertainty 0.40.
- **nuts:** 0.566 g/ml (USDA) / 0.63 (FAO) × a 1.2–2.5 cm layer (ASSUMPTION) = 0.7–1.4 → **1.0**, uncertainty 0.40.
- **cheese_butter:** a cheese slice: density ~1.1 (ASSUMPTION) × 0.2–0.3 cm = **0.25**, uncertainty 0.40 (SR 170845 mozzarella: 6 slices = 170 g, i.e. ~28 g/slice; no dimensions). Spread butter: 0.911 g/ml (FAO row 208) × 0.15 cm (ASSUMPTION) ≈ 0.14.
- **sauce:** density 1.10 g/ml (USDA: 260 g/cup) × a 0.4 cm layer (ASSUMPTION) = 0.44 → **0.45**, uncertainty 0.50.
- **other:** 1.0, uncertainty 0.50 (ASSUMPTION).

## 4. Reliability notes and suggestions

1. **The breaded cutlet is the least documented high-calorie item** (the USDA "coated pork chop" proxy). A check sketch from assumed proportions (ASSUMPTION, not a source): ~83 g raw pork loin (1 pound for 6 cutlets per polishyourkitchen.com) + ~18 g breadcrumbs and ~8 g egg + ~6 g fat → about 100 g of finished cutlet at ~300 kcal/100 g. The real value for your cutlets may be higher than 252 kcal; best to compute it from your own recipe.
2. **Fries, cutlets, sauces and soups:** the spread comes from the cooking method (oven fries 158 kcal vs fast food 312). If you mostly eat one version, use that entry.
3. **USDA values ≠ Polish tables:** USDA kcal are Atwater; in NIZP-PZH the energy is additionally corrected for fiber; pasta/rice/potatoes in the Polish tables may be a few % lower/higher. The difference is smaller than the portion uncertainty.
4. **g_cm2 is worth calibrating** on 3–4 weighed meals (boxed pizza, bread slices, a pasta portion); the biggest uncertainty is in piles (pasta, rice, salad, fries, vegetables, nuts).
5. Pizza and bread have strong geometry/mass data; sausage and potatoes — medium (USDA geometry, but many ways of serving); the remaining piles — assumptions.

## 5. Sources (URLs)

Nutrition data:
- USDA FoodData Central, SR Legacy (04/2018), CSV: https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip (download page: https://fdc.nal.usda.gov/download-datasets)
- USDA FoodData Central, FNDDS / Survey (10/2022), CSV: https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_survey_food_csv_2022-10-28.zip
- USDA FoodData Central API (check of a few values): https://api.nal.usda.gov/fdc/v1/foods/search (DEMO_KEY, request limit exhausted — the CSV files were used after that)
- NIZP-PZH database (license only, not available): https://www.pzh.gov.pl/uslugi/tabele-wartosci-odzywczej-produktow/baza-danych-wersja-pelna/ ; cover/description: https://www.pzh.gov.pl/wp-content/uploads/2021/03/TABELE-WARTOSCI-ODZYWCZEJ_OPIS_OKLADKA_WERSJA-PELNA_26032021.pdf
- Dr. Oetker Ristorante Pizza Margherita label (CZ): https://www.rohlik.cz/en-CZ/1458535-dr-oetker-ristorante-pizza-margherita (295 g, ⌀24.5 cm, 253 kcal/100 g, 10 P, 11 F, 27 C)
- Biedronka zapiekanka with mushrooms and cheese (user database, weak): https://kalkulatorkalorii.net/kalkulator-kalorii/11931-100-zapiekanka-z-pieczarkami-i-serem-z-biedronki

Densities:
- FAO/INFOODS Density Database Version 2.0 (2012): page https://www.fao.org/infoods/infoods/tables-and-databases/faoinfoods-databases ; Excel https://www.fao.org/fileadmin/templates/food_composition/documents/density_DB_v2_0_final-1__1_.xlsx ; PDF https://www.fao.org/fileadmin/templates/food_composition/documents/density_DB_v2_0_01.pdf ; record https://openknowledge.fao.org/handle/20.500.14283/ap815e

Thicknesses, dimensions, masses:
- Pizza 31 cm, 366 g: https://www.scattidigusto.it/2023/10/17/il-giusto-peso-della-pizza
- Kotlet schabowy, pounded to ¼ inch: https://www.whollytasteful.com/wprm_print/kotlet-schabowy-polish-breaded-pork-chops ; https://polishyourkitchen.com/polish-fried-pork-cutlets
- Dan Cake toast bread (slicing thickness ~10 mm): https://webshop.chefsculinar.pl/en/food/cakes-baked-goods-and-sweets/baked-goods/dan-cake-dc-whole-grain-toast-bread-500g-500-g-pk-60076328
- Slice size and 12–13 mm thickness (shop blog, weak): https://instacuppastore.com/blogs/main-page/bread-size-for-sandwich-maker
- Zapiekanka (half a baguette, up to 50 cm, mushrooms, cheese, ketchup): https://en.wikipedia.org/wiki/Zapiekanka

## 6. Classes added on 2026-10-13 (burger, hot_dog, burrito, dumplings, drink split)

Read from the same FNDDS CSV (`FoodData_Central_survey_food_csv_2022-10-28`, `food_nutrient.csv`; in this file
`nutrient_id` is the nutrient number: 208 kcal, 203 protein, 204 fat, 205 carbohydrate). Values per 100 g.

| Class | kcal | protein | fat | carbs | Source | Confidence |
|---|---|---|---|---|---|---|
| burger | 292 | 16.9 | 16.4 | 18.0 | Mean of FNDDS 2342334 "Cheeseburger, from fast food, 1 small patty" (300/16.47/14.87/23.92), 2342342 "… 1 medium patty" (297/17.91/16.21/18.68), 2342344 "Whopper with cheese (Burger King)" (268/13.69/15.80/17.73), 2342352 "Double cheeseburger, on white bun, 2 medium patties" (301/19.69/18.91/11.77) | M |
| hot_dog | 296 | 10.9 | 17.4 | 23.7 | FNDDS 2342501 "Hot dog sandwich, NFS, on white bun" (= 2342505 beef). The sausage alone, FNDDS 2341575 "Hot dog, NFS", is 310/11.7/28.0/2.89 | H |
| burrito | 219 | 11.2 | 8.6 | 23.9 | FNDDS 2344018 "Burrito, NFS" | M |
| dumplings | 195 | 5.3 | 6.1 | 29.6 | FNDDS 2344204 "Pierogi". For comparison: 2344189 "Wonton, dumpling or pot sticker, fried" 192/8.76/11.13/14.05; 2344192 "… steamed" 113/6.9/4.6/11.07 | H for pierogi, M for the class |
| drink (juice, soda, wine) | 53 | 0.2 | 0.2 | 9.0 | **ASSUMED mix** 50% juice (mean of FNDDS 2344681 "Orange juice, 100%, NFS" 47 and 2344814 "Apple juice, 100%" 48), 30% FNDDS 2346111 "Soft drink, cola" (42), 20% wine (mean of 2346263 red 85 and 2346264 white 82) | L |
| coffee_tea | 17 | 0.8 | 0.4 | 2.6 | **ASSUMED recipe**: 80% FNDDS 2345935 "Coffee, brewed" / 2346058 "Tea, hot, leaf, black" (1 kcal), 20% FNDDS 2340763 "Milk, reduced fat (2%)" (50/3.36/1.90/4.90), 1 tsp sugar (4 g) per 250 ml mug. Black coffee or tea alone = 1 kcal | L |
| milk_drink | 86 | 3.4 | 4.3 | 8.6 | **ASSUMED** 50/50: milk (mean of FNDDS 2340762 "Milk, whole" 61/3.27/3.20/4.63 and 2340763 2% 50/3.36/1.90/4.90) and milkshake (mean of 2340902 / 2340903 "Milk shake, home recipe" 120 and 113 kcal) | L |

g_cm2 (all **ASSUMED** from typical portion ÷ area seen from above): burger 2.0 (fast-food burgers 120–270 g on
~70–110 cm²), hot_dog 1.6 (~110 g on ~70 cm²), burrito 2.3 (~230 g on ~100 cm²), dumplings 1.4 (one pieróg ~33 g
on ~24 cm²), coffee_tea 5.0 (250 ml mug, ~50 cm² opening), milk_drink 6.0 (250 ml glass, ~40 cm²).
