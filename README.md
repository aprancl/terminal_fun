# globe-term

An interactive ASCII globe rendered in the terminal with mouse-driven rotation and zoom.

Built entirely with the Python standard library (curses, argparse) -- no external dependencies.

<!-- TODO: Add terminal screenshot or gif here -->

## Installation

```bash
pip install globe-term
```

Or install from source:

```bash
git clone https://github.com/aprancl/terminal_fun.git
cd terminal_fun
pip install .
```

## Usage

Launch the globe:

```bash
globe_term
```

Or run as a Python module:

```bash
python -m globe_term
```

### CLI Options

```
globe_term [OPTIONS]

Options:
  --speed SPEED    Auto-rotation speed multiplier (default: 1.0)
  --theme NAME     Visual theme name (default: geography)
  --no-color       Disable color output (monochrome mode)
  --size SIZE      Globe size: small, medium, large, or auto (default: auto)
  --version        Show version and exit
  --help           Show help message and exit
```

### Examples

```bash
# Use the matrix theme (green-on-black digital aesthetic)
globe_term --theme matrix

# Large globe with no color
globe_term --size large --no-color

# Slow auto-rotation
globe_term --speed 0.5
```

### Controls

- **Click and drag** to rotate the globe
- **Scroll** to zoom in and out
- **q** or **Ctrl+C** to quit

## Built-in Themes

- **geography** -- Blue oceans, green land (default)
- **matrix** -- Green-on-black digital aesthetic

## Creating a Custom Theme

Themes are declarative Python dataclasses. To create a new built-in theme:

1. Create a new `.py` file under `globe_term/themes/` (e.g. `my_theme.py`).

2. Define a module-level `Theme` instance:

```python
from globe_term.themes.base import Theme

MY_THEME = Theme(
    name="my_theme",
    description="A cool custom theme",
    ocean_char="~",
    land_char="#",
    ocean_fg=4,   # blue
    ocean_bg=0,   # black
    land_fg=2,    # green
    land_bg=0,    # black
    border_fg=7,  # white
    shading_chars=" .:-=+*#%@",
)
```

3. The theme registry will pick it up automatically. Use it with:

```bash
globe_term --theme my_theme
```

Only the `name` field is required -- all other fields have sensible defaults.
See `globe_term/themes/base.py` for the full field reference.

## Requirements

- Python >= 3.9
- A POSIX terminal with curses support (Linux, macOS)

## License

MIT
