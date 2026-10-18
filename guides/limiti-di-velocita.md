# Limiti di velocità per veicolo e tipo di strada

Velocità massime in km/h, salvo diversa segnalazione.
I valori vengono dalle affermazioni vero/falso di `data/quiz.json`.
Quelli che il quiz non copre sono presi dal Codice della Strada (vedi [Fonti](#fonti)).

**Legenda**

- ☀️ condizioni normali
- 🌧️ precipitazioni atmosferiche (pioggia, grandine, …)
- 🌫️ nebbia fitta con visibilità inferiore a 100 m (possono essere imposti limiti temporanei)
- 🪧 solo con apposito segnale, nei tratti con particolari caratteristiche
- 🚫 circolazione vietata su questa strada

| Veicolo | Centro abitato | Extraurbana secondaria | Extraurbana principale | Autostrada |
| :--- | ---: | ---: | ---: | ---: |
| Autovettura<br>Motociclo<br>Autoveicolo fino a 3,5 t (autocarro, autocaravan)<br>Autovettura con carrello appendice | ☀️ 50<br>🪧 70 | 90 | ☀️ 110<br>🌧️ 90<br>🌫️ ≤ 50 | ☀️ 130<br>🌧️ 110<br>🌫️ ≤ 50<br>🪧 150 |
| Autovettura con rimorchio (caravan, imbarcazioni, cavalli, motocicli)<br>Autotreno | 50 | 70 | 70 | 80 |
| Neopatentato (patente da meno di 3 anni) | 50 | 90 | 90 | 100 |
| Quadriciclo non leggero | 50 | 80 | 🚫 | 🚫 |
| Ciclomotore<br>Quadriciclo leggero | 45 | 45 | 🚫 | 🚫 |
| Macchina agricola / operatrice gommata | 40 | 40 | 🚫 | 🚫 |

## Note e trabocchetti dalle domande

- Il quadriciclo leggero è equiparato al ciclomotore: massimo 45 km/h, anche modificando il motore (18577).
  Il limite di 80 km/h fuori dai centri abitati vale per il quadriciclo **non** leggero.
- Il neopatentato ha limiti ridotti solo su autostrade (100) ed extraurbane principali (90). Altrove valgono i limiti normali.
- I valori 🌧️, 🌫️ e 🪧 della prima riga sono chiesti per l'autovettura, ma il quiz li ripete anche come regole generali,
  senza indicare il veicolo (22397, 22402–22404, 22454): per questo valgono per tutta la riga.
- 150 km/h **non** è mai un limite generale. Vale solo con apposito segnale, su alcuni tratti di autostrada.
  "Su qualsiasi autostrada 150 km/h" è **falso**.
- Sulle extraurbane principali non esiste il limite di 130 km/h, nemmeno nei tratti con particolari caratteristiche.
- Il limite non si può mai superare: né di notte con gli abbaglianti, né in discesa, né per sorpassare in città, né con veicoli ad elevate prestazioni.
- Non esiste un limite di 170 km/h sulle autostrade a quattro corsie, e nella corsia di sorpasso non c'è un tetto di 110 km/h.
- Con i pneumatici invernali non ci sono limiti di velocità inferiori a quelli ordinari.
- Le autovetture che non raggiungono in piano gli 80 km/h non possono circolare su autostrade ed extraurbane principali.
- La luce gialla lampeggiante non alza il limite delle macchine agricole e operatrici.
- Il limite di 50 km/h in città è "ordinario", non "sempre": con apposito segnale può salire a 70.
- Il limite urbano non vale fino a 1 km dopo l'uscita dal paese.
- I limiti su autostrade e strade extraurbane non sono uguali in tutti gli stati d'Europa.
- Superare il limite di oltre 10 km/h fa perdere punti sulla patente. Di oltre 40 km/h comporta la sospensione della patente.

## Fonti

Dal Codice della Strada, per le celle che il quiz non copre:

- **Centro abitato, 50 km/h**: limite generale per tutti i veicoli (art. 142, comma 1; nel quiz anche 22399).
  Vale per autoveicolo fino a 3,5 t, carrello appendice, rimorchio, autotreno, quadriciclo non leggero e neopatentato.
- **Autotreno in autostrada, 80 km/h**: art. 142, comma 3 ("70 km/h fuori dei centri abitati; 80 km/h sulle autostrade").
- **Neopatentato su extraurbana secondaria, 90 km/h**: l'art. 117 limita solo autostrade ed extraurbane principali.
- **🚫 su autostrade ed extraurbane principali**: art. 175, comma 2.
  Vietati ciclomotori (quindi anche i quadricicli leggeri), "altri motoveicoli di massa a vuoto fino a 400 kg o di massa complessiva fino a 1300 kg" (i quadricicli non leggeri), macchine agricole e macchine operatrici.

Riferimenti: Codice della Strada (D.Lgs. 30 aprile 1992, n. 285), artt. 117, 142 e 175.

## ID delle domande di riferimento

Autovettura: 22328–22331, 22336–22339, 22342–22346, 22402–22405, 22409, 22454
Motociclo: 22335, 22368, 22371, 22374, 22377, 22381, 22383, 22416, 22418, 22426
Fino a 3,5 t: 22332–22334, 22349–22351, 22369, 22378, 22411, 22413, 22414, 22421–22423, 22429
Carrello appendice: 22366, 22372, 22380, 22417, 22419, 22430
Rimorchio: 22367, 22370, 22373, 22375, 22376, 22379, 22382, 22410, 22420, 22428, 22458, 22459, 22471
Autotreno: 22412, 22423
Quadriciclo: 18577, 22341, 22347, 22407, 22425
Ciclomotore: 18553, 22340, 22400, 22424, 23861
Macchine agricole / operatrici: 22353–22356, 22401, 22472
Neopatentato: 22357, 22358, 22364, 22365
Note: 22465–22470, 22474, 23546, 22680, 25255, 23853, 22456, 24620, 24655
