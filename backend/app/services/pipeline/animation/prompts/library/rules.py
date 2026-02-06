"""
Critical rules, constraints, and valid API references for Manim.
"""

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

3. **self.wait(0)** - Zero-duration waits cause CRASHES
   - [WRONG] `self.wait(0)` - CRASHES with duration error
   - [WRONG] `self.wait(52.5 - 52.66 if 52.5 > 52.66 else 0)` - CRASHES when condition is False
   - [WRONG] `self.wait(target - current if target > current else 0)` - CRASHES when target <= current
   - [CORRECT] Skip the wait entirely if time has passed
   - [CORRECT] Use `max(0.01, target - current)` if you must have minimum duration
   - **WHY THIS CRASHES**: Manim's wait() validates duration > 0. Any conditional that CAN evaluate to 0 will eventually crash.

4. **Undefined colors** - See "Valid Manim Colors" section above

5. **scale() on groups** - Must use animate syntax for groups
   - [WRONG] `group.scale(2)` (doesn't animate)
   - [CORRECT] `group.animate.scale(2)`

6. **Missing imports** - Always start with `from manim import *`

7. **Forgetting background** - Always set dark background
   - [CORRECT] `self.camera.background_color = "#171717"`

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
    - [WRONG] Text at X=6.5 with width 2.0 → right edge at X=7.5, clipped!
    - [CORRECT] Use `.scale(0.8)` to shrink large groups
    - [CORRECT] Check positions with `.move_to(ORIGIN)` then shift
    - [CORRECT] X range: -6 to 6, Y range: -3.5 to 3.5 (visible area)
    - [CORRECT] Text needs ≥0.5 units margin from screen edges
    - **WHY THIS MATTERS**: Even 0.1 units past the screen edge clips text characters visibly.

16. **Common Undefined Names & Hallucinations (DO NOT USE)**
    - [WRONG] `CYAN` (causes crash). Use `BLUE_C` or `TEAL` instead.
    - [WRONG] `CENTER` (causes crash). Use `ORIGIN` instead.
    - [WRONG] `create_neural_net()`, `NeuralNetwork()`, `Axes2D()` - These are NOT in Manim Community.
    - [FIX] Build complex objects from primitives: Circles for neurons, Lines for synapses, Axes for plots.

17. **ManimGL vs Community Syntax**
    - [WRONG] `self.add(obj.set_color(RED))` (ManimGL style)
    - [CORRECT] `obj.set_color(RED); self.add(obj)` (Community style)
    - [WRONG] `self.play(obj.animate.scale(2))` inside `self.add_foreground_mobject`
    - [CORRECT] Keep animations and additions separate.

18. **Tables and large groups MUST be scaled** (CRITICAL)
    - [WRONG] `table = MobjectTable(...)` then positioning without scaling → TABLE OVERFLOWS SCREEN
    - [WRONG] `table = Table(...)` without `.scale_to_fit_width(11)` → columns push off-screen
    - [CORRECT] `table = MobjectTable(...); table.scale_to_fit_width(11); table.move_to(ORIGIN)`
    - [CORRECT] Any VGroup with 4+ items: `.scale_to_fit_width(11)` after creation
    - **WHY THIS CRASHES**: Tables with 4+ columns are typically 15-20 units wide. Screen is only 14.2 units.

19. **Highlight rectangles MUST be stroke-only** (CRITICAL)
    - [WRONG] `SurroundingRectangle(cell, color=GREEN)` → filled green box COVERS digits!
    - [WRONG] `Rectangle(fill_opacity=0.5).move_to(text)` → text becomes unreadable
    - [CORRECT] `SurroundingRectangle(cell, color=GREEN, fill_opacity=0, stroke_width=2)`
    - [CORRECT] `SurroundingRectangle(cell, color=GREEN, fill_opacity=0.1, stroke_width=3)` (very light fill OK)
    - **WHY THIS MATTERS**: The default SurroundingRectangle has fill_opacity that covers the text.

20. **Row labels MUST be attached to table** (CRITICAL for tables)
    - [WRONG] Creating Text labels and positioning them independently → labels misalign from rows
    - [CORRECT] Use `table.add_highlighted_cell()` or `table.get_rows()` to reference cells
    - [CORRECT] `label.next_to(table.get_rows()[i], LEFT, buff=0.3)` to attach label to row
    - **WHY THIS MATTERS**: Independently positioned labels won't track if table is scaled/moved.

21. **Do NOT fake tables with MathTex array + manual shifts** (CRITICAL)
    - [WRONG] `table = MathTex(r"\\begin{{array}}...")` with highlights positioned by
      `.stretch_to_fit_width(table.width/8)` and `.shift(RIGHT * 3.3)` → unstable/misaligned pivots
    - [CORRECT] `table = MathTable(...)` or `MobjectTable(...)`, then use
      `table.get_rows()`, `table.get_columns()`, `table.get_cell()` for highlights
    - **WHY THIS MATTERS**: hardcoded shifts break when text metrics change and cause repeated visual defects.
'''

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

DIRECTION_CONSTANTS = '''
## Direction Constants (USE ONLY THESE)

- `UP`, `DOWN`, `LEFT`, `RIGHT`
- `UL`, `UR`, `DL`, `DR`
- `IN`, `OUT`, `ORIGIN`

DO NOT use: `TOP`, `BOTTOM`, `UPPER`, `LOWER`
'''
