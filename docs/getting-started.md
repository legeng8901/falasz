# Getting started with Falasz

This guide installs Falasz 0.1 (alpha) on Linux or Windows, runs a first
program and walks through the language in about fifteen minutes. The complete
rules are in [spec.md](spec.md) (in Polish); this guide is enough to start
writing programs.

## 1. Install

Falasz needs **Python 3.12 or newer**. It has no other dependencies.

The recommended tool is [pipx](https://pipx.pypa.io/): it installs Falasz in
its own environment and puts the `falasz` command on your `PATH`, so you never
have to activate a virtual environment or type a path like `.venv/bin/falasz`.

### Linux

1. Check Python:

   ```console
   python3 --version
   ```

2. Install pipx and let it add its command directory (`~/.local/bin`) to `PATH`:

   ```console
   sudo dnf install pipx        # Fedora
   sudo apt install pipx        # Debian, Ubuntu
   pipx ensurepath
   ```

   Close the terminal and open a new one.

3. Get the source and install it:

   ```console
   git clone https://github.com/legeng8901/falasz.git
   pipx install ./falasz
   ```

   If you have a built wheel instead: `pipx install falasz-0.1.0a0-py3-none-any.whl`.

4. Check it:

   ```console
   falasz --version
   ```

   It prints `falasz 0.1.0a0`.

Without pipx, `python3 -m pip install --user ./falasz` also works on
distributions that allow it (Fedora does; recent Debian and Ubuntu refuse with
"externally-managed-environment", use pipx there). The command lands in
`~/.local/bin`, which must be on `PATH`.

### Windows

1. Install Python 3.12 or newer from [python.org](https://www.python.org/downloads/windows/)
   (tick **"Add python.exe to PATH"** in the installer) or with
   `winget install Python.Python.3.13`. Check it in a new terminal:

   ```console
   py --version
   ```

2. Install pipx and add its command directory to `PATH`:

   ```console
   py -m pip install --user pipx
   py -m pipx ensurepath
   ```

   Close the terminal and open a new one.

3. Get the source and install it:

   ```console
   git clone https://github.com/legeng8901/falasz.git
   pipx install .\falasz
   ```

4. Check it:

   ```console
   falasz --version
   ```

If `falasz` is "not recognized", the new `PATH` has not reached your terminal
yet: open a new one (or sign out and in). `py -m falasz` works in the meantime;
it accepts exactly the same arguments as `falasz`.

### Updating and removing

```console
pipx install --force ./falasz     # after pulling a new version
pipx uninstall falasz
```

## 2. Your first program

Create a file `hello.falasz` in any editor. Save it as **UTF-8** (the default
in VS Code, Notepad and most editors):

```falasz
LET name = INPUT("What is your name? ")
SAY "Hello, " + name + "!"
LET year = 2026
SAY "Falasz is " + STR(year - 2025) + " year old."
```

Run it:

```console
falasz run hello.falasz
```

```text
What is your name? Ada
Hello, Ada!
Falasz is 1 year old.
```

`falasz check hello.falasz` checks the program (syntax, names, imports)
**without running anything** and prints `OK` or every problem it finds.

When something goes wrong, the message names the file, line and column. If
line 4 forgot the `STR(...)`, as in `SAY "Falasz is " + (year - 2025) + " year old."`,
the program stops there:

```text
hello.falasz:4:18: TypeError: unsupported operand types for +: STRING and INTEGER
```

The exit code tells scripts what happened: `0` success, `1` the program failed
while running, `2` wrong command-line arguments or a missing file, `3` the
program has errors and did not start.

## 3. The language in fifteen minutes

### Values and variables

```falasz
LET count = 3              # INTEGER, up to 4300 digits
LET price = 9.99           # FLOAT
LET title = "Falasz"       # STRING
LET ready = TRUE           # BOOLEAN: TRUE or FALSE
LET nothing = NULL
LET items = [1, "two", 3.0]
LET ages = {"Ada": 36, "Linus": 21}

count = count + 1          # assignment: the variable must exist already
SAY count
SAY items[1]
SAY ages["Ada"]
SAY LEN(items)
```

```text
4
two
36
3
```

`LET` declares, `=` assigns. Keywords are UPPERCASE; names are case-sensitive.
Comments start with `#`.

### No hidden conversions

Falasz never converts types behind your back. Convert explicitly with `STR`,
`INT` and `FLOAT`:

```falasz
LET age = 20
SAY "Age: " + STR(age)
SAY INT("42") + 1
SAY 7 / 2
SAY INT(7 / 2)
SAY 7 % 2
```

```text
Age: 20
43
3.5
3
1
```

`/` always gives a FLOAT; `INT` cuts off the fraction. `"Age: " + age` is a
`TypeError`.

### Conditions and loops

Conditions must be BOOLEAN: `IF count` is an error, write `IF count > 0`.

```falasz
LET temperature = 18
IF temperature >= 25
    SAY "hot"
ELSE IF temperature >= 15
    SAY "mild"
ELSE
    SAY "cold"
END

LET n = 3
WHILE n > 0
    SAY n
    n = n - 1
END

FOR i IN RANGE(0, 10, 4)
    SAY i
END

FOR letter IN "ab"
    SAY letter
END

FOR key IN {"x": 1, "y": 2}
    SAY key
END
```

```text
mild
3
2
1
0
4
8
a
b
x
y
```

`RANGE(start, stop)` stops *before* `stop`. `BREAK` and `CONTINUE` work in both
loops. Combine conditions with `AND`, `OR`, `NOT`.

### Functions

```falasz
FUNC area(width, height)
    RETURN width * height
END

FUNC factorial(n)
    IF n <= 1
        RETURN 1
    END
    RETURN n * factorial(n - 1)
END

SAY area(3, 4)
SAY factorial(25)
```

```text
12
15511210043330985984000000
```

Functions can be stored in variables, passed as arguments and returned
(closures). Recursion is allowed up to 500 nested calls.

### Lists and maps

```falasz
LET scores = [90, 75]
scores = scores + [60]
scores[0] = 95
SAY scores

LET stock = {}
stock["apples"] = 10
stock["pears"] = 4
stock["apples"] = stock["apples"] - 3
SAY stock
```

```text
[95, 75, 60]
{"apples": 7, "pears": 4}
```

Map keys are INTEGER, STRING or BOOLEAN. Reading a missing key or index is an
error, so check with `LEN` or loop over the keys first.

### Reading input

`INPUT()` returns the next line of standard input as a STRING, or `NULL` when
the input has ended, which makes "read until the end" loops simple:

```falasz
LET total = 0
LET line = INPUT()
WHILE line != NULL
    total = total + INT(line)
    line = INPUT()
END
SAY total
```

### Files

```falasz
IMPORT files
files.write_text("note.txt", "first line\nsecond line\n")
SAY files.read_text("note.txt")
```

Relative paths are relative to the **main script's directory**, not to the
directory you run `falasz` from, so a program finds its data files from
anywhere. Text is UTF-8 and line endings are kept exactly as they are in the
file.

### Modules

Split a program into files that sit in the same directory:

```text
greetings.falasz:                main.falasz:
    EXPORT hello                     IMPORT LOCAL greetings
    FUNC hello(name)                 SAY greetings.hello("Ada")
        RETURN "Hi " + name
    END
```

A module shares only the names it lists in `EXPORT`. It runs once, the first
time it is imported.

## 4. Rules that surprise newcomers

* **Blocks do not create scopes.** A variable declared inside `IF`, `WHILE` or
  `FOR` is visible after the block; only functions and modules have their own
  scope. Each name is declared once per scope, and that includes `FOR` loop
  variables: `LET item = 1` followed by `FOR item IN ...` in the same scope is
  an error. Pick another name.
* **A statement ends at the end of the line.** A long expression may continue
  on the next line only inside `( )`, `[ ]` or `{ }`:

  ```falasz
  LET total = (1 + 2 + 3
      + 4 + 5)
  SAY total
  ```

  ```text
  15
  ```

* **String escapes** are only `\"`, `\\`, `\n` and `\t`.
* **There are no string or list helper functions yet** (no split, trim,
  contains, `HAS`, `APPEND`). Write small functions instead; the examples show
  how. They are planned after 0.1.
* **A FLOAT is printed in full** (`37.77777777777778`). Round it yourself for
  display: see `round_to` in [examples/temperature.falasz](../examples/temperature.falasz).
* **No exceptions.** Any error stops the program. Validate input before using it,
  as [examples/grades.falasz](../examples/grades.falasz) does.

## 5. Windows notes

* **Feeding a file to standard input.** `falasz run grades.falasz < grades.in`
  works in `cmd.exe`, but PowerShell has no `<` operator. In PowerShell use:

  ```console
  Get-Content grades.in | falasz run grades.falasz
  ```

  Windows PowerShell 5.1 sends non-ASCII characters through a pipe as `?`; use
  PowerShell 7 (`pwsh`) or `cmd.exe` when the input has Polish letters or other
  non-ASCII text.
* **Saving output to a file.** Falasz always writes UTF-8 with `\n` line
  endings. Windows PowerShell 5.1 re-encodes `>` redirection as UTF-16;
  PowerShell 7.4 or newer and `cmd.exe` keep the bytes unchanged.
* **Paths in programs.** Use `/` in paths (`"data/input.txt"`); it works on
  every system. A backslash must be doubled inside a string (`"data\\input.txt"`).
  Drive-relative paths like `"C:data.txt"` are rejected; `"C:/data.txt"` works.
* **Line endings.** Source files may use Windows (`\r\n`) or Unix (`\n`) line
  endings. Text read with `files.read_text` is returned unchanged, so a file
  saved by Notepad contains `\r` before each `\n`;
  [examples/budget/csv.falasz](../examples/budget/csv.falasz) shows how to cope.

## 6. Where next

Run the examples from the `examples` directory:

| Command | Shows |
|---|---|
| `falasz run fizzbuzz.falasz` | loops and conditions |
| `falasz run caesar.falasz` | working with strings character by character |
| `falasz run temperature.falasz` | FLOAT arithmetic and rounding |
| `falasz run grades.falasz < grades.in` | reading and validating input |
| `falasz run budget/main.falasz` | modules, reading a CSV file, writing a report |
| `falasz run closures.falasz` | functions as values |
| `falasz run --sensors-mock thermostat.sensors.json thermostat.falasz` | the `sensors` module with test data |

* [README.md](../README.md): command-line options and exit codes.
* [limitations.md](limitations.md): what version 0.1 does not do.
* [sensors.md](sensors.md): the sensors API and the mock data format.
