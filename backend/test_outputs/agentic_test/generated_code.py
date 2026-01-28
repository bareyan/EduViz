
# Create a Square
square = Square(color=RED)

        # Create a Line
        line = Line(start=square.get_left(), end=square.get_right() + UP, color=GREEN)

        # Create Text and MathTex
        text = Text("Geometry", color=WHITE).next_to(square, UP)
        math_tex = MathTex(r"A = s^2", color=BLUE).next_to(square, DOWN)
        tex_desc = Tex("This is a square", color=WHITE).scale(0.8).to_edge(UP)

        # Animations
        self.play(Create(square))
        self.play(Create(line))
        self.play(Write(text))
        self.play(Write(tex_desc))
        self.play(FadeIn(math_tex))
        self.wait(2)
