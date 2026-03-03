"""OpenRCT2 sprite category presets for AI restyling.

Categories define style prompts, tiling flags, and description hints.
Unlike the ottd pipeline, these do NOT define sprite ID ranges —
OpenRCT2 sprites are discovered from the filesystem.
"""

CATEGORIES = {
    "scenery_small": {
        "tiling": False,
        "style_prompt": (
            "Cartoony hand-painted fantasy scenery. Bold outlines, bright saturated "
            "colors, warm lighting. Rich detail, painterly textures. "
            "Think Warcraft III or Clash of Clans decorations."
        ),
        "description_hint": "small scenery object sprite (bench, lamp, fence, planter, etc.)",
    },
    "scenery_large": {
        "tiling": False,
        "style_prompt": (
            "Cartoony hand-painted fantasy scenery. Bold outlines, bright saturated "
            "colors, warm lighting. Large decorative structures with rich detail. "
            "Think theme park attractions in a fantasy art style."
        ),
        "description_hint": "large scenery object sprite (building, tower, statue, etc.)",
    },
    "scenery_wall": {
        "tiling": True,
        "style_prompt": (
            "Cartoony hand-painted fantasy walls and fences. Bold outlines, "
            "warm browns for wood, gray for stone, vibrant colors for decorative walls. "
            "Painterly textures. Think medieval fantasy theme park barriers."
        ),
        "description_hint": "wall or fence segment sprite",
    },
    "terrain": {
        "tiling": True,
        "style_prompt": (
            "Cartoony hand-painted fantasy terrain. Rich vibrant greens and warm "
            "earth tones. Bold color gradients. Painterly brushstroke textures. "
            "Keep isometric diamond shape and edge pixels unchanged."
        ),
        "description_hint": "isometric terrain ground tile",
    },
    "footpath": {
        "tiling": True,
        "style_prompt": (
            "Cartoony hand-painted fantasy footpaths. Warm cobblestone or "
            "wooden plank textures. Bold outlines between stones/planks. "
            "Medieval fantasy style path tiles. Keep exact shape and edges."
        ),
        "description_hint": "footpath or queue surface tile",
    },
    "ride": {
        "tiling": False,
        "style_prompt": (
            "Cartoony hand-painted fantasy ride vehicle. Bold outlines, bright "
            "saturated colors, warm lighting. Keep exact silhouette and proportions. "
            "Think whimsical theme park ride in fantasy art style."
        ),
        "description_hint": "ride vehicle or track piece sprite",
    },
}
