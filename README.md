# simLP - Fork with Automated Feedback Generation

This is a fork of the original simLP project with enhanced functionality for automated feedback generation for LLM-generated Prolog rules.

## What's New in This Fork

### Added Feedback Generation System

This fork introduces an automated feedback generation mechanism that provides detailed, actionable feedback when comparing LLM-generated Prolog rules against ground truth definitions.

#### Key Enhancement: Feedback Generator Module

`feedback_generator.py` module under the `src/` directory that:

- **Analyzes atom-level differences** between generated and expected Prolog atoms
- **Provides structured feedback** on rule heads, bodies, structure, and variable usage
- **Generates comprehensive reports** for entire event descriptions
- **Formats feedback** in a clear, LLM-consumable format

#### Integration with Distance Metric

The `distance_metric.py` module has been enhanced with optional feedback generation.

### Usage
#### Option 1
```
# Clone the repository
git clone https://github.com/PanagopoulosGeorge/simLP.git
cd simLP

# Install in editable mode (for development)
pip install -e .

# Or install normally
pip install .
```
#### Option 2
```
# Build wheel and source distribution
python -m build

# Install from built package
pip install dist/simlp-0.1.0-py3-none-any.whl
```

```python
from simlp import parse_and_compute_distance

# Set generate_feedback=True to get automated feedback
print(help(parse_and_compute_distance))
```

### Feedback Output

The feedback generator produces structured output including:

- **Rule-by-rule analysis** with similarity scores
- **Detailed issue identification** for heads, bodies, structure, and variables
- **Overall recommendations** for improving rule generation
- **Summary statistics** comparing generated vs. expected rules

### Files Added/Modified

- **New:** `src/feedback_generator.py` - Complete feedback generation system
- **Modified:** `src/distance_metric.py` - Added optional feedback generation parameter and integration

---

For the original project documentation, see [README_main.md](README_main.md).
