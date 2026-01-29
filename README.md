# Fractional Sets Program Builder

A Streamlit-based application for building and analyzing strength training programs using fractional set counting methodology.

## Features

### Program Building

- **Multi-week program support** - Plan entire mesocycles with different week types (training, deload, testing, intensification, volume)
- **Day-by-day exercise planning** - Add exercises for each day of the week
- **Copy functionality** - Copy days within a week or copy entire weeks
- **Templates** - Quick-start templates including:
  - Basic splits (Upper/Lower, Push/Pull/Legs, Full Body)
  - MSP3 Bodybuilding programs (2-6 day options)
  - MSP3 Powerlifting programs

### Analysis & Tracking

- **Fractional set counting** - Automatically calculates volume using:
  - 1.0 sets for primary muscles
  - 0.5 sets for secondary/synergist muscles
- **Weekly statistics** - Track total sets, strength vs hypertrophy volume, body region balance
- **Muscle map visualization** - SVG body diagrams showing muscle activation by volume
- **Mesocycle graphs** - Visualize volume progression across weeks

### 1RM Management

- **Track your 1RM** for any exercise
- **Calculate from reps** - Estimate 1RM from weight × reps using Epley formula
- **Bulk import/export** - Upload/download 1RM data as JSON
- **Weight suggestions** - Get recommended weights for different rep ranges

### Workout Sheet

- **Printable workout sheet** with calculated weights based on your 1RMs
- **Goal RIR (Reps in Reserve)** guidance

### Exercise Library

- **870+ exercises** from the free-exercise-db database
- **Exercise details** including instructions and images
- **Custom exercises** - Add your own exercises manually or via JSON import

### Local Development

```bash
# Clone the repository
git clone <your-repo-url>
cd strength_training_app

# Create virtual environment (optional)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py
```

## Data Sources

- **Exercise Database**: [free-exercise-db](https://github.com/yuhonas/free-exercise-db) - A comprehensive, open-source exercise database
- **Training Guidelines**: Based on "The Muscle & Strength Pyramid" by Eric Helms

## Scientific Reference

The fractional set counting methodology is based on:

> Baz-Valle, E., Balsalobre-Fernández, C., Alix-Fages, C., & Santos-Concejero, J. (2022).
> A Systematic Review of The Effects of Different Resistance Training Volumes on Muscle Hypertrophy.
> Journal of Human Kinetics, 81, 199-210.

## License

This application is provided for personal use. The exercise database (free-exercise-db) is licensed under the [Unlicense](http://unlicense.org/) (Public Domain).
