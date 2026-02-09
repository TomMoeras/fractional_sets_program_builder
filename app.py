"""
Training Program Builder with Fractional Sets Analysis

Build your weekly training program and see real-time fractional set calculations
for both hypertrophy (muscle-focused) and strength (exercise-focused) training.

Usage:
    streamlit run program_builder.py
"""

import streamlit as st
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
from collections import defaultdict
from pathlib import Path

# Import body diagram generator
from body_diagram import (
    generate_combined_body_diagram,
    get_volume_legend_html,
    aggregate_muscle_volumes,
)

# Image hosting URL for free-exercise-db
IMAGEKIT_BASE_URL = "https://ik.imagekit.io/yuhonas"

# Page configuration
st.set_page_config(
    page_title="Fractional Sets Program Builder",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for blue buttons
st.markdown(
    """
    <style>
    /* Make primary/action buttons blue */
    .stButton > button {
        border-color: #1f77b4;
    }
    .stButton > button:hover {
        border-color: #1a5f8f;
        color: #1a5f8f;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Days of the week
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# Big 5 compound lift categories with name patterns for matching
BIG_5_CATEGORIES = {
    "Squat": ["squat"],
    "Deadlift": ["deadlift"],
    "Bench Press": ["bench press"],
    "Overhead Press": ["military press", "overhead press", "shoulder press"],
    "Row": ["barbell row", "pendlay row", "t-bar row", "seal row"],
}

# Flat list derived from categories (used by is_big5_exercise)
BIG_5_PATTERNS = [p for patterns in BIG_5_CATEGORIES.values() for p in patterns]


def is_big5_exercise(exercise_name):
    """Check if an exercise matches a Big 5 compound lift pattern."""
    name_lower = exercise_name.lower()
    return any(pattern in name_lower for pattern in BIG_5_PATTERNS)


def get_big5_category(exercise_name):
    """Get the Big 5 category for an exercise, or None if not a Big 5 lift."""
    name_lower = exercise_name.lower()
    for category, patterns in BIG_5_CATEGORIES.items():
        if any(p in name_lower for p in patterns):
            return category
    return None


def get_big5_coverage(program):
    """
    Check which Big 5 categories are covered in the program at strength rep ranges.

    Args:
        program: Dict of day -> list of exercise entries

    Returns:
        Tuple of (covered_dict, missing_list):
        - covered: {category: [{exercise, day, sets, reps}, ...]}
        - missing: [category_name, ...]
    """
    covered = {}
    missing = []

    for category, patterns in BIG_5_CATEGORIES.items():
        matching = []
        for day in DAYS:
            for entry in program.get(day, []):
                if entry["reps"] <= 6:
                    name_lower = entry["exercise"].lower()
                    if any(p in name_lower for p in patterns):
                        matching.append(
                            {
                                "exercise": entry["exercise"],
                                "day": day,
                                "sets": entry["sets"],
                                "reps": entry["reps"],
                            }
                        )

        if matching:
            covered[category] = matching
        else:
            missing.append(category)

    return covered, missing


# All muscle groups available in the exercise database
ALL_MUSCLE_GROUPS = [
    "abdominals",
    "abductors",
    "adductors",
    "biceps",
    "calves",
    "chest",
    "forearms",
    "front deltoids",
    "glutes",
    "hamstrings",
    "lats",
    "lower back",
    "middle back",
    "neck",
    "quadriceps",
    "rear deltoids",
    "rotator cuff",
    "side deltoids",
    "traps",
    "triceps",
]

# Week types for mesocycle planning
WEEK_TYPES = {
    "training": {
        "name": "Training",
        "description": "Normal training week",
        "volume_modifier": 1.0,
        "intensity_modifier": 1.0,
        "color": "#4CAF50",  # Green
    },
    "deload": {
        "name": "Deload",
        "description": "Reduced volume/intensity for recovery",
        "volume_modifier": 0.5,  # 50% of normal volume
        "intensity_modifier": 0.9,  # 90% of normal intensity
        "color": "#2196F3",  # Blue
    },
    "testing": {
        "name": "1RM Testing",
        "description": "Testing week for maximal strength",
        "volume_modifier": 0.3,  # Low volume
        "intensity_modifier": 1.0,  # High intensity
        "color": "#FF9800",  # Orange
    },
    "intensification": {
        "name": "Intensification",
        "description": "Higher intensity, lower volume",
        "volume_modifier": 0.8,
        "intensity_modifier": 1.1,
        "color": "#9C27B0",  # Purple
    },
    "volume": {
        "name": "Volume",
        "description": "Higher volume accumulation",
        "volume_modifier": 1.2,
        "intensity_modifier": 0.9,
        "color": "#00BCD4",  # Cyan
    },
}

# Training Status Definitions (from Table 7.14)
TRAINING_STATUS = {
    "Novice": {
        "description": "Can add load/reps each session or week",
        "progression": "Session-to-session or weekly progress",
        "duration": "First 6 months to 2 years of consistent training",
        "volume_multiplier": 0.8,  # Can use lower end of ranges
    },
    "Intermediate": {
        "description": "Progress slows; add reps weekly or load monthly",
        "progression": "Weekly rep progress, monthly load progress",
        "duration": "Years 1-5 of consistent training",
        "volume_multiplier": 1.0,  # Standard ranges
    },
    "Advanced": {
        "description": "Very slow gains; progress over months",
        "progression": "Monthly rep/load progress",
        "duration": "5+ years approaching genetic potential",
        "volume_multiplier": 1.2,  # May need higher volumes
    },
}

# Volume Tiers (from Table 7.4)
VOLUME_TIERS = {
    "Minimal": {
        "sets_range": (4, 8),
        "time_commitment": "~1-2.5 hours/week",
        "avg_stimulus_per_set": "Highest",
        "total_stimulus": "Lowest (~25-45% of max)",
        "description": "For minimal time investment or beginners",
        "frequency_range": (1, 2),
    },
    "Low": {
        "sets_range": (9, 12),
        "time_commitment": "~3-4.5 hours/week",
        "avg_stimulus_per_set": "High",
        "total_stimulus": "Modest (~45-60% of max)",
        "description": "Good return on time for most lifters",
        "frequency_range": (1, 2),
    },
    "Medium": {
        "sets_range": (13, 16),
        "time_commitment": "~5-6.5 hours/week",
        "avg_stimulus_per_set": "Medium",
        "total_stimulus": "Medium (~60-70% of max)",
        "description": "Balanced approach for dedicated lifters",
        "frequency_range": (2, 3),
    },
    "High": {
        "sets_range": (17, 20),
        "time_commitment": "~7-8.5 hours/week",
        "avg_stimulus_per_set": "Low",
        "total_stimulus": "High (~70-85% of max)",
        "description": "For serious bodybuilders/athletes",
        "frequency_range": (2, 3),
    },
    "Very High": {
        "sets_range": (21, 30),
        "time_commitment": "~9+ hours/week",
        "avg_stimulus_per_set": "Lowest",
        "total_stimulus": "Highest (~85-100% if sustainable)",
        "description": "Advanced lifters, specialization phases only",
        "frequency_range": (3, 4),
    },
}

# Frequency by Volume (Table 7.6)
FREQUENCY_BY_VOLUME = [
    {"sets_range": (4, 10), "frequency": (1, 2)},
    {"sets_range": (11, 20), "frequency": (2, 3)},
    {"sets_range": (21, 30), "frequency": (3, 4)},
]


def get_recommended_frequency(weekly_sets):
    """Get recommended training frequency based on weekly sets per muscle."""
    for entry in FREQUENCY_BY_VOLUME:
        if entry["sets_range"][0] <= weekly_sets <= entry["sets_range"][1]:
            return entry["frequency"]
    if weekly_sets < 4:
        return (1, 1)
    return (3, 4)  # For very high volume


@st.cache_data
def load_exercise_library():
    """Load exercise library from JSON file, including custom exercises."""
    # Try different possible paths for deployment flexibility
    possible_paths = [
        Path(__file__).parent / "data/exercises.json",
        Path("data/exercises.json"),
        Path("free-exercise-db/dist/exercises.json"),
        Path(__file__).parent / "free-exercise-db/dist/exercises.json",
    ]

    exercises = []

    # Load main exercise library
    for path in possible_paths:
        if path.exists():
            try:
                with open(path, "r") as f:
                    exercises = json.load(f)
                break
            except Exception as e:
                st.error(f"Error loading exercise library: {e}")
                return []

    if not exercises:
        st.error(
            "Exercise library not found. Please ensure data/exercises.json exists."
        )
        return []

    # Load custom exercises if available
    custom_paths = [
        Path(__file__).parent / "data/custom_exercises.json",
        Path("data/custom_exercises.json"),
    ]

    for path in custom_paths:
        if path.exists():
            try:
                with open(path, "r") as f:
                    custom_exercises = json.load(f)
                    exercises.extend(custom_exercises)
                    break
            except Exception as e:
                # Custom exercises are optional, so just log a warning
                st.warning(f"Note: Could not load custom exercises: {e}")

    return exercises


@st.cache_data
def load_program_templates():
    """Load program templates from JSON file."""
    possible_paths = [
        Path(__file__).parent / "data/program_templates.json",
        Path("data/program_templates.json"),
    ]

    for path in possible_paths:
        if path.exists():
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception as e:
                st.error(f"Error loading templates: {e}")
                return {}

    return {}


def get_exercise_by_name(exercises, name):
    """Find exercise by name from library."""
    for ex in exercises:
        if ex["name"] == name:
            return ex
    return None


def get_primary_muscle(exercise):
    """Get the primary muscle from an exercise (first element of primaryMuscles array)."""
    if not exercise:
        return "Unknown"
    primary = exercise.get("primaryMuscles", [])
    return primary[0].title() if primary else "Unknown"


def get_secondary_muscles(exercise):
    """Get secondary muscles from an exercise."""
    if not exercise:
        return []
    return [m.title() for m in exercise.get("secondaryMuscles", [])]


def get_exercise_image_url(image_path, thumbnail=False):
    """
    Get the imagekit.io URL for an exercise image.

    Args:
        image_path: The image path from the exercise JSON (e.g., "3_4_Sit-Up/0.jpg")
        thumbnail: If True, return a smaller thumbnail version
    """
    if thumbnail:
        return f"{IMAGEKIT_BASE_URL}/tr:w-250,h-180/{image_path}"
    return f"{IMAGEKIT_BASE_URL}/{image_path}"


def render_exercise_images(exercise, key_prefix=""):
    """Render exercise images with navigation."""
    images = exercise.get("images", [])
    if not images:
        return

    # Initialize image index in session state
    state_key = f"img_idx_{key_prefix}_{exercise.get('id', exercise.get('name'))}"
    if state_key not in st.session_state:
        st.session_state[state_key] = 0

    current_idx = st.session_state[state_key]

    # Display current image
    col1, col2, col3 = st.columns([1, 4, 1])

    with col1:
        if len(images) > 1:
            if st.button("◀", key=f"prev_{state_key}"):
                st.session_state[state_key] = (current_idx - 1) % len(images)
                st.rerun()

    with col2:
        image_url = get_exercise_image_url(images[current_idx])
        st.image(image_url, use_container_width=True)
        st.caption(f"Image {current_idx + 1} of {len(images)}")

    with col3:
        if len(images) > 1:
            if st.button("▶", key=f"next_{state_key}"):
                st.session_state[state_key] = (current_idx + 1) % len(images)
                st.rerun()


def render_exercise_details(
    exercise, show_images=True, show_instructions=True, key_prefix=""
):
    """Render exercise details including images and instructions."""
    if not exercise:
        return

    st.markdown(f"**{exercise.get('name', 'Unknown')}**")

    # Basic info
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.caption(f"🎯 {get_primary_muscle(exercise)}")
    with col2:
        st.caption(f"📊 {exercise.get('level', 'N/A').title()}")
    with col3:
        st.caption(f"⚙️ {exercise.get('mechanic', 'N/A') or 'N/A'}")
    with col4:
        st.caption(f"🏋️ {exercise.get('equipment', 'N/A').title()}")

    # Secondary muscles
    secondary = get_secondary_muscles(exercise)
    if secondary:
        st.caption(f"Synergists: {', '.join(secondary)}")

    # Images
    if show_images and exercise.get("images"):
        render_exercise_images(exercise, key_prefix)

    # Instructions
    if show_instructions:
        instructions = exercise.get("instructions", [])
        if instructions:
            with st.expander("📋 Instructions"):
                for i, step in enumerate(instructions, 1):
                    st.markdown(f"{i}. {step}")


def initialize_session_state():
    """Initialize session state for program storage."""
    # Legacy single-week program (kept for backwards compatibility)
    if "program" not in st.session_state:
        st.session_state.program = {day: [] for day in DAYS}
    if "program_name" not in st.session_state:
        st.session_state.program_name = "My Training Program"
    if "exercise_1rm" not in st.session_state:
        st.session_state.exercise_1rm = {}  # {exercise_name: 1rm_kg}

    # Multi-week program structure
    if "program_weeks" not in st.session_state:
        st.session_state.program_weeks = [
            {
                "name": "Week 1",
                "type": "training",  # training, deload, testing, intensification, volume
                "days": {day: [] for day in DAYS},
                "notes": "",
            }
        ]
    if "current_week" not in st.session_state:
        st.session_state.current_week = 0
    if "selected_day" not in st.session_state:
        st.session_state.selected_day = "Monday"

    # User profile settings
    if "user_profile" not in st.session_state:
        st.session_state.user_profile = {
            "training_status": "Intermediate",
            "volume_tier": "Medium",
            "use_custom_targets": False,
            "custom_hypertrophy_target": 15,  # sets/muscle/week
            "custom_strength_target": 4,  # sets/lift/week
        }

    # Custom exercises storage
    if "custom_exercises" not in st.session_state:
        st.session_state.custom_exercises = {}  # {source_name: [exercises]}

    # Run migration if needed
    migrate_to_multi_week()


def migrate_to_multi_week():
    """
    Migrate old single-week program format to multi-week format.
    This ensures backwards compatibility with existing saved programs.
    """
    # Check if we have old format data that needs migration
    old_program = st.session_state.get("program", {})
    has_old_data = any(old_program.get(day, []) for day in DAYS)

    # Check if program_weeks is empty (only has default empty week)
    weeks = st.session_state.get("program_weeks", [])
    weeks_is_empty = len(weeks) == 1 and not any(
        weeks[0]["days"].get(day, []) for day in DAYS
    )

    # Migrate if old program has data but new weeks structure is empty
    if has_old_data and weeks_is_empty:
        st.session_state.program_weeks = [
            {
                "name": "Week 1",
                "type": "training",
                "days": {day: list(old_program.get(day, [])) for day in DAYS},
                "notes": "",
            }
        ]
        # Don't clear old program data yet for safety


def sync_legacy_program():
    """
    Sync the multi-week program data back to legacy format for compatibility.
    This keeps st.session_state.program in sync with the current week.
    """
    if st.session_state.program_weeks:
        current_week = st.session_state.program_weeks[st.session_state.current_week]
        st.session_state.program = current_week["days"]


def export_program_to_json():
    """
    Export the full multi-week program to JSON format.

    Returns:
        dict: Program data in exportable format
    """
    return {
        "name": st.session_state.program_name,
        "format_version": "2.0",  # Multi-week format
        "weeks": st.session_state.program_weeks,
        "exercise_1rm": st.session_state.exercise_1rm,
        "user_profile": st.session_state.user_profile,
    }


def import_program_from_json(data):
    """
    Import program from JSON, handling both old and new formats.

    Args:
        data: Dict with program data (can be old or new format)

    Returns:
        bool: True if import successful
    """
    try:
        # Check format version
        format_version = data.get("format_version", "1.0")

        if format_version == "2.0":
            # New multi-week format
            st.session_state.program_name = data.get("name", "Imported Program")
            st.session_state.program_weeks = data.get("weeks", [])
            st.session_state.current_week = 0

            # Import optional data
            if "exercise_1rm" in data:
                st.session_state.exercise_1rm = data["exercise_1rm"]
            if "user_profile" in data:
                st.session_state.user_profile.update(data["user_profile"])

        else:
            # Old single-week format (days directly in data)
            if "days" in data:
                days_data = data["days"]
            else:
                # Even older format where keys are day names directly
                days_data = {day: data.get(day, []) for day in DAYS}

            # Ensure all 7 days are present (missing days = rest days)
            for day in DAYS:
                if day not in days_data:
                    days_data[day] = []

            st.session_state.program_name = data.get("name", "Imported Program")
            st.session_state.program_weeks = [
                {
                    "name": "Week 1",
                    "type": "training",
                    "days": days_data,
                    "notes": "",
                }
            ]
            st.session_state.current_week = 0

            # Also update legacy format
            st.session_state.program = days_data

            # Import 1RM if present
            if "exercise_1rm" in data:
                st.session_state.exercise_1rm = data["exercise_1rm"]

        return True
    except Exception as e:
        st.error(f"Error importing program: {e}")
        return False


# =============================================================================
# Week Management Functions
# =============================================================================


def get_current_week():
    """Get the current week's data."""
    idx = st.session_state.current_week
    if 0 <= idx < len(st.session_state.program_weeks):
        return st.session_state.program_weeks[idx]
    return st.session_state.program_weeks[0] if st.session_state.program_weeks else None


def get_current_week_days():
    """Get the days dict for the current week."""
    week = get_current_week()
    return week["days"] if week else {day: [] for day in DAYS}


def add_week(copy_from=None, week_type="training", name=None):
    """
    Add a new week to the program.

    Args:
        copy_from: Index of week to copy from (None for empty week)
        week_type: Type of week (training, deload, testing, etc.)
        name: Custom name for the week (auto-generated if None)
    """
    week_num = len(st.session_state.program_weeks) + 1

    if name is None:
        type_info = WEEK_TYPES.get(week_type, WEEK_TYPES["training"])
        if week_type == "training":
            name = f"Week {week_num}"
        else:
            name = f"Week {week_num} ({type_info['name']})"

    if copy_from is not None and 0 <= copy_from < len(st.session_state.program_weeks):
        # Deep copy the days from the source week
        source_days = st.session_state.program_weeks[copy_from]["days"]
        new_days = {
            day: [ex.copy() for ex in exercises]
            for day, exercises in source_days.items()
        }

        # Apply volume modifier if copying to a different week type
        if week_type != "training":
            modifier = WEEK_TYPES.get(week_type, {}).get("volume_modifier", 1.0)
            for day_exercises in new_days.values():
                for ex in day_exercises:
                    ex["sets"] = max(1, int(ex["sets"] * modifier))
    else:
        new_days = {day: [] for day in DAYS}

    new_week = {
        "name": name,
        "type": week_type,
        "days": new_days,
        "notes": "",
    }

    st.session_state.program_weeks.append(new_week)
    return len(st.session_state.program_weeks) - 1  # Return index of new week


def delete_week(week_index):
    """
    Delete a week from the program.

    Args:
        week_index: Index of the week to delete

    Returns:
        True if deleted, False if can't delete (last week)
    """
    if len(st.session_state.program_weeks) <= 1:
        return False  # Can't delete the last week

    if 0 <= week_index < len(st.session_state.program_weeks):
        st.session_state.program_weeks.pop(week_index)

        # Adjust current week if needed
        if st.session_state.current_week >= len(st.session_state.program_weeks):
            st.session_state.current_week = len(st.session_state.program_weeks) - 1

        return True
    return False


def copy_week(from_index, to_index=None):
    """
    Copy a week to a new position.

    Args:
        from_index: Index of week to copy
        to_index: Index where to insert (None = append at end)

    Returns:
        Index of the new week
    """
    if not (0 <= from_index < len(st.session_state.program_weeks)):
        return None

    source_week = st.session_state.program_weeks[from_index]

    # Deep copy
    new_week = {
        "name": f"{source_week['name']} (Copy)",
        "type": source_week["type"],
        "days": {
            day: [ex.copy() for ex in exercises]
            for day, exercises in source_week["days"].items()
        },
        "notes": source_week.get("notes", ""),
    }

    if to_index is None:
        st.session_state.program_weeks.append(new_week)
        return len(st.session_state.program_weeks) - 1
    else:
        st.session_state.program_weeks.insert(to_index, new_week)
        return to_index


def set_week_type(week_index, week_type, apply_modifiers=False):
    """
    Change the type of a week.

    Args:
        week_index: Index of the week to modify
        week_type: New week type
        apply_modifiers: If True, adjust sets based on volume modifier
    """
    if not (0 <= week_index < len(st.session_state.program_weeks)):
        return False

    week = st.session_state.program_weeks[week_index]
    old_type = week["type"]
    week["type"] = week_type

    if apply_modifiers and old_type != week_type:
        old_modifier = WEEK_TYPES.get(old_type, {}).get("volume_modifier", 1.0)
        new_modifier = WEEK_TYPES.get(week_type, {}).get("volume_modifier", 1.0)

        # Calculate relative modifier
        if old_modifier > 0:
            relative_modifier = new_modifier / old_modifier

            for day_exercises in week["days"].values():
                for ex in day_exercises:
                    ex["sets"] = max(1, int(ex["sets"] * relative_modifier))

    return True


def apply_deload_modifier(week_index, volume_modifier=0.5, sets_modifier=None):
    """
    Apply deload modifications to a week.

    Args:
        week_index: Index of the week to modify
        volume_modifier: Multiplier for sets (0.5 = 50% of sets)
        sets_modifier: If provided, use this instead of volume_modifier
    """
    if not (0 <= week_index < len(st.session_state.program_weeks)):
        return False

    modifier = sets_modifier if sets_modifier is not None else volume_modifier
    week = st.session_state.program_weeks[week_index]

    for day_exercises in week["days"].values():
        for ex in day_exercises:
            ex["sets"] = max(1, int(ex["sets"] * modifier))

    week["type"] = "deload"
    return True


def copy_day_to_day(source_day, target_day, week_index=None):
    """
    Copy exercises from one day to another within the same week.

    Args:
        source_day: Day to copy from (e.g., "Monday")
        target_day: Day to copy to (e.g., "Tuesday")
        week_index: Week index (None = current week)
    """
    if week_index is None:
        week_index = st.session_state.current_week

    if not (0 <= week_index < len(st.session_state.program_weeks)):
        return False

    week = st.session_state.program_weeks[week_index]

    if source_day not in week["days"] or target_day not in week["days"]:
        return False

    # Deep copy exercises
    week["days"][target_day] = [ex.copy() for ex in week["days"][source_day]]
    return True


def rename_week(week_index, new_name):
    """Rename a week."""
    if 0 <= week_index < len(st.session_state.program_weeks):
        st.session_state.program_weeks[week_index]["name"] = new_name
        return True
    return False


def reorder_weeks(new_order):
    """
    Reorder weeks based on a new index order.

    Args:
        new_order: List of indices representing new order
    """
    if len(new_order) != len(st.session_state.program_weeks):
        return False

    try:
        st.session_state.program_weeks = [
            st.session_state.program_weeks[i] for i in new_order
        ]
        return True
    except IndexError:
        return False


# =============================================================================
# Statistics Calculation Functions
# =============================================================================


def calculate_week_stats(week_days, exercises):
    """
    Calculate statistics for a week.

    Returns dict with total_sets, strength_sets, hypertrophy_sets,
    body_region_splits, movement_splits, and muscle_breakdown.
    """
    stats = {
        "total_sets": 0,
        "strength_sets": 0,
        "hypertrophy_sets": 0,
        "upper_sets": 0,
        "lower_sets": 0,
        "core_sets": 0,
        "push_sets": 0,
        "pull_sets": 0,
        "legs_sets": 0,
        "muscle_breakdown": defaultdict(float),
    }

    # Define muscle group categories
    upper_muscles = {
        "chest",
        "front deltoids",
        "side deltoids",
        "rear deltoids",
        "rotator cuff",
        "triceps",
        "biceps",
        "lats",
        "traps",
        "middle back",
        "forearms",
    }
    lower_muscles = {
        "quadriceps",
        "hamstrings",
        "glutes",
        "calves",
        "adductors",
        "abductors",
    }
    core_muscles = {"abdominals", "lower back"}

    push_muscles = {"chest", "front deltoids", "side deltoids", "triceps"}
    pull_muscles = {"lats", "middle back", "rear deltoids", "biceps", "traps", "forearms"}
    leg_muscles = {
        "quadriceps",
        "hamstrings",
        "glutes",
        "calves",
        "adductors",
        "abductors",
    }

    for day, day_exercises in week_days.items():
        for entry in day_exercises:
            num_sets = entry.get("sets", 0)
            reps = entry.get("reps", 0)

            stats["total_sets"] += num_sets

            # Classify by rep range
            if reps <= 6:
                stats["strength_sets"] += num_sets
            else:
                stats["hypertrophy_sets"] += num_sets

            # Get exercise info for muscle categorization
            exercise = get_exercise_by_name(exercises, entry.get("exercise", ""))
            if exercise:
                primary_muscles = [
                    m.lower() for m in exercise.get("primaryMuscles", [])
                ]
                secondary_muscles = [
                    m.lower() for m in exercise.get("secondaryMuscles", [])
                ]

                # Muscle breakdown (fractional counting)
                for muscle in primary_muscles:
                    stats["muscle_breakdown"][muscle] += num_sets * 1.0
                for muscle in secondary_muscles:
                    stats["muscle_breakdown"][muscle] += num_sets * 0.5

                # Body region classification
                for muscle in primary_muscles:
                    if muscle in upper_muscles:
                        stats["upper_sets"] += num_sets
                    elif muscle in lower_muscles:
                        stats["lower_sets"] += num_sets
                    elif muscle in core_muscles:
                        stats["core_sets"] += num_sets

                    # Movement pattern classification
                    if muscle in push_muscles:
                        stats["push_sets"] += num_sets
                    elif muscle in pull_muscles:
                        stats["pull_sets"] += num_sets
                    elif muscle in leg_muscles:
                        stats["legs_sets"] += num_sets

    return stats


def calculate_day_stats(day_exercises, exercises):
    """
    Calculate statistics for a single day.

    Returns dict with sets counts and muscle breakdown.
    """
    stats = {
        "total_sets": 0,
        "strength_sets": 0,
        "hypertrophy_sets": 0,
        "muscle_breakdown": defaultdict(float),
    }

    for entry in day_exercises:
        num_sets = entry.get("sets", 0)
        reps = entry.get("reps", 0)

        stats["total_sets"] += num_sets

        if reps <= 6:
            stats["strength_sets"] += num_sets
        else:
            stats["hypertrophy_sets"] += num_sets

        # Get exercise info
        exercise = get_exercise_by_name(exercises, entry.get("exercise", ""))
        if exercise:
            primary_muscles = [m.lower() for m in exercise.get("primaryMuscles", [])]
            secondary_muscles = [
                m.lower() for m in exercise.get("secondaryMuscles", [])
            ]

            for muscle in primary_muscles:
                stats["muscle_breakdown"][muscle] += num_sets * 1.0
            for muscle in secondary_muscles:
                stats["muscle_breakdown"][muscle] += num_sets * 0.5

    return stats


# =============================================================================
# Enhanced Weekly Editor UI Components
# =============================================================================


def render_week_navigation():
    """Render the week navigation bar with selector, add button, and type badges."""
    weeks = st.session_state.program_weeks
    current_idx = st.session_state.current_week

    # Ensure current_idx is valid
    if current_idx >= len(weeks):
        current_idx = len(weeks) - 1
        st.session_state.current_week = current_idx

    # Navigation row
    col_selector, col_type, col_actions = st.columns([4, 2, 4])

    with col_selector:
        # Week selector dropdown
        week_options = [f"{i+1}. {w['name']}" for i, w in enumerate(weeks)]
        selected = st.selectbox(
            "Select Week",
            options=range(len(weeks)),
            format_func=lambda i: week_options[i],
            index=current_idx,
            key="week_selector",
            label_visibility="collapsed",
        )
        if selected != current_idx:
            st.session_state.current_week = selected
            st.rerun()

    with col_type:
        # Week type badge
        current_week = weeks[current_idx]
        week_type = current_week.get("type", "training")
        type_info = WEEK_TYPES.get(week_type, WEEK_TYPES["training"])
        st.markdown(
            f"<span style='background-color:{type_info['color']};color:white;padding:4px 12px;"
            f"border-radius:12px;font-size:0.85em;'>{type_info['name']}</span>",
            unsafe_allow_html=True,
        )

    with col_actions:
        # Action buttons
        btn_cols = st.columns([1, 1, 1, 1])

        with btn_cols[0]:
            if st.button("➕", help="Add new week", key="add_week_btn"):
                new_idx = add_week(copy_from=current_idx)
                st.session_state.current_week = new_idx
                st.rerun()

        with btn_cols[1]:
            if st.button("📋", help="Copy this week", key="copy_week_btn"):
                copy_week(current_idx)
                st.rerun()

        with btn_cols[2]:
            if len(weeks) > 1:
                with st.popover("🗑️", help="Delete this week"):
                    st.warning(f"Delete '{current_week['name']}'?")
                    if st.button(
                        "Yes, Delete Week", type="primary", key="confirm_delete_week"
                    ):
                        delete_week(current_idx)
                        st.rerun()

        with btn_cols[3]:
            # Week type selector
            with st.popover("⚙️", help="Week settings"):
                st.markdown("**Week Settings**")

                # Rename
                new_name = st.text_input(
                    "Week Name",
                    value=current_week["name"],
                    key="week_rename_input",
                )
                if new_name != current_week["name"]:
                    rename_week(current_idx, new_name)

                # Type selector
                type_options = list(WEEK_TYPES.keys())
                current_type_idx = (
                    type_options.index(week_type) if week_type in type_options else 0
                )
                new_type = st.selectbox(
                    "Week Type",
                    options=type_options,
                    format_func=lambda t: WEEK_TYPES[t]["name"],
                    index=current_type_idx,
                    key="week_type_select",
                )

                if new_type != week_type:
                    apply_mods = st.checkbox("Adjust sets for new type", value=True)
                    if st.button("Apply Type Change"):
                        set_week_type(current_idx, new_type, apply_modifiers=apply_mods)
                        st.rerun()

                # Notes
                notes = st.text_area(
                    "Week Notes",
                    value=current_week.get("notes", ""),
                    key="week_notes_input",
                    height=80,
                )
                if notes != current_week.get("notes", ""):
                    st.session_state.program_weeks[current_idx]["notes"] = notes

    # Week overview bar
    if len(weeks) > 1:
        st.markdown("**Program Overview:**")
        week_cols = st.columns(min(len(weeks), 8))
        for i, week in enumerate(weeks[:8]):  # Show max 8 weeks
            with week_cols[i]:
                type_info = WEEK_TYPES.get(
                    week.get("type", "training"), WEEK_TYPES["training"]
                )
                is_current = i == current_idx
                border = "3px solid #fff" if is_current else "1px solid #555"

                st.markdown(
                    f"""<div style='text-align:center;padding:8px;background-color:{type_info['color']};
                    color:white;border-radius:8px;border:{border};cursor:pointer;font-size:0.8em;'>
                    W{i+1}<br/><small>{type_info['name'][:3]}</small></div>""",
                    unsafe_allow_html=True,
                )

        if len(weeks) > 8:
            st.caption(f"... and {len(weeks) - 8} more weeks")


def render_week_stats_panel(week_days, exercises):
    """Render the week statistics panel."""
    stats = calculate_week_stats(week_days, exercises)

    st.markdown("### 📊 Week Stats")

    # Set totals
    st.markdown("**Set Categories**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total", stats["total_sets"])
    with col2:
        st.metric("Strength", stats["strength_sets"], help="1-6 reps")
    with col3:
        st.metric("Hypertrophy", stats["hypertrophy_sets"], help=">6 reps")

    st.markdown("---")

    # Body region split
    st.markdown("**Body Region Split**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Upper", stats["upper_sets"])
    with col2:
        st.metric("Lower", stats["lower_sets"])
    with col3:
        st.metric("Core", stats["core_sets"])

    st.markdown("---")

    # Push/Pull/Legs split
    st.markdown("**Movement Pattern Split**")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Push", stats["push_sets"])
    with col2:
        st.metric("Pull", stats["pull_sets"])
    with col3:
        st.metric("Legs", stats["legs_sets"])

    return stats


def render_day_stats_panel(day_exercises, exercises, selected_day):
    """Render the day statistics panel with muscle breakdown."""
    stats = calculate_day_stats(day_exercises, exercises)

    st.markdown(f"### 📅 {selected_day} Stats")

    # Quick metrics
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Sets", stats["total_sets"])
    with col2:
        rep_type = (
            "Str" if stats["strength_sets"] > stats["hypertrophy_sets"] else "Hyp"
        )
        st.metric("Focus", rep_type)

    st.markdown("---")

    # Muscle breakdown
    st.markdown("**Muscle Breakdown**")

    if stats["muscle_breakdown"]:
        # Group muscles by body region
        upper_muscles = [
            "front deltoids",
            "side deltoids",
            "rear deltoids",
            "rotator cuff",
            "chest",
            "triceps",
            "biceps",
            "lats",
            "traps",
            "middle back",
            "forearms",
        ]
        core_muscles = ["abdominals", "lower back"]
        lower_muscles = [
            "glutes",
            "quadriceps",
            "hamstrings",
            "calves",
            "adductors",
            "abductors",
        ]

        # Upper body
        upper_data = {
            m: stats["muscle_breakdown"].get(m, 0)
            for m in upper_muscles
            if stats["muscle_breakdown"].get(m, 0) > 0
        }
        if upper_data:
            st.markdown("*Upper Body*")
            for muscle, sets in sorted(upper_data.items(), key=lambda x: -x[1]):
                st.markdown(f"- {muscle.title()}: **{sets:.1f}** sets")

        # Core
        core_data = {
            m: stats["muscle_breakdown"].get(m, 0)
            for m in core_muscles
            if stats["muscle_breakdown"].get(m, 0) > 0
        }
        if core_data:
            st.markdown("*Core*")
            for muscle, sets in sorted(core_data.items(), key=lambda x: -x[1]):
                st.markdown(f"- {muscle.title()}: **{sets:.1f}** sets")

        # Lower body
        lower_data = {
            m: stats["muscle_breakdown"].get(m, 0)
            for m in lower_muscles
            if stats["muscle_breakdown"].get(m, 0) > 0
        }
        if lower_data:
            st.markdown("*Lower Body*")
            for muscle, sets in sorted(lower_data.items(), key=lambda x: -x[1]):
                st.markdown(f"- {muscle.title()}: **{sets:.1f}** sets")
    else:
        st.caption("No exercises added yet")

    return stats


def render_body_diagrams(muscle_breakdown):
    """Render the anatomical body diagrams with muscle volume coloring."""
    import streamlit.components.v1 as components

    st.markdown("### 🏋️ Muscle Map")

    if muscle_breakdown:
        # Aggregate volumes for SVG
        aggregated = aggregate_muscle_volumes(dict(muscle_breakdown))

        # Generate and display the combined diagram using components.html for proper SVG rendering
        diagram_html = generate_combined_body_diagram(aggregated)

        # Wrap in a full HTML document for proper rendering
        full_html = f"""
        <html>
        <head>
            <style>
                body {{ margin: 0; padding: 10px; font-family: sans-serif; background: transparent; }}
                .muscle {{ stroke: #333; stroke-width: 1; }}
                .label {{ font-size: 8px; fill: #666; text-anchor: middle; }}
            </style>
        </head>
        <body>
            {diagram_html}
        </body>
        </html>
        """

        components.html(full_html, height=350, scrolling=False)

        # Legend
        legend_html = get_volume_legend_html()
        st.markdown(legend_html, unsafe_allow_html=True)
    else:
        st.caption("Add exercises to see muscle activation")


def render_mesocycle_graphs(exercises):
    """
    Render volume/intensity graphs across all weeks in the program.
    Shows volume progression for mesocycle planning.
    """
    weeks = st.session_state.program_weeks

    if len(weeks) < 2:
        st.info("Add more weeks to see mesocycle progression graphs")
        return

    st.markdown("### 📈 Mesocycle Overview")

    # Calculate stats for each week
    week_data = []
    for i, week in enumerate(weeks):
        stats = calculate_week_stats(week["days"], exercises)
        week_data.append(
            {
                "Week": f"W{i+1}",
                "Week Name": week["name"],
                "Type": WEEK_TYPES.get(week["type"], WEEK_TYPES["training"])["name"],
                "Total Sets": stats["total_sets"],
                "Strength Sets": stats["strength_sets"],
                "Hypertrophy Sets": stats["hypertrophy_sets"],
                "Upper Sets": stats["upper_sets"],
                "Lower Sets": stats["lower_sets"],
                "Core Sets": stats["core_sets"],
            }
        )

    df = pd.DataFrame(week_data)

    # Graph selection
    graph_type = st.radio(
        "Select graph",
        ["Volume by Week", "Set Type Split", "Body Region Split"],
        horizontal=True,
        key="mesocycle_graph_type",
    )

    if graph_type == "Volume by Week":
        # Line chart showing total volume per week
        fig = go.Figure()

        # Add total sets line
        fig.add_trace(
            go.Scatter(
                x=df["Week"],
                y=df["Total Sets"],
                mode="lines+markers+text",
                name="Total Sets",
                line=dict(width=3, color="#1976D2"),
                marker=dict(size=10),
                text=df["Total Sets"],
                textposition="top center",
            )
        )

        # Color bars by week type
        colors = [
            WEEK_TYPES.get(weeks[i]["type"], WEEK_TYPES["training"])["color"]
            for i in range(len(weeks))
        ]

        fig.add_trace(
            go.Bar(
                x=df["Week"],
                y=df["Total Sets"],
                marker_color=colors,
                opacity=0.3,
                name="Week Type",
                showlegend=False,
            )
        )

        fig.update_layout(
            title="Weekly Volume Progression",
            xaxis_title="Week",
            yaxis_title="Total Sets",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
        )

        st.plotly_chart(fig, use_container_width=True)

    elif graph_type == "Set Type Split":
        # Stacked bar chart for strength vs hypertrophy
        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=df["Week"],
                y=df["Strength Sets"],
                name="Strength (1-6 reps)",
                marker_color="#FF5722",
            )
        )

        fig.add_trace(
            go.Bar(
                x=df["Week"],
                y=df["Hypertrophy Sets"],
                name="Hypertrophy (>6 reps)",
                marker_color="#4CAF50",
            )
        )

        fig.update_layout(
            title="Strength vs Hypertrophy Sets",
            xaxis_title="Week",
            yaxis_title="Sets",
            barmode="stack",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )

        st.plotly_chart(fig, use_container_width=True)

    else:  # Body Region Split
        # Stacked bar chart for body regions
        fig = go.Figure()

        fig.add_trace(
            go.Bar(
                x=df["Week"],
                y=df["Upper Sets"],
                name="Upper Body",
                marker_color="#2196F3",
            )
        )

        fig.add_trace(
            go.Bar(
                x=df["Week"],
                y=df["Lower Sets"],
                name="Lower Body",
                marker_color="#9C27B0",
            )
        )

        fig.add_trace(
            go.Bar(
                x=df["Week"],
                y=df["Core Sets"],
                name="Core",
                marker_color="#FF9800",
            )
        )

        fig.update_layout(
            title="Body Region Volume by Week",
            xaxis_title="Week",
            yaxis_title="Sets",
            barmode="stack",
            height=300,
            margin=dict(l=20, r=20, t=40, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )

        st.plotly_chart(fig, use_container_width=True)

    # Week type legend
    st.caption("Week type colors in Volume chart:")
    type_legend = " | ".join(
        [
            f"<span style='color:{info['color']}'>{info['name']}</span>"
            for info in WEEK_TYPES.values()
        ]
    )
    st.markdown(type_legend, unsafe_allow_html=True)


def render_day_editor_enhanced(
    day, exercises, exercise_names, display_to_name, name_to_display
):
    """
    Enhanced day editor with inline copy functionality.
    """
    week_idx = st.session_state.current_week
    week = st.session_state.program_weeks[week_idx]
    day_program = week["days"].get(day, [])

    # Inline copy day feature at the top
    with st.expander("📋 Copy from another day", expanded=False):
        other_days = [d for d in DAYS if d != day]
        col1, col2 = st.columns([3, 1])
        with col1:
            source_day = st.selectbox(
                "Copy from",
                options=other_days,
                key=f"copy_source_{day}",
                label_visibility="collapsed",
            )
        with col2:
            if st.button("Copy", key=f"copy_btn_{day}"):
                copy_day_to_day(source_day, day, week_idx)
                st.rerun()

    # Initialize edit state if needed
    if "editing_exercise" not in st.session_state:
        st.session_state.editing_exercise = None

    # Display existing exercises for this day
    if day_program:
        for i, entry in enumerate(day_program):
            edit_key = f"{day}_{week_idx}_{i}"
            is_editing = st.session_state.editing_exercise == edit_key

            # Get display name for current exercise
            current_display_name = name_to_display.get(
                entry["exercise"], entry["exercise"]
            )

            if is_editing:
                # Edit mode
                st.markdown(f"**✏️ Editing: {entry['exercise']}**")

                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    try:
                        current_index = exercise_names.index(current_display_name)
                    except ValueError:
                        current_index = 0

                    selected_display_name = st.selectbox(
                        "Exercise",
                        options=exercise_names,
                        index=current_index,
                        key=f"edit_ex_{edit_key}",
                    )
                    new_exercise = display_to_name.get(
                        selected_display_name, selected_display_name
                    )

                with col2:
                    new_sets = st.number_input(
                        "Sets",
                        min_value=1,
                        max_value=10,
                        value=entry["sets"],
                        key=f"edit_sets_{edit_key}",
                    )

                with col3:
                    new_reps = st.number_input(
                        "Reps",
                        min_value=1,
                        max_value=30,
                        value=entry["reps"],
                        key=f"edit_reps_{edit_key}",
                    )

                col_save, col_cancel = st.columns(2)
                with col_save:
                    if st.button("💾 Save", key=f"save_{edit_key}"):
                        week["days"][day][i] = {
                            "exercise": new_exercise,
                            "sets": new_sets,
                            "reps": new_reps,
                        }
                        st.session_state.editing_exercise = None
                        st.rerun()

                with col_cancel:
                    if st.button("❌ Cancel", key=f"cancel_{edit_key}"):
                        st.session_state.editing_exercise = None
                        st.rerun()

                st.markdown("---")

            else:
                # Display mode
                col1, col2, col3, col4, col_info, col6, col7 = st.columns(
                    [3, 1, 1, 1, 0.5, 0.5, 0.5]
                )

                with col1:
                    st.text(entry["exercise"])
                with col2:
                    st.text(f"{entry['sets']} sets")
                with col3:
                    st.text(f"{entry['reps']} reps")
                with col4:
                    rep_type = "💪 Hyp" if entry["reps"] > 6 else "🏋️ Str"
                    st.text(rep_type)
                with col_info:
                    details_key = f"show_details_{edit_key}"
                    if st.button(
                        "ℹ️", key=f"info_{edit_key}", help="View exercise details"
                    ):
                        st.session_state[details_key] = not st.session_state.get(
                            details_key, False
                        )
                        st.rerun()
                with col6:
                    if st.button("✏️", key=f"edit_{edit_key}", help="Edit exercise"):
                        st.session_state.editing_exercise = edit_key
                        st.rerun()
                with col7:
                    if st.button("🗑️", key=f"remove_{edit_key}", help="Remove exercise"):
                        week["days"][day].pop(i)
                        st.rerun()

                # Show muscle contribution
                exercise_info = get_exercise_by_name(exercises, entry["exercise"])
                if exercise_info:
                    target = get_primary_muscle(exercise_info)
                    synergists = get_secondary_muscles(exercise_info)
                    num_sets = entry["sets"]

                    if entry["reps"] > 6:
                        contrib_parts = [f"**{target}**: {num_sets:.0f}"]
                        for syn in synergists[:2]:
                            if syn:
                                contrib_parts.append(f"{syn}: {num_sets * 0.5:.1f}")
                        st.caption(f"   ↳ {' | '.join(contrib_parts)}")
                    else:
                        st.caption(
                            f"   ↳ {entry['exercise']}: {num_sets:.0f} direct | {target}"
                        )

                # Show details if toggled
                details_key = f"show_details_{edit_key}"
                if st.session_state.get(details_key, False):
                    with st.container():
                        st.markdown("---")
                        render_exercise_details(
                            exercise_info,
                            show_images=True,
                            show_instructions=True,
                            key_prefix=edit_key,
                        )
                        if st.button("Close", key=f"close_{edit_key}"):
                            st.session_state[details_key] = False
                            st.rerun()

                st.markdown("")

    else:
        st.caption("No exercises added yet")

    # Add new exercise form
    with st.expander("➕ Add Exercise"):
        selected_display_name = st.selectbox(
            "Exercise",
            options=exercise_names,
            key=f"select_{day}_{week_idx}",
        )
        selected_exercise = display_to_name.get(
            selected_display_name, selected_display_name
        )

        # Show exercise info
        if selected_exercise:
            exercise = get_exercise_by_name(exercises, selected_exercise)
            if exercise:
                primary = get_primary_muscle(exercise)
                secondary = get_secondary_muscles(exercise)
                st.caption(f"**Target:** {primary}")
                if secondary:
                    st.caption(f"**Synergists:** {', '.join(secondary[:3])}")

        col1, col2 = st.columns(2)
        with col1:
            sets = st.number_input(
                "Sets", min_value=1, max_value=10, value=3, key=f"sets_{day}_{week_idx}"
            )
        with col2:
            reps = st.number_input(
                "Reps",
                min_value=1,
                max_value=30,
                value=10,
                key=f"reps_{day}_{week_idx}",
            )

        # 1RM section - inline add/edit
        if selected_exercise:
            current_1rm = st.session_state.exercise_1rm.get(selected_exercise, 0)

            with st.container():
                st.markdown("**🎯 1RM & Weight Suggestion**")

                if current_1rm > 0:
                    # Show current 1RM and suggested weight
                    suggested_weight = get_weight_for_reps(current_1rm, reps)
                    training_type = "Strength" if reps <= 6 else "Hypertrophy"
                    pct = (suggested_weight / current_1rm) * 100

                    col_rm, col_weight = st.columns(2)
                    with col_rm:
                        new_1rm = st.number_input(
                            "1RM (kg)",
                            min_value=0.0,
                            max_value=500.0,
                            value=float(current_1rm),
                            step=2.5,
                            key=f"1rm_{day}_{week_idx}",
                            help="Your one-rep max for this exercise",
                        )
                        if new_1rm != current_1rm and new_1rm > 0:
                            st.session_state.exercise_1rm[selected_exercise] = new_1rm
                            st.rerun()
                    with col_weight:
                        st.metric(
                            f"Suggested ({training_type})",
                            f"{suggested_weight:.1f} kg",
                            f"{pct:.0f}% of 1RM",
                        )
                else:
                    # No 1RM set - offer to add one
                    st.caption("No 1RM set - add one for weight suggestions")

                    rm_method = st.radio(
                        "Add 1RM",
                        ["Enter directly", "Calculate from lift"],
                        key=f"rm_method_{day}_{week_idx}",
                        horizontal=True,
                    )

                    if rm_method == "Enter directly":
                        new_1rm = st.number_input(
                            "1RM (kg)",
                            min_value=0.0,
                            max_value=500.0,
                            value=0.0,
                            step=2.5,
                            key=f"new_1rm_{day}_{week_idx}",
                        )
                        if new_1rm > 0:
                            if st.button(
                                "💾 Save 1RM", key=f"save_1rm_{day}_{week_idx}"
                            ):
                                st.session_state.exercise_1rm[selected_exercise] = (
                                    new_1rm
                                )
                                st.rerun()
                    else:
                        col_w, col_r = st.columns(2)
                        with col_w:
                            lift_weight = st.number_input(
                                "Weight lifted (kg)",
                                min_value=0.0,
                                max_value=500.0,
                                value=0.0,
                                step=2.5,
                                key=f"lift_weight_{day}_{week_idx}",
                            )
                        with col_r:
                            lift_reps = st.number_input(
                                "Reps completed",
                                min_value=1,
                                max_value=30,
                                value=5,
                                key=f"lift_reps_{day}_{week_idx}",
                            )

                        if lift_weight > 0:
                            est_1rm = calculate_1rm_from_reps(lift_weight, lift_reps)
                            st.info(f"Estimated 1RM: **{est_1rm:.1f} kg**")
                            if st.button(
                                "💾 Save Est. 1RM", key=f"save_est_1rm_{day}_{week_idx}"
                            ):
                                st.session_state.exercise_1rm[selected_exercise] = (
                                    est_1rm
                                )
                                st.rerun()

        # Real-time fractional set preview
        if selected_exercise:
            exercise = get_exercise_by_name(exercises, selected_exercise)
            if exercise:
                primary = get_primary_muscle(exercise)
                secondary = get_secondary_muscles(exercise)
                is_hypertrophy = reps > 6

                st.markdown("---")
                if is_hypertrophy:
                    st.markdown("**📊 Fractional Set Preview (Hypertrophy)**")
                    preview_parts = [f"**{primary}**: +{sets:.1f} sets"]
                    for syn in secondary[:4]:
                        if syn:
                            preview_parts.append(f"{syn}: +{sets * 0.5:.1f}")
                    st.success(f"→ {' | '.join(preview_parts)}")
                else:
                    st.markdown("**📊 Fractional Set Preview (Strength)**")
                    st.info(
                        f"→ **{selected_exercise}**: +{sets} strength sets | Primary: {primary}"
                    )
                st.markdown("---")

        if st.button("Add Exercise", key=f"add_{day}_{week_idx}"):
            week["days"][day].append(
                {
                    "exercise": selected_exercise,
                    "sets": sets,
                    "reps": reps,
                }
            )
            st.rerun()


def render_user_profile_compact():
    """Render a compact user profile widget for the weekly editor sidebar."""
    profile = st.session_state.user_profile
    targets = get_volume_targets()

    with st.expander("👤 Profile & Targets", expanded=True):
        # Training status
        selected_status = st.selectbox(
            "Training Status",
            options=list(TRAINING_STATUS.keys()),
            index=list(TRAINING_STATUS.keys()).index(profile["training_status"]),
            key="compact_profile_status",
            help="Your experience level affects volume recommendations",
        )
        if selected_status != profile["training_status"]:
            st.session_state.user_profile["training_status"] = selected_status
            st.rerun()

        # Volume tier
        selected_tier = st.selectbox(
            "Volume Tier",
            options=list(VOLUME_TIERS.keys()),
            index=list(VOLUME_TIERS.keys()).index(profile["volume_tier"]),
            key="compact_profile_tier",
            help="How much time can you dedicate to training?",
        )
        if selected_tier != profile["volume_tier"]:
            st.session_state.user_profile["volume_tier"] = selected_tier
            st.rerun()

        # Show current targets
        st.markdown("**🎯 Weekly Targets**")
        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                "Hyp",
                f"{targets['hypertrophy']['low']}-{targets['hypertrophy']['high']}",
                help="Sets per muscle group for hypertrophy",
            )
        with col2:
            st.metric(
                "Str",
                f"{targets['strength']['low']}-{targets['strength']['high']}",
                help="Sets per lift for strength",
            )

        # Custom targets toggle
        use_custom = st.checkbox(
            "Custom targets",
            value=profile["use_custom_targets"],
            key="compact_use_custom",
        )
        if use_custom != profile["use_custom_targets"]:
            st.session_state.user_profile["use_custom_targets"] = use_custom
            st.rerun()

        if use_custom:
            custom_hyp = st.number_input(
                "Hypertrophy target",
                min_value=4,
                max_value=30,
                value=profile["custom_hypertrophy_target"],
                key="compact_custom_hyp",
            )
            if custom_hyp != profile["custom_hypertrophy_target"]:
                st.session_state.user_profile["custom_hypertrophy_target"] = custom_hyp
                st.rerun()

            custom_str = st.number_input(
                "Strength target",
                min_value=1,
                max_value=10,
                value=profile["custom_strength_target"],
                key="compact_custom_str",
            )
            if custom_str != profile["custom_strength_target"]:
                st.session_state.user_profile["custom_strength_target"] = custom_str
                st.rerun()


def render_analysis_filters(exercises):
    """Render analysis tracking filters for muscle groups and strength exercises."""
    profile = st.session_state.user_profile

    with st.expander("🔬 Analysis Filters", expanded=False):
        # --- Hypertrophy Muscle Tracking ---
        st.markdown("**💪 Hypertrophy Muscles**")
        st.caption("Select which muscle groups to include in volume analysis")

        current_hyp = profile.get("hypertrophy_tracked_muscles")
        all_muscles = [m.title() for m in ALL_MUSCLE_GROUPS]
        is_tracking_all = current_hyp is None

        track_all_hyp = st.checkbox(
            "Track all muscle groups",
            value=is_tracking_all,
            key="hyp_track_all_cb",
        )

        if track_all_hyp:
            if not is_tracking_all:
                st.session_state.user_profile["hypertrophy_tracked_muscles"] = None
                st.rerun()
        else:
            # Show muscle group picker
            if is_tracking_all:
                default_muscles = all_muscles
            else:
                default_muscles = [
                    m.title() for m in current_hyp if m.title() in all_muscles
                ]

            selected_muscles = st.multiselect(
                "Tracked muscles",
                options=all_muscles,
                default=default_muscles,
                key="hyp_muscles_ms",
                label_visibility="collapsed",
            )
            # Sync selection to profile
            st.session_state.user_profile["hypertrophy_tracked_muscles"] = [
                m.lower() for m in selected_muscles
            ]

        st.markdown("---")

        # --- Strength Exercise Tracking ---
        st.markdown("**🏋️ Strength Exercises**")
        st.caption("Select which exercises to track for strength volume")

        mode = profile.get("strength_tracking_mode", "compound")
        mode_options = ["compound", "all", "custom"]
        mode_labels = {
            "compound": "Big 5 lifts (squat, deadlift, bench, OHP, row)",
            "all": "All exercises",
            "custom": "Custom selection",
        }

        new_mode = st.radio(
            "Strength tracking mode",
            options=mode_options,
            format_func=lambda x: mode_labels[x],
            index=mode_options.index(mode) if mode in mode_options else 0,
            key="str_mode_radio",
            label_visibility="collapsed",
        )

        if new_mode != mode:
            st.session_state.user_profile["strength_tracking_mode"] = new_mode
            st.rerun()

        if new_mode == "compound":
            # Show Big 5 coverage by category
            current_program = {}
            if st.session_state.program_weeks:
                week_idx = st.session_state.current_week
                current_program = st.session_state.program_weeks[week_idx]["days"]

            covered, missing = get_big5_coverage(current_program)

            for cat in BIG_5_CATEGORIES:
                if cat in covered:
                    exs = covered[cat]
                    ex_names = sorted(set(e["exercise"] for e in exs))
                    st.caption(f"  ✅ {cat}: {', '.join(ex_names)}")
                else:
                    st.caption(f"  ❌ {cat}: *not in program*")

            if missing:
                st.warning(
                    f"Missing {len(missing)}/{len(BIG_5_CATEGORIES)}: "
                    f"{', '.join(missing)}"
                )

        elif new_mode == "custom":
            current_custom = profile.get("strength_tracked_exercises", [])

            # Gather all exercises from all weeks
            program_exercises = set()
            for week in st.session_state.program_weeks:
                for day_exs in week["days"].values():
                    for entry in day_exs:
                        program_exercises.add(entry["exercise"])

            all_ex_options = sorted(program_exercises | set(current_custom))

            if all_ex_options:
                selected_exs = st.multiselect(
                    "Tracked exercises",
                    options=all_ex_options,
                    default=[e for e in current_custom if e in all_ex_options],
                    key="str_exercises_ms",
                    label_visibility="collapsed",
                )
                st.session_state.user_profile[
                    "strength_tracked_exercises"
                ] = selected_exs
            else:
                st.caption("Add exercises to your program first")


def render_weekly_editor_enhanced(
    exercises, exercise_names, display_to_name, name_to_display
):
    """
    Enhanced weekly editor with multi-week support and stats panel.
    Uses 70/30 column layout.
    """
    # Week navigation at the top
    render_week_navigation()

    st.markdown("---")

    # Get current week data
    week_idx = st.session_state.current_week
    week = st.session_state.program_weeks[week_idx]
    week_days = week["days"]

    # Workout sheet for current week at the top
    with st.expander("📄 Workout Sheet (click to expand)", expanded=False):
        render_workout_sheet(week_days, show_header=False)

    st.markdown("---")

    # Two-column layout: 70% editor, 30% stats
    col_editor, col_stats = st.columns([7, 3])

    with col_editor:
        st.header("✏️ Edit Program")

        # Day tabs
        day_tabs = st.tabs(DAYS)

        for i, day in enumerate(DAYS):
            with day_tabs[i]:
                # Track selected day for stats panel
                if st.session_state.selected_day != day:
                    # This won't trigger on first render, which is fine
                    pass

                render_day_editor_enhanced(
                    day, exercises, exercise_names, display_to_name, name_to_display
                )

    with col_stats:
        # Compact user profile at top of stats panel
        render_user_profile_compact()

        # Analysis filter settings
        render_analysis_filters(exercises)

        st.markdown("---")

        # Week stats panel
        week_stats = render_week_stats_panel(week_days, exercises)

        st.markdown("---")

        # Body diagrams showing muscle volume
        render_body_diagrams(week_stats["muscle_breakdown"])

        st.markdown("---")

        # Day stats panel - use selectbox to choose day
        selected_day = st.selectbox(
            "View day stats",
            options=DAYS,
            key="stats_day_selector",
        )
        day_exercises = week_days.get(selected_day, [])
        render_day_stats_panel(day_exercises, exercises, selected_day)

    # Mesocycle graphs below the main editor (full width)
    if len(st.session_state.program_weeks) > 1:
        st.markdown("---")
        with st.expander("📈 Mesocycle Progression Graphs", expanded=False):
            render_mesocycle_graphs(exercises)


def generate_exercise_id(name):
    """Generate an ID from exercise name (similar to free-exercise-db format)."""
    # Replace spaces and special characters with underscores
    import re

    # Remove special characters except spaces, replace spaces with underscores
    clean_name = re.sub(r"[^a-zA-Z0-9\s]", "", name)
    return clean_name.replace(" ", "_")


def get_all_exercises(base_exercises):
    """
    Merge base exercises with custom exercises.
    Custom exercises are displayed first and include their source in the name.
    """
    all_exercises = []

    # Add custom exercises first (they appear at top of lists)
    for source_name, exercises in st.session_state.get("custom_exercises", {}).items():
        for ex in exercises:
            # Create a copy with source information
            ex_with_source = ex.copy()
            ex_with_source["_source"] = source_name
            ex_with_source["_display_name"] = f"{ex['name']} [{source_name}]"
            all_exercises.append(ex_with_source)

    # Add base exercises (from free-exercise-db)
    for ex in base_exercises:
        ex_with_source = ex.copy()
        ex_with_source["_source"] = "free-exercise-db"
        ex_with_source["_display_name"] = ex["name"]
        all_exercises.append(ex_with_source)

    return all_exercises


def get_exercise_display_name(exercise):
    """Get the display name for an exercise (includes source for custom exercises)."""
    return exercise.get("_display_name", exercise.get("name", "Unknown"))


def add_custom_exercise(source_name, exercise):
    """Add a custom exercise to a source collection."""
    if source_name not in st.session_state.custom_exercises:
        st.session_state.custom_exercises[source_name] = []

    # Generate ID if not provided
    if "id" not in exercise or not exercise["id"]:
        exercise["id"] = generate_exercise_id(exercise["name"])

    # Check for duplicates within the same source
    existing_names = [
        e["name"].lower() for e in st.session_state.custom_exercises[source_name]
    ]
    if exercise["name"].lower() not in existing_names:
        st.session_state.custom_exercises[source_name].append(exercise)
        return True
    return False


def remove_custom_exercise(source_name, exercise_name):
    """Remove a custom exercise from a source collection."""
    if source_name in st.session_state.custom_exercises:
        st.session_state.custom_exercises[source_name] = [
            e
            for e in st.session_state.custom_exercises[source_name]
            if e["name"] != exercise_name
        ]
        # Remove empty sources
        if not st.session_state.custom_exercises[source_name]:
            del st.session_state.custom_exercises[source_name]


def import_custom_exercises_from_json(json_data, source_name):
    """
    Import exercises from JSON data.
    Expects either a list of exercises or a single exercise object.
    Returns (success_count, error_count, errors).
    """
    success_count = 0
    error_count = 0
    errors = []

    # Handle single exercise or list
    if isinstance(json_data, dict):
        exercises = [json_data]
    elif isinstance(json_data, list):
        exercises = json_data
    else:
        return 0, 1, ["Invalid JSON format: expected object or array"]

    for i, ex in enumerate(exercises):
        # Validate required fields
        if not isinstance(ex, dict):
            errors.append(f"Item {i}: Not a valid object")
            error_count += 1
            continue

        if "name" not in ex or not ex["name"]:
            errors.append(f"Item {i}: Missing required field 'name'")
            error_count += 1
            continue

        if "primaryMuscles" not in ex or not ex["primaryMuscles"]:
            errors.append(
                f"Item {i} ({ex.get('name', 'unknown')}): Missing required field 'primaryMuscles'"
            )
            error_count += 1
            continue

        if "secondaryMuscles" not in ex:
            ex["secondaryMuscles"] = []  # Default to empty if not provided

        # Create clean exercise object
        clean_exercise = {
            "name": ex["name"],
            "primaryMuscles": ex["primaryMuscles"],
            "secondaryMuscles": ex.get("secondaryMuscles", []),
            "id": ex.get("id") or generate_exercise_id(ex["name"]),
            "force": ex.get("force"),
            "level": ex.get("level"),
            "mechanic": ex.get("mechanic"),
            "equipment": ex.get("equipment"),
            "instructions": ex.get("instructions", []),
            "category": ex.get("category"),
            "images": ex.get("images", []),
        }

        if add_custom_exercise(source_name, clean_exercise):
            success_count += 1
        else:
            errors.append(f"'{ex['name']}': Duplicate exercise name in source")
            error_count += 1

    return success_count, error_count, errors


def export_custom_exercises(source_name=None):
    """Export custom exercises to JSON format."""
    if source_name:
        return st.session_state.custom_exercises.get(source_name, [])
    return st.session_state.custom_exercises


def calculate_1rm_from_reps(weight, reps):
    """Calculate estimated 1RM using Epley formula."""
    if reps == 1:
        return weight
    return weight * (1 + reps / 30)


def get_weight_for_reps(one_rm, target_reps):
    """Calculate weight for target reps based on 1RM (inverse Epley)."""
    if target_reps == 1:
        return one_rm
    return one_rm / (1 + target_reps / 30)


def get_training_recommendations(one_rm):
    """
    Get training recommendations based on 1RM.
    Returns dict with strength, hypertrophy, and endurance recommendations.
    """
    recommendations = {
        "strength": {
            "description": "Strength (1-5 reps)",
            "percentage_range": (85, 100),
            "rep_ranges": [
                {"reps": 1, "weight": one_rm * 1.00, "pct": 100},
                {"reps": 2, "weight": one_rm * 0.95, "pct": 95},
                {"reps": 3, "weight": one_rm * 0.93, "pct": 93},
                {"reps": 4, "weight": one_rm * 0.90, "pct": 90},
                {"reps": 5, "weight": one_rm * 0.87, "pct": 87},
            ],
        },
        "hypertrophy": {
            "description": "Hypertrophy (6-12 reps)",
            "percentage_range": (65, 85),
            "rep_ranges": [
                {"reps": 6, "weight": one_rm * 0.85, "pct": 85},
                {"reps": 8, "weight": one_rm * 0.80, "pct": 80},
                {"reps": 10, "weight": one_rm * 0.75, "pct": 75},
                {"reps": 12, "weight": one_rm * 0.70, "pct": 70},
            ],
        },
        "endurance": {
            "description": "Muscular Endurance (15+ reps)",
            "percentage_range": (50, 65),
            "rep_ranges": [
                {"reps": 15, "weight": one_rm * 0.65, "pct": 65},
                {"reps": 20, "weight": one_rm * 0.60, "pct": 60},
            ],
        },
    }
    return recommendations


def get_volume_targets():
    """Get current volume targets based on user profile."""
    profile = st.session_state.user_profile

    if profile["use_custom_targets"]:
        return {
            "hypertrophy": {
                "low": profile["custom_hypertrophy_target"],
                "high": profile["custom_hypertrophy_target"],
            },
            "strength": {
                "low": profile["custom_strength_target"],
                "high": profile["custom_strength_target"],
            },
        }

    # Use volume tier targets
    tier = VOLUME_TIERS[profile["volume_tier"]]
    status = TRAINING_STATUS[profile["training_status"]]

    # Adjust based on training status
    base_low, base_high = tier["sets_range"]
    multiplier = status["volume_multiplier"]

    return {
        "hypertrophy": {
            "low": max(4, int(base_low * multiplier)),
            "high": min(30, int(base_high * multiplier)),
        },
        "strength": {
            "low": 3,  # Practical ED minimum
            "high": 5,  # Practical ED maximum (short-term)
        },
    }


def render_user_profile():
    """Render user profile settings."""
    st.header("👤 User Profile & Volume Settings")
    st.caption("Configure your training status and volume targets")

    profile = st.session_state.user_profile

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Training Status")

        # Training status selection
        selected_status = st.selectbox(
            "Your Training Status",
            options=list(TRAINING_STATUS.keys()),
            index=list(TRAINING_STATUS.keys()).index(profile["training_status"]),
            key="profile_training_status",
        )

        if selected_status != profile["training_status"]:
            st.session_state.user_profile["training_status"] = selected_status

        # Show status details
        status_info = TRAINING_STATUS[selected_status]
        st.info(f"**{selected_status}**: {status_info['description']}")
        st.caption(f"📈 Expected progression: {status_info['progression']}")
        st.caption(f"⏱️ Typical duration: {status_info['duration']}")

        # Training status reference
        with st.expander("📚 Training Status Definitions"):
            st.markdown(
                """
                **Based on The Muscle & Strength Pyramid (Table 7.14)**
                
                | Status | Definition | Progress Rate |
                |--------|------------|---------------|
                | **Novice** | First months-years of training | Add load/reps each session or week |
                | **Intermediate** | Years 1-5 of consistent training | Add reps weekly, load monthly |
                | **Advanced** | 5+ years, near genetic potential | Small gains over months |
                
                **Key Points:**
                - Minimum volume produces gains in novices but only maintenance in advanced lifters
                - Advanced lifters need lower RIR (closer to failure) for stimulus
                - Don't overestimate your status - most lifters are intermediate
                """
            )

    with col2:
        st.subheader("📈 Volume Tier")

        # Volume tier selection
        selected_tier = st.selectbox(
            "Volume Tier (Time Commitment)",
            options=list(VOLUME_TIERS.keys()),
            index=list(VOLUME_TIERS.keys()).index(profile["volume_tier"]),
            key="profile_volume_tier",
        )

        if selected_tier != profile["volume_tier"]:
            st.session_state.user_profile["volume_tier"] = selected_tier

        # Show tier details
        tier_info = VOLUME_TIERS[selected_tier]
        st.info(
            f"**{tier_info['sets_range'][0]}-{tier_info['sets_range'][1]}** sets/muscle/week"
        )
        st.caption(f"⏱️ {tier_info['time_commitment']}")
        st.caption(f"💪 Stimulus per set: {tier_info['avg_stimulus_per_set']}")
        st.caption(f"📊 Total stimulus: {tier_info['total_stimulus']}")

        # Volume tier reference table
        with st.expander("📚 Volume Tier Reference (Table 7.4)"):
            tier_data = []
            for name, info in VOLUME_TIERS.items():
                tier_data.append(
                    {
                        "Tier": name,
                        "Sets/Week": f"{info['sets_range'][0]}-{info['sets_range'][1]}",
                        "Time": info["time_commitment"],
                        "Stimulus/Set": info["avg_stimulus_per_set"],
                        "Frequency": f"{info['frequency_range'][0]}-{info['frequency_range'][1]}x",
                    }
                )
            st.dataframe(
                pd.DataFrame(tier_data), use_container_width=True, hide_index=True
            )

    # Custom volume targets section
    st.markdown("---")
    st.subheader("🎯 Custom Volume Targets")

    use_custom = st.checkbox(
        "Use custom volume targets (override tier recommendations)",
        value=profile["use_custom_targets"],
        key="profile_use_custom",
    )

    if use_custom != profile["use_custom_targets"]:
        st.session_state.user_profile["use_custom_targets"] = use_custom

    if use_custom:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**💪 Hypertrophy Target (sets/muscle/week)**")

            custom_hyp = st.slider(
                "Target hypertrophy sets per muscle group",
                min_value=4,
                max_value=30,
                value=profile["custom_hypertrophy_target"],
                key="profile_custom_hyp",
                help="Recommended range: 10-20 for practical ED",
            )

            if custom_hyp != profile["custom_hypertrophy_target"]:
                st.session_state.user_profile["custom_hypertrophy_target"] = custom_hyp

            # Show recommendation context
            if custom_hyp < 4:
                st.warning("⚠️ Below minimum effective dose (4 sets)")
            elif custom_hyp < 10:
                st.info("📉 Below practical range (10-20 sets)")
            elif custom_hyp <= 20:
                st.success("✅ Within practical range")
            elif custom_hyp <= 30:
                st.warning("⚠️ Above practical range - consider specialization phases")
            else:
                st.error("❌ Above maximum (30 sets)")

        with col2:
            st.markdown("**🏋️ Strength Target (sets/lift/week)**")

            custom_str = st.slider(
                "Target strength sets per main lift",
                min_value=1,
                max_value=10,
                value=profile["custom_strength_target"],
                key="profile_custom_str",
                help="Recommended range: 3-5 for practical ED (short-term)",
            )

            if custom_str != profile["custom_strength_target"]:
                st.session_state.user_profile["custom_strength_target"] = custom_str

            # Show recommendation context
            if custom_str < 1:
                st.warning("⚠️ Below minimum (1 set)")
            elif custom_str < 3:
                st.info("📉 Below practical range (3-5 sets)")
            elif custom_str <= 5:
                st.success("✅ Within practical range")
            else:
                st.warning("⚠️ Above short-term max (5 sets) - ensure adequate recovery")

        st.caption(
            "💡 **Tip:** These targets will be used in Program Analysis and Program Designer. "
            "Recommendations shown are based on The Muscle & Strength Pyramid guidelines."
        )
    else:
        # Show calculated targets based on tier and status
        targets = get_volume_targets()
        st.info(
            f"**Current Targets** (based on {profile['volume_tier']} tier + {profile['training_status']} status): "
            f"Hypertrophy: {targets['hypertrophy']['low']}-{targets['hypertrophy']['high']} sets/muscle/week | "
            f"Strength: {targets['strength']['low']}-{targets['strength']['high']} sets/lift/week"
        )

    # Recommendations summary
    st.markdown("---")
    st.subheader("📋 Your Personalized Recommendations")

    targets = get_volume_targets()
    tier_info = VOLUME_TIERS[profile["volume_tier"]]

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**📊 Volume**")
        st.markdown(
            f"- Hypertrophy: **{targets['hypertrophy']['low']}-{targets['hypertrophy']['high']}** sets/muscle/wk"
        )
        st.markdown(
            f"- Strength: **{targets['strength']['low']}-{targets['strength']['high']}** sets/lift/wk"
        )

    with col2:
        st.markdown("**🔄 Frequency**")
        freq = tier_info["frequency_range"]
        st.markdown(f"- Per muscle: **{freq[0]}-{freq[1]}x**/week")
        st.markdown(f"- Main lifts: **2-6x**/week")

    with col3:
        st.markdown("**⚖️ Intensity**")
        st.markdown("- Hypertrophy: 4-30 RM (30-90% 1RM)")
        st.markdown("- Strength: 1-8 RM (80%+ 1RM)")


# =============================================================================
# Analysis Filter Functions
# =============================================================================


def get_tracked_hypertrophy_muscles():
    """
    Get the set of muscles to include in hypertrophy analysis.
    Returns None if all muscles should be tracked (default).
    Returns a set of title-cased muscle names if filtered.
    """
    tracked = st.session_state.user_profile.get("hypertrophy_tracked_muscles")
    if not tracked:
        return None  # All muscles
    return set(m.title() for m in tracked)


def get_tracked_strength_exercises(exercises):
    """
    Get the set of exercise names to include in strength analysis.
    Returns None if all exercises should be tracked.
    Returns a set of exercise names if filtered.

    Modes:
    - "compound": Big 5 lifts - squat, deadlift, bench, OHP, row (default)
    - "all": All exercises (no filter)
    - "custom": User-selected exercises
    """
    mode = st.session_state.user_profile.get("strength_tracking_mode", "compound")

    if mode == "all":
        return None
    elif mode == "custom":
        custom = st.session_state.user_profile.get("strength_tracked_exercises", [])
        return set(custom) if custom else None
    else:  # compound (default) — Big 5 pattern matching
        return {ex["name"] for ex in exercises if is_big5_exercise(ex["name"])}


def filter_hypertrophy_results(hyp_sets):
    """Filter hypertrophy sets to only include tracked muscles."""
    tracked = get_tracked_hypertrophy_muscles()
    if tracked is None:
        return hyp_sets
    return {
        day: {m: s for m, s in muscles.items() if m in tracked}
        for day, muscles in hyp_sets.items()
    }


def filter_strength_results(str_sets, exercises):
    """Filter strength sets to only include tracked exercises."""
    tracked = get_tracked_strength_exercises(exercises)
    if tracked is None:
        return str_sets
    return {
        day: {e: s for e, s in exs.items() if e in tracked}
        for day, exs in str_sets.items()
    }


# =============================================================================
# Fractional Sets Calculation Functions
# =============================================================================


def calculate_hypertrophy_sets(program, exercises):
    """
    Calculate hypertrophy fractional sets (>6 reps).
    - 1.0 set for primary (target) muscle groups
    - 0.5 set for secondary (synergist) muscle groups
    Returns per-day and total breakdown.
    """
    daily_sets = {day: defaultdict(float) for day in DAYS}

    for day, day_exercises in program.items():
        for entry in day_exercises:
            # Only count sets with >6 reps
            if entry["reps"] <= 6:
                continue

            exercise = get_exercise_by_name(exercises, entry["exercise"])
            if not exercise:
                continue

            num_sets = entry["sets"]

            # Primary muscles: 1.0 set per set
            primary_muscles = exercise.get("primaryMuscles", [])
            for muscle in primary_muscles:
                if muscle:
                    daily_sets[day][muscle.title()] += num_sets * 1.0

            # Secondary muscles: 0.5 set per set
            secondary_muscles = exercise.get("secondaryMuscles", [])
            for syn in secondary_muscles:
                if syn:
                    daily_sets[day][syn.title()] += num_sets * 0.5

    return daily_sets


def calculate_strength_sets(program, exercises):
    """
    Calculate strength fractional sets (1-6 reps).
    - 1.0 set for the actual exercise performed
    - 0.5 set for exercises sharing muscle targets
    Returns per-day and total breakdown.
    """
    # Build exercise-to-muscles mapping
    exercise_muscles = {}
    for ex in exercises:
        muscles = set()
        for muscle in ex.get("primaryMuscles", []):
            if muscle:
                muscles.add(muscle.lower())
        for syn in ex.get("secondaryMuscles", []):
            if syn:
                muscles.add(syn.lower())
        exercise_muscles[ex["name"]] = muscles

    daily_sets = {day: defaultdict(float) for day in DAYS}

    for day, day_exercises in program.items():
        for entry in day_exercises:
            # Only count sets with 1-6 reps
            if entry["reps"] < 1 or entry["reps"] > 6:
                continue

            current_exercise = entry["exercise"]
            current_muscles = exercise_muscles.get(current_exercise, set())
            num_sets = entry["sets"]

            # 1.0 set for the actual exercise
            daily_sets[day][current_exercise] += num_sets * 1.0

            # 0.5 set for other exercises that share muscle targets
            for other_exercise, other_muscles in exercise_muscles.items():
                if (
                    other_exercise != current_exercise
                    and current_muscles & other_muscles
                ):
                    daily_sets[day][other_exercise] += num_sets * 0.5

    return daily_sets


def calculate_hypertrophy_sets_for_week(week_index, exercises):
    """
    Calculate hypertrophy sets for a specific week.

    Args:
        week_index: Index of the week to calculate
        exercises: Exercise library

    Returns:
        Dict of daily muscle sets
    """
    if 0 <= week_index < len(st.session_state.program_weeks):
        week = st.session_state.program_weeks[week_index]
        return calculate_hypertrophy_sets(week["days"], exercises)
    return {day: defaultdict(float) for day in DAYS}


def calculate_strength_sets_for_week(week_index, exercises):
    """
    Calculate strength sets for a specific week.

    Args:
        week_index: Index of the week to calculate
        exercises: Exercise library

    Returns:
        Dict of daily exercise sets
    """
    if 0 <= week_index < len(st.session_state.program_weeks):
        week = st.session_state.program_weeks[week_index]
        return calculate_strength_sets(week["days"], exercises)
    return {day: defaultdict(float) for day in DAYS}


def calculate_sets_for_current_week(exercises):
    """
    Calculate both hypertrophy and strength sets for the current week.

    Args:
        exercises: Exercise library

    Returns:
        Tuple of (hypertrophy_sets, strength_sets)
    """
    week_idx = st.session_state.current_week
    hyp = calculate_hypertrophy_sets_for_week(week_idx, exercises)
    str_sets = calculate_strength_sets_for_week(week_idx, exercises)
    return hyp, str_sets


def calculate_total_program_volume(exercises):
    """
    Calculate total volume across all weeks in the program.

    Args:
        exercises: Exercise library

    Returns:
        Dict with per-week and total stats
    """
    weeks_stats = []

    for i, week in enumerate(st.session_state.program_weeks):
        stats = calculate_week_stats(week["days"], exercises)
        stats["week_index"] = i
        stats["week_name"] = week["name"]
        stats["week_type"] = week["type"]
        weeks_stats.append(stats)

    # Calculate totals across all weeks
    total_stats = {
        "total_sets": sum(w["total_sets"] for w in weeks_stats),
        "strength_sets": sum(w["strength_sets"] for w in weeks_stats),
        "hypertrophy_sets": sum(w["hypertrophy_sets"] for w in weeks_stats),
        "weeks": weeks_stats,
    }

    return total_stats


def render_1rm_manager(exercises, exercise_names, display_to_name=None):
    """Render 1RM management section."""
    st.header("🎯 1RM Manager")
    st.caption("Enter your 1RM values to get personalized weight recommendations")

    # Default mapping if not provided
    if display_to_name is None:
        display_to_name = {name: name for name in exercise_names}

    col1, col2 = st.columns([2, 1])

    with col1:
        # Add/update 1RM
        st.subheader("Add or Update 1RM")

        selected_display = st.selectbox(
            "Select Exercise",
            options=exercise_names,
            key="1rm_exercise_select",
        )
        # Convert display name to actual name
        selected_ex = display_to_name.get(selected_display, selected_display)

        # Show current 1RM if exists
        current_1rm = st.session_state.exercise_1rm.get(selected_ex)
        if current_1rm:
            st.info(f"Current 1RM for {selected_ex}: **{current_1rm:.1f} kg**")

        input_method = st.radio(
            "Input Method",
            ["Enter 1RM directly", "Calculate from weight × reps"],
            key="1rm_input_method",
            horizontal=True,
        )

        if input_method == "Enter 1RM directly":
            new_1rm = st.number_input(
                "1RM (kg)",
                min_value=0.0,
                max_value=500.0,
                value=current_1rm if current_1rm else 0.0,
                step=2.5,
                key="direct_1rm_input",
            )
            if st.button("Save 1RM", key="save_direct_1rm"):
                if new_1rm > 0:
                    st.session_state.exercise_1rm[selected_ex] = new_1rm
                    st.success(f"Saved {selected_ex}: {new_1rm:.1f} kg")
                    st.rerun()
        else:
            col_w, col_r = st.columns(2)
            with col_w:
                weight = st.number_input(
                    "Weight lifted (kg)",
                    min_value=0.0,
                    max_value=500.0,
                    value=0.0,
                    step=2.5,
                    key="calc_weight",
                )
            with col_r:
                reps_done = st.number_input(
                    "Reps completed",
                    min_value=1,
                    max_value=30,
                    value=5,
                    key="calc_reps",
                )

            if weight > 0:
                estimated = calculate_1rm_from_reps(weight, reps_done)
                st.info(f"Estimated 1RM: **{estimated:.1f} kg**")

                if st.button("Save Estimated 1RM", key="save_calc_1rm"):
                    st.session_state.exercise_1rm[selected_ex] = estimated
                    st.success(f"Saved {selected_ex}: {estimated:.1f} kg")
                    st.rerun()

    with col2:
        # Show saved 1RMs
        st.subheader("Saved 1RMs")
        if st.session_state.exercise_1rm:
            for ex_name, rm_value in sorted(
                st.session_state.exercise_1rm.items(), key=lambda x: x[0]
            ):
                col_ex, col_rm, col_del = st.columns([3, 1, 1])
                with col_ex:
                    st.caption(ex_name[:25] + "..." if len(ex_name) > 25 else ex_name)
                with col_rm:
                    st.caption(f"{rm_value:.1f}kg")
                with col_del:
                    if st.button("×", key=f"del_1rm_{ex_name}"):
                        del st.session_state.exercise_1rm[ex_name]
                        st.rerun()
        else:
            st.caption("No 1RMs saved yet")

    # Bulk Import/Export section
    st.markdown("---")
    with st.expander("📦 Bulk Import/Export 1RM Data"):
        import_tab, export_tab = st.tabs(["Import JSON", "Export JSON"])

        with import_tab:
            st.markdown(
                """
            Upload a JSON file with your 1RM values. Format should be:
            ```json
            {
                "Exercise Name": 100.0,
                "Another Exercise": 80.5
            }
            ```
            or as a list:
            ```json
            [
                {"exercise": "Exercise Name", "1rm": 100.0},
                {"exercise": "Another Exercise", "1rm": 80.5}
            ]
            ```
            """
            )

            uploaded_1rm = st.file_uploader(
                "Upload 1RM JSON", type=["json"], key="1rm_json_upload"
            )

            if uploaded_1rm is not None:
                merge_mode = st.radio(
                    "Import mode",
                    [
                        "Merge (keep existing, add/update new)",
                        "Replace (clear existing, use uploaded)",
                    ],
                    key="1rm_import_mode",
                    horizontal=True,
                )

                if st.button("Import 1RM Data", key="import_1rm_btn"):
                    try:
                        uploaded_1rm.seek(0)
                        data = json.load(uploaded_1rm)

                        # Handle different formats
                        imported_1rms = {}

                        if isinstance(data, dict):
                            # Simple dict format: {"exercise": 1rm_value}
                            for k, v in data.items():
                                if isinstance(v, (int, float)) and v > 0:
                                    imported_1rms[k] = float(v)
                        elif isinstance(data, list):
                            # List format: [{"exercise": "name", "1rm": value}, ...]
                            for item in data:
                                if isinstance(item, dict):
                                    ex_name = (
                                        item.get("exercise")
                                        or item.get("name")
                                        or item.get("Exercise")
                                    )
                                    rm_val = (
                                        item.get("1rm")
                                        or item.get("1RM")
                                        or item.get("rm")
                                        or item.get("value")
                                    )
                                    if ex_name and rm_val and float(rm_val) > 0:
                                        imported_1rms[ex_name] = float(rm_val)

                        if imported_1rms:
                            if "Replace" in merge_mode:
                                st.session_state.exercise_1rm = imported_1rms
                            else:
                                st.session_state.exercise_1rm.update(imported_1rms)

                            st.success(f"Imported {len(imported_1rms)} 1RM values!")
                            st.rerun()
                        else:
                            st.error("No valid 1RM data found in the file")
                    except json.JSONDecodeError:
                        st.error("Invalid JSON file")
                    except Exception as e:
                        st.error(f"Error importing: {e}")

        with export_tab:
            if st.session_state.exercise_1rm:
                st.markdown(
                    f"**{len(st.session_state.exercise_1rm)} 1RM values saved**"
                )

                export_data = json.dumps(st.session_state.exercise_1rm, indent=2)

                st.download_button(
                    label="📥 Download 1RM Data (JSON)",
                    data=export_data,
                    file_name="my_1rm_values.json",
                    mime="application/json",
                    key="export_1rm_btn",
                )

                # Preview
                with st.expander("Preview data"):
                    st.code(export_data, language="json")
            else:
                st.info("No 1RM data to export. Add some values first!")

        # Clear all button with confirmation
        st.markdown("---")
        if st.session_state.exercise_1rm:
            with st.popover("🗑️ Clear All 1RM Data"):
                st.warning(
                    f"Delete all {len(st.session_state.exercise_1rm)} 1RM values?"
                )
                if st.button("Yes, Clear All", type="primary", key="confirm_clear_1rm"):
                    st.session_state.exercise_1rm = {}
                    st.rerun()

    # Show recommendations if exercise has 1RM
    if selected_ex and st.session_state.exercise_1rm.get(selected_ex):
        st.markdown("---")
        render_weight_recommendations(
            selected_ex, st.session_state.exercise_1rm[selected_ex]
        )


def render_weight_recommendations(exercise_name, one_rm):
    """Render weight/rep recommendations based on 1RM."""
    st.subheader(f"📊 Training Recommendations for {exercise_name}")
    st.caption(f"Based on 1RM: {one_rm:.1f} kg")

    recommendations = get_training_recommendations(one_rm)

    cols = st.columns(3)

    for i, (training_type, data) in enumerate(recommendations.items()):
        with cols[i]:
            if training_type == "strength":
                icon = "🏋️"
                color = "red"
            elif training_type == "hypertrophy":
                icon = "💪"
                color = "blue"
            else:
                icon = "🔄"
                color = "green"

            st.markdown(f"**{icon} {data['description']}**")
            st.caption(
                f"{data['percentage_range'][0]}-{data['percentage_range'][1]}% of 1RM"
            )

            for rec in data["rep_ranges"]:
                st.markdown(
                    f"• **{rec['reps']} reps** @ {rec['weight']:.1f} kg ({rec['pct']}%)"
                )


def render_weekly_summary(hyp_sets, str_sets, program=None, exercises=None):
    """Render the weekly summary of fractional sets."""
    st.header("📊 Weekly Fractional Sets Summary")

    # Tabs for hypertrophy and strength
    hyp_tab, str_tab, combined_tab = st.tabs(
        ["💪 Hypertrophy (>6 reps)", "🏋️ Strength (1-6 reps)", "📈 Combined View"]
    )

    with hyp_tab:
        render_hypertrophy_summary(hyp_sets, program=program, exercises=exercises)

    with str_tab:
        render_strength_summary(str_sets, program=program, exercises_lib=exercises)

    with combined_tab:
        render_combined_summary(hyp_sets, str_sets)


def get_pyramid_guidelines(use_user_targets=True):
    """
    Return the Muscle & Strength Pyramid training guidelines.
    Based on Eric Helms' research-backed recommendations.

    If use_user_targets is True, will use the user's custom targets or tier-based targets.
    """
    # Get user-defined targets if available
    if use_user_targets:
        targets = get_volume_targets()
        hyp_low = targets["hypertrophy"]["low"]
        hyp_high = targets["hypertrophy"]["high"]
        str_low = targets["strength"]["low"]
        str_high = targets["strength"]["high"]
    else:
        hyp_low, hyp_high = 10, 20
        str_low, str_high = 3, 5

    return {
        "hypertrophy": {
            "volume": {
                "minimum": 4,  # sets/muscle/week (absolute minimum)
                "maximum": 30,  # absolute maximum
                "practical_low": hyp_low,  # user's target low
                "practical_high": hyp_high,  # user's target high
                "per_session_max": 10,  # fractional sets per muscle per session
            },
            "intensity": {
                "load_range": (30, 90),  # % 1RM
                "rep_range": (4, 30),
                "rir_guidelines": [
                    {"reps": "4-6", "rir": "4-0 RIR"},
                    {"reps": "6-8", "rir": "3 RIR to failure"},
                    {"reps": "8-12", "rir": "2 RIR to failure"},
                    {"reps": ">12", "rir": "1 RIR to failure"},
                ],
            },
            "frequency": {
                "minimum": 1,  # per muscle per week
                "note": "If >10 weekly sets per muscle, increase frequency",
            },
        },
        "strength": {
            "volume": {
                "minimum": 1,  # sets/lift/week
                "maximum": 5,  # short-term
                "practical_low": str_low,  # user's target low
                "practical_high": str_high,  # user's target high
                "hypertrophy_support": (5, 10),  # sets/muscle/week long-term
            },
            "intensity": {
                "load_range": (80, 100),  # % 1RM
                "rep_range": (1, 8),
                "rir_note": "Load dictates RIR. Higher loads = closer to failure inherently.",
            },
            "frequency": {
                "minimum": 2,
                "maximum": 6,  # per lift per week
                "sets_per_session": (1, 2),  # direct sets per main lift per session
                "note": "Spread sets over as many days as possible",
            },
        },
    }


def render_pyramid_guidelines():
    """Display the Muscle & Strength Pyramid guidelines."""
    st.header("📖 Training Guidelines")
    st.caption("Based on The Muscle & Strength Pyramid by Eric Helms")

    guidelines = get_pyramid_guidelines(
        use_user_targets=False
    )  # Show standard guidelines

    tab_hyp, tab_str, tab_rir, tab_volume, tab_freq = st.tabs(
        [
            "💪 Hypertrophy",
            "🏋️ Strength",
            "🎯 RIR Guidelines",
            "📊 Volume Tiers",
            "🔄 Frequency",
        ]
    )

    with tab_hyp:
        st.subheader("Hypertrophy Training Guidelines")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**📊 Volume (sets/muscle/week)**")
            st.markdown(
                f"- Minimum: **{guidelines['hypertrophy']['volume']['minimum']}** sets"
            )
            st.markdown(
                f"- Maximum: **{guidelines['hypertrophy']['volume']['maximum']}** sets"
            )
            st.markdown(
                f"- Practical: **{guidelines['hypertrophy']['volume']['practical_low']}-"
                f"{guidelines['hypertrophy']['volume']['practical_high']}** sets"
            )
            st.caption("Higher volume for specialization phases")

        with col2:
            st.markdown("**⚖️ Intensity**")
            st.markdown(
                f"- Load: **{guidelines['hypertrophy']['intensity']['rep_range'][0]}-"
                f"{guidelines['hypertrophy']['intensity']['rep_range'][1]} RM** "
                f"(~{guidelines['hypertrophy']['intensity']['load_range'][0]}-"
                f"{guidelines['hypertrophy']['intensity']['load_range'][1]}% 1RM)"
            )
            st.markdown("- RIR varies by rep range (see RIR tab)")

        with col3:
            st.markdown("**🔄 Frequency**")
            st.markdown(
                f"- Minimum: **{guidelines['hypertrophy']['frequency']['minimum']}x**/muscle/week"
            )
            st.markdown(
                f"- Per session: max **{guidelines['hypertrophy']['volume']['per_session_max']}** "
                "fractional sets/muscle"
            )
            st.caption("If >10 sets/muscle/week, split across more sessions")

        st.info(
            "💡 **Fractional Sets**: Primary muscles = 1.0 set, Secondary/synergist = 0.5 set"
        )

    with tab_str:
        st.subheader("Strength Training Guidelines")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown("**📊 Volume (sets/lift/week)**")
            st.markdown(
                f"- Minimum: **{guidelines['strength']['volume']['minimum']}** set"
            )
            st.markdown(
                f"- Short-term max: **{guidelines['strength']['volume']['maximum']}** sets"
            )
            st.markdown(
                f"- Practical: **{guidelines['strength']['volume']['practical_low']}-"
                f"{guidelines['strength']['volume']['practical_high']}** sets/lift"
            )
            st.caption("Long-term: include hypertrophy work (5-10 sets/muscle/week)")

        with col2:
            st.markdown("**⚖️ Intensity**")
            st.markdown(
                f"- Load: **{guidelines['strength']['intensity']['rep_range'][0]}-"
                f"{guidelines['strength']['intensity']['rep_range'][1]} RM** "
                f"(~{guidelines['strength']['intensity']['load_range'][0]}-"
                f"{guidelines['strength']['intensity']['load_range'][1]}% 1RM)"
            )
            st.markdown("- Load dictates proximity to failure")

        with col3:
            st.markdown("**🔄 Frequency**")
            st.markdown(
                f"- **{guidelines['strength']['frequency']['minimum']}-"
                f"{guidelines['strength']['frequency']['maximum']}x**/lift/week"
            )
            st.markdown(
                f"- **{guidelines['strength']['frequency']['sets_per_session'][0]}-"
                f"{guidelines['strength']['frequency']['sets_per_session'][1]}** "
                "direct sets/lift/session"
            )
            st.caption("Spread sets over as many days as possible")

        st.info(
            "💡 **Long-term strength** requires hypertrophy. Include some hypertrophy volume "
            "in the efficient range (10-20 sets/muscle/week)."
        )

    with tab_rir:
        st.subheader("RIR (Reps In Reserve) Guidelines")

        st.markdown("**For Hypertrophy** - RIR varies by rep range:")

        rir_data = [
            {
                "Rep Range": "4-6 reps/set",
                "RIR Recommendation": "4-0 RIR",
                "Notes": "Can train further from failure at heavy loads",
            },
            {
                "Rep Range": "6-8 reps/set",
                "RIR Recommendation": "3 RIR to failure",
                "Notes": "Moderate proximity to failure",
            },
            {
                "Rep Range": "8-12 reps/set",
                "RIR Recommendation": "2 RIR to failure",
                "Notes": "Classic hypertrophy range",
            },
            {
                "Rep Range": ">12 reps/set",
                "RIR Recommendation": "1 RIR to failure",
                "Notes": "Need to be close to failure for stimulus",
            },
        ]

        st.dataframe(pd.DataFrame(rir_data), use_container_width=True, hide_index=True)

        st.markdown("**For Strength:**")
        st.markdown(
            "Load dictates RIR - higher loads inherently bring you closer to failure. "
            "Focus on load selection (~80%+ 1RM) rather than RIR targets."
        )

        with st.expander("📚 Understanding RIR"):
            st.markdown(
                """
            **RIR = Reps In Reserve** (how many more reps you could have done)
            
            - **0 RIR** = Failure (couldn't do another rep)
            - **1 RIR** = Could do 1 more rep
            - **2 RIR** = Could do 2 more reps
            - etc.
            
            **Key Points:**
            - RIR underestimation is more likely at lower loads (higher reps)
            - High loads (low reps) are effective for hypertrophy even at higher RIR
            - Sets must be ≥4 reps for hypertrophy stimulus
            - Trained lifters need lower RIR (closer to failure) for minimum effective volume
            """
            )

    with tab_volume:
        st.subheader("📊 Volume Tiers by Time Commitment")
        st.caption("From Table 7.4 - Choose based on your available training time")

        # Volume tiers table
        tier_data = []
        for name, info in VOLUME_TIERS.items():
            tier_data.append(
                {
                    "Tier": name,
                    "Sets/Muscle/Week": f"{info['sets_range'][0]}-{info['sets_range'][1]}",
                    "Time Commitment": info["time_commitment"],
                    "Avg Stimulus/Set": info["avg_stimulus_per_set"],
                    "Total Stimulus": info["total_stimulus"],
                    "Recommended Frequency": f"{info['frequency_range'][0]}-{info['frequency_range'][1]}x/wk",
                }
            )

        st.dataframe(pd.DataFrame(tier_data), use_container_width=True, hide_index=True)

        st.markdown("---")
        st.markdown("**Key Insights:**")
        st.markdown(
            """
            - **Higher volume ≠ better results** - diminishing returns apply
            - **Minimal tier** (4-8 sets) provides ~25-45% of max stimulus with highest efficiency per set
            - **Very High tier** (21-30 sets) often best accomplished via **specialization cycles**
            - Match volume to your **recovery capacity** and **time availability**
            - **Intermediate/Advanced** lifters may need higher volumes to continue progressing
            """
        )

        # Training status table
        st.markdown("---")
        st.subheader("📈 Training Status Definitions")
        st.caption(
            "From Table 7.14 - Know your training status for realistic expectations"
        )

        status_data = []
        for name, info in TRAINING_STATUS.items():
            status_data.append(
                {
                    "Status": name,
                    "Description": info["description"],
                    "Expected Progression": info["progression"],
                    "Typical Duration": info["duration"],
                }
            )

        st.dataframe(
            pd.DataFrame(status_data), use_container_width=True, hide_index=True
        )

        st.info(
            "💡 **Tip:** Most lifters overestimate their training status. "
            "True advanced status takes 5+ years of dedicated, progressive training."
        )

    with tab_freq:
        st.subheader("🔄 Frequency Recommendations")
        st.caption("From Table 7.6 - How often to train based on weekly volume")

        st.markdown("**Hypertrophy (Muscle Group Frequency)**")

        freq_data = [
            {
                "Weekly Sets/Muscle": "4-10",
                "Recommended Frequency": "1-2x/week",
                "Notes": "Lower volume, less frequency needed",
            },
            {
                "Weekly Sets/Muscle": "11-20",
                "Recommended Frequency": "2-3x/week",
                "Notes": "Standard practical range",
            },
            {
                "Weekly Sets/Muscle": "21-30",
                "Recommended Frequency": "3-4x/week",
                "Notes": "High volume, must distribute across sessions",
            },
        ]
        st.dataframe(pd.DataFrame(freq_data), use_container_width=True, hide_index=True)

        st.markdown(
            "**Key Principle:** If you exceed ~10 fractional sets for a muscle in a single session, "
            "increase frequency to distribute volume better and maintain session quality."
        )

        st.markdown("---")
        st.markdown("**Strength (Lift Frequency)**")
        st.markdown(
            """
            - **2-6x per lift per week** depending on volume
            - **1-2 direct sets per main lift per session** is optimal
            - **Spread sets over as many days as possible**
            - Higher frequency enhances skill practice and movement quality
            
            **For Powerlifting:**
            - Squat/Deadlift share overlap (hip hinge) - each adds 0.5 to the other's frequency
            - Ideally train each main lift at least 2x/week directly
            """
        )

        st.markdown("---")
        st.markdown("**Split Selection Guidelines:**")

        split_data = [
            {
                "Training Days": "2-3",
                "Good Options": "Full Body, Upper/Lower",
                "Per-Muscle Freq": "1-2x",
            },
            {
                "Training Days": "4",
                "Good Options": "Upper/Lower, Full Push/Pull",
                "Per-Muscle Freq": "2x",
            },
            {
                "Training Days": "5-6",
                "Good Options": "PPL, Arnold Split, Full Body rotation",
                "Per-Muscle Freq": "2-3x",
            },
        ]
        st.dataframe(
            pd.DataFrame(split_data), use_container_width=True, hide_index=True
        )


def analyze_program_guidelines(program, exercises, hyp_sets, str_sets):
    """
    Analyze the program against Muscle & Strength Pyramid guidelines.
    Returns analysis dict with recommendations.
    """
    guidelines = get_pyramid_guidelines()
    analysis = {
        "hypertrophy": {"muscles": {}, "issues": [], "suggestions": []},
        "strength": {"exercises": {}, "issues": [], "suggestions": []},
        "frequency": {"days": {}, "issues": [], "suggestions": []},
    }

    # Analyze hypertrophy volume per muscle
    muscle_totals = defaultdict(float)
    muscle_per_day = defaultdict(lambda: defaultdict(float))

    for day, muscles in hyp_sets.items():
        for muscle, sets in muscles.items():
            muscle_totals[muscle] += sets
            muscle_per_day[muscle][day] += sets

    for muscle, total in muscle_totals.items():
        status = "optimal"
        if total < guidelines["hypertrophy"]["volume"]["minimum"]:
            status = "below_minimum"
            analysis["hypertrophy"]["issues"].append(
                f"{muscle}: {total:.1f} sets < minimum ({guidelines['hypertrophy']['volume']['minimum']})"
            )
        elif total < guidelines["hypertrophy"]["volume"]["practical_low"]:
            status = "below_practical"
        elif total > guidelines["hypertrophy"]["volume"]["maximum"]:
            status = "above_maximum"
            analysis["hypertrophy"]["issues"].append(
                f"{muscle}: {total:.1f} sets > maximum ({guidelines['hypertrophy']['volume']['maximum']})"
            )
        elif total > guidelines["hypertrophy"]["volume"]["practical_high"]:
            status = "above_practical"

        # Check per-session volume
        max_session = (
            max(muscle_per_day[muscle].values()) if muscle_per_day[muscle] else 0
        )
        session_warning = (
            max_session > guidelines["hypertrophy"]["volume"]["per_session_max"]
        )

        analysis["hypertrophy"]["muscles"][muscle] = {
            "total": total,
            "status": status,
            "per_day": dict(muscle_per_day[muscle]),
            "max_session": max_session,
            "session_warning": session_warning,
        }

        if session_warning:
            analysis["hypertrophy"]["suggestions"].append(
                f"{muscle}: {max_session:.1f} sets in one session > recommended max (10). Consider splitting."
            )

    # Analyze strength volume per exercise
    exercise_totals = defaultdict(float)
    exercise_per_day = defaultdict(lambda: defaultdict(float))

    for day, exs in str_sets.items():
        for ex, sets in exs.items():
            exercise_totals[ex] += sets
            exercise_per_day[ex][day] += sets

    # Only analyze exercises actually in the program with strength rep ranges
    program_strength_exercises = set()
    for day, day_exs in program.items():
        for entry in day_exs:
            if entry["reps"] <= 6:
                program_strength_exercises.add(entry["exercise"])

    # Apply strength tracking filter
    tracked_str = get_tracked_strength_exercises(exercises)
    if tracked_str is not None:
        program_strength_exercises &= tracked_str

    for ex in program_strength_exercises:
        total = exercise_totals.get(ex, 0)
        # Count direct sets only
        direct_sets = sum(
            entry["sets"]
            for day, day_exs in program.items()
            for entry in day_exs
            if entry["exercise"] == ex and entry["reps"] <= 6
        )

        days_trained = sum(1 for d in DAYS if exercise_per_day[ex].get(d, 0) > 0)

        status = "optimal"
        if direct_sets < guidelines["strength"]["volume"]["minimum"]:
            status = "below_minimum"
        elif direct_sets > guidelines["strength"]["volume"]["maximum"]:
            status = "above_maximum"
            analysis["strength"]["issues"].append(
                f"{ex}: {direct_sets} direct sets > short-term max ({guidelines['strength']['volume']['maximum']})"
            )

        analysis["strength"]["exercises"][ex] = {
            "direct_sets": direct_sets,
            "total_fractional": total,
            "status": status,
            "days_trained": days_trained,
            "per_day": dict(exercise_per_day[ex]),
        }

        # Check frequency
        if days_trained < guidelines["strength"]["frequency"]["minimum"]:
            analysis["strength"]["suggestions"].append(
                f"{ex}: trained {days_trained}x/week < recommended ({guidelines['strength']['frequency']['minimum']}-{guidelines['strength']['frequency']['maximum']}x)"
            )

    # Big 5 coverage check (only when tracking Big 5)
    mode = st.session_state.user_profile.get("strength_tracking_mode", "compound")
    if mode == "compound":
        covered, missing_cats = get_big5_coverage(program)
        analysis["strength"]["big5_covered"] = covered
        analysis["strength"]["big5_missing"] = missing_cats
        if missing_cats:
            analysis["strength"]["suggestions"].append(
                f"Missing Big 5 categories: {', '.join(missing_cats)}. "
                f"Consider adding exercises for balanced strength development."
            )

    # Analyze training frequency per day
    for day in DAYS:
        day_exercises = program.get(day, [])
        if day_exercises:
            analysis["frequency"]["days"][day] = {
                "exercises": len(day_exercises),
                "total_sets": sum(e["sets"] for e in day_exercises),
                "hyp_sets": sum(e["sets"] for e in day_exercises if e["reps"] > 6),
                "str_sets": sum(e["sets"] for e in day_exercises if e["reps"] <= 6),
            }

    training_days = sum(1 for d in DAYS if program.get(d, []))
    analysis["frequency"]["training_days"] = training_days

    return analysis


def get_exercise_suggestions(analysis, exercises, guidelines):
    """Get exercise suggestions for muscles with low volume."""
    suggestions = []

    for muscle, info in analysis["hypertrophy"]["muscles"].items():
        if info["status"] in ["below_minimum", "below_practical"]:
            # Find exercises targeting this muscle (compare lowercase)
            matching_exercises = [
                ex["name"]
                for ex in exercises
                if muscle.lower() in [m.lower() for m in ex.get("primaryMuscles", [])]
            ]
            if matching_exercises:
                deficit = (
                    guidelines["hypertrophy"]["volume"]["practical_low"] - info["total"]
                )
                suggestions.append(
                    {
                        "muscle": muscle,
                        "current": info["total"],
                        "target": guidelines["hypertrophy"]["volume"]["practical_low"],
                        "deficit": max(0, deficit),
                        "suggested_exercises": matching_exercises[:5],
                    }
                )

    return suggestions


def get_strength_exercise_suggestions(analysis, exercises, guidelines):
    """Get exercise suggestions for lifts with low volume."""
    suggestions = []

    for ex_name, info in analysis["strength"]["exercises"].items():
        if info["status"] in ["below_minimum"]:
            deficit = (
                guidelines["strength"]["volume"]["practical_low"] - info["direct_sets"]
            )
            suggestions.append(
                {
                    "exercise": ex_name,
                    "current": info["direct_sets"],
                    "target": guidelines["strength"]["volume"]["practical_low"],
                    "deficit": max(0, deficit),
                    "days_trained": info["days_trained"],
                }
            )

    return suggestions


def render_program_designer(program, exercises, hyp_sets, str_sets):
    """Render a program designer helper based on guidelines."""
    st.header("🎨 Program Designer")

    # Show user's current targets
    profile = st.session_state.user_profile
    targets = get_volume_targets()

    st.info(
        f"**Your Targets** ({profile['training_status']} | {profile['volume_tier']} tier): "
        f"💪 Hypertrophy: **{targets['hypertrophy']['low']}-{targets['hypertrophy']['high']}** sets/muscle/week | "
        f"🏋️ Strength: **{targets['strength']['low']}-{targets['strength']['high']}** sets/lift/week"
    )

    if profile["use_custom_targets"]:
        st.caption("Using custom volume targets. Change in 👤 User Profile.")
    else:
        st.caption(
            f"Based on {profile['volume_tier']} tier + {profile['training_status']} status. Customize in 👤 User Profile."
        )

    analysis = analyze_program_guidelines(program, exercises, hyp_sets, str_sets)
    guidelines = get_pyramid_guidelines()

    # Show what's missing - two columns for hypertrophy and strength
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("💪 Hypertrophy (Muscles)")
        st.caption(
            f"Target: {guidelines['hypertrophy']['volume']['practical_low']}-"
            f"{guidelines['hypertrophy']['volume']['practical_high']} sets/muscle/week"
        )

        hyp_suggestions = get_exercise_suggestions(analysis, exercises, guidelines)

        if hyp_suggestions:
            for sugg in sorted(
                hyp_suggestions, key=lambda x: x["deficit"], reverse=True
            ):
                with st.expander(
                    f"🔴 {sugg['muscle']} ({sugg['current']:.1f}/{sugg['target']} sets)"
                ):
                    st.markdown(f"**Need ~{sugg['deficit']:.0f} more sets**")
                    st.markdown("**Suggested exercises:**")
                    for ex in sugg["suggested_exercises"]:
                        st.markdown(f"- {ex}")

                    # Quick add suggestion
                    sets_needed = max(1, int(sugg["deficit"] / 2))  # Assume 2 sessions
                    st.info(
                        f"💡 Add {sets_needed} sets of a {sugg['muscle']} exercise "
                        f"to 2 different days"
                    )
        else:
            st.success("✅ All muscles have adequate hypertrophy volume!")

    with col2:
        st.subheader("🏋️ Strength (Lifts)")
        st.caption(
            f"Target: {guidelines['strength']['volume']['practical_low']}-"
            f"{guidelines['strength']['volume']['practical_high']} sets/lift/week"
        )

        str_suggestions = get_strength_exercise_suggestions(
            analysis, exercises, guidelines
        )

        if str_suggestions:
            for sugg in sorted(
                str_suggestions, key=lambda x: x["deficit"], reverse=True
            ):
                with st.expander(
                    f"🔴 {sugg['exercise']} ({sugg['current']}/{sugg['target']} sets)"
                ):
                    st.markdown(f"**Need ~{sugg['deficit']:.0f} more sets**")
                    st.markdown(f"**Currently trained:** {sugg['days_trained']}x/week")

                    freq_target = guidelines["strength"]["frequency"]["minimum"]
                    if sugg["days_trained"] < freq_target:
                        st.warning(
                            f"⚠️ Frequency below minimum ({freq_target}x/week recommended)"
                        )

                    st.info(
                        f"💡 Add 1-2 sets of {sugg['exercise']} to "
                        f"{max(1, freq_target - sugg['days_trained'])} more days"
                    )
        else:
            if analysis["strength"]["exercises"]:
                st.success("✅ All strength lifts have adequate volume!")
            else:
                st.info("No strength exercises (1-6 reps) in program yet")

    # Quick stats section
    st.markdown("---")
    st.subheader("📊 Quick Stats")

    col1, col2, col3, col4 = st.columns(4)

    # Hypertrophy stats
    status_counts = defaultdict(int)
    for muscle, info in analysis["hypertrophy"]["muscles"].items():
        status_counts[info["status"]] += 1

    total_muscles = len(analysis["hypertrophy"]["muscles"])

    with col1:
        if total_muscles > 0:
            optimal_pct = (status_counts["optimal"] / total_muscles) * 100
            st.metric("Muscles Optimal", f"{status_counts['optimal']}/{total_muscles}")
        else:
            st.metric("Muscles Optimal", "0/0")

    with col2:
        low_vol = status_counts.get("below_minimum", 0) + status_counts.get(
            "below_practical", 0
        )
        st.metric("Muscles Low Vol", low_vol)

    # Strength stats
    str_count = len(analysis["strength"]["exercises"])
    str_optimal = sum(
        1
        for ex, info in analysis["strength"]["exercises"].items()
        if info["status"] == "optimal"
    )

    with col3:
        st.metric("Strength Lifts", f"{str_optimal}/{str_count} optimal")

    with col4:
        training_days = analysis["frequency"]["training_days"]
        st.metric("Training Days/Week", training_days)

    # Recommendations
    st.markdown("---")
    st.markdown("**📋 Balanced Program Recommendations:**")
    st.markdown(
        f"""
    - **Hypertrophy**: {guidelines['hypertrophy']['volume']['practical_low']}-{guidelines['hypertrophy']['volume']['practical_high']} sets/muscle/week (>6 reps)
    - **Strength**: {guidelines['strength']['volume']['practical_low']}-{guidelines['strength']['volume']['practical_high']} sets/lift/week (1-6 reps at 80%+ 1RM)
    - **Frequency**: Train each muscle ≥2x/week, main lifts {guidelines['strength']['frequency']['minimum']}-{guidelines['strength']['frequency']['maximum']}x/week
    - **Per Session**: Max 10 fractional sets/muscle for hypertrophy
    """
    )


def get_muscle_exercise_contributors(muscle_name, program, exercises):
    """
    Get all exercises that contribute to a muscle group's hypertrophy volume.

    Args:
        muscle_name: Title-cased muscle name (e.g., "Chest")
        program: Dict of day -> list of exercise entries
        exercises: Exercise library

    Returns:
        List of contributor dicts with exercise, day, sets, reps, role, contribution.
    """
    muscle_lower = muscle_name.lower()
    contributors = []

    for day in DAYS:
        for entry in program.get(day, []):
            if entry["reps"] <= 6:
                continue  # Hypertrophy only (>6 reps)

            ex_info = get_exercise_by_name(exercises, entry["exercise"])
            if not ex_info:
                continue

            primary = [m.lower() for m in ex_info.get("primaryMuscles", [])]
            secondary = [m.lower() for m in ex_info.get("secondaryMuscles", [])]

            if muscle_lower in primary:
                role = "primary"
                multiplier = 1.0
            elif muscle_lower in secondary:
                role = "secondary"
                multiplier = 0.5
            else:
                continue

            contributors.append(
                {
                    "exercise": entry["exercise"],
                    "day": day,
                    "sets": entry["sets"],
                    "reps": entry["reps"],
                    "role": role,
                    "multiplier": multiplier,
                    "contribution": entry["sets"] * multiplier,
                }
            )

    return contributors


def get_strength_exercise_details(exercise_name, program, exercises):
    """
    Get detailed breakdown for a strength exercise's volume.

    Args:
        exercise_name: Name of the exercise
        program: Dict of day -> list of exercise entries
        exercises: Exercise library

    Returns:
        Dict with 'direct' (list of direct training instances) and
        'indirect' (list of indirect contributions from related exercises).
    """
    ex_info = get_exercise_by_name(exercises, exercise_name)
    if not ex_info:
        return {"direct": [], "indirect": []}

    ex_muscles = set()
    for m in ex_info.get("primaryMuscles", []):
        if m:
            ex_muscles.add(m.lower())
    for m in ex_info.get("secondaryMuscles", []):
        if m:
            ex_muscles.add(m.lower())

    direct = []
    indirect = []

    for day in DAYS:
        for entry in program.get(day, []):
            if entry["reps"] > 6:
                continue  # Strength only (<=6 reps)

            if entry["exercise"] == exercise_name:
                direct.append(
                    {
                        "day": day,
                        "sets": entry["sets"],
                        "reps": entry["reps"],
                    }
                )
            else:
                other_info = get_exercise_by_name(exercises, entry["exercise"])
                if other_info:
                    other_muscles = set()
                    for m in other_info.get("primaryMuscles", []):
                        if m:
                            other_muscles.add(m.lower())
                    for m in other_info.get("secondaryMuscles", []):
                        if m:
                            other_muscles.add(m.lower())

                    shared = ex_muscles & other_muscles
                    if shared:
                        indirect.append(
                            {
                                "exercise": entry["exercise"],
                                "day": day,
                                "sets": entry["sets"],
                                "reps": entry["reps"],
                                "shared_muscles": sorted(m.title() for m in shared),
                                "contribution": entry["sets"] * 0.5,
                            }
                        )

    return {"direct": direct, "indirect": indirect}


def render_muscle_drilldown(muscle, info, program, exercises, key_prefix="analysis"):
    """Render a drill-down expander for a single muscle group."""
    status_icon = {
        "below_minimum": "🔴",
        "below_practical": "🟡",
        "optimal": "🟢",
        "above_practical": "🟡",
        "above_maximum": "🔴",
    }.get(info["status"], "⚪")

    with st.expander(
        f"{status_icon} **{muscle}** — {info['total']:.1f} sets/week"
    ):
        # Per-day volume breakdown
        st.markdown("**📅 Volume by Day:**")
        day_cols = st.columns(7)
        for i, day in enumerate(DAYS):
            with day_cols[i]:
                day_val = info["per_day"].get(day, 0)
                if day_val > 0:
                    st.metric(day[:3], f"{day_val:.1f}")
                else:
                    st.metric(day[:3], "—")

        # Contributing exercises
        st.markdown("---")
        st.markdown("**🏋️ Contributing Exercises:**")
        contributors = get_muscle_exercise_contributors(muscle, program, exercises)

        if contributors:
            # Group by exercise name
            by_exercise = {}
            for c in contributors:
                key = c["exercise"]
                if key not in by_exercise:
                    by_exercise[key] = {
                        "role": c["role"],
                        "multiplier": c["multiplier"],
                        "entries": [],
                        "total": 0,
                    }
                by_exercise[key]["entries"].append(c)
                by_exercise[key]["total"] += c["contribution"]

            for ex_name, ex_data in sorted(
                by_exercise.items(), key=lambda x: -x[1]["total"]
            ):
                role_tag = (
                    "🎯 Primary (1.0x)"
                    if ex_data["role"] == "primary"
                    else "↳ Synergist (0.5x)"
                )
                st.markdown(
                    f"**{ex_name}** — {role_tag} — "
                    f"**{ex_data['total']:.1f}** sets"
                )
                for e in ex_data["entries"]:
                    st.caption(
                        f"  {e['day']}: {e['sets']}×{e['reps']} "
                        f"→ {e['contribution']:.1f} sets"
                    )
        else:
            st.caption("No contributing exercises found")


def render_strength_drilldown(ex_name, info, program, exercises, key_prefix="analysis"):
    """Render a drill-down expander for a single strength exercise."""
    status_icon = {
        "below_minimum": "🔴",
        "optimal": "🟢",
        "above_maximum": "🔴",
    }.get(info["status"], "🟢")

    with st.expander(
        f"{status_icon} **{ex_name}** — {info['direct_sets']} direct / "
        f"{info['total_fractional']:.1f} total sets ({info['days_trained']}x/wk)"
    ):
        details = get_strength_exercise_details(ex_name, program, exercises)

        # Direct training
        if details["direct"]:
            st.markdown("**📅 Direct Training (1.0x per set):**")
            for d in details["direct"]:
                st.markdown(
                    f"- **{d['day']}**: {d['sets']}×{d['reps']} "
                    f"→ {d['sets']:.0f} direct sets"
                )

        # Indirect contributors
        if details["indirect"]:
            st.markdown("---")
            st.markdown("**↳ Indirect Contributors (0.5x per set):**")
            for c in details["indirect"]:
                shared = ", ".join(c["shared_muscles"])
                st.markdown(
                    f"- **{c['exercise']}** ({c['day']}): "
                    f"{c['sets']}×{c['reps']} → +{c['contribution']:.1f} sets "
                    f"*(shared: {shared})*"
                )

        # Summary
        total_direct = sum(d["sets"] for d in details["direct"])
        total_indirect = sum(c["contribution"] for c in details["indirect"])
        st.markdown("---")
        st.markdown(
            f"**Total:** {total_direct:.0f} direct + "
            f"{total_indirect:.1f} indirect = "
            f"**{total_direct + total_indirect:.1f}** fractional sets"
        )


def render_program_analysis(program, exercises, hyp_sets, str_sets):
    """Render the program analysis against guidelines."""
    st.header("🔍 Program Analysis")

    # Show user's current targets
    profile = st.session_state.user_profile
    targets = get_volume_targets()

    st.info(
        f"**Analyzing against your targets** ({profile['training_status']} | {profile['volume_tier']} tier): "
        f"💪 Hypertrophy: **{targets['hypertrophy']['low']}-{targets['hypertrophy']['high']}** sets/muscle/week | "
        f"🏋️ Strength: **{targets['strength']['low']}-{targets['strength']['high']}** sets/lift/week"
    )

    analysis = analyze_program_guidelines(program, exercises, hyp_sets, str_sets)
    guidelines = get_pyramid_guidelines()

    # Overall summary
    col1, col2, col3 = st.columns(3)

    with col1:
        hyp_issues = len(analysis["hypertrophy"]["issues"])
        if hyp_issues == 0:
            st.success(f"✅ Hypertrophy volume OK")
        else:
            st.warning(f"⚠️ {hyp_issues} hypertrophy issues")

    with col2:
        str_issues = len(analysis["strength"]["issues"])
        missing_cats = analysis["strength"].get("big5_missing", [])
        if str_issues == 0 and not missing_cats:
            st.success(f"✅ Strength volume OK")
        elif str_issues == 0 and missing_cats:
            st.warning(
                f"⚠️ Missing Big 5: {', '.join(missing_cats)}"
            )
        else:
            st.warning(f"⚠️ {str_issues} strength issues")

    with col3:
        st.info(f"📅 {analysis['frequency']['training_days']} training days/week")

    # Detailed tabs
    tab_hyp, tab_str, tab_freq = st.tabs(
        ["💪 Hypertrophy Analysis", "🏋️ Strength Analysis", "📅 Frequency Analysis"]
    )

    with tab_hyp:
        st.subheader("Hypertrophy Volume per Muscle Group")
        st.caption(
            f"Target: {guidelines['hypertrophy']['volume']['practical_low']}-"
            f"{guidelines['hypertrophy']['volume']['practical_high']} sets/muscle/week"
        )

        if analysis["hypertrophy"]["muscles"]:
            # Build DataFrame with status indicators
            data = []
            for muscle, info in sorted(
                analysis["hypertrophy"]["muscles"].items(),
                key=lambda x: x[1]["total"],
                reverse=True,
            ):
                status_icon = {
                    "below_minimum": "🔴",
                    "below_practical": "🟡",
                    "optimal": "🟢",
                    "above_practical": "🟡",
                    "above_maximum": "🔴",
                }.get(info["status"], "⚪")

                session_icon = "⚠️" if info["session_warning"] else ""

                data.append(
                    {
                        "Status": status_icon,
                        "Muscle": muscle,
                        "Weekly Sets": f"{info['total']:.1f}",
                        "Max/Session": f"{info['max_session']:.1f} {session_icon}",
                        "Assessment": info["status"].replace("_", " ").title(),
                    }
                )

            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Visual bar chart
            muscle_data = [
                {"Muscle": m, "Sets": info["total"]}
                for m, info in analysis["hypertrophy"]["muscles"].items()
            ]
            if muscle_data:
                chart_df = pd.DataFrame(muscle_data).sort_values("Sets", ascending=True)

                import plotly.graph_objects as go

                fig = go.Figure()

                # Add bars with color based on range
                colors = []
                for _, row in chart_df.iterrows():
                    if row["Sets"] < guidelines["hypertrophy"]["volume"]["minimum"]:
                        colors.append("red")
                    elif (
                        row["Sets"]
                        < guidelines["hypertrophy"]["volume"]["practical_low"]
                    ):
                        colors.append("orange")
                    elif (
                        row["Sets"]
                        <= guidelines["hypertrophy"]["volume"]["practical_high"]
                    ):
                        colors.append("green")
                    elif row["Sets"] <= guidelines["hypertrophy"]["volume"]["maximum"]:
                        colors.append("orange")
                    else:
                        colors.append("red")

                fig.add_trace(
                    go.Bar(
                        y=chart_df["Muscle"],
                        x=chart_df["Sets"],
                        orientation="h",
                        marker_color=colors,
                    )
                )

                # Add reference lines
                fig.add_vline(
                    x=guidelines["hypertrophy"]["volume"]["practical_low"],
                    line_dash="dash",
                    line_color="green",
                    annotation_text="Min practical",
                )
                fig.add_vline(
                    x=guidelines["hypertrophy"]["volume"]["practical_high"],
                    line_dash="dash",
                    line_color="green",
                    annotation_text="Max practical",
                )

                fig.update_layout(
                    title="Weekly Hypertrophy Sets per Muscle",
                    xaxis_title="Fractional Sets",
                    showlegend=False,
                    height=max(300, len(chart_df) * 25),
                )

                st.plotly_chart(fig, use_container_width=True)

            # Show suggestions
            if analysis["hypertrophy"]["suggestions"]:
                st.markdown("**💡 Suggestions:**")
                for sugg in analysis["hypertrophy"]["suggestions"]:
                    st.markdown(f"- {sugg}")

            # Drill-down details per muscle group
            st.markdown("---")
            st.markdown("**🔍 Click a muscle group for detailed breakdown:**")
            for muscle, info in sorted(
                analysis["hypertrophy"]["muscles"].items(),
                key=lambda x: x[1]["total"],
                reverse=True,
            ):
                render_muscle_drilldown(
                    muscle, info, program, exercises, key_prefix="analysis_hyp"
                )

        else:
            st.info("Add exercises with >6 reps to see hypertrophy analysis")

    with tab_str:
        st.subheader("Strength Volume per Exercise")
        st.caption(
            f"Target: {guidelines['strength']['volume']['practical_low']}-"
            f"{guidelines['strength']['volume']['practical_high']} direct sets/lift/week"
        )

        if analysis["strength"]["exercises"]:
            data = []
            for ex, info in sorted(
                analysis["strength"]["exercises"].items(),
                key=lambda x: x[1]["direct_sets"],
                reverse=True,
            ):
                status_icon = {
                    "below_minimum": "🔴",
                    "optimal": "🟢",
                    "above_maximum": "🔴",
                }.get(info["status"], "🟢")

                data.append(
                    {
                        "Status": status_icon,
                        "Exercise": ex,
                        "Direct Sets": info["direct_sets"],
                        "Days/Week": info["days_trained"],
                        "Assessment": info["status"].replace("_", " ").title(),
                    }
                )

            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Big 5 coverage panel
            if "big5_covered" in analysis["strength"]:
                covered = analysis["strength"]["big5_covered"]
                missing_cats = analysis["strength"]["big5_missing"]

                st.markdown("---")
                st.markdown(
                    f"**Big 5 Coverage: {len(covered)}/{len(BIG_5_CATEGORIES)} categories**"
                )

                cols = st.columns(len(BIG_5_CATEGORIES))
                for i, cat in enumerate(BIG_5_CATEGORIES):
                    with cols[i]:
                        if cat in covered:
                            exs = covered[cat]
                            ex_names = sorted(set(e["exercise"] for e in exs))
                            st.success(f"✅ {cat}")
                            for name in ex_names:
                                st.caption(name)
                        else:
                            st.error(f"❌ {cat}")
                            st.caption("Not in program")

                if missing_cats:
                    st.warning(
                        f"⚠️ **Missing {len(missing_cats)} Big 5 "
                        f"{'category' if len(missing_cats) == 1 else 'categories'}:** "
                        f"{', '.join(missing_cats)}. "
                        f"Consider adding these for balanced strength development."
                    )

            if analysis["strength"]["suggestions"]:
                st.markdown("**💡 Suggestions:**")
                for sugg in analysis["strength"]["suggestions"]:
                    st.markdown(f"- {sugg}")

            # Drill-down details per strength exercise
            st.markdown("---")
            st.markdown("**🔍 Click an exercise for detailed breakdown:**")
            for ex, info in sorted(
                analysis["strength"]["exercises"].items(),
                key=lambda x: x[1]["direct_sets"],
                reverse=True,
            ):
                render_strength_drilldown(
                    ex, info, program, exercises, key_prefix="analysis_str"
                )

        else:
            st.info("Add exercises with 1-6 reps to see strength analysis")

    with tab_freq:
        st.subheader("Training Frequency")

        if analysis["frequency"]["days"]:
            data = []
            for day in DAYS:
                if day in analysis["frequency"]["days"]:
                    info = analysis["frequency"]["days"][day]
                    data.append(
                        {
                            "Day": day,
                            "Exercises": info["exercises"],
                            "Total Sets": info["total_sets"],
                            "Hypertrophy": info["hyp_sets"],
                            "Strength": info["str_sets"],
                        }
                    )
                else:
                    data.append(
                        {
                            "Day": day,
                            "Exercises": 0,
                            "Total Sets": 0,
                            "Hypertrophy": 0,
                            "Strength": 0,
                        }
                    )

            df = pd.DataFrame(data)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Check muscle frequency
            st.markdown("**Muscle Training Frequency:**")
            muscle_freq = defaultdict(int)
            for day, muscles in hyp_sets.items():
                for muscle, sets in muscles.items():
                    if sets > 0:
                        muscle_freq[muscle] += 1

            freq_data = [
                {"Muscle": m, "Days/Week": f, "Adequate": "✅" if f >= 2 else "⚠️"}
                for m, f in sorted(
                    muscle_freq.items(), key=lambda x: x[1], reverse=True
                )
            ]
            if freq_data:
                st.dataframe(
                    pd.DataFrame(freq_data), use_container_width=True, hide_index=True
                )

        else:
            st.info("Add exercises to see frequency analysis")


def render_volume_recommendations():
    """Display volume recommendations per muscle group."""
    st.subheader("📚 Quick Volume Reference")
    st.caption("Based on The Muscle & Strength Pyramid guidelines")

    guidelines = get_pyramid_guidelines()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**💪 Hypertrophy (sets/muscle/week)**")
        st.markdown(f"- Minimum: {guidelines['hypertrophy']['volume']['minimum']}")
        st.markdown(
            f"- Practical: {guidelines['hypertrophy']['volume']['practical_low']}-"
            f"{guidelines['hypertrophy']['volume']['practical_high']}"
        )
        st.markdown(f"- Maximum: {guidelines['hypertrophy']['volume']['maximum']}")

    with col2:
        st.markdown("**🏋️ Strength (sets/lift/week)**")
        st.markdown(f"- Minimum: {guidelines['strength']['volume']['minimum']}")
        st.markdown(
            f"- Practical: {guidelines['strength']['volume']['practical_low']}-"
            f"{guidelines['strength']['volume']['practical_high']}"
        )
        st.markdown(f"- Short-term max: {guidelines['strength']['volume']['maximum']}")

    with st.expander("ℹ️ Understanding Fractional Sets"):
        st.markdown(
            """
        **Hypertrophy Counting:**
        - Primary/target muscle = **1.0 set**
        - Secondary/synergist muscle = **0.5 set**
        
        **Strength Counting:**
        - Direct work on the lift = **1.0 set**
        - Related exercises (same muscles) = **0.5 set**
        
        **Key Principle:** The minimum volume produces gains in beginners but only 
        maintenance in advanced lifters. Practical range is where most people should train.
        """
        )


def render_hypertrophy_summary(hyp_sets, program=None, exercises=None):
    """Render hypertrophy fractional sets summary."""
    st.subheader("Muscle-Focused Fractional Sets")
    st.caption("1.0 set for primary muscles, 0.5 for synergist muscles (>6 reps only)")

    # Aggregate by muscle across all days
    muscle_totals = defaultdict(float)
    for day, muscles in hyp_sets.items():
        for muscle, sets in muscles.items():
            muscle_totals[muscle] += sets

    if not muscle_totals:
        st.info("No hypertrophy sets (>6 reps) in program yet.")
        return

    # Create daily breakdown table
    all_muscles = sorted(set(m for d in hyp_sets.values() for m in d.keys()))

    if all_muscles:
        # Build DataFrame
        data = []
        for muscle in all_muscles:
            row = {"Muscle Group": muscle}
            total = 0
            for day in DAYS:
                day_sets = hyp_sets[day].get(muscle, 0)
                row[day[:3]] = day_sets  # Use abbreviated day names
                total += day_sets
            row["Total"] = total
            data.append(row)

        df = pd.DataFrame(data)
        df = df.sort_values("Total", ascending=False)

        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Weekly Sets", f"{df['Total'].sum():.1f}")
        with col2:
            st.metric("Muscle Groups Hit", len(df))
        with col3:
            top_muscle = df.iloc[0]["Muscle Group"] if len(df) > 0 else "N/A"
            st.metric("Most Trained", top_muscle)

        # Format and display table
        st.dataframe(
            df.style.format(
                {col: "{:.1f}" for col in df.columns if col != "Muscle Group"}
            ),
            use_container_width=True,
            hide_index=True,
        )

        # Bar chart
        fig = px.bar(
            df.head(15),
            x="Muscle Group",
            y="Total",
            title="Weekly Hypertrophy Sets by Muscle Group",
            color="Total",
            color_continuous_scale="Blues",
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

        # Drill-down per muscle group
        if program is not None and exercises is not None:
            st.markdown("---")
            st.markdown("**🔍 Click a muscle group for details:**")

            # Build per-day info for each muscle (matches analysis format)
            muscle_per_day = defaultdict(lambda: defaultdict(float))
            for day, muscles in hyp_sets.items():
                for muscle, sets in muscles.items():
                    muscle_per_day[muscle][day] += sets

            for muscle in df["Muscle Group"].values:
                total = muscle_totals[muscle]
                per_day = dict(muscle_per_day[muscle])

                # Simplified info dict compatible with render_muscle_drilldown
                info = {
                    "total": total,
                    "status": "optimal",  # No assessment in summary view
                    "per_day": per_day,
                }

                render_muscle_drilldown(
                    muscle, info, program, exercises, key_prefix="summary_hyp"
                )


def render_strength_summary(str_sets, program=None, exercises_lib=None):
    """Render strength fractional sets summary."""
    st.subheader("Exercise-Focused Fractional Sets")
    st.caption("1.0 set for direct work, 0.5 for related exercises (1-6 reps only)")

    # Aggregate by exercise across all days
    exercise_totals = defaultdict(float)
    for day, exercises in str_sets.items():
        for exercise, sets in exercises.items():
            exercise_totals[exercise] += sets

    if not exercise_totals:
        st.info("No strength sets (1-6 reps) in program yet.")
        return

    # Create daily breakdown table
    all_exercises = sorted(set(e for d in str_sets.values() for e in d.keys()))

    if all_exercises:
        # Build DataFrame
        data = []
        for exercise in all_exercises:
            row = {"Exercise": exercise}
            total = 0
            for day in DAYS:
                day_sets = str_sets[day].get(exercise, 0)
                row[day[:3]] = day_sets
                total += day_sets
            row["Total"] = total
            data.append(row)

        df = pd.DataFrame(data)
        df = df.sort_values("Total", ascending=False)

        # Summary metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Weekly Sets", f"{df['Total'].sum():.1f}")
        with col2:
            st.metric("Exercises Tracked", len(df))
        with col3:
            top_exercise = df.iloc[0]["Exercise"] if len(df) > 0 else "N/A"
            st.metric("Most Trained", top_exercise)

        # Format and display table
        st.dataframe(
            df.style.format({col: "{:.1f}" for col in df.columns if col != "Exercise"}),
            use_container_width=True,
            hide_index=True,
        )

        # Bar chart
        fig = px.bar(
            df.head(15),
            x="Exercise",
            y="Total",
            title="Weekly Strength Sets by Exercise",
            color="Total",
            color_continuous_scale="Reds",
        )
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)

        # Big 5 coverage (in summary view)
        if program is not None:
            mode = st.session_state.user_profile.get(
                "strength_tracking_mode", "compound"
            )
            if mode == "compound":
                covered, missing_cats = get_big5_coverage(program)
                if missing_cats:
                    st.markdown("---")
                    st.warning(
                        f"⚠️ **Big 5 Coverage: {len(covered)}/{len(BIG_5_CATEGORIES)}** — "
                        f"Missing: {', '.join(missing_cats)}. "
                        f"Consider adding these for balanced strength."
                    )

        # Drill-down per exercise
        if program is not None and exercises_lib is not None:
            st.markdown("---")
            st.markdown("**🔍 Click an exercise for details:**")

            # Build per-day info for each exercise
            exercise_per_day = defaultdict(lambda: defaultdict(float))
            for day, exs in str_sets.items():
                for ex, sets in exs.items():
                    exercise_per_day[ex][day] += sets

            for ex_name in df["Exercise"].values:
                total = exercise_totals[ex_name]
                days_trained = sum(
                    1 for d in DAYS if exercise_per_day[ex_name].get(d, 0) > 0
                )

                # Count direct sets from program
                direct_sets = sum(
                    entry["sets"]
                    for day_exs in program.values()
                    for entry in day_exs
                    if entry["exercise"] == ex_name and entry["reps"] <= 6
                )

                # Simplified info dict compatible with render_strength_drilldown
                info = {
                    "direct_sets": direct_sets,
                    "total_fractional": total,
                    "status": "optimal",
                    "days_trained": days_trained,
                }

                render_strength_drilldown(
                    ex_name, info, program, exercises_lib, key_prefix="summary_str"
                )


def render_combined_summary(hyp_sets, str_sets):
    """Render combined view of both hypertrophy and strength."""
    st.subheader("Weekly Training Overview")

    # Calculate totals per day
    daily_hyp = {day: sum(muscles.values()) for day, muscles in hyp_sets.items()}
    daily_str = {day: sum(exercises.values()) for day, exercises in str_sets.items()}

    # Create summary DataFrame
    data = []
    for day in DAYS:
        data.append(
            {
                "Day": day[:3],
                "Hypertrophy Sets": daily_hyp[day],
                "Strength Sets": daily_str[day],
                "Total Sets": daily_hyp[day] + daily_str[day],
            }
        )

    df = pd.DataFrame(data)

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Weekly Hypertrophy", f"{sum(daily_hyp.values()):.1f}")
    with col2:
        st.metric("Weekly Strength", f"{sum(daily_str.values()):.1f}")
    with col3:
        st.metric("Total Weekly Sets", f"{df['Total Sets'].sum():.1f}")
    with col4:
        training_days = sum(1 for d in DAYS if daily_hyp[d] + daily_str[d] > 0)
        st.metric("Training Days", training_days)

    # Display table
    st.dataframe(
        df.style.format(
            {
                "Hypertrophy Sets": "{:.1f}",
                "Strength Sets": "{:.1f}",
                "Total Sets": "{:.1f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    # Stacked bar chart
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            name="Hypertrophy",
            x=[d[:3] for d in DAYS],
            y=[daily_hyp[d] for d in DAYS],
            marker_color="royalblue",
        )
    )
    fig.add_trace(
        go.Bar(
            name="Strength",
            x=[d[:3] for d in DAYS],
            y=[daily_str[d] for d in DAYS],
            marker_color="firebrick",
        )
    )
    fig.update_layout(
        barmode="stack",
        title="Daily Training Distribution",
        xaxis_title="Day",
        yaxis_title="Fractional Sets",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_program_actions():
    """Render program save/load/clear actions."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("📁 Program Actions")

    # Program name
    st.session_state.program_name = st.sidebar.text_input(
        "Program Name",
        value=st.session_state.program_name,
    )

    # Show program summary
    num_weeks = len(st.session_state.program_weeks)
    st.sidebar.caption(f"📊 {num_weeks} week{'s' if num_weeks > 1 else ''} in program")

    # Export program (new multi-week format)
    program_data = export_program_to_json()
    st.sidebar.download_button(
        label="📥 Save Program (JSON)",
        data=json.dumps(program_data, indent=2),
        file_name=f"{st.session_state.program_name.replace(' ', '_').lower()}.json",
        mime="application/json",
        use_container_width=True,
    )

    # Import program
    uploaded_file = st.sidebar.file_uploader("📤 Import Program", type=["json"])
    if uploaded_file is not None:
        # Show file info
        st.sidebar.caption(f"File: {uploaded_file.name}")

        # Load button
        if st.sidebar.button("📂 Load Program from File", use_container_width=True):
            try:
                # Reset file position to beginning
                uploaded_file.seek(0)
                program_data = json.load(uploaded_file)

                # Use the new import function that handles both formats
                if import_program_from_json(program_data):
                    st.sidebar.success("Program loaded successfully!")
                    st.rerun()
            except Exception as e:
                st.sidebar.error(f"Error loading: {e}")

    # Clear program with confirmation
    with st.sidebar.popover("🗑️ Clear All Weeks"):
        st.warning("⚠️ This will delete all weeks and exercises!")
        st.caption("This action cannot be undone.")
        if st.button("Yes, Clear Everything", type="primary", key="confirm_clear_all"):
            st.session_state.program_weeks = [
                {
                    "name": "Week 1",
                    "type": "training",
                    "days": {day: [] for day in DAYS},
                    "notes": "",
                }
            ]
            st.session_state.current_week = 0
            st.session_state.program = {day: [] for day in DAYS}  # Legacy
            st.rerun()


def render_quick_templates():
    """Render quick template options using templates from JSON file."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚡ Quick Templates")

    # Load templates from JSON
    all_templates = load_program_templates()

    if not all_templates:
        st.sidebar.warning("No templates available")
        return

    # Get category list
    categories = list(all_templates.keys())

    template_category = st.sidebar.selectbox(
        "Template Category",
        categories,
        key="template_category",
    )

    # Get templates for selected category
    category_templates = all_templates.get(template_category, {})
    template_names = ["Select..."] + list(category_templates.keys())

    template = st.sidebar.selectbox(
        "Load Template",
        template_names,
        key="template_select",
    )

    if st.sidebar.button("Apply Template") and template != "Select...":
        apply_template(template_category, template)
        st.rerun()


def apply_template(category, template_name):
    """Apply a program template from the JSON file."""
    # Load templates
    all_templates = load_program_templates()

    if not all_templates:
        st.error("Could not load templates")
        return

    # Get template data
    category_templates = all_templates.get(category, {})
    template_data = category_templates.get(template_name, {})

    if not template_data:
        st.error(f"Template '{template_name}' not found in category '{category}'")
        return

    # Clear current week's program
    week_idx = st.session_state.current_week
    st.session_state.program_weeks[week_idx]["days"] = {day: [] for day in DAYS}

    # Get reference to current week days
    program = st.session_state.program_weeks[week_idx]["days"]

    # Apply template days
    for day, exercises in template_data.get("days", {}).items():
        if day in program:
            program[day] = [dict(ex) for ex in exercises]  # Deep copy

    # Set program name
    st.session_state.program_name = template_data.get("program_name", template_name)

    # Also update legacy format for compatibility
    st.session_state.program = program


# Templates have been moved to data/program_templates.json
# See apply_template() function above for the new implementation


# CLEANUP: Delete from here to render_muscle_balance function
# This section will be removed


def render_muscle_balance(hyp_sets, exercises):
    """Render muscle balance analysis."""
    st.subheader("⚖️ Muscle Balance Analysis")

    # Aggregate totals
    muscle_totals = defaultdict(float)
    for day, muscles in hyp_sets.items():
        for muscle, sets in muscles.items():
            muscle_totals[muscle] += sets

    if not muscle_totals:
        st.info("Add exercises with >6 reps to see muscle balance.")
        return

    # Calculate push vs pull (using free-exercise-db muscle names, title-cased)
    push_muscles = {
        "Chest",
        "Shoulders",
        "Triceps",
    }
    pull_muscles = {
        "Lats",
        "Middle Back",
        "Lower Back",
        "Traps",
        "Biceps",
        "Forearms",
    }

    push_total = sum(sets for m, sets in muscle_totals.items() if m in push_muscles)
    pull_total = sum(sets for m, sets in muscle_totals.items() if m in pull_muscles)

    # Calculate upper vs lower
    upper_muscles = push_muscles | pull_muscles | {"Abdominals", "Neck"}
    lower_muscles = {
        "Quadriceps",
        "Glutes",
        "Hamstrings",
        "Calves",
        "Adductors",
        "Abductors",
    }

    upper_total = sum(sets for m, sets in muscle_totals.items() if m in upper_muscles)
    lower_total = sum(sets for m, sets in muscle_totals.items() if m in lower_muscles)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Push Sets", f"{push_total:.1f}")
    with col2:
        st.metric("Pull Sets", f"{pull_total:.1f}")
    with col3:
        if push_total > 0:
            ratio = pull_total / push_total
            st.metric("Pull:Push Ratio", f"{ratio:.2f}:1")
            if ratio < 0.8:
                st.warning("⚠️ Add more pulling")
            elif ratio > 1.2:
                st.info("Pull emphasis")
            else:
                st.success("✅ Balanced")
        else:
            st.metric("Pull:Push Ratio", "N/A")

    with col4:
        if upper_total > 0:
            ratio = lower_total / upper_total
            st.metric("Lower:Upper Ratio", f"{ratio:.2f}:1")
        else:
            st.metric("Lower:Upper Ratio", "N/A")

    # Pie chart of muscle distribution
    col1, col2 = st.columns(2)

    with col1:
        # Group into categories
        categories = {
            "Chest": sum(s for m, s in muscle_totals.items() if "Pectoral" in m),
            "Back": sum(
                s
                for m, s in muscle_totals.items()
                if m in {"Latissimus Dorsi", "Rhomboids", "Trapezius"}
            ),
            "Shoulders": sum(s for m, s in muscle_totals.items() if "Deltoid" in m),
            "Arms": sum(
                s
                for m, s in muscle_totals.items()
                if m in {"Biceps Brachii", "Triceps Brachii", "Brachialis"}
            ),
            "Quads": muscle_totals.get("Quadriceps", 0),
            "Glutes/Hams": sum(
                s
                for m, s in muscle_totals.items()
                if m in {"Gluteus Maximus", "Hamstrings", "Glutes"}
            ),
            "Core": sum(
                s
                for m, s in muscle_totals.items()
                if m in {"Core", "Obliques", "Rectus Abdominis"}
            ),
        }
        categories = {k: v for k, v in categories.items() if v > 0}

        if categories:
            fig = px.pie(
                values=list(categories.values()),
                names=list(categories.keys()),
                title="Muscle Group Distribution",
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Push vs Pull pie
        push_pull = {"Push": push_total, "Pull": pull_total}
        push_pull = {k: v for k, v in push_pull.items() if v > 0}

        if push_pull:
            fig = px.pie(
                values=list(push_pull.values()),
                names=list(push_pull.keys()),
                title="Push vs Pull Distribution",
                color_discrete_sequence=["#ff6b6b", "#4ecdc4"],
            )
            st.plotly_chart(fig, use_container_width=True)


def render_day_compact_view(program, exercises):
    """Render a compact weekly view showing all days."""
    st.header("🗓️ Weekly Overview")

    # Create 7 columns for the week
    cols = st.columns(7)

    for i, day in enumerate(DAYS):
        with cols[i]:
            st.markdown(f"**{day[:3]}**")
            day_exercises = program.get(day, [])

            if day_exercises:
                # Calculate day totals
                hyp_sets = 0
                str_sets = 0

                for entry in day_exercises:
                    rep_icon = "💪" if entry["reps"] > 6 else "🏋️"
                    ex_name = entry["exercise"]
                    short_name = ex_name[:12] + ".." if len(ex_name) > 12 else ex_name

                    # Get target muscle
                    ex_info = get_exercise_by_name(exercises, ex_name)
                    target = ""
                    if ex_info:
                        target = get_primary_muscle(ex_info)[:8]

                    st.caption(f"{rep_icon} {short_name}")

                    # Show weight if 1RM exists
                    one_rm = st.session_state.exercise_1rm.get(entry["exercise"])
                    if one_rm:
                        weight = get_weight_for_reps(one_rm, entry["reps"])
                        st.caption(f"  {entry['sets']}×{entry['reps']}@{weight:.0f}kg")
                    else:
                        st.caption(f"  {entry['sets']}×{entry['reps']} ({target})")

                    # Count sets
                    if entry["reps"] > 6:
                        hyp_sets += entry["sets"]
                    else:
                        str_sets += entry["sets"]

                # Show day totals
                st.markdown("---")
                if hyp_sets > 0:
                    st.caption(f"💪 {hyp_sets} hyp")
                if str_sets > 0:
                    st.caption(f"🏋️ {str_sets} str")
            else:
                st.caption("Rest day")


def get_goal_rir(reps):
    """
    Get goal RIR based on rep range (from Muscle & Strength Pyramid).
    - 4-6 reps/set: 4-0 RIR
    - 6-8 reps/set: 3 RIR to failure
    - 8-12 reps/set: 2 RIR to failure
    - >12 reps/set: 1 RIR to failure
    """
    if reps <= 6:
        return "0-4"  # Strength: load dictates, can be further from failure
    elif reps <= 8:
        return "0-3"
    elif reps <= 12:
        return "0-2"
    else:
        return "0-1"


def render_custom_exercises():
    """Render the custom exercises management view."""
    st.header("➕ Custom Exercises")
    st.caption("Add your own exercises to the library")

    # Available muscle groups (from free-exercise-db)
    MUSCLE_OPTIONS = [
        "abdominals",
        "abductors",
        "adductors",
        "biceps",
        "calves",
        "chest",
        "forearms",
        "front deltoids",
        "glutes",
        "hamstrings",
        "lats",
        "lower back",
        "middle back",
        "neck",
        "quadriceps",
        "rear deltoids",
        "rotator cuff",
        "side deltoids",
        "traps",
        "triceps",
    ]

    tab_add, tab_import, tab_manage = st.tabs(
        ["✏️ Add Manually", "📥 Import JSON", "📋 Manage"]
    )

    with tab_add:
        st.subheader("Add New Exercise")

        # Source name
        existing_sources = list(st.session_state.custom_exercises.keys())
        source_options = existing_sources + ["+ Create new source"]

        source_selection = st.selectbox(
            "Source Collection *",
            options=source_options if existing_sources else ["+ Create new source"],
            help="Group your exercises by source (e.g., 'my_exercises', 'gym_machines')",
        )

        if source_selection == "+ Create new source":
            source_name = st.text_input(
                "New Source Name *",
                placeholder="e.g., my_exercises",
                help="Use lowercase with underscores, no spaces",
            )
            # Clean the source name
            if source_name:
                import re

                source_name = re.sub(r"[^a-zA-Z0-9_]", "_", source_name.lower())
        else:
            source_name = source_selection

        st.markdown("---")

        # Required fields
        st.markdown("**Required Fields**")

        exercise_name = st.text_input(
            "Exercise Name *", placeholder="e.g., Cable Lateral Raise"
        )

        primary_muscles = st.multiselect(
            "Primary Muscles *",
            options=MUSCLE_OPTIONS,
            help="Select the main muscle(s) targeted by this exercise",
        )

        secondary_muscles = st.multiselect(
            "Secondary Muscles",
            options=[m for m in MUSCLE_OPTIONS if m not in primary_muscles],
            help="Select synergist muscles (optional but recommended)",
        )

        st.markdown("---")
        st.markdown("**Optional Fields**")

        col1, col2 = st.columns(2)

        with col1:
            category = st.selectbox(
                "Category",
                options=[
                    "",
                    "strength",
                    "stretching",
                    "plyometrics",
                    "cardio",
                    "strongman",
                    "powerlifting",
                    "olympic weightlifting",
                ],
                index=0,
            )

            level = st.selectbox(
                "Level", options=["", "beginner", "intermediate", "expert"], index=0
            )

            mechanic = st.selectbox(
                "Mechanic", options=["", "compound", "isolation"], index=0
            )

        with col2:
            force = st.selectbox(
                "Force", options=["", "push", "pull", "static"], index=0
            )

            equipment = st.text_input(
                "Equipment", placeholder="e.g., cable, dumbbell, barbell"
            )

        # Instructions
        instructions_text = st.text_area(
            "Instructions (one step per line)",
            placeholder="Step 1: ...\nStep 2: ...\nStep 3: ...",
            height=100,
        )

        # Add button
        if st.button("➕ Add Exercise", type="primary"):
            # Validation
            errors = []
            if not source_name:
                errors.append("Source name is required")
            if not exercise_name:
                errors.append("Exercise name is required")
            if not primary_muscles:
                errors.append("At least one primary muscle is required")

            if errors:
                for error in errors:
                    st.error(error)
            else:
                # Create exercise object
                new_exercise = {
                    "name": exercise_name,
                    "primaryMuscles": primary_muscles,
                    "secondaryMuscles": secondary_muscles,
                }

                # Add optional fields if provided
                if category:
                    new_exercise["category"] = category
                if level:
                    new_exercise["level"] = level
                if mechanic:
                    new_exercise["mechanic"] = mechanic
                if force:
                    new_exercise["force"] = force
                if equipment:
                    new_exercise["equipment"] = equipment
                if instructions_text.strip():
                    new_exercise["instructions"] = [
                        line.strip()
                        for line in instructions_text.split("\n")
                        if line.strip()
                    ]

                if add_custom_exercise(source_name, new_exercise):
                    st.success(f"✅ Added '{exercise_name}' to [{source_name}]")
                    st.rerun()
                else:
                    st.error(
                        f"Exercise '{exercise_name}' already exists in [{source_name}]"
                    )

    with tab_import:
        st.subheader("Import from JSON")
        st.markdown(
            """
            Import exercises from a JSON file. The format should match the 
            [free-exercise-db](https://github.com/yuhonas/free-exercise-db) structure.
            
            **Required fields:** `name`, `primaryMuscles`
            
            **Optional fields:** `secondaryMuscles`, `force`, `level`, `mechanic`, 
            `equipment`, `instructions`, `category`, `images`
            """
        )

        # Source name for import
        existing_sources = list(st.session_state.custom_exercises.keys())
        import_source_options = existing_sources + ["+ Create new source"]

        import_source_selection = st.selectbox(
            "Import to Source *",
            options=(
                import_source_options if existing_sources else ["+ Create new source"]
            ),
            key="import_source_select",
        )

        if import_source_selection == "+ Create new source":
            import_source_name = st.text_input(
                "New Source Name *",
                placeholder="e.g., imported_exercises",
                key="import_source_name",
            )
            if import_source_name:
                import re

                import_source_name = re.sub(
                    r"[^a-zA-Z0-9_]", "_", import_source_name.lower()
                )
        else:
            import_source_name = import_source_selection

        # File upload
        uploaded_file = st.file_uploader(
            "Upload JSON file", type=["json"], key="custom_exercise_json"
        )

        if uploaded_file and import_source_name:
            if st.button("📥 Import Exercises", type="primary"):
                try:
                    json_data = json.load(uploaded_file)
                    success, errors_count, error_msgs = (
                        import_custom_exercises_from_json(json_data, import_source_name)
                    )

                    if success > 0:
                        st.success(f"✅ Successfully imported {success} exercise(s)")
                    if errors_count > 0:
                        st.warning(
                            f"⚠️ {errors_count} exercise(s) could not be imported"
                        )
                        with st.expander("View errors"):
                            for msg in error_msgs:
                                st.text(f"• {msg}")

                    if success > 0:
                        st.rerun()

                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON: {e}")

        # Example JSON
        with st.expander("📝 Example JSON format"):
            st.code(
                """[
  {
    "name": "My Custom Exercise",
    "primaryMuscles": ["chest", "front deltoids"],
    "secondaryMuscles": ["triceps"],
    "force": "push",
    "level": "intermediate",
    "mechanic": "compound",
    "equipment": "cable",
    "instructions": [
      "Step 1: Setup...",
      "Step 2: Execute...",
      "Step 3: Return..."
    ],
    "category": "strength"
  }
]""",
                language="json",
            )

    with tab_manage:
        st.subheader("Manage Custom Exercises")

        custom_exercises = st.session_state.custom_exercises

        if not custom_exercises:
            st.info(
                "No custom exercises added yet. Use the 'Add Manually' or 'Import JSON' tabs to add exercises."
            )
        else:
            # Summary
            total_custom = sum(len(exs) for exs in custom_exercises.values())
            st.metric("Total Custom Exercises", total_custom)

            # Export all
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("📤 Export All"):
                    export_data = {}
                    for source, exercises in custom_exercises.items():
                        export_data[source] = exercises
                    st.download_button(
                        "💾 Download JSON",
                        data=json.dumps(export_data, indent=2),
                        file_name="custom_exercises.json",
                        mime="application/json",
                    )

            st.markdown("---")

            # List by source
            for source_name, exercises in custom_exercises.items():
                with st.expander(
                    f"📁 {source_name} ({len(exercises)} exercises)", expanded=True
                ):
                    # Export this source
                    col1, col2 = st.columns([3, 1])
                    with col2:
                        st.download_button(
                            "📤 Export",
                            data=json.dumps(exercises, indent=2),
                            file_name=f"{source_name}_exercises.json",
                            mime="application/json",
                            key=f"export_{source_name}",
                        )

                    # List exercises
                    for ex in exercises:
                        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])

                        with col1:
                            st.markdown(f"**{ex['name']}**")
                        with col2:
                            primary = ", ".join(ex.get("primaryMuscles", []))
                            st.caption(f"🎯 {primary}")
                        with col3:
                            secondary = (
                                ", ".join(ex.get("secondaryMuscles", [])) or "none"
                            )
                            st.caption(f"↳ {secondary}")
                        with col4:
                            if st.button(
                                "🗑️",
                                key=f"del_{source_name}_{ex['name']}",
                                help="Delete",
                            ):
                                remove_custom_exercise(source_name, ex["name"])
                                st.rerun()


def render_exercise_library(exercises):
    """Render an exercise library browser with search, images, and instructions."""
    # Count custom vs base exercises
    custom_count = sum(
        len(exs) for exs in st.session_state.get("custom_exercises", {}).values()
    )
    base_count = len([e for e in exercises if e.get("_source") == "free-exercise-db"])

    st.header("📚 Exercise Library")
    st.caption(
        f"Browse {len(exercises)} exercises ({custom_count} custom, {base_count} from "
        "[free-exercise-db](https://github.com/yuhonas/free-exercise-db)) "
        "• [Browse online](https://yuhonas.github.io/free-exercise-db/)"
    )

    # Search and filter
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        search_term = st.text_input("🔍 Search exercises", key="lib_search")

    with col2:
        # Source filter
        sources = ["All", "free-exercise-db"] + list(
            st.session_state.get("custom_exercises", {}).keys()
        )
        selected_source = st.selectbox("Source", sources, key="lib_source")

    with col3:
        categories = ["All"] + sorted(
            set(
                ex.get("category", "Unknown").title()
                for ex in exercises
                if ex.get("category")
            )
        )
        selected_category = st.selectbox("Category", categories, key="lib_category")

    with col4:
        muscles = ["All"] + sorted(
            set(
                muscle.title()
                for ex in exercises
                for muscle in ex.get("primaryMuscles", [])
                if muscle
            )
        )
        selected_muscle = st.selectbox("Primary Muscle", muscles, key="lib_muscle")

    with col5:
        equipment_list = ["All"] + sorted(
            set(
                ex.get("equipment", "Unknown").title()
                for ex in exercises
                if ex.get("equipment")
            )
        )
        selected_equipment = st.selectbox(
            "Equipment", equipment_list, key="lib_equipment"
        )

    # Filter exercises
    filtered = exercises

    if search_term:
        search_lower = search_term.lower()
        filtered = [
            ex
            for ex in filtered
            if search_lower in ex.get("name", "").lower()
            or search_lower in " ".join(ex.get("instructions", [])).lower()
        ]

    if selected_source != "All":
        filtered = [ex for ex in filtered if ex.get("_source") == selected_source]

    if selected_category != "All":
        filtered = [
            ex for ex in filtered if ex.get("category", "").title() == selected_category
        ]

    if selected_muscle != "All":
        filtered = [
            ex
            for ex in filtered
            if selected_muscle.lower()
            in [m.lower() for m in ex.get("primaryMuscles", [])]
        ]

    if selected_equipment != "All":
        filtered = [
            ex
            for ex in filtered
            if ex.get("equipment", "").title() == selected_equipment
        ]

    st.caption(f"Showing {len(filtered)} exercises")

    # Pagination
    items_per_page = 12
    total_pages = max(1, (len(filtered) + items_per_page - 1) // items_per_page)

    if "lib_page" not in st.session_state:
        st.session_state.lib_page = 0

    # Reset page if filters changed
    if len(filtered) <= st.session_state.lib_page * items_per_page:
        st.session_state.lib_page = 0

    # Page navigation
    col1, col2, col3 = st.columns([1, 3, 1])
    with col1:
        if st.button("◀ Previous", disabled=st.session_state.lib_page == 0):
            st.session_state.lib_page -= 1
            st.rerun()
    with col2:
        st.markdown(
            f"<center>Page {st.session_state.lib_page + 1} of {total_pages}</center>",
            unsafe_allow_html=True,
        )
    with col3:
        if st.button("Next ▶", disabled=st.session_state.lib_page >= total_pages - 1):
            st.session_state.lib_page += 1
            st.rerun()

    # Display exercises in a grid
    start_idx = st.session_state.lib_page * items_per_page
    end_idx = min(start_idx + items_per_page, len(filtered))
    page_exercises = filtered[start_idx:end_idx]

    # Create a 3-column grid
    cols = st.columns(3)

    for i, exercise in enumerate(page_exercises):
        with cols[i % 3]:
            with st.container():
                # Exercise card
                source = exercise.get("_source", "free-exercise-db")
                if source != "free-exercise-db":
                    st.markdown(f"**{exercise.get('name', 'Unknown')}** `[{source}]`")
                else:
                    st.markdown(f"**{exercise.get('name', 'Unknown')}**")

                # Show first image as thumbnail (only for free-exercise-db)
                images = exercise.get("images", [])
                if images and source == "free-exercise-db":
                    thumb_url = get_exercise_image_url(images[0], thumbnail=True)
                    st.image(thumb_url, use_container_width=True)
                elif source != "free-exercise-db":
                    st.info("📝 Custom exercise")

                # Quick info
                primary = get_primary_muscle(exercise)
                level = exercise.get("level", "N/A")
                equipment = exercise.get("equipment", "N/A")

                st.caption(f"🎯 {primary} | 📊 {level.title() if level else 'N/A'}")
                st.caption(f"🏋️ {equipment.title() if equipment else 'N/A'}")

                # Expand for details
                with st.expander("📋 Details"):
                    # Secondary muscles
                    secondary = get_secondary_muscles(exercise)
                    if secondary:
                        st.markdown(f"**Secondary:** {', '.join(secondary)}")

                    # All images
                    if len(images) > 1:
                        st.markdown("**Images:**")
                        render_exercise_images(
                            exercise, key_prefix=f"lib_{exercise.get('id', i)}"
                        )

                    # Instructions
                    instructions = exercise.get("instructions", [])
                    if instructions:
                        st.markdown("**Instructions:**")
                        for j, step in enumerate(instructions, 1):
                            st.markdown(f"{j}. {step}")

                st.markdown("---")


def render_workout_sheet(program, show_header=True):
    """Generate a printable workout sheet with all weights."""
    if show_header:
        st.header("📄 Workout Sheet")
    st.caption("Printable workout sheet with calculated weights and goal RIR")

    # Check if any 1RMs are saved
    if not st.session_state.exercise_1rm:
        st.warning("Add 1RM values in the 1RM Manager to see suggested weights.")

    # Build workout sheet data
    sheet_data = []

    for day in DAYS:
        day_exercises = program.get(day, [])
        if not day_exercises:
            continue

        for entry in day_exercises:
            one_rm = st.session_state.exercise_1rm.get(entry["exercise"])
            if one_rm:
                weight = get_weight_for_reps(one_rm, entry["reps"])
                pct = (weight / one_rm) * 100
            else:
                weight = None
                pct = None

            goal_rir = get_goal_rir(entry["reps"])

            sheet_data.append(
                {
                    "Day": day,
                    "Exercise": entry["exercise"],
                    "Sets": entry["sets"],
                    "Reps": entry["reps"],
                    "Weight (kg)": f"{weight:.1f}" if weight else "N/A",
                    "% 1RM": f"{pct:.0f}%" if pct else "N/A",
                    "Goal RIR": goal_rir,
                    "Type": "Strength" if entry["reps"] <= 6 else "Hypertrophy",
                }
            )

    if sheet_data:
        df = pd.DataFrame(sheet_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # RIR legend
        with st.expander("ℹ️ RIR Guidelines"):
            st.markdown(
                """
            **RIR = Reps In Reserve** (how many more reps you could do)
            
            | Rep Range | Goal RIR | Notes |
            |-----------|----------|-------|
            | 1-6 reps | 0-4 RIR | Strength: load dictates proximity to failure |
            | 6-8 reps | 0-3 RIR | Moderate proximity to failure |
            | 8-12 reps | 0-2 RIR | Classic hypertrophy range |
            | >12 reps | 0-1 RIR | Need to be close to failure |
            """
            )

        # Create downloadable CSV
        csv = df.to_csv(index=False)
        st.download_button(
            label="📥 Download Workout Sheet (CSV)",
            data=csv,
            file_name=f"{st.session_state.program_name.replace(' ', '_').lower()}_workout_sheet.csv",
            mime="text/csv",
        )

        # Create text version for easy viewing
        with st.expander("📝 Text Version (copy/paste friendly)"):
            current_day = None
            text_output = []

            for row in sheet_data:
                if row["Day"] != current_day:
                    current_day = row["Day"]
                    text_output.append(f"\n=== {current_day.upper()} ===")

                weight_str = row["Weight (kg)"] if row["Weight (kg)"] != "N/A" else "?"
                text_output.append(
                    f"  {row['Exercise']}: {row['Sets']}×{row['Reps']} @ {weight_str}kg (RIR {row['Goal RIR']})"
                )

            st.code("\n".join(text_output), language=None)
    else:
        st.info("Add exercises to your program to generate a workout sheet.")


def main():
    """Main application entry point."""
    initialize_session_state()

    # Load exercise library and merge with custom exercises
    base_exercises = load_exercise_library()
    exercises = get_all_exercises(base_exercises)

    # Create sorted list of exercise names (custom exercises first due to get_all_exercises order)
    # Use display names for the list but keep mapping to actual names
    exercise_names = [get_exercise_display_name(ex) for ex in exercises]
    # Create mapping from display name to actual exercise name
    display_to_name = {get_exercise_display_name(ex): ex["name"] for ex in exercises}
    name_to_display = {ex["name"]: get_exercise_display_name(ex) for ex in exercises}

    # Sidebar
    st.sidebar.title("📋 Program Builder")
    st.sidebar.markdown("Build your training program and analyze fractional sets.")

    # View selector
    view = st.sidebar.radio(
        "View",
        [
            "📅 Weekly Editor",  # Includes compact profile in stats panel
            "📚 Exercises & 1RM",  # Library + Custom + 1RM Manager
            "📊 Analysis",  # Combined Program Designer + Analysis
            "📖 Guidelines",
        ],
    )

    # Show user profile summary
    profile = st.session_state.user_profile
    targets = get_volume_targets()
    st.sidebar.markdown(
        f"**👤 Profile:** {profile['training_status']} | {profile['volume_tier']}"
    )
    st.sidebar.caption(
        f"Targets: {targets['hypertrophy']['low']}-{targets['hypertrophy']['high']} sets/muscle/wk"
    )

    # Show custom exercises count
    custom_count = sum(len(exs) for exs in st.session_state.custom_exercises.values())
    if custom_count > 0:
        st.sidebar.info(f"➕ {custom_count} custom exercise(s)")

    # Show 1RM count
    rm_count = len(st.session_state.exercise_1rm)
    if rm_count > 0:
        st.sidebar.success(f"🎯 {rm_count} exercise 1RMs saved")
    else:
        st.sidebar.info("🎯 No 1RMs saved yet - add some for weight suggestions!")

    # Sidebar tools
    render_quick_templates()
    # Note: Copy day functionality is now inline in the weekly editor
    render_program_actions()

    # Exercise search/filter in sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔍 Exercise Filter")

    # Source filter (custom sources + free-exercise-db)
    sources = ["All", "free-exercise-db"] + list(
        st.session_state.custom_exercises.keys()
    )
    selected_source = st.sidebar.selectbox("Source", sources)

    # Category filter (using free-exercise-db format)
    categories = sorted(
        set(
            ex.get("category", "Unknown").title()
            for ex in exercises
            if ex.get("category")
        )
    )
    selected_category = st.sidebar.selectbox("Category", ["All"] + categories)

    # Muscle filter (using primaryMuscles from free-exercise-db)
    muscles = sorted(
        set(
            muscle.title()
            for ex in exercises
            for muscle in ex.get("primaryMuscles", [])
            if muscle
        )
    )
    selected_muscle = st.sidebar.selectbox("Target Muscle", ["All"] + muscles)

    # Equipment filter
    equipment_list = sorted(
        set(
            ex.get("equipment", "Unknown").title()
            for ex in exercises
            if ex.get("equipment")
        )
    )
    selected_equipment = st.sidebar.selectbox("Equipment", ["All"] + equipment_list)

    # Apply filters
    if (
        selected_source != "All"
        or selected_category != "All"
        or selected_muscle != "All"
        or selected_equipment != "All"
    ):
        filtered_exercises = [
            get_exercise_display_name(ex)
            for ex in exercises
            if (selected_source == "All" or ex.get("_source") == selected_source)
            and (
                selected_category == "All"
                or ex.get("category", "").title() == selected_category
            )
            and (
                selected_muscle == "All"
                or selected_muscle.lower()
                in [m.lower() for m in ex.get("primaryMuscles", [])]
            )
            and (
                selected_equipment == "All"
                or ex.get("equipment", "").title() == selected_equipment
            )
        ]
        exercise_names = filtered_exercises  # Already in correct order (custom first)
        st.sidebar.caption(f"Showing {len(exercise_names)} exercises")

    # Main title with research reference
    st.title(f"📋 {st.session_state.program_name}")

    # Research reference and explanation
    with st.expander("ℹ️ About Fractional Set Counting (click to learn more)"):
        st.markdown(
            """
            This program builder implements the **fractional set counting method** from recent 
            resistance training research.
            
            **📚 Research Reference:**
            
            > Pelland JC, Remmert JF, Robinson ZP, Hinson SR, Zourdos MC. *The Resistance Training 
            > Dose Response: Meta-Regressions Exploring the Effects of Weekly Volume and Frequency 
            > on Muscle Hypertrophy and Strength Gains.* Sports Med. 2025 Dec 4. 
            > [DOI: 10.1007/s40279-025-02344-w](https://doi.org/10.1007/s40279-025-02344-w)
            
            **🔬 Key Findings:**
            
            - The **fractional quantification method** showed the strongest relative evidence for 
              predicting training adaptations
            - **Direct sets** (targeting the measured muscle/lift) count as **1.0 set**
            - **Indirect sets** (synergist/related work) count as **0.5 set**
            - Volume and frequency have unique dose-response relationships with hypertrophy and strength
            - Strength gains show more pronounced diminishing returns than hypertrophy
            - Frequency has consistently identifiable effects on strength but not hypertrophy
            
            **💡 How This Tool Uses It:**
            
            - **Hypertrophy (>6 reps):** Primary muscle = 1.0 set, synergist muscles = 0.5 set
            - **Strength (1-6 reps):** Direct lift work = 1.0 set, related exercises = 0.5 set
            
            This allows for more accurate tracking of effective training dose per muscle group 
            and per lift.
            
            ---
            
            **🏋️ Exercise Database:**
            
            This tool uses the **Free Exercise DB** - an open public domain exercise dataset with 
            800+ exercises including images and instructions.
            
            > 📦 GitHub: [yuhonas/free-exercise-db](https://github.com/yuhonas/free-exercise-db)
            > 
            > 🌐 Browse exercises: [yuhonas.github.io/free-exercise-db](https://yuhonas.github.io/free-exercise-db/)
            > 
            > 📜 License: [Unlicense](http://unlicense.org/) (Public Domain)
            """
        )

    if view == "📅 Weekly Editor":
        # Use the enhanced multi-week editor
        render_weekly_editor_enhanced(
            exercises, exercise_names, display_to_name, name_to_display
        )

    elif view == "📚 Exercises & 1RM":
        # Combined Exercise Library + Custom Exercises + 1RM Manager with tabs
        st.header("📚 Exercises & 1RM Data")
        lib_tab, custom_tab, rm_tab = st.tabs(
            ["🔍 Browse Library", "➕ My Custom Exercises", "🎯 1RM Manager"]
        )

        with lib_tab:
            render_exercise_library(exercises)

        with custom_tab:
            render_custom_exercises()

        with rm_tab:
            st.caption(
                "Track your 1RM values to get weight suggestions in the weekly editor"
            )
            render_1rm_manager(exercises, exercise_names, display_to_name)

    elif view == "📊 Analysis":
        # Combined Program Designer + Analysis with tabs
        st.header("📊 Program Analysis")
        current_week_days = get_current_week_days()
        hyp_sets = calculate_hypertrophy_sets(current_week_days, exercises)
        str_sets = calculate_strength_sets(current_week_days, exercises)

        # Apply analysis filters
        hyp_sets = filter_hypertrophy_results(hyp_sets)
        str_sets = filter_strength_results(str_sets, exercises)

        designer_tab, analysis_tab, balance_tab = st.tabs(
            ["🎨 Volume Check", "🔍 Detailed Analysis", "⚖️ Muscle Balance"]
        )

        with designer_tab:
            render_program_designer(current_week_days, exercises, hyp_sets, str_sets)

        with analysis_tab:
            render_program_analysis(current_week_days, exercises, hyp_sets, str_sets)

        with balance_tab:
            render_muscle_balance(hyp_sets, exercises)

    elif view == "📖 Guidelines":
        render_pyramid_guidelines()

    # Show summary section (except for views that have their own detailed analysis)
    if view not in ["📖 Guidelines", "📊 Analysis"]:
        st.markdown("---")

        # Calculate fractional sets for current week
        current_week_days = get_current_week_days()
        hyp_sets = calculate_hypertrophy_sets(current_week_days, exercises)
        str_sets = calculate_strength_sets(current_week_days, exercises)

        # Apply analysis filters
        hyp_sets = filter_hypertrophy_results(hyp_sets)
        str_sets = filter_strength_results(str_sets, exercises)

        render_weekly_summary(
            hyp_sets, str_sets, program=current_week_days, exercises=exercises
        )

        # Add muscle balance analysis
        st.markdown("---")
        render_muscle_balance(hyp_sets, exercises)

        # Quick analysis summary
        st.markdown("---")
        with st.expander("🔍 Quick Program Check (Click to expand)"):
            analysis = analyze_program_guidelines(
                current_week_days, exercises, hyp_sets, str_sets
            )

            # Show quick summary
            hyp_below = sum(
                1
                for m, info in analysis["hypertrophy"]["muscles"].items()
                if info["status"] in ["below_minimum", "below_practical"]
            )
            hyp_above = sum(
                1
                for m, info in analysis["hypertrophy"]["muscles"].items()
                if info["status"] in ["above_maximum", "above_practical"]
            )
            hyp_ok = sum(
                1
                for m, info in analysis["hypertrophy"]["muscles"].items()
                if info["status"] == "optimal"
            )

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Muscles - Optimal", hyp_ok, delta=None)
            with col2:
                st.metric("Muscles - Low Volume", hyp_below, delta=None)
            with col3:
                st.metric("Muscles - High Volume", hyp_above, delta=None)

            if (
                analysis["hypertrophy"]["issues"]
                or analysis["hypertrophy"]["suggestions"]
            ):
                st.markdown("**Issues/Suggestions:**")
                for issue in analysis["hypertrophy"]["issues"][:3]:
                    st.markdown(f"- 🔴 {issue}")
                for sugg in analysis["hypertrophy"]["suggestions"][:3]:
                    st.markdown(f"- 💡 {sugg}")

            st.caption("View full analysis in '🔍 Program Analysis' tab")

        # Volume recommendations
        st.markdown("---")
        with st.expander("📚 Volume Guidelines (Click to expand)"):
            render_volume_recommendations()


if __name__ == "__main__":
    main()
