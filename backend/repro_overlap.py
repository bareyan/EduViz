
from app.services.pipeline.animation.generation.validation import CodeValidator
import json

code = r"""
from manim import *
import numpy as np

class SceneIntroTheProblem(Scene):
    def construct(self):
        self.camera.background_color = "#171717"  # Slate dark

        # Initial setup
        self.camera.background_color = "#171717"
        
        # --- SEGMENT 0: NN Graph (0.0s - 6.24s) ---
        # Create NN Graph structure
        layers = [3, 5, 5, 3]
        nodes = VGroup()
        edges = VGroup()
        
        for i, num_nodes in enumerate(layers):
            layer = VGroup(*[Circle(radius=0.12, color=BLUE_A, fill_opacity=1) for _ in range(num_nodes)])
            layer.arrange(DOWN, buff=0.3)
            layer.move_to(RIGHT * (i - 1.5) * 1.4)
            nodes.add(layer)
            
        for i in range(len(layers) - 1):
            for node_a in nodes[i]:
                for node_b in nodes[i+1]:
                    edge = Line(node_a.get_center(), node_b.get_center(), stroke_width=1, color=GRAY, stroke_opacity=0.3)
                    edges.add(edge)
        
        nn_graph = VGroup(edges, nodes).scale(0.8)
        
        self.wait(0.5)
        self.play(Create(nn_graph), run_time=2.0, rate_func=smooth)
        
        # Scale/Zoom effect
        self.play(nn_graph.animate.scale(2.5).move_to(LEFT*2), run_time=2.5, rate_func=smooth)
        
        # Golden Pulse
        highlight_edges = VGroup(*[edges[i] for i in range(0, len(edges), 10)])
        self.play(
            highlight_edges.animate.set_color(GOLD).set_stroke(width=3, opacity=1),
            run_time=0.6, rate_func=smooth
        )
        self.play(
            highlight_edges.animate.set_color(GRAY).set_stroke(width=1, opacity=0.3),
            run_time=0.64, rate_func=smooth
        )

        # --- SEGMENT 1: Loss Surface (6.24s - 12.08s) ---
        # 2D representation of a loss surface (concentric ellipses)
        surface = VGroup(*[
            Ellipse(width=i*1.2, height=i*0.6, color=BLUE_E, stroke_width=2) 
            for i in range(1, 8)
        ]).rotate(15 * DEGREES).move_to(ORIGIN)
        
        self.play(
            ReplacementTransform(nn_graph, surface),
            run_time=1.5, rate_func=smooth
        )
        
        self.wait(0.26)
        
        # Gradient Arrow
        grad_arrow = Arrow(start=UP*2 + RIGHT*2, end=ORIGIN, color=GREEN, buff=0)
        grad_arrow.move_to(surface.get_center() + UP*1.2 + RIGHT*0.8)
        
        self.play(GrowArrow(grad_arrow), run_time=1.0)
        self.wait(0.5)
        
        # Descent animation
        self.play(
            grad_arrow.animate.move_to(surface.get_center() + UP*0.3 + RIGHT*0.2).scale(0.7),
            run_time=2.0, rate_func=smooth
        )
        self.wait(0.58)

        # --- SEGMENT 2: Finite Difference (12.08s - 22.00s) ---
        self.play(surface.animate.move_to(LEFT * 3.5).scale(0.7), run_time=0.42)
        
        formula = MathTex(r"\frac{f(x+h) - f(x)}{h}", color=WHITE).scale(1.2).move_to(RIGHT * 3.5 + UP * 1)
        self.play(Write(formula), run_time=1.5)
        
        self.wait(1.0)
        
        counter_label = Text("Run:", font_size=32).move_to(RIGHT * 2.8 + DOWN * 0.5)
        tracker = ValueTracker(1)
        counter_num = always_redraw(lambda: 
            DecimalNumber(tracker.get_value(), num_decimal_places=0, group_with_commas=True)
            .next_to(counter_label, RIGHT)
        )
        counter_group = VGroup(counter_label, counter_num)
        
        self.play(FadeIn(counter_group), run_time=1.0)
        
        # Rapid spin
        self.play(tracker.animate.set_value(1000000), run_time=5.0, rate_func=rush_into)
        
        # Red Shake
        counter_group.add(formula)
        self.play(
            counter_group.animate.set_color(RED),
            Flash(counter_group, color=RED),
            run_time=0.5
        )
        self.play(Indicate(counter_group, color=RED, scale_factor=1.1), run_time=1.5)

        # --- SEGMENT 3: Adjoint Trick (22.00s - 27.84s) ---
        self.play(
            FadeOut(surface), FadeOut(grad_arrow), FadeOut(counter_group),
            run_time=0.5, rate_func=linear
        )
        self.wait(1.0)
        
        title = Text("The Adjoint Trick", gradient=(YELLOW, GOLD), font_size=64).set_glow_factor(0.2)
        self.play(Write(title), run_time=1.5)
        
        # Pulse effect
        pulse_ring = Circle(radius=0.1, color=GOLD, stroke_width=2).move_to(title)
        self.play(
            pulse_ring.animate.scale(60).set_stroke(opacity=0),
            run_time=2.84, rate_func=smooth
        )
        self.remove(pulse_ring)

        # --- SEGMENT 4: Efficiency (27.84s - 38.48s) ---
        self.play(title.animate.scale(0.6).to_edge(UP), run_time=2.16)
        
        # Field Icons
        ml_icon = VGroup(Circle(radius=0.3), Line(LEFT*0.3, RIGHT*0.3), Line(UP*0.3, DOWN*0.3)).scale(0.8)
        physics_icon = VGroup(*[Ellipse(width=0.8, height=0.2).rotate(a) for a in [0, 60*DEGREES, 120*DEGREES]], Dot())
        eng_icon = Star(n=8, inner_radius=0.4, outer_radius=0.6).set_fill(GRAY, 1)
        
        icons = VGroup(ml_icon, physics_icon, eng_icon).arrange(RIGHT, buff=2).move_to(DOWN * 1.5)
        ml_label = Text("ML", font_size=24).next_to(ml_icon, DOWN)
        phys_label = Text("Physics", font_size=24).next_to(physics_icon, DOWN)
        eng_label = Text("Engineering", font_size=24).next_to(eng_icon, DOWN)
        
        self.play(FadeIn(ml_icon), FadeIn(ml_label), run_time=1.0)
        self.play(FadeIn(physics_icon), FadeIn(phys_label), run_time=1.0)
        self.play(FadeIn(eng_icon), FadeIn(eng_label), run_time=1.0)
        
        self.wait(1.0)
        
        # Connecting lines
        lines = VGroup(*[Line(title.get_bottom(), icon.get_top(), stroke_opacity=0.5) for icon in icons])
        self.play(Create(lines), run_time=2.0)
        
        self.wait(0.5)
        
        efficiency_text = Text("EFFICIENCY", font_size=72, color=GOLD, weight=BOLD)
        self.play(
            ReplacementTransform(VGroup(icons, ml_label, phys_label, eng_label, lines), efficiency_text),
            run_time=1.98
        )

        # --- SEGMENT 5: Reverse Flow (38.48s - 52.16s) ---
        self.play(FadeOut(efficiency_text), FadeOut(title), run_time=0.52)
        
        # Simplified Chain
        chain_nodes = VGroup(*[Circle(radius=0.3, color=WHITE) for _ in range(4)]).arrange(RIGHT, buff=1.5)
        chain_labels = VGroup(
            MathTex("x"), MathTex("a"), MathTex("b"), MathTex("y")
        )
        for i in range(4):
            chain_labels[i].move_to(chain_nodes[i].get_center())
        
        chain_edges = VGroup(*[
            Arrow(chain_nodes[i].get_right(), chain_nodes[i+1].get_left(), buff=0.1) 
            for i in range(3)
        ])
        
        full_chain = VGroup(chain_nodes, chain_labels, chain_edges).move_to(ORIGIN)
        self.play(Create(full_chain), run_time=2.0)
        
        # Reverse Pulse
        pulse = Dot(color=YELLOW).move_to(chain_nodes[3].get_center())
        self.wait(2.0)
        
        self.play(
            pulse.animate.move_to(chain_nodes[0].get_center()),
            run_time=3.0, rate_func=smooth
        )
        self.remove(pulse)
        
        self.wait(1.0)
        
        out_label = Text("Output", color=BLUE).next_to(chain_nodes[3], UP)
        in_label = Text("Inputs", color=GREEN).next_to(chain_nodes[0], UP)
        self.play(Write(out_label), Write(in_label), run_time=3.0)
        
        # Highlight all
        self.play(full_chain.animate.set_color(GOLD), run_time=4.16)

        # --- SEGMENT 6: Final (52.16s - 56.0s) ---
        # Brain icon representation
        brain_l = Arc(radius=1, start_angle=90*DEGREES, angle=180*DEGREES)
        brain_r = Arc(radius=1, start_angle=-90*DEGREES, angle=180*DEGREES)
        brain_center = VGroup(Line(UP, DOWN), Line(LEFT*0.5, RIGHT*0.5))
        brain = VGroup(brain_l, brain_r, brain_center).scale(0.8).move_to(UP*0.5)
        
        self.play(ReplacementTransform(full_chain, brain), run_time=1.5)
        self.wait(0.10)
        
        final_text = Text("The Adjoint Trick", font_size=36, color=GOLD).next_to(brain, DOWN)
        self.play(FadeIn(final_text), run_time=1.68)
        
        self.play(FadeOut(Group(*self.mobjects)), run_time=0.32)

        # Final padding to ensure video >= audio duration
        self.wait(14.0)
"""

validator = CodeValidator()
result = validator.validate_code(code)
print(json.dumps(result, indent=2))
