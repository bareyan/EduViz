from manim import *

class TestFadeOut(Scene):
    def construct(self):
        txt = Text("Test")
        self.play(Write(txt))
        print(f"After Write: mobjects = {len(self.mobjects)}, txt opacity = {txt.get_fill_opacity()}, stroke = {txt.get_stroke_opacity()}")
        
        self.play(FadeOut(txt))
        print(f"IMMEDIATE after FadeOut: mobjects = {len(self.mobjects)}, txt fill = {txt.get_fill_opacity()}, stroke = {txt.get_stroke_opacity()}")
        print(f"txt in self.mobjects? {txt in self.mobjects}")
        
        self.wait(0.1)
        print(f"After tiny wait: mobjects = {len(self.mobjects)}, txt fill = {txt.get_fill_opacity()}, stroke = {txt.get_stroke_opacity()}")
        
        self.wait(5)
        print(f"After long wait: mobjects = {len(self.mobjects)}, txt fill = {txt.get_fill_opacity()}, stroke = {txt.get_stroke_opacity()}")

if __name__ == "__main__":
    config.quality = "low_quality"
    config.preview = False
    config.write_to_movie = False
    scene = TestFadeOut()
    scene.render()
