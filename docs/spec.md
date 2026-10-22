# Falasz v0.1 — specyfikacja języka

Status: **ZATWIERDZONA z poprawkami (2026-10-22)**. Sekcje oznaczone *[zamrożone]*
stanowią minimalne API v0.1 i zmieniają się tylko przez wpis w CHANGELOG.
Szczegóły zaprojektowane na podstawie poprawek właściciela (P6, P11, P12, P16) są
opisane w sekcji 12 jako N1–N6 — do potwierdzenia, ale gramatyka już je obejmuje.

Decyzje właściciela:
- `/` zawsze zwraca FLOAT; dzielenie przez zero to błąd czasu wykonania.
- Warunki `IF`/`WHILE` oraz `AND`/`OR`/`NOT` przyjmują wyłącznie BOOLEAN.
- Wbudowane konwersje `STR`, `INT`, `FLOAT`, `LEN`; literały list i map; indeksowanie.
- Zatwierdzone: P1–P5, P7–P10, P13–P15.
- P6: `IF`/`WHILE`/`FOR` **nie** tworzą zakresu; zakresy mają tylko funkcje i moduły.
- P11: jednoznaczny import lokalny przy konfliktach nazw (`IMPORT LOCAL`, `AS`).
- P12: jawny `EXPORT`; nic nie jest eksportowane automatycznie.
- P16: `INPUT()` należy do v0.1; `TRY/CATCH`, lambdy, metody list i interpolacja — nie.

---

## 1. Plik źródłowy

- Kodowanie UTF-8 (opcjonalny BOM jest pomijany). Niepoprawny UTF-8 → `SyntaxError`.
- Końce linii: `\n`, `\r\n` lub `\r` — wszystkie traktowane jako jeden NEWLINE
  (gwarancja identycznego zachowania na Linux i Windows).
- Rozszerzenie `.falasz`. Maksymalny rozmiar pliku źródłowego: 1 MiB (limit, sekcja 10).
- Komentarz: od `#` (poza literałem tekstowym) do końca linii.
- Wcięcia nie mają znaczenia składniowego.
- Instrukcje kończy NEWLINE. Puste linie są ignorowane.
  Wewnątrz nawiasów `( )`, `[ ]`, `{ }` znaki nowej linii są ignorowane,
  więc długie wyrażenia można łamać.

## 2. Leksyka *[zamrożone]*

### 2.1 Słowa kluczowe
Wielkość liter ma znaczenie; słowa kluczowe pisane są wyłącznie WIELKIMI literami (P1):

```
LET SAY IF ELSE WHILE FOR IN FUNC RETURN END BREAK CONTINUE
IMPORT LOCAL AS EXPORT
TRUE FALSE NULL AND OR NOT
```

`if`, `Let`, `local` itd. są zwykłymi identyfikatorami.

### 2.2 Nazwy wbudowane
`RANGE`, `STR`, `INT`, `FLOAT`, `LEN`, `INPUT` są nazwami funkcji wbudowanych
w zakresie wbudowanym (nad zakresem modułu). Nie są słowami kluczowymi, ale są
zastrzeżone: nie można ich zadeklarować ani przypisać (`LET STR = 1`,
`FUNC LEN()`, parametr `INPUT`, `IMPORT x AS RANGE`, zmienna `FOR STR IN …`) → `NameError`.

### 2.3 Identyfikatory
`[A-Za-z_][A-Za-z0-9_]*` — tylko ASCII. Wielkość liter ma znaczenie.

### 2.4 Literały
- INTEGER: `0` lub `[1-9][0-9]*` (bez zer wiodących, bez znaku — minus to operator).
  Precyzja nieograniczona.
- FLOAT: `[0-9]+ "." [0-9]+` (np. `3.5`, `0.25`). Brak notacji wykładniczej w v0.1.
  `1.` i `.5` → `SyntaxError`.
- STRING: w cudzysłowach `"..."`, jednoliniowy. Sekwencje: `\"` `\\` `\n` `\t`.
  Inna sekwencja `\x` lub niezamknięty literał → `SyntaxError`.
- `TRUE`, `FALSE`, `NULL`.

### 2.5 Operatory i interpunkcja
```
+ - * / % == != < > <= >= = ( ) [ ] { } , . :
```
Każdy inny znak poza literałem tekstowym i komentarzem → `SyntaxError`.

## 3. Gramatyka (EBNF) *[zamrożone]*

Notacja: `{ x }` = zero lub więcej, `[ x ]` = opcjonalne, `|` = alternatywa,
terminale w cudzysłowach, `NL` = jeden lub więcej NEWLINE.

```ebnf
program        = [ NL ] { statement NL } EOF ;

block          = [ NL ] { statement NL } ;          (* kończony przez END lub ELSE *)

statement      = import_stmt
               | export_stmt
               | let_stmt
               | func_stmt
               | if_stmt
               | while_stmt
               | for_stmt
               | say_stmt
               | return_stmt
               | "BREAK"
               | "CONTINUE"
               | assign_or_expr ;

import_stmt    = "IMPORT" [ "LOCAL" ] IDENT [ "AS" IDENT ] ;
export_stmt    = "EXPORT" IDENT { "," IDENT } ;
let_stmt       = "LET" IDENT "=" expression ;
func_stmt      = "FUNC" IDENT "(" [ IDENT { "," IDENT } ] ")" NL block "END" ;
if_stmt        = "IF" expression NL block [ "ELSE" ( NL block | if_stmt_noend ) ] "END" ;
if_stmt_noend  = "IF" expression NL block [ "ELSE" ( NL block | if_stmt_noend ) ] ;
while_stmt     = "WHILE" expression NL block "END" ;
for_stmt       = "FOR" IDENT "IN" expression NL block "END" ;
say_stmt       = "SAY" expression ;
return_stmt    = "RETURN" [ expression ] ;
assign_or_expr = expression [ "=" expression ] ;   (* lewa strona: patrz 3.1 *)

expression     = or_expr ;
or_expr        = and_expr { "OR" and_expr } ;
and_expr       = not_expr { "AND" not_expr } ;
not_expr       = "NOT" not_expr | comparison ;
comparison     = additive [ comp_op additive ] ;   (* bez łańcuchów *)
comp_op        = "==" | "!=" | "<" | ">" | "<=" | ">=" ;
additive       = multiplicative { ( "+" | "-" ) multiplicative } ;
multiplicative = unary { ( "*" | "/" | "%" ) unary } ;
unary          = "-" unary | postfix ;
postfix        = primary { call_suffix | index_suffix | member_suffix } ;
call_suffix    = "(" [ expression { "," expression } [ "," ] ] ")" ;
index_suffix   = "[" expression "]" ;
member_suffix  = "." IDENT ;
primary        = INTEGER | FLOAT | STRING | "TRUE" | "FALSE" | "NULL"
               | IDENT
               | "(" expression ")"
               | list_literal
               | map_literal ;
list_literal   = "[" [ expression { "," expression } [ "," ] ] "]" ;
map_literal    = "{" [ map_entry { "," map_entry } [ "," ] ] "}" ;
map_entry      = expression ":" expression ;
```

Uwagi:
- `ELSE IF cond` jest skrótem (P9) — cały łańcuch `IF … ELSE IF … ELSE … END`
  zamyka **jedno** `END`.
- `ELSE` musi rozpoczynać linię.
- `IMPORT` i `EXPORT` mogą wystąpić tylko na najwyższym poziomie pliku, poza
  jakimkolwiek blokiem (`IF`, `WHILE`, `FOR`, `FUNC`) → inaczej `SyntaxError`.

### 3.1 Cele przypisania
Lewa strona `=` musi być jednym z: `IDENT`, `postfix "[" expression "]"`.
Przypisanie do `module.name` → `NameError` („module members are read-only”);
do wywołania, literału lub innego wyrażenia → `SyntaxError`.

### 3.2 Instrukcja-wyrażenie
Samodzielne wyrażenie jako instrukcja jest dozwolone tylko, jeśli jest wywołaniem
funkcji (np. `files.write_text(p, s)`) (P8). `1 + 2` w osobnej linii → `SyntaxError`.

## 4. Priorytety operatorów *[zamrożone]*

Od najniższego do najwyższego:

| Poziom | Operatory | Łączność |
|---|---|---|
| 1 | `OR` | lewostronna |
| 2 | `AND` | lewostronna |
| 3 | `NOT` | prefiksowy |
| 4 | `==` `!=` `<` `>` `<=` `>=` | **brak** — `a < b < c` → `SyntaxError` |
| 5 | `+` `-` | lewostronna |
| 6 | `*` `/` `%` | lewostronna |
| 7 | `-` (unarny) | prefiksowy |
| 8 | wywołanie `f()`, indeks `x[i]`, członek `m.f` | lewostronna |

Przykłady: `NOT a == b` ≡ `NOT (a == b)`; `-2 * 3` ≡ `(-2) * 3`; `1 + 2 * 3` = `7`.

## 5. Typy i wartości *[zamrożone]*

| Typ | Przykład | Zmienny? | Reprezentacja w `SAY`/`STR` |
|---|---|---|---|
| INTEGER | `42` | nie | `42` |
| FLOAT | `3.5` | nie | najkrótsza dokładna postać dziesiętna, zawsze z kropką, bez wykładnika: `2.0`, `0.1`, `100000000000000000000.0` |
| STRING | `"hi"` | nie | treść bez cudzysłowów: `hi` |
| BOOLEAN | `TRUE` | nie | `TRUE` / `FALSE` |
| NULL | `NULL` | nie | `NULL` |
| LIST | `[1, "a"]` | **tak** (referencja) | `[1, "a"]` (napisy w cudzysłowach, z escape’ami) |
| MAP | `{"a": 1}` | **tak** (referencja) | `{"a": 1}` (kolejność wstawiania) |
| FUNCTION | `greet` | nie | `<func greet>` (wbudowane: `<builtin LEN>`) |
| MODULE | `files` | nie | `<module files>` |

FUNCTION i MODULE są typami wewnętrznymi (wartości pierwszej klasy, ale nie mają
literałów). Spec pierwotna wymienia 7 typów użytkowych — te dwa są dodatkowe.

Klucze MAP: tylko INTEGER, STRING, BOOLEAN. Inny typ klucza → `TypeError`.
Powtórzony klucz w literale (`{"a": 1, "a": 2}`) — wygrywa ostatnia wartość,
pozycja w kolejności pochodzi z pierwszego wystąpienia.

Struktury cykliczne (lista zawierająca samą siebie po `xs[0] = xs`) są dozwolone.
`STR`/`SAY` wypisują powtórzone odwołanie jako `[...]` lub `{...}`; porównanie `==`
dwóch struktur cyklicznych jest dobrze określone (nie zawiesza się).
`-0.0` wypisywane jest jako `-0.0` i równe `0.0`.
`TRUE` i `1` są **różnymi** kluczami (w odróżnieniu od Pythona).

### 5.1 Semantyka operatorów

Brak niejawnej konwersji między liczbami a tekstem. Mieszanie INTEGER i FLOAT
w arytmetyce **jest** dozwolone (wynik FLOAT) — to promocja liczbowa (P2).
Każda niewymieniona kombinacja typów → `TypeError`.

| Operacja | Typy | Wynik |
|---|---|---|
| `a + b` | INT, INT | INT |
| | liczba, liczba (≥1 FLOAT) | FLOAT |
| | STRING, STRING | STRING (konkatenacja) |
| | LIST, LIST | nowa LIST (konkatenacja) |
| `a - b`, `a * b` | liczby | INT jeśli oba INT, inaczej FLOAT |
| `a / b` | liczby | **zawsze FLOAT**; `b == 0` → `ZeroDivisionError` |
| `a % b` | liczby | znak wyniku = znak dzielnika (`-7 % 3` = `2`) (P4); `b == 0` → `ZeroDivisionError` |
| `-a` | liczba | ten sam typ |
| `==`, `!=` | dowolne | patrz 5.2; nigdy błąd |
| `<` `>` `<=` `>=` | liczba, liczba | BOOLEAN |
| | STRING, STRING | BOOLEAN, porządek punktów kodowych Unicode |
| `AND`, `OR` | BOOLEAN | skracane; lewy i (jeśli obliczany) prawy operand muszą być BOOLEAN |
| `NOT a` | BOOLEAN | BOOLEAN |

BOOLEAN nie jest liczbą: `TRUE + 1` → `TypeError`.
Operacja FLOAT dająca nieskończoność lub NaN (także konwersja zbyt dużego INTEGER
na FLOAT) → `ArithmeticError`.

### 5.2 Równość (P3)
- INTEGER i FLOAT porównywane liczbowo (dokładnie): `1 == 1.0` → `TRUE`.
- BOOLEAN nie równa się liczbie: `TRUE == 1` → `FALSE`.
- LIST/MAP: równość strukturalna (rekurencyjna).
- FUNCTION/MODULE: tożsamość.
- Różne typy (poza parą liczbową) → `FALSE`.

### 5.3 Warunki
`IF`, `WHILE` (i każdy element `ELSE IF`) wymagają BOOLEAN; inna wartość → `TypeError`.

### 5.4 Indeksowanie
- `list[i]`: `i` musi być INTEGER, `0 <= i < LEN(list)`; ujemne i poza zakresem → `IndexError` (P5).
- `string[i]`: jak wyżej, zwraca jednoznakowy STRING (znak = punkt kodowy).
- `map[k]`: brak klucza → `KeyError`.
- `list[i] = v`: zakres jak wyżej (nie powiększa listy).
- `map[k] = v`: wstawia lub nadpisuje.
- STRING jest niezmienny: `s[0] = "x"` → `TypeError`.

### 5.5 Iteracja `FOR x IN expr`
- LIST: elementy po kolei. Iteracja odbywa się po **migawce** z chwili rozpoczęcia
  pętli — modyfikacje listy w trakcie nie zmieniają przebiegu.
- STRING: kolejne znaki.
- MAP: klucze w kolejności wstawiania (migawka).
- Inny typ → `TypeError`.
- Zmienna pętli należy do bieżącego zakresu (funkcji lub modułu) — patrz 6.2.

## 6. Zmienne i zakresy *[zamrożone]* (P6)

### 6.1 Zakresy
Istnieją dokładnie trzy rodzaje zakresów:
1. **wbudowany** — nazwy z 2.2, tylko do odczytu;
2. **modułu** — najwyższy poziom każdego pliku `.falasz` (także głównego skryptu);
3. **funkcji** — tworzony przy każdym wywołaniu; zawiera parametry i deklaracje ciała.

`IF`, `ELSE`, `WHILE` i `FOR` **nie tworzą** zakresu: deklaracje w ich ciałach
należą do najbliższej otaczającej funkcji lub do modułu i są widoczne po zakończeniu bloku.

### 6.2 Deklaracje
Deklaracją jest: `LET x`, `FUNC x`, parametr `x`, `IMPORT … x` / `IMPORT … AS x`,
zmienna pętli `FOR x`.

- W jednym zakresie dana nazwa może być zadeklarowana **tylko raz w tekście programu**
  (sprawdzane statycznie). Druga deklaracja tej samej nazwy w tym samym zakresie —
  także w innej gałęzi `IF`/`ELSE` — → `NameError`.
- **Wyjątek:** kilka pętli `FOR` w tym samym zakresie może używać tej samej zmiennej
  pętli, o ile nazwa nie jest zadeklarowana w tym zakresie w inny sposób.
- Ponowne **wykonanie** tej samej deklaracji (np. `LET` w ciele pętli) nie jest błędem
  — przypisuje nową wartość.
- Zmienna pętli `FOR` po zakończeniu pętli zachowuje ostatnią przypisaną wartość.
- Przesłanianie jest możliwe tylko między zakresami: funkcja może zadeklarować nazwę
  istniejącą w module lub w funkcji otaczającej.

### 6.3 Odczyt i przypisanie
- Nazwa jest rozwiązywana **statycznie** (leksykalnie): walidator ustala, w którym
  zakresie — bieżącym, otaczającym lub wbudowanym — znajduje się jej deklaracja.
  W czasie wykonania odczyt dotyczy tylko tego zakresu; nigdy nie „przecieka”
  do zakresu zewnętrznego.
- `x = e` przypisuje do najbliższej widocznej deklaracji `x` (także w funkcji
  otaczającej — domknięcia). Brak deklaracji → `NameError`.
- **Kolejność statyczna:** w obrębie jednego zakresu nazwa musi być zadeklarowana
  w tekście **przed** pierwszym użyciem (odczytem lub przypisaniem) → inaczej `NameError`.
  Wyrażenie inicjujące należy do tekstu przed deklaracją: w `LET x = x + 1` prawe `x`
  jest użyte przed deklaracją. Jeśli `x` jest zadeklarowane gdziekolwiek w bieżącym
  zakresie, użycie odnosi się do tej deklaracji, a nie do zakresu zewnętrznego.
  Wyjątek (P7): ciało funkcji widzi wszystkie nazwy zakresów otaczających,
  także zadeklarowane w tekście później.
- **Zmienna powstaje w chwili wykonania deklaracji (N2):** `LET` tworzy zmienną
  dopiero po obliczeniu wyrażenia; `FUNC` — w chwili wykonania instrukcji; zmienna
  `FOR` — przy pierwszym przypisaniu elementu; `IMPORT` — w chwili importu. Jeśli
  deklaracja nie została wykonana (np. `LET` w gałęzi `IF`, która się nie wykonała;
  pętla `FOR` bez iteracji), zmienna **nie istnieje**: zarówno odczyt, jak i
  przypisanie `x = e` → `NameError` w czasie wykonania
  („variable 'x' does not exist: its declaration was not executed”).

### 6.4 Funkcje i domknięcia
- `FUNC f(...)` wiąże `f` w chwili wykonania instrukcji — **brak hoistingu** (P7).
- Domknięcia przechwytują zakres (nie wartości). Ponieważ pętle nie tworzą zakresu,
  wszystkie funkcje utworzone w jednej pętli widzą tę samą zmienną.

## 7. Funkcje *[zamrożone]*

- Parametry są zmiennymi zakresu funkcji. Duplikat nazwy parametru → `SyntaxError`.
- Liczba argumentów musi się zgadzać dokładnie → `ArityError`.
- Argumenty obliczane od lewej do prawej, przekazywane przez wartość
  (LIST/MAP jako referencja do tego samego obiektu).
- `RETURN` bez wyrażenia lub koniec ciała → `NULL`.
- Funkcje są wartościami: można je przypisać, przekazać i zwrócić.
- Rekurencja dozwolona do limitu głębokości (sekcja 10) → `RecursionLimitError`.

### 7.1 Walidacja statyczna
Wykonywana przez `falasz check` oraz przed każdym `falasz run`, dla programu
i wszystkich przechodnio importowanych modułów lokalnych.

Etap składniowy (parser):
- `RETURN` poza ciałem funkcji → `SyntaxError`.
- `BREAK`/`CONTINUE` poza pętlą (także wewnątrz funkcji zagnieżdżonej w pętli) → `SyntaxError`.
- `IMPORT`/`EXPORT` poza najwyższym poziomem pliku → `SyntaxError`.
- Duplikat parametru, łańcuch porównań, instrukcja-wyrażenie bez wywołania,
  niepoprawny cel przypisania → `SyntaxError`.

Etap nazw (walidator):
- reguły deklaracji i kolejności z sekcji 6 → `NameError`;
- deklaracja lub przypisanie nazwy wbudowanej → `NameError`;
- `EXPORT` nazwy niezadeklarowanej w zakresie modułu, podwójny `EXPORT` tej samej nazwy → `NameError`;
- `m.x`, gdy `m` jest nazwą z `IMPORT`, a moduł nie eksportuje `x` → `NameError`;
- moduł nie istnieje, cykl importów → `ImportError`.

## 8. Biblioteka wbudowana *[zamrożone]*

| Nazwa | Sygnatura | Opis |
|---|---|---|
| `SAY` | instrukcja `SAY e` | wypisuje `STR(e)` + `\n` na stdout (zawsze `\n`, także na Windows) |
| `RANGE` | `RANGE(start, stop)`, `RANGE(start, stop, step)` | LIST INTEGER, `stop` wyłączny; argumenty INTEGER; `step == 0` → `ValueError`; długość > limitu → `LimitError` (P13) |
| `STR` | `STR(x)` | reprezentacja jak w tabeli z sekcji 5 |
| `INT` | `INT(x)` | INT→INT; FLOAT→obcięcie w stronę zera; STRING w postaci `-?[0-9]+` → INT, inny tekst (także ze spacjami) → `ValueError`; inne typy → `TypeError` |
| `FLOAT` | `FLOAT(x)` | INT/FLOAT→FLOAT; STRING w postaci `-?[0-9]+(\.[0-9]+)?` → FLOAT, inny tekst → `ValueError`; wynik poza zakresem FLOAT → `ArithmeticError`; inne typy → `TypeError` |
| `LEN` | `LEN(x)` | STRING (punkty kodowe), LIST, MAP → INT; inne → `TypeError` |
| `INPUT` | `INPUT()`, `INPUT(prompt)` | patrz 8.1 |

### 8.1 `INPUT` (P16)
- `prompt` (opcjonalny) musi być STRING → inaczej `TypeError`. Jest wypisywany na
  stdout **bez** znaku nowej linii, po czym stdout jest opróżniany (flush).
- Czyta jedną linię ze standardowego wejścia jako UTF-8 (niezależnie od platformy
  i strony kodowej konsoli Windows). Usuwa końcowe `\n` lub `\r\n`; nie usuwa spacji.
- Zwraca STRING (pusta linia → `""`). Koniec wejścia (EOF) → `NULL`.
- Niepoprawny UTF-8 na wejściu → `ValueError`.
- Źródło wejścia jest wstrzykiwane do interpretera (testy podają tekst wprost).
- `falasz check` nigdy nie wywołuje `INPUT`.

## 9. Moduły i biblioteka standardowa *[zamrożone]*

### 9.1 Import (P11)

| Forma | Znaczenie | Wiąże nazwę |
|---|---|---|
| `IMPORT name` | moduł standardowy `name`; jeśli nie istnieje — lokalny plik `name.falasz` | `name` |
| `IMPORT LOCAL name` | **zawsze** lokalny plik `name.falasz`, nigdy moduł standardowy | `name` |
| `IMPORT name AS alias` / `IMPORT LOCAL name AS alias` | jak wyżej | `alias` |

- Moduły standardowe v0.1: `files`, `sensors`.
- Plik lokalny = `name.falasz` w **katalogu pliku importującego**. Brak importu
  podkatalogów ani ścieżek w v0.1.
- Rozwiązywanie konfliktów nazw: gdy obok skryptu istnieje `files.falasz`,
  `IMPORT files` zawsze oznacza moduł standardowy, a lokalny plik uzyskuje się przez
  `IMPORT LOCAL files AS my_files`. Obie formy mogą występować w jednym pliku,
  o ile wiążą różne nazwy.
- `falasz check` ostrzega (nie błąd), gdy `IMPORT name` wskazuje moduł standardowy,
  a obok istnieje lokalny `name.falasz` — sugeruje `IMPORT LOCAL`.
- Zalecenie: moduły lokalne importuj przez `IMPORT LOCAL`, aby przyszłe moduły
  standardowe o tej samej nazwie nie zmieniły znaczenia programu.
- Nazwa wiązana przez `IMPORT` jest deklaracją w zakresie modułu (sekcja 6.2):
  kolizja z inną deklaracją → `NameError`.
- Brak pliku → `ImportError` z listą sprawdzonych ścieżek.
- Moduł wykonywany jest raz na uruchomienie (cache po ścieżce kanonicznej);
  kolejne importy — także pod innym aliasem — zwracają ten sam obiekt.
- Cykl importów → `ImportError` z łańcuchem, np. `a.falasz -> b.falasz -> a.falasz`,
  zgłoszony przy `IMPORT` zamykającym cykl.
- Nigdy nie jest importowany kod Python.

### 9.2 Eksport (P12)
- `EXPORT name1, name2` — tylko na najwyższym poziomie pliku; może wystąpić
  wielokrotnie i w dowolnym miejscu pliku (także przed deklaracją).
- Każda eksportowana nazwa musi być zadeklarowana w zakresie modułu (`LET`, `FUNC`,
  `IMPORT`, zmienna `FOR` najwyższego poziomu) → inaczej `NameError`.
- Ta sama nazwa eksportowana dwukrotnie → `NameError`.
- **Nazwy nieeksportowane są prywatne.** `m.x` dla nieeksportowanego `x` → `NameError`
  („module 'm' does not export 'x'”).
- `m.x` odczytuje **bieżącą** wartość zmiennej modułu (wiązanie na żywo); z zewnątrz
  tylko do odczytu. Odczyt eksportowanej zmiennej, która nie istnieje (N2) → `NameError`.
- `EXPORT` w głównym skrypcie jest dozwolony (plik może być zarówno skryptem, jak i modułem).

### 9.3 `files`
Eksportuje: `read_text`, `write_text`.
- `files.read_text(path)` → STRING; `files.write_text(path, content)` → NULL
  (tworzy lub nadpisuje; nie tworzy katalogów).
- Argumenty muszą być STRING → inaczej `TypeError`.
- Ścieżki względne rozwiązywane względem **katalogu głównego skryptu** (pliku
  podanego do `falasz run`), niezależnie od bieżącego katalogu i od tego, który
  moduł wywołuje funkcję (P10). Ścieżki bezwzględne są dozwolone.
- Kodowanie UTF-8 przy odczycie i zapisie; zapis z `\n` bez translacji.
  Odczyt nie normalizuje końców linii.
- Błędy I/O (brak pliku, uprawnienia, niepoprawny UTF-8, przekroczenie limitu
  rozmiaru) → `FileError` ze ścieżką i przyczyną.
- `files` **nie jest piaskownicą** — ma uprawnienia procesu.

### 9.4 `sensors`
Eksportuje: `available`, `read`.
- `sensors.available()` → LIST STRING (posortowane nazwy).
- `sensors.read(name)` → INTEGER, FLOAT, BOOLEAN lub STRING (zależnie od czujnika);
  nieznana nazwa → `SensorError`.
- Dostawca (provider) jest wstrzykiwany do interpretera:
  - domyślnie `null` — `available()` zwraca `[]`;
  - `mock` — wartości ze słownika (w testach) lub z pliku JSON:
    `falasz run --sensors-mock sensors.json prog.falasz`, gdzie plik to
    `{"temperature": 21.5, "door_open": false}`. Wartość może być też listą —
    kolejne `read` zwracają kolejne elementy, a po wyczerpaniu → `SensorError`.
- Brak obsługi rzeczywistych czujników w v0.1.

## 10. Limity zasobów *[zamrożone: nazwy i domyślne wartości]*

| Limit | Domyślnie | Błąd |
|---|---|---|
| Rozmiar pliku źródłowego | 1 MiB | `LimitError` |
| Głębokość zagnieżdżenia wyrażeń/bloków w parserze | 200 | `SyntaxError` |
| Głębokość wywołań funkcji | 500 | `RecursionLimitError` |
| Liczba kroków interpretera | bez limitu w CLI; konfigurowalna (`--max-steps N`) | `LimitError` |
| Długość wyniku `RANGE` | 10 000 000 | `LimitError` |
| Rozmiar pliku w `files.read_text` | 16 MiB | `FileError` |
| Głębokość zagnieżdżenia wartości przy `STR`, `SAY`, `==` | 500 | `LimitError` |
| Liczba cyfr przy konwersji INTEGER ↔ tekst (literał, `STR`, `INT`, `SAY`) | 4300 (limit Pythona) | `LimitError` |

Limity służą testom i niezaufanym danym; nie zastępują izolacji systemu operacyjnego.

## 11. Diagnostyka *[zamrożone]*

### 11.1 Format
```
<ścieżka>:<linia>:<kolumna>: <Kategoria>: <komunikat>
```
Linie i kolumny liczone od 1; kolumna w punktach kodowych. Ścieżka głównego skryptu
tak, jak podano w CLI; ścieżki modułów — względem katalogu głównego skryptu,
z separatorem `/` na każdej platformie.
Dla błędów czasu wykonania z wnętrza funkcji następuje ślad stosu (najgłębsze wywołanie ostatnie):

```
Traceback:
  main.falasz:12:5 in <main>
  lib.falasz:3:12 in divide
lib.falasz:3:12: ZeroDivisionError: division by zero
```

Komunikaty diagnostyczne są w języku angielskim (P14). Ostrzeżenia mają postać
`<ścieżka>:<linia>:<kolumna>: Warning: <komunikat>` i nie zmieniają kodu wyjścia.

Na co wskazuje lokalizacja błędu:
- operator dwuargumentowy (`+`, `/`, `<`, …) — token operatora;
- wywołanie / indeks — token `(` / `[`; dostęp do członka — token `.`;
- błąd zgłoszony wewnątrz funkcji wbudowanej lub standardowej (np. zły typ argumentu
  `INPUT(5)`, `FileError`) — token `(` tego wywołania;
- operand `AND`/`OR`/`NOT` lub warunek `IF`/`WHILE` niebędący BOOLEAN — początek tego operandu/warunku;
- deklaracja (`LET`, `FUNC`, parametr, zmienna `FOR`, nazwa/alias w `IMPORT`) — deklarowana nazwa;
- przypisanie/użycie nazwy, nazwa w `EXPORT` — ta nazwa;
- `RETURN`/`BREAK`/`CONTINUE`/`IMPORT`/`EXPORT` w złym miejscu, błąd rozwiązania
  importu (brak pliku, cykl) — słowo kluczowe `IMPORT`/odpowiednie słowo kluczowe;
- brak `END` — koniec pliku; niezamknięty tekst — otwierający `"`;
- błąd konwersji wartości na tekst w `SAY` (np. `LimitError`) — słowo kluczowe `SAY`;
- pozostałe błędy składni — pierwszy nieoczekiwany token.

### 11.2 Kategorie
`SyntaxError`, `NameError`, `TypeError`, `ValueError`, `ArityError`,
`ZeroDivisionError`, `ArithmeticError`, `IndexError`, `KeyError`, `ImportError`,
`FileError`, `SensorError`, `RecursionLimitError`, `LimitError`.

v0.1 nie ma przechwytywania błędów — każdy błąd kończy program.
Wewnętrzny błąd interpretera (bug) → `InternalError` z prośbą o zgłoszenie, nigdy
surowy traceback Pythona (chyba że `--debug`).

### 11.3 Kody wyjścia CLI (P15)
| Kod | Znaczenie |
|---|---|
| 0 | sukces |
| 1 | błąd czasu wykonania |
| 2 | błędne użycie CLI (argumenty, brak pliku wejściowego) |
| 3 | błąd składni / walidacji statycznej (w tym `ImportError` wykryty statycznie) |
| 70 | `InternalError` |

### 11.4 CLI
- `falasz run [--sensors-mock FILE] [--max-steps N] FILE` — walidacja całego programu
  (z modułami), następnie wykonanie.
- `falasz check FILE` — lexer + parser + walidacja statyczna pliku i wszystkich
  lokalnych modułów importowanych przechodnio; **nic nie wykonuje** (także modułów
  i `INPUT`). Wypisuje `OK` lub listę błędów: **pierwszy** błąd składni z każdego pliku
  (parser nie kontynuuje po błędzie, aby nie zgłaszać błędów pochodnych) oraz
  wszystkie błędy walidacji nazw z plików poprawnych składniowo.
- `falasz --version` → `falasz 0.1.0a0`.

## 12. Rejestr decyzji

### 12.1 Zatwierdzone (2026-10-22)

| # | Temat | Decyzja |
|---|---|---|
| P1 | Wielkość liter słów kluczowych | tylko WIELKIE |
| P2 | Mieszanie INT i FLOAT | dozwolone, wynik FLOAT |
| P3 | `1 == 1.0` | `TRUE`; inne różne typy → `FALSE` bez błędu |
| P4 | Semantyka `%` | znak wyniku jak dzielnika, działa też na FLOAT |
| P5 | Indeksy ujemne | niedozwolone |
| P6 | Zakresy | **zmienione:** tylko funkcje i moduły tworzą zakres (sekcja 6) |
| P7 | Hoisting `FUNC` | brak; ciała funkcji widzą późniejsze deklaracje otoczenia |
| P8 | Instrukcja-wyrażenie | tylko wywołania funkcji |
| P9 | `ELSE IF` | dozwolone, jedno `END` |
| P10 | Ścieżki w `files` | względem katalogu głównego skryptu |
| P11 | Import | **zmienione:** względem pliku importującego, stdlib ma pierwszeństwo, `IMPORT LOCAL` i `AS` dla konfliktów (9.1) |
| P12 | Eksport | **zmienione:** jawny `EXPORT` (9.2) |
| P13 | `RANGE` | 2 lub 3 argumenty, zachłannie, z limitem |
| P14 | Komunikaty błędów | po angielsku |
| P15 | Kody wyjścia | 0/1/2/3/70 |
| P16 | Zakres v0.1 | **zmienione:** `INPUT()` w v0.1; poza v0.1: `TRY/CATCH`, lambdy, metody list, interpolacja tekstu, notacja `1e5` |

### 12.2 Szczegóły zaprojektowane przez Claude — do potwierdzenia

| # | Temat | Propozycja |
|---|---|---|
| N1 | Deklaracje bez zakresów bloków (P6) | jedna deklaracja nazwy na zakres w tekście (także między gałęziami `IF`/`ELSE`); ponowne wykonanie `LET` w pętli dozwolone |
| N2 | Zmienna niezainicjalizowana (P6) | statyczna kolejność deklaracji + `NameError` w czasie wykonania przy odczycie przed wykonaniem deklaracji |
| N3 | Zmienna `FOR` (P6) | należy do zakresu funkcji/modułu, zachowuje ostatnią wartość, kilka pętli może ją współdzielić |
| N4 | Składnia importu (P11) | `IMPORT [LOCAL] name [AS alias]`; nowe słowa kluczowe `LOCAL`, `AS` |
| N5 | Składnia eksportu (P12) | instrukcja `EXPORT a, b` na najwyższym poziomie, w dowolnym miejscu pliku; wiązanie na żywo, tylko do odczytu |
| N6 | `INPUT` (P16) | `INPUT([prompt])` → STRING bez końca linii; EOF → `NULL`; zawsze UTF-8 |
| N7 | `falasz check` (11.4) | jeden (pierwszy) błąd składni na plik; wszystkie błędy walidacji nazw |
| N8 | Limit zagnieżdżenia (10) | każde `ELSE IF` liczy się jako poziom zagnieżdżenia — łańcuch dłuższy niż ~200 gałęzi → `SyntaxError` |

N1–N8 zatwierdzone 2026-10-22; N2 doprecyzowane przez właściciela: zmienna powstaje
dopiero w chwili wykonania `LET`, niewykonana deklaracja = zmienna nie istnieje.

### 12.3 Przypadki brzegowe ustalone w Etapie 3 — zatwierdzone 2026-10-22

| # | Temat | Propozycja |
|---|---|---|
| E1 | Powtórzony klucz w literale MAP | ostatnia wartość wygrywa |
| E2 | Struktury cykliczne | dozwolone; `[...]`/`{...}` w `STR`; `==` się kończy |
| E3 | Limity wartości | zagnieżdżenie 500, konwersja INTEGER↔tekst 4300 cyfr → `LimitError` |
| E4 | `FLOAT("007")`, `INT("007")` | dozwolone (zera wiodące tylko w tekście, nie w literałach źródła) |
| E5 | `-0.0` | wypisywane jako `-0.0`, równe `0.0` |
| E6 | Krok interpretera (`--max-steps`) | każda wykonana instrukcja i każda iteracja pętli |
| E7 | Kolejność obliczeń w przypisaniu | najpierw prawa strona, potem cel (`x[i] = e`: `e`, potem `x`, potem `i`) |
| E8 | Równość MAP | niezależna od kolejności wstawiania (`{"a": 1, "b": 2} == {"b": 2, "a": 1}` → `TRUE`) |
| E9 | Klucz MAP złego typu w literale | `TypeError` wskazuje początek wyrażenia klucza |

## 13. Plan rozwoju po v0.1 (poza zakresem v0.1)

Zgłoszone przez właściciela do realizacji **po** ukończeniu v0.1 — nie implementować wcześniej:
- `HAS(map, key)` → BOOLEAN — sprawdzenie obecności klucza w MAP;
- `APPEND(list, value)` — dopisanie elementu do LIST w miejscu.

Kandydaci (bez decyzji): funkcje tekstowe (podział, wielkość liter, wycinki),
`TRY/CATCH`, lambdy, interpolacja tekstu, notacja wykładnicza, kompilator.

## 14. Przykłady

Korpus w `tests/spec_examples/`:
- `valid/X.falasz` + `X.out` (oczekiwane stdout) + opcjonalnie `X.in` (stdin);
- `valid/X/` — przykład wieloplikowy: punkt wejścia `main.falasz`, wynik `main.out`;
- `invalid/X.falasz` + `X.err`, `invalid/X/` z `main.falasz` + `main.err`.
  Pierwsza linia `.err`: `<plik>:<linia>:<kolumna>: <Kategoria>`, gdzie `<plik>` jest
  ścieżką względem katalogu przykładu.

Od Etapu 2 przykłady z błędami `SyntaxError` są sprawdzane przez parser, a wszystkie
pozostałe muszą się parsować; od Etapu 3 przykłady są wykonywane.
