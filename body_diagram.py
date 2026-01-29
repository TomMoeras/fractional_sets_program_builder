"""
Body Diagram SVG Generator

Generates SVG body diagrams with color-coded muscles based on training volume.
Used for visualizing which muscles are being trained in the program builder.
"""

from typing import Dict, Optional


def get_volume_color(volume: float, target_low: float = 10, target_high: float = 20) -> str:
    """
    Get color based on volume relative to targets.
    
    Args:
        volume: Current volume (sets)
        target_low: Low end of target range
        target_high: High end of target range
    
    Returns:
        Hex color string
    """
    if volume == 0:
        return "#9E9E9E"  # Gray for no volume
    elif volume < target_low * 0.5:
        return "#F44336"  # Red - very low
    elif volume < target_low:
        return "#FF9800"  # Orange - below target
    elif volume <= target_high:
        return "#4CAF50"  # Green - on target
    else:
        return "#2196F3"  # Blue - above target


def generate_body_svg_front(muscle_volumes: Dict[str, float], width: int = 200, height: int = 400) -> str:
    """
    Generate front view body diagram SVG.
    
    Args:
        muscle_volumes: Dict mapping muscle names to volume (sets)
        width: SVG width
        height: SVG height
    
    Returns:
        SVG string
    """
    # Get colors for each muscle group
    chest_color = get_volume_color(muscle_volumes.get("chest", 0))
    shoulders_color = get_volume_color(muscle_volumes.get("shoulders", 0))
    biceps_color = get_volume_color(muscle_volumes.get("biceps", 0))
    abs_color = get_volume_color(muscle_volumes.get("abdominals", 0))
    quads_color = get_volume_color(muscle_volumes.get("quadriceps", 0))
    forearms_color = get_volume_color(muscle_volumes.get("forearms", 0))
    
    svg = f'''<svg width="{width}" height="{height}" viewBox="0 0 200 400" xmlns="http://www.w3.org/2000/svg">
    <!-- Head -->
    <ellipse cx="100" cy="30" rx="25" ry="28" fill="#e0c8b0" stroke="#333" stroke-width="1"/>
    
    <!-- Neck -->
    <rect x="88" y="55" width="24" height="20" fill="#e0c8b0" stroke="#333" stroke-width="1"/>
    
    <!-- Shoulders (Deltoids) -->
    <ellipse cx="55" cy="85" rx="20" ry="15" fill="{shoulders_color}" stroke="#333" stroke-width="1"/>
    <ellipse cx="145" cy="85" rx="20" ry="15" fill="{shoulders_color}" stroke="#333" stroke-width="1"/>
    
    <!-- Chest (Pectorals) -->
    <path d="M 65 80 Q 80 85 100 90 Q 120 85 135 80 L 135 115 Q 120 125 100 130 Q 80 125 65 115 Z" 
          fill="{chest_color}" stroke="#333" stroke-width="1"/>
    
    <!-- Upper Arms (Biceps visible from front) -->
    <ellipse cx="45" cy="120" rx="12" ry="30" fill="{biceps_color}" stroke="#333" stroke-width="1"/>
    <ellipse cx="155" cy="120" rx="12" ry="30" fill="{biceps_color}" stroke="#333" stroke-width="1"/>
    
    <!-- Forearms -->
    <ellipse cx="40" cy="175" rx="10" ry="28" fill="{forearms_color}" stroke="#333" stroke-width="1"/>
    <ellipse cx="160" cy="175" rx="10" ry="28" fill="{forearms_color}" stroke="#333" stroke-width="1"/>
    
    <!-- Torso outline -->
    <path d="M 65 115 L 55 170 L 60 220 L 75 220 L 75 170 L 100 175 L 125 170 L 125 220 L 140 220 L 145 170 L 135 115" 
          fill="#e0c8b0" stroke="#333" stroke-width="1"/>
    
    <!-- Abs -->
    <rect x="80" y="135" width="40" height="80" rx="5" fill="{abs_color}" stroke="#333" stroke-width="1"/>
    <!-- Ab segments -->
    <line x1="80" y1="155" x2="120" y2="155" stroke="#333" stroke-width="0.5"/>
    <line x1="80" y1="175" x2="120" y2="175" stroke="#333" stroke-width="0.5"/>
    <line x1="80" y1="195" x2="120" y2="195" stroke="#333" stroke-width="0.5"/>
    <line x1="100" y1="135" x2="100" y2="215" stroke="#333" stroke-width="0.5"/>
    
    <!-- Quadriceps -->
    <ellipse cx="75" cy="290" rx="22" ry="55" fill="{quads_color}" stroke="#333" stroke-width="1"/>
    <ellipse cx="125" cy="290" rx="22" ry="55" fill="{quads_color}" stroke="#333" stroke-width="1"/>
    
    <!-- Lower legs (neutral) -->
    <ellipse cx="72" cy="365" rx="12" ry="30" fill="#e0c8b0" stroke="#333" stroke-width="1"/>
    <ellipse cx="128" cy="365" rx="12" ry="30" fill="#e0c8b0" stroke="#333" stroke-width="1"/>
    
    <!-- Hands -->
    <ellipse cx="35" cy="215" rx="8" ry="12" fill="#e0c8b0" stroke="#333" stroke-width="1"/>
    <ellipse cx="165" cy="215" rx="8" ry="12" fill="#e0c8b0" stroke="#333" stroke-width="1"/>
</svg>'''
    
    return svg


def generate_body_svg_back(muscle_volumes: Dict[str, float], width: int = 200, height: int = 400) -> str:
    """
    Generate back view body diagram SVG.
    
    Args:
        muscle_volumes: Dict mapping muscle names to volume (sets)
        width: SVG width
        height: SVG height
    
    Returns:
        SVG string
    """
    # Get colors for each muscle group
    traps_color = get_volume_color(muscle_volumes.get("traps", 0))
    lats_color = get_volume_color(muscle_volumes.get("lats", 0))
    triceps_color = get_volume_color(muscle_volumes.get("triceps", 0))
    lower_back_color = get_volume_color(muscle_volumes.get("lower back", 0))
    glutes_color = get_volume_color(muscle_volumes.get("glutes", 0))
    hamstrings_color = get_volume_color(muscle_volumes.get("hamstrings", 0))
    calves_color = get_volume_color(muscle_volumes.get("calves", 0))
    middle_back_color = get_volume_color(muscle_volumes.get("middle back", 0))
    
    svg = f'''<svg width="{width}" height="{height}" viewBox="0 0 200 400" xmlns="http://www.w3.org/2000/svg">
    <!-- Head -->
    <ellipse cx="100" cy="30" rx="25" ry="28" fill="#e0c8b0" stroke="#333" stroke-width="1"/>
    
    <!-- Neck/Traps -->
    <path d="M 75 55 Q 100 50 125 55 L 135 80 Q 100 75 65 80 Z" fill="{traps_color}" stroke="#333" stroke-width="1"/>
    
    <!-- Shoulders (rear delts) -->
    <ellipse cx="55" cy="85" rx="18" ry="12" fill="{traps_color}" stroke="#333" stroke-width="1"/>
    <ellipse cx="145" cy="85" rx="18" ry="12" fill="{traps_color}" stroke="#333" stroke-width="1"/>
    
    <!-- Upper Arms (Triceps visible from back) -->
    <ellipse cx="45" cy="120" rx="12" ry="30" fill="{triceps_color}" stroke="#333" stroke-width="1"/>
    <ellipse cx="155" cy="120" rx="12" ry="30" fill="{triceps_color}" stroke="#333" stroke-width="1"/>
    
    <!-- Lats -->
    <path d="M 65 85 Q 55 120 60 160 L 80 150 Q 100 145 120 150 L 140 160 Q 145 120 135 85 
             Q 120 80 100 82 Q 80 80 65 85 Z" fill="{lats_color}" stroke="#333" stroke-width="1"/>
    
    <!-- Middle Back (Rhomboids/Mid Traps) -->
    <rect x="85" y="90" width="30" height="40" rx="5" fill="{middle_back_color}" stroke="#333" stroke-width="1"/>
    
    <!-- Lower Back (Erectors) -->
    <path d="M 80 155 Q 100 150 120 155 L 120 200 Q 100 210 80 200 Z" 
          fill="{lower_back_color}" stroke="#333" stroke-width="1"/>
    
    <!-- Forearms -->
    <ellipse cx="40" cy="175" rx="10" ry="28" fill="#e0c8b0" stroke="#333" stroke-width="1"/>
    <ellipse cx="160" cy="175" rx="10" ry="28" fill="#e0c8b0" stroke="#333" stroke-width="1"/>
    
    <!-- Glutes -->
    <ellipse cx="80" cy="230" rx="22" ry="20" fill="{glutes_color}" stroke="#333" stroke-width="1"/>
    <ellipse cx="120" cy="230" rx="22" ry="20" fill="{glutes_color}" stroke="#333" stroke-width="1"/>
    
    <!-- Hamstrings -->
    <ellipse cx="75" cy="295" rx="18" ry="45" fill="{hamstrings_color}" stroke="#333" stroke-width="1"/>
    <ellipse cx="125" cy="295" rx="18" ry="45" fill="{hamstrings_color}" stroke="#333" stroke-width="1"/>
    
    <!-- Calves -->
    <ellipse cx="72" cy="365" rx="12" ry="30" fill="{calves_color}" stroke="#333" stroke-width="1"/>
    <ellipse cx="128" cy="365" rx="12" ry="30" fill="{calves_color}" stroke="#333" stroke-width="1"/>
    
    <!-- Hands -->
    <ellipse cx="35" cy="215" rx="8" ry="12" fill="#e0c8b0" stroke="#333" stroke-width="1"/>
    <ellipse cx="165" cy="215" rx="8" ry="12" fill="#e0c8b0" stroke="#333" stroke-width="1"/>
</svg>'''
    
    return svg


def generate_combined_body_diagram(muscle_volumes: Dict[str, float]) -> str:
    """
    Generate a combined HTML with both front and back views side by side.
    
    Args:
        muscle_volumes: Dict mapping muscle names to volume (sets)
    
    Returns:
        HTML string with both SVGs
    """
    front_svg = generate_body_svg_front(muscle_volumes, width=140, height=280)
    back_svg = generate_body_svg_back(muscle_volumes, width=140, height=280)
    
    html = f'''<div style="display: flex; justify-content: space-around; align-items: flex-start; gap: 10px;">
<div style="text-align: center;">
<div style="font-size: 12px; font-weight: bold; margin-bottom: 5px; color: #333;">Front</div>
{front_svg}
</div>
<div style="text-align: center;">
<div style="font-size: 12px; font-weight: bold; margin-bottom: 5px; color: #333;">Back</div>
{back_svg}
</div>
</div>'''
    
    return html


def get_volume_legend_html() -> str:
    """
    Generate HTML for the volume color legend.
    
    Returns:
        HTML string for the legend
    """
    legend = '''
    <div style="font-size: 10px; margin-top: 10px;">
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <span style="display: inline-flex; align-items: center; gap: 3px;"><span style="display: inline-block; width: 12px; height: 12px; background: #9E9E9E; border-radius: 2px;"></span>None</span>
            <span style="display: inline-flex; align-items: center; gap: 3px;"><span style="display: inline-block; width: 12px; height: 12px; background: #F44336; border-radius: 2px;"></span>Very low</span>
            <span style="display: inline-flex; align-items: center; gap: 3px;"><span style="display: inline-block; width: 12px; height: 12px; background: #FF9800; border-radius: 2px;"></span>Below</span>
            <span style="display: inline-flex; align-items: center; gap: 3px;"><span style="display: inline-block; width: 12px; height: 12px; background: #4CAF50; border-radius: 2px;"></span>On target</span>
            <span style="display: inline-flex; align-items: center; gap: 3px;"><span style="display: inline-block; width: 12px; height: 12px; background: #2196F3; border-radius: 2px;"></span>Above</span>
        </div>
    </div>
    '''
    return legend


# Muscle name normalization for different naming conventions
MUSCLE_ALIASES = {
    "abs": "abdominals",
    "core": "abdominals",
    "pecs": "chest",
    "pectorals": "chest",
    "delts": "shoulders",
    "deltoids": "shoulders",
    "bis": "biceps",
    "tris": "triceps",
    "back": "lats",
    "upper back": "middle back",
    "rhomboids": "middle back",
    "erectors": "lower back",
    "spinal erectors": "lower back",
    "hams": "hamstrings",
    "quads": "quadriceps",
    "trapezius": "traps",
}


def normalize_muscle_name(muscle: str) -> str:
    """
    Normalize muscle name to match SVG muscle names.
    
    Args:
        muscle: Input muscle name (can be various formats)
    
    Returns:
        Normalized muscle name
    """
    muscle_lower = muscle.lower().strip()
    return MUSCLE_ALIASES.get(muscle_lower, muscle_lower)


def aggregate_muscle_volumes(muscle_breakdown: Dict[str, float]) -> Dict[str, float]:
    """
    Aggregate muscle volumes and normalize names for SVG display.
    
    Args:
        muscle_breakdown: Dict from calculate_week_stats or similar
    
    Returns:
        Dict with normalized muscle names and aggregated volumes
    """
    aggregated = {}
    
    for muscle, volume in muscle_breakdown.items():
        normalized = normalize_muscle_name(muscle)
        if normalized in aggregated:
            aggregated[normalized] += volume
        else:
            aggregated[normalized] = volume
    
    return aggregated
