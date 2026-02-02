"""
Manim Patterns Library

Curated, working examples of common Manim patterns that can be injected
into prompts to guide the LLM toward correct code generation.

These patterns are:
- Production-tested and known to work
- Following 3Blue1Brown style conventions
- Optimized for educational visualizations
"""

# =============================================================================
# NEURAL NETWORK PATTERNS
# =============================================================================

NEURAL_NETWORK_EXAMPLE = '''
# Neural Network Visualization Pattern
# Creates a simple feedforward network with animated connections

from manim import *
import numpy as np

class NeuralNetworkScene(Scene):
    def construct(self):
        self.camera.background_color = "#171717"
        
        # Create layers
        layer_sizes = [4, 6, 4, 2]  # Input, hidden1, hidden2, output
        layers = []
        
        for i, size in enumerate(layer_sizes):
            layer = VGroup(*[
                Circle(radius=0.2, color=BLUE, fill_opacity=0.3)
                for _ in range(size)
            ])
            layer.arrange(DOWN, buff=0.4)
            layer.move_to(RIGHT * (i * 2.5 - 3.75))
            layers.append(layer)
        
        all_nodes = VGroup(*layers)
        
        # Create connections
        connections = VGroup()
        for i in range(len(layers) - 1):
            for node1 in layers[i]:
                for node2 in layers[i + 1]:
                    line = Line(
                        node1.get_center(), 
                        node2.get_center(),
                        stroke_width=1,
                        stroke_opacity=0.3,
                        color=GRAY
                    )
                    connections.add(line)
        
        # Animate
        self.play(Create(connections), run_time=1.5)
        self.play(
            LaggedStart(*[FadeIn(layer) for layer in layers], lag_ratio=0.3),
            run_time=2.0
        )
        self.wait(1.0)
'''

# =============================================================================
# MATHEMATICAL EQUATION PATTERNS
# =============================================================================

EQUATION_ANIMATION_EXAMPLE = '''
# Mathematical Equation Animation Pattern
# Shows how to animate equations with transformations

from manim import *

class EquationScene(Scene):
    def construct(self):
        self.camera.background_color = "#171717"
        
        # Create equations
        eq1 = MathTex(r"f(x) = x^2", color=WHITE)
        eq2 = MathTex(r"f'(x) = 2x", color=YELLOW)
        
        eq1.move_to(UP)
        eq2.move_to(DOWN)
        
        # Animate equation appearance
        self.play(Write(eq1), run_time=1.5)
        self.wait(0.5)
        
        # Transform to derivative
        self.play(
            TransformMatchingTex(eq1.copy(), eq2),
            run_time=1.5
        )
        self.wait(1.0)
'''

# =============================================================================
# GRAPH/PLOT PATTERNS
# =============================================================================

GRAPH_PLOT_EXAMPLE = '''
# Graph and Plot Animation Pattern
# Shows how to create axes and animate function plots

from manim import *

class GraphScene(Scene):
    def construct(self):
        self.camera.background_color = "#171717"
        
        # Create axes
        axes = Axes(
            x_range=[-3, 3, 1],
            y_range=[-1, 5, 1],
            x_length=6,
            y_length=4,
            axis_config={"include_tip": True, "color": GRAY}
        )
        axes.move_to(ORIGIN)
        
        # Create function
        graph = axes.plot(lambda x: x**2, color=BLUE)
        graph_label = axes.get_graph_label(graph, label="f(x)=x^2")
        
        # Animate
        self.play(Create(axes), run_time=1.0)
        self.play(Create(graph), run_time=1.5)
        self.play(Write(graph_label), run_time=0.5)
        self.wait(1.0)
        
        # Animate a moving dot along the curve
        dot = Dot(color=RED)
        dot.move_to(axes.c2p(-2, 4))
        
        self.play(FadeIn(dot))
        self.play(
            MoveAlongPath(dot, graph),
            run_time=3.0,
            rate_func=linear
        )
        self.wait(0.5)
'''

# =============================================================================
# TIMING AND SYNCHRONIZATION PATTERNS
# =============================================================================

TIMING_SYNC_EXAMPLE = '''
# Timing Synchronization Pattern
# Shows how to sync animations with narration segments

from manim import *

class TimedScene(Scene):
    def construct(self):
        self.camera.background_color = "#171717"
        
        # Segment 1: 0.0s - 3.0s (show title)
        title = Text("Introduction", font_size=48, color=WHITE)
        self.play(Write(title), run_time=1.5)
        self.wait(1.5)  # Total: 3.0s
        
        # Segment 2: 3.0s - 6.0s (transition to content)
        content = Text("Main Content", font_size=36, color=BLUE)
        content.next_to(title, DOWN, buff=0.5)
        
        self.play(
            title.animate.scale(0.7).to_edge(UP),
            FadeIn(content),
            run_time=2.0
        )
        self.wait(1.0)  # Total: 6.0s
        
        # Segment 3: 6.0s - 10.0s (final animation)
        self.play(
            content.animate.set_color(YELLOW),
            run_time=2.0
        )
        self.wait(2.0)  # Total: 10.0s
'''

# =============================================================================
# VALUE TRACKER PATTERN (Common pitfall fix)
# =============================================================================

VALUE_TRACKER_EXAMPLE = '''
# ValueTracker Pattern
# CORRECT way to use ValueTracker for animated counters

from manim import *

class CounterScene(Scene):
    def construct(self):
        self.camera.background_color = "#171717"
        
        # Create a value tracker
        counter = ValueTracker(0)
        
        # Create a number that updates based on the tracker
        number = always_redraw(
            lambda: DecimalNumber(counter.get_value(), num_decimal_places=0)
            .set_color(WHITE)
            .scale(2)
        )
        
        label = Text("Count: ", font_size=36).next_to(number, LEFT)
        
        self.add(label, number)
        
        # Animate the counter from 0 to 100
        self.play(
            counter.animate.set_value(100),
            run_time=3.0,
            rate_func=linear
        )
        self.wait(1.0)
'''

# =============================================================================
# COMMON MISTAKES TO AVOID
# =============================================================================

COMMON_MISTAKES = '''
## Common Manim Mistakes to Avoid

1. **ValueTracker.number** - WRONG! Use `tracker.get_value()` instead
   - ❌ `tracker.number`
   - ✅ `tracker.get_value()`

2. **ease_in_expo, exponential** - Not standard rate functions
   - ❌ `rate_func=ease_in_expo`
   - ✅ `rate_func=smooth` or `rate_func=linear`

3. **self.wait(0)** - Zero-duration waits cause issues
   - ❌ `self.wait(0)`
   - ✅ Skip the wait entirely

4. **Undefined colors** - Always use Manim color constants
   - ❌ `color="blue"` (may not work)
   - ✅ `color=BLUE`

5. **scale() on groups** - Must use animate syntax for groups
   - ❌ `group.scale(2)` (doesn't animate)
   - ✅ `group.animate.scale(2)`

6. **Missing imports** - Always start with `from manim import *`

7. **Forgetting background** - Always set dark background
   - ✅ `self.camera.background_color = "#171717"`
'''

# =============================================================================
# AVAILABLE RATE FUNCTIONS
# =============================================================================

AVAILABLE_RATE_FUNCS = '''
## Available Manim Rate Functions

Use ONLY these rate functions:
- `linear` - Constant speed
- `smooth` - Smooth ease in/out (default, good for most animations)
- `rush_into` - Fast start, slow end
- `rush_from` - Slow start, fast end
- `there_and_back` - Goes forward then returns
- `double_smooth` - Extra smooth transitions
- `lingering` - Slows down at the end

DO NOT use: ease_in, ease_out, exponential, ease_in_expo (these don't exist)
'''

# =============================================================================
# FULL PATTERNS PROMPT INJECTION
# =============================================================================

def get_patterns_for_prompt() -> str:
    """Returns a curated set of patterns for injection into the generation prompt."""
    return f"""
## Working Manim Code Examples

These are production-tested patterns. Use them as reference:

### Neural Network Visualization
{NEURAL_NETWORK_EXAMPLE}

### Graph and Axes
{GRAPH_PLOT_EXAMPLE}

### ValueTracker (Animated Counters)
{VALUE_TRACKER_EXAMPLE}

{COMMON_MISTAKES}

{AVAILABLE_RATE_FUNCS}
"""


def get_compact_patterns() -> str:
    """Returns a compact version of patterns for token efficiency."""
    return f"""
## Manim Quick Reference

{COMMON_MISTAKES}

{AVAILABLE_RATE_FUNCS}

### Key Patterns
- Background: `self.camera.background_color = "#171717"`
- Counter: Use `ValueTracker` with `always_redraw` and `tracker.get_value()`
- Axes: `Axes(x_range=[...], y_range=[...], axis_config={{"include_tip": True}})`
- Network: Create nodes as `VGroup` of `Circle`, connections as `Line` objects
"""
