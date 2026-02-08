from manim import *

class SceneIntroTheProblem(Scene):
    def construct(self):
        # Initial Setup
        self.camera.background_color = "#171717"

        # --- Segment 0 (0.00s - 6.24s): "Imagine you are training a massive neural network..." ---
        
        # Layer 1: Input Nodes
        input_nodes = VGroup(*[Circle(radius=0.15, color=BLUE_B, fill_opacity=0.8) for _ in range(3)])
        for i, node in enumerate(input_nodes):
            node.move_to([-4.0, (i - 1) * 0.75, 0])
        
        # Layer 2: Hidden 1
        hidden1_nodes = VGroup(*[Circle(radius=0.15, color=BLUE_C, fill_opacity=0.8) for _ in range(4)])
        for i, node in enumerate(hidden1_nodes):
            node.move_to([-1.5, (i - 1.5) * 0.66, 0])
            
        # Layer 3: Hidden 2
        hidden2_nodes = VGroup(*[Circle(radius=0.15, color=BLUE_D, fill_opacity=0.8) for _ in range(4)])
        for i, node in enumerate(hidden2_nodes):
            node.move_to([1.5, (i - 1.5) * 0.66, 0])
            
        # Layer 4: Output Node
        output_node = Circle(radius=0.15, color=GOLD, fill_opacity=0.8).move_to([4.0, 0, 0])
        
        # Connections
        nn_connections = VGroup()
        for i_n in input_nodes:
            for h1_n in hidden1_nodes:
                nn_connections.add(Line(i_n.get_center(), h1_n.get_center(), stroke_width=1, stroke_opacity=0.4))
        for h1_n in hidden1_nodes:
            for h2_n in hidden2_nodes:
                nn_connections.add(Line(h1_n.get_center(), h2_n.get_center(), stroke_width=1, stroke_opacity=0.4))
        for h2_n in hidden2_nodes:
            nn_connections.add(Line(h2_n.get_center(), output_node.get_center(), stroke_width=1, stroke_opacity=0.4))

        # Labels
        input_text = Text("Input", font_size=24).move_to([-4.0, -1.5, 0])
        output_text = Text("Output", font_size=24).move_to([4.0, -1.5, 0])

        # Animation Sequence Segment 0
        self.play(LaggedStart(*[FadeIn(node) for node in input_nodes], lag_ratio=0.1), run_time=0.5)
        self.play(LaggedStart(*[FadeIn(node) for node in hidden1_nodes], lag_ratio=0.1), run_time=0.5)
        self.play(LaggedStart(*[FadeIn(node) for node in hidden2_nodes], lag_ratio=0.1), run_time=0.5)
        self.play(FadeIn(output_node), run_time=0.5)
        self.play(Create(nn_connections), run_time=1.5)
        self.play(FadeIn(input_text), FadeIn(output_text), run_time=0.5)
        
        # Pulse connections
        self.play(nn_connections.animate.set_stroke(opacity=0.8), rate_func=there_and_back, run_time=1.0)
        self.wait(0.74)

        # Create Network Group
        neural_network_group = VGroup(
            input_nodes, hidden1_nodes, hidden2_nodes, output_node, 
            nn_connections, input_text, output_text
        )

        # --- Segment 1 (6.24s - 12.08s): "To improve it, you need the gradient..." ---
        
        self.play(neural_network_group.animate.scale(0.5).move_to([-4.0, 2.0, 0]), run_time=0.7)
        
        # Error Surface (2D Projection of a 3D Concept)
        axes = Axes(x_range=[-2, 2], y_range=[-1, 2], x_length=6, y_length=4, axis_config={"include_tip": False})
        error_surface = axes.plot(lambda x: 0.5 * x**2, color=BLUE_E)
        surface_label = Text("Error Surface", font_size=20).next_to(error_surface, UP)
        
        point_on_surface = Dot(axes.c2p(1.5, 1.125), color=RED)
        gradient_arrow = Arrow(start=axes.c2p(1.5, 1.125), end=axes.c2p(0.5, 0.125), color=YELLOW, buff=0)
        gradient_text = Text("Gradient", font_size=24, color=YELLOW).move_to([3.0, 2.0, 0])

        self.play(Create(axes), Create(error_surface), FadeIn(surface_label), FadeIn(point_on_surface), run_time=1.5)
        self.play(GrowArrow(gradient_arrow), run_time=1.0)
        self.play(FadeIn(gradient_text), run_time=0.5)
        
        # Move point downhill
        self.play(point_on_surface.animate.move_to(axes.c2p(0, 0)), run_time=1.5)
        self.wait(0.08)

        # --- Segment 2 (12.08s - 22.00s): "Finite difference method..." ---
        
        self.play(FadeOut(axes), FadeOut(error_surface), FadeOut(surface_label), 
                  FadeOut(point_on_surface), FadeOut(gradient_arrow), FadeOut(gradient_text), run_time=0.8)
        
        self.play(neural_network_group.animate.move_to([-2.5, 1.0, 0]), run_time=0.5)
        
        slider_rect = Rectangle(width=3.0, height=0.1, fill_color=GRAY).move_to([0.5, -1.8, 0])
        slider_handle = Circle(radius=0.15, color=WHITE, fill_opacity=1).move_to([0.5, -1.8, 0])
        param_value = DecimalNumber(0.500, num_decimal_places=3, font_size=24).move_to([2.5, -1.8, 0])
        param_label = MathTex(r"\theta_1 =", font_size=24).next_to(param_value, LEFT)
        
        model_run_icon = VGroup(
            Triangle(color=GREEN, fill_opacity=1).rotate(-PI/2).scale(0.3),
            Circle(color=WHITE, stroke_width=2).scale(0.5)
        ).move_to([1.5, 0, 0])

        self.play(FadeIn(slider_rect), run_time=0.5)
        self.play(FadeIn(slider_handle), run_time=0.3)
        self.play(FadeIn(param_value), FadeIn(param_label), run_time=0.3)
        self.play(FadeIn(model_run_icon), run_time=0.5)

        # Simulated "Billions of runs"
        for i in range(2):
            self.play(
                nn_connections.animate.set_color(GREEN_B if i==0 else BLUE_B),
                model_run_icon.animate.scale(1.2),
                rate_func=there_and_back, run_time=0.3
            )
            val = 0.501 if i == 0 else 0.499
            self.play(
                slider_handle.animate.shift(RIGHT*0.2 if i==0 else LEFT*0.4),
                param_value.animate.set_value(val),
                run_time=0.2
            )
            
        run_count = Text("Runs: 0", font_size=32).move_to([0, -2.5, 0])
        self.play(FadeIn(run_count))
        
        # Rapid counting
        for c in [100, 10000, 1000000]:
            new_count = Text(f"Runs: {c}", font_size=32).move_to([0, -2.5, 0])
            self.play(Transform(run_count, new_count), run_time=0.4)

        impossible_text = Text("IMPOSSIBLE!", font_size=72, color=RED).move_to(ORIGIN)
        self.play(Write(impossible_text), run_time=1.0)
        self.wait(1.5)

        # --- Segment 3 (22.00s - 38.50s): "The Adjoint Trick" ---
        
        # Cleanup
        self.play(*[FadeOut(m) for m in self.mobjects])
        
        adjoint_title = Text("The Adjoint Trick", font_size=60, color=GOLD).move_to(ORIGIN)
        self.play(Write(adjoint_title), run_time=1.5)
        self.play(adjoint_title.animate.to_edge(UP).scale(0.7), run_time=1.0)
        
        # Icons for ML, Physics, Engineering
        ml_icon = VGroup(Circle(radius=0.4, color=BLUE), Text("ML", font_size=20)).move_to([-2.5, -0.5, 0])
        phys_icon = VGroup(Circle(radius=0.4, color=RED), Text("Phys", font_size=20)).move_to([0, -0.5, 0])
        eng_icon = VGroup(Circle(radius=0.4, color=GREEN), Text("Eng", font_size=20)).move_to([2.5, -0.5, 0])
        
        self.play(FadeIn(ml_icon), run_time=0.5)
        self.wait(0.5)
        self.play(FadeIn(phys_icon), run_time=0.5)
        self.wait(0.5)
        self.play(FadeIn(eng_icon), run_time=0.5)
        self.wait(5.0)

        # --- Segment 4 (38.50s - 56.00s): "Backpropagation / AI" ---
        
        self.play(FadeOut(ml_icon), FadeOut(phys_icon), FadeOut(eng_icon), run_time=1.0)
        
        # Restore NN at small scale
        neural_network_group.scale(1.2).move_to(ORIGIN)
        self.play(FadeIn(neural_network_group), run_time=1.0)
        
        backprop_text = Text("Backpropagation", font_size=28, color=BLUE_B).move_to([-3.0, 2.0, 0])
        reverse_ad_text = Text("Reverse-mode AD", font_size=28, color=GREEN_B).move_to([3.0, 2.0, 0])
        
        self.play(FadeIn(backprop_text), run_time=0.5)
        self.play(FadeIn(reverse_ad_text), run_time=0.5)
        
        # Backward flow arrows
        arrows = VGroup()
        for i in range(5):
            arrow = Arrow(start=[2.0, (i-2)*0.5, 0], end=[-2.0, (i-2)*0.5, 0], color=YELLOW, stroke_width=2)
            arrows.add(arrow)
            
        self.play(LaggedStart(*[GrowArrow(a) for a in arrows], lag_ratio=0.2), run_time=2.0)
        
        self.wait(3.0)
        
        ai_text = Text("Modern AI", font_size=48, color=GOLD).move_to([0, -2.0, 0])
        self.play(FadeOut(backprop_text), FadeOut(reverse_ad_text), FadeOut(arrows), run_time=1.0)
        self.play(Write(ai_text), run_time=1.5)
        
        self.wait(2.14) # Final buffer to reach 56s approximately