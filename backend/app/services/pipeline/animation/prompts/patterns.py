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
## CRITICAL RULES & COMMON PITFALLS (STRICT ADHERENCE REQUIRED)

[CRITICAL_WARNING] MOST FREQUENT ERROR: FORGETTING TO CLEAN UP OLD OBJECTS
   - You often forget to remove objects before adding new ones at the same position.
   - **Visual Result**: Unreadable text overlaps and cluttered scenes.
   - **Fix**: ALWAYS use `FadeOut()`, `ReplacementTransform()`, or `self.remove()` before placing new content.

1. **ValueTracker.number** - WRONG! Use `tracker.get_value()` instead
   - [WRONG] `tracker.number`
   - [CORRECT] `tracker.get_value()`

2. **ease_in_expo, exponential** - Not standard rate functions
   - [WRONG] `rate_func=ease_in_expo`
   - [CORRECT] `rate_func=smooth` or `rate_func=linear`

3. **self.wait(0)** - Zero-duration waits cause issues
   - [WRONG] `self.wait(0)`
   - [CORRECT] Skip the wait entirely

4. **Undefined colors** - See "Valid Manim Colors" section above

5. **scale() on groups** - Must use animate syntax for groups
   - [WRONG] `group.scale(2)` (doesn't animate)
   - [CORRECT] `group.animate.scale(2)`

6. **Missing imports** - Always start with `from manim import *`

7. **Overriding theme background** - Do not set background manually
   - [CORRECT] Leave background to theme enforcement

8. **Animating lists** - `Animation` only works on Mobjects, not lists
   - [WRONG] `self.play(FadeOut(self.mobjects))` (Crash! list not Mobject)
   - [CORRECT] `self.play(*[FadeOut(m) for m in self.mobjects])` (animate each)
   
9. **VGroup vs Group** - VGroup only accepts VMobjects, Group accepts any Mobject
   - [WRONG] `VGroup(Group(...))` (Crash! Group inside VGroup)
   - [CORRECT] `Group(*self.mobjects)` for mixed mobjects
   - [CORRECT] `VGroup(*[m for m in self.mobjects if isinstance(m, VMobject)])` for VMobjects only

10. **CENTER doesn't exist** - Use ORIGIN for center position
    - [WRONG] `obj.move_to(CENTER)` (Crash!)
    - [CORRECT] `obj.move_to(ORIGIN)`

11. **Camera.frame doesn't exist on regular Camera** - MovingCameraScene uses self.camera differently
    - [WRONG] `self.camera.frame.scale(2)` (Crash on regular Scene!)
    - [CORRECT] For MovingCameraScene: `self.camera.frame.animate.scale(2)` 
    - [CORRECT] For regular Scene: Use `self.play(self.camera.frame.animate.scale(2))` ONLY if using MovingCameraScene

12. **Mobject init kwargs** - Don't pass unexpected keyword arguments
    - [WRONG] `Circle(size=2)` (Crash! no 'size' param)
    - [CORRECT] `Circle(radius=2)`
    - [WRONG] `Text("hi", size=24)` (Crash! no 'size' param)
    - [CORRECT] `Text("hi", font_size=24)`

13. **Forgetting to remove old objects** - Clean up before placing new items
    - [WRONG] Creating new text without removing old → Text overlaps!
    - [CORRECT] `self.play(FadeOut(old_text)); self.play(FadeIn(new_text))`
    - [CORRECT] `self.play(ReplacementTransform(old_obj, new_obj))`
    - [CORRECT] `self.remove(old_obj)` before adding new at same position

14. **Text/label overlapping** - Always position labels to avoid overlaps
    - [WRONG] Multiple labels at same position → Unreadable!
    - [CORRECT] Use `.next_to(obj, direction, buff=0.3)` to position labels
    - [CORRECT] Use `.shift(UP * 0.5)` to offset overlapping items
    - [CORRECT] For axis labels, use `.to_edge(DOWN)` or `.to_corner()`

15. **Objects going out of frame** - Keep everything visible
    - [WRONG] Objects positioned at edges get cut off
    - [CORRECT] Use `.scale(0.8)` to shrink large groups
    - [CORRECT] Check positions with `.move_to(ORIGIN)` then shift
    - [CORRECT] X range: -6 to 6, Y range: -3.5 to 3.5 (visible area)
'''

# =============================================================================
# VALID MANIM COLORS
# =============================================================================

VALID_COLORS = '''
## Valid Manim Colors (USE ONLY THESE)

### Primary Colors
WHITE, BLACK, RED, GREEN, BLUE, YELLOW, ORANGE, PINK, PURPLE, TEAL, GOLD, GRAY, GREY

### Color Variants (lighter to darker with _A through _E)
- RED_A, RED_B, RED_C, RED_D, RED_E
- BLUE_A, BLUE_B, BLUE_C, BLUE_D, BLUE_E  
- GREEN_A, GREEN_B, GREEN_C, GREEN_D, GREEN_E
- YELLOW_A, YELLOW_B, YELLOW_C, YELLOW_D, YELLOW_E
- GRAY_A, GRAY_B, GRAY_C, GRAY_D, GRAY_E (also GREY_*)

### Special Colors
MAROON, LIGHT_GRAY, DARK_GRAY, DARK_BLUE, LIGHT_PINK, DARK_BROWN

### COLORS THAT DO NOT EXIST (will crash!)
[WRONG] CYAN - Use TEAL instead
[WRONG] MAGENTA - Use PINK or PURPLE instead  
[WRONG] LIGHT_BLUE - Use BLUE_A or BLUE_B instead
[WRONG] DARK_RED - Use RED_E or MAROON instead
[WRONG] AQUA - Use TEAL instead
'''

# =============================================================================
# VALID MANIM ANIMATIONS
# =============================================================================

VALID_ANIMATIONS = '''
## Valid Manim Animations (USE ONLY THESE)

### Creation Animations
- `Create(mobject)` - Draw lines/shapes progressively
- `Write(text)` - Write text character by character
- `FadeIn(mobject)` - Fade in from transparent
- `FadeOut(mobject)` - Fade out to transparent
- `GrowFromCenter(mobject)` - Grow from center point
- `GrowFromPoint(mobject, point)` - Grow from a specific point
- `DrawBorderThenFill(mobject)` - Draw outline then fill

### Transform Animations  
- `Transform(source, target)` - Morph one mobject into another
- `ReplacementTransform(source, target)` - Transform and replace
- `TransformMatchingTex(source, target)` - Transform matching LaTeX parts
- `TransformMatchingShapes(source, target)` - Transform matching shapes
- `MoveToTarget(mobject)` - Move to mobject.target (set with .generate_target())

### Movement Animations
- `Rotate(mobject, angle)` - Rotate by angle in radians
- `Circumscribe(mobject)` - Circle around a mobject
- `Indicate(mobject)` - Briefly highlight
- `Flash(point)` - Flash at a point
- `Wiggle(mobject)` - Wiggle in place
- `ApplyWave(mobject)` - Wave effect

### Group Animations
- `LaggedStart(*animations, lag_ratio=0.1)` - Stagger animations
- `AnimationGroup(*animations)` - Play animations together
- `Succession(*animations)` - Play animations in sequence

### ANIMATIONS THAT DO NOT EXIST (will crash!)
[WRONG] Shake - Use Wiggle instead
[WRONG] Pulse - Use Indicate instead
[WRONG] Blink - Use Flash instead
[WRONG] Appear - Use FadeIn instead
[WRONG] Disappear - Use FadeOut instead
[WRONG] Morph - Use Transform instead
[WRONG] Slide - Use mobject.animate.shift() instead

### API Gotchas
- `Create(mobject)` - Takes ONLY the mobject, no other positional args
- `Write(text)` - Takes ONLY the text object
- Use `run_time=X` as keyword arg: `self.play(Create(obj), run_time=2)`
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
# DIRECTION CONSTANTS
# =============================================================================

DIRECTION_CONSTANTS = '''
## Direction Constants (USE ONLY THESE)

- `UP`, `DOWN`, `LEFT`, `RIGHT`
- `UL`, `UR`, `DL`, `DR`
- `IN`, `OUT`, `ORIGIN`

DO NOT use: `TOP`, `BOTTOM`, `UPPER`, `LOWER`
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

{DIRECTION_CONSTANTS}
"""


def get_compact_patterns() -> str:
    """Returns a compact version of patterns for token efficiency."""
    return f"""
## Manim Quick Reference

{VALID_COLORS}

{VALID_ANIMATIONS}

{COMMON_MISTAKES}

{AVAILABLE_RATE_FUNCS}

{DIRECTION_CONSTANTS}

### Key Patterns
- Background: set by theme (do not override)
- Counter: Use `ValueTracker` with `always_redraw` and `tracker.get_value()`
- Axes: `Axes(x_range=[...], y_range=[...], axis_config={{"include_tip": True}})`
- Network: Create nodes as `VGroup` of `Circle`, connections as `Line` objects
"""
