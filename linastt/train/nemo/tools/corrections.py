_corrections_caracteres_speciaux_fr = [(re.compile('%s' % x[0]), '%s' % x[1])
                  for x in [
                    (" ", " "),
                    ("а","a"),
                    ("â","â"),
                    ("à","à"),
                    ("á","a"),
                    ("ã","à"),
                    ("ä","a"),
                    ("å","a"),
                    ("ā","a"),
                    ("ă","a"),
                    ("ǎ","a"),
                    ("Å","A"),
                    ("е","e"),
                    ("ê","ê"),
                    ("é","é"),
                    ("è","è"),
                    ("ē","e"),
                    ("ĕ","e"),
                    ("ė","e"),
                    ("ę","e"),
                    ("ě","e"),
                    ("ё","e"),
                    ("ϊ","ï"),
                    ("ΐ","ï"),
                    ("ĩ","i"),
                    ("ī","i"),
                    ("ĭ","i"),
                    ("į","i"),
                    ("į","i"),
                    ("î","î"),
                    ("ı","i"),
                    ("í","i"),
                    ("ô","ô"),
                    ("ό","ο"),
                    ("ö","o"),
                    ("ó","o"),
                    ("ǒ","o"),
                    ("ō","o"),
                    ("ő","o"),
                    ("ò","o"),
                    ("ø","o"),
                    ("Ø","O"),
                    ("Ö","O"),
                    ("û","û"),
                    ("ǔ","u"),
                    ("ǜ","u"),
                    ("ü","u"),
                    ("ύ","u"),
                    ("ū","u"),
                    ("ú","u"),
                    ("ŷ","y"),
                    ("ý","y"),
                    ("ÿ","y"),
                    ("ć","c"),
                    ("č","c"),
                    ("ƒ","f"),
                    ("ĝ","g"),
                    ("ğ","g"),
                    ("ġ","g"),
                    ("ĥ","h"),
                    ("ķ","k"),
                    ("ł","l"),
                    ("ń","n"),
                    ("ņ","n"),
                    ("ň","n"),
                    ("ñ","n"),
                    ("ř","r"),
                    ("ś","s"),
                    ("ş","s"),
                    ("š","s"),
                    ("ș","s"),
                    ("ß","ss"),
                    ("ţ","t"),
                    ("ț","t"),
                    ("ť","t"),
                    ("ŵ","w"),
                    ("ź","z"),
                    ("ż","z"),
                    ("ž","z"),
                    ("ð","d"),
                    ("þ","z"), # utilisée pour transcrire le son d'une consonne fricative dentale sourde (comme le « th » de « thick » en anglais moderne)
                    ("Ã","a"),
                    # ('À','À'),
                    # ('É','É'),
                    # ('È','È'),
                    # ('Â','Â'),
                    # ('Ê','Ê'),
                    # ('Ç','Ç'),
                    # ('Ù','Ù'),
                    # ('Û','Û'),
                    # ('Î','Î'),
                    ("×", " fois "),
                    ("÷", " divisé par "),
                    ('ａ', 'a'), ('ｂ', 'b'), ('ｃ', 'c'), ('ｄ', 'd'), ('ｅ', 'e'), ('ｆ', 'f'), ('ｇ', 'g'), ('ｈ', 'h'), ('ｉ', 'i'), ('ｊ', 'j'), ('ｋ', 'k'), ('ｌ', 'l'), ('ｍ', 'm'), ('ｎ', 'n'), ('ｏ', 'o'), ('ｐ', 'p'), ('ｑ', 'q'), ('ｒ', 'r'), ('ｓ', 's'), ('ｔ', 't'), ('ｕ', 'u'), ('ｖ', 'v'), ('ｗ', 'w'), ('ｘ', 'x'), ('ｙ', 'y'), ('ｚ', 'z'),
                    ("α", " alpha "),
                    ("β", " beta "),
                    ("γ", " gamma "),
                    ("δ", " delta "),
                    ("ε", " epsilon "),
                    ("ζ", " zeta "),
                    ("η", " eta "),
                    ("θ", " theta "),
                    ("ι", " iota "),
                    ("κ", " kappa "),
                    ("λ", " lambda "),
                    ("ν", " nu "),
                    ("ξ", " xi "),
                    ("ο", " omicron "),
                    ("π", " pi "),
                    ("ρ", " rho "),
                    ("σ", " sigma "),
                    ("τ", " tau "),
                    ("υ", " upsilon "),
                    ("φ", " phi "),
                    ("χ", " chi "),
                    ("ψ", " psi "),
                    ("ω", " omega "),
                    ("Α", " alpha "),
                    ("Β", " beta "),
                    ("Γ", " gamma "),
                    ("Δ", " delta "),
                    ("Ε", " epsilon "),
                    ("Ζ", " zeta "),
                    ("Η", " eta "),
                    ("Θ", " theta "),
                    ("Ι", " iota "),
                    ("Κ", " kappa "),
                    ("Λ", " lambda "),
                    ("Μ", " micro "),
                    ("Ν", " nu "),
                    ("Ξ", " xi "),
                    ("Ο", " omicron "),
                    ("Π", " pi "),
                    ("Ρ", " rho "),
                    ("Σ", " sigma "),
                    ("Τ", " tau "),
                    ("Υ", " upsilon "),
                    ("Φ", " phi "),
                    ("Χ", " chi "),
                    ("Ψ", " psi "),
                    ("Ω", " omega "),
                    ("♠", " pique "),
                    ("♣", " trèfle "),
                    ("♥", " coeur "),
                    ("♦", " carreau "),
                    ("♜", " tour "),
                    ("♞", " cavalier "),
                    ("♝", " fou "),
                    ("♛", " reine "),
                    ("♚", " roi "),
                    ("♟", " pion "),
                    ("♔", " roi "),
                    ("♕", " reine "),
                    ("♖", " tour "),
                    ("♗", " fou "),
                    ("♘", " cavalier "),
                    ("♙", " pion "),
                    ("♭", " bémol "),
                    ("♮", " dièse "),
                    ("♂", " mâle "),
                    ("♀", " femelle "),
                    ("☿", " mercure "),
                    ("∈", " appartient à "),
                    ("∉", " n'appartient pas à "),
                    ("∅", " vide "),
                    ("∪", " union "),
                    ("∩", " intersection "),
                    ("∧", " et "),
                    ("∨", " ou "),
                    ("∀", " pour tout "),
                    ("∃", " il existe "),
                    ("∂", " dérivée de "),
                    ("∇", " gradient de "),
                    ("√", " racine carrée de "),
                    ("∫", " intégrale de "),
                    ("∬", " double intégrale de "),
                    ("∭", " triple intégrale de "),
                    ("∮", " intégrale de surface de "),
                    ("∯", " double intégrale de surface de "),
                    ("∰", " triple intégrale de surface de "),
                    ("∴", " donc "),
                    ("∵", " car "),
                    ("∼", " environ "),
                    ("≈", " estime "),
                    ("≠", " différent de "),
                    ("≡", " égal à "),
                    ("≤", " inférieur ou égal à "),
                    ("≥", " supérieur ou égal à "),
                    ("⊂", " est inclus dans "),
                    ("⊃", " contient "),
                    ("⊄", " n'est pas inclus dans "),
                    ("⊆", " est inclus dans ou égal à "),
                    ("⊇", " contient ou est égal à "),
                    ("⊕", " addition "),
                    ("⊗", " multiplication "),
                    ("⊥", " perpendiculaire à "),
                    ("∑", " somme de "),
                    ("∏", " produit de "),
                    ("∐", " somme directe de "),
                    ("⇒", " implique "),
                    ("⇔", " équivaut à "),
                    ("⇐", " est impliqué par "),
                    ("⇆", " est équivalent à "),
                    ("⇎", " est défini par "),
                    ("ℤ", " entiers "),
                    ("ℚ", " rationnels "),
                    ("ℝ", " réels "),
                    ("ℂ", " complexes "),
                    ("ℕ", " naturels "),
                    ("ℵ", " aleph "),
                    ("ℶ", " beth "),
                    ("ℷ", " gimel "),
                    ("ℸ", " daleth "),
                    ("ℹ", " information "),
                ]]