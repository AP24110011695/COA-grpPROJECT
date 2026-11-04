"""Design tokens (docs/design.md §4) — the single Python source for colors
and layout constants. ui/styles.css mirrors them as CSS variables and the
charts import the same values so CSS and matplotlib never drift
(docs/design.md §11)."""

ACCENT = "#1F5FA8"
ACCENT_SOFT = "#E8F0F8"
BG = "#FFFFFF"
BG_SUBTLE = "#F5F7FA"
BORDER = "#D9DEE4"
TEXT = "#1F2933"
TEXT_SECONDARY = "#52606D"
SUCCESS = "#2E7D32"
SUCCESS_SOFT = "#E6F2E8"
DANGER = "#C62828"
DANGER_SOFT = "#FBEAEA"
WARNING = "#B26A00"
WARNING_SOFT = "#FBF1E2"
BOT2 = "#0B7285"

CHART_HITS = SUCCESS
CHART_MISSES = DANGER
CHART_EVICTIONS = WARNING

MAX_CONTENT_WIDTH = 1100
EVENT_TABLE_ROWS = 500

# Widget choices — powers of two per prd.md 5 (the engine re-validates
# authoritatively; the selects make invalid input untypable).
BLOCK_SIZES = [1, 2, 4, 8, 16, 32, 64, 128]
CAPACITIES = [2 ** exponent for exponent in range(0, 21)]  # 1 .. 2^20 B
ADDRESS_WIDTH_MIN = 4
ADDRESS_WIDTH_MAX = 64

# Theme palettes (docs/design.md §4 light tokens; dark tokens verified for
# WCAG contrast in the 2026-10-27 dark-mode audit — see docs/memory.md).
# Light stays the default and is byte-compatible with the delivered UI.
THEMES = {
    "light": {
        "BG": "#FFFFFF",
        "BG_SUBTLE": "#F5F7FA",
        "BORDER": "#D9DEE4",
        "TEXT": "#1F2933",
        "TEXT_SECONDARY": "#52606D",
        "ACCENT": "#1F5FA8",
        "ACCENT_SOFT": "#E8F0F8",
        "SUCCESS": "#2E7D32",
        "SUCCESS_SOFT": "#E6F2E8",
        "DANGER": "#C62828",
        "DANGER_SOFT": "#FBEAEA",
        "WARNING": "#B26A00",
        "WARNING_SOFT": "#FBF1E2",
        "BOT2": "#0B7285",
        "CHART_HITS": "#2E7D32",
        "CHART_MISSES": "#C62828",
        "CHART_EVICTIONS": "#B26A00",
    },
    "dark": {
        "BG": "#16181D",
        "BG_SUBTLE": "#1F232B",
        "BORDER": "#667080",
        "TEXT": "#E8EAED",
        "TEXT_SECONDARY": "#A8B0BD",
        "ACCENT": "#4F8DE8",
        "ACCENT_SOFT": "#22304A",
        "SUCCESS": "#66BB6A",
        "SUCCESS_SOFT": "#1E3A27",
        "DANGER": "#EF5350",
        "DANGER_SOFT": "#3A1D20",
        "WARNING": "#FFB74D",
        "WARNING_SOFT": "#3D2E14",
        "BOT2": "#38B2C4",
        "CHART_HITS": "#66BB6A",
        "CHART_MISSES": "#EF5350",
        "CHART_EVICTIONS": "#FFB74D",
    },
}


def get_tokens(theme="light"):
    """Returns the color mapping for `theme` ("light"/"dark"). Unknown or
    missing themes fall back to Light — the delivered default."""
    return dict(THEMES.get((theme or "light").lower(), THEMES["light"]))
