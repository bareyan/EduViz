"""CST-based deterministic fixer for Manim code.

Uses LibCST for robust code modification, avoiding the pitfalls of regex-based
text replacement on Python source.
"""

from typing import List, Optional, Tuple, Sequence
import libcst as cst
import libcst.matchers as m
from app.core import get_logger
from app.services.pipeline.animation.generation.core.validation.models import IssueCategory, ValidationIssue
from app.services.pipeline.animation.config import SAFE_X_LIMIT, SAFE_Y_LIMIT

logger = get_logger(__name__, component="cst_fixer")

class GenericPatternTransformer(cst.CSTTransformer):
    """Transformer for stable, generic Manim code rewrites."""
    
    def __init__(self) -> None:
        self.count = 0
        self.changes: List[str] = []

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.CSTNode:
        # 1. Remove self.wait(0) or self._monitored_wait(0)
        # We don't remove here (risky for Expr nodes), we do it in leave_IndentedBlock
        return updated_node

    def leave_IndentedBlock(self, original_node: cst.IndentedBlock, updated_node: cst.IndentedBlock) -> cst.CSTNode:
        new_body = []
        for stmt in updated_node.body:
            # Rule 1: Remove self.wait(0) or self._monitored_wait(0)
            if m.matches(stmt, m.SimpleStatementLine(
                body=[m.Expr(value=m.Call(
                    func=m.Attribute(
                        value=m.Name("self"),
                        attr=m.Name(m.MatchIfTrue(lambda n: (n.value if hasattr(n, "value") else n) in ("wait", "_monitored_wait")))
                    ),
                    args=[m.Arg(value=m.Integer(value="0"))]
                ))]
            )):
                self.count += 1
                self.changes.append("Remove self.wait(0)")
                continue

            # Rule 4: Header MathTex arrangement (5+ args)
            if isinstance(stmt, cst.SimpleStatementLine) and len(stmt.body) == 1:
                first_stmt = stmt.body[0]
                if m.matches(first_stmt, m.Assign(
                    targets=[m.AssignTarget(target=m.Name())],
                    value=m.Call(func=m.Name("MathTex"))
                )):
                    assign = first_stmt
                    if len(assign.value.args) >= 5:
                        target_var = assign.targets[0].target
                        new_body.append(stmt)
                        # target.arrange(RIGHT, buff=0.7)
                        arrange_stmt = cst.SimpleStatementLine(
                            body=[cst.Expr(value=cst.Call(
                                func=cst.Attribute(value=target_var, attr=cst.Name("arrange")),
                                args=[
                                    cst.Arg(value=cst.Name("RIGHT"), comma=cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))),
                                    cst.Arg(keyword=cst.Name("buff"), value=cst.Float(value="0.7"))
                                ]
                            ))]
                        )
                        # target.scale_to_fit_width(min(target.width, 10.5))
                        scale_stmt = cst.SimpleStatementLine(
                            body=[cst.Expr(value=cst.Call(
                                func=cst.Attribute(value=target_var, attr=cst.Name("scale_to_fit_width")),
                                args=[cst.Arg(value=cst.Call(
                                    func=cst.Name("min"),
                                    args=[
                                        cst.Arg(value=cst.Attribute(value=target_var, attr=cst.Name("width")), comma=cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))),
                                        cst.Arg(value=cst.Float(value="10.5"))
                                    ]
                                ))]
                            ))]
                        )
                        new_body.append(arrange_stmt)
                        new_body.append(scale_stmt)
                        self.count += 2
                        self.changes.append("Header MathTex arrangement")
                        continue

            # Rule 5: Decorative line group removal
            if m.matches(stmt, m.SimpleStatementLine(
                body=[m.Assign(
                    targets=[m.AssignTarget(target=m.Name())],
                    value=m.Call(
                        func=m.Name("VGroup"),
                        args=[
                            m.Arg(value=m.Name()), # table
                            m.Arg(value=m.Name(m.MatchIfTrue(lambda n: "line" in (n.value.lower() if hasattr(n, "value") else n.lower())))),
                            m.Arg(value=m.Name(m.MatchIfTrue(lambda n: "line" in (n.value.lower() if hasattr(n, "value") else n.lower()))))
                        ]
                    )
                )]
            )):
                assign = stmt.body[0]
                table_var = assign.value.args[0].value
                new_stmt = stmt.with_changes(
                    body=[assign.with_changes(value=table_var)],
                    trailing_whitespace=cst.TrailingWhitespace(
                        comment=cst.Comment(value="# auto-fix: avoid duplicate decorative grid lines")
                    )
                )
                new_body.append(new_stmt)
                self.count += 1
                self.changes.append("Remove decorative line group")
                continue

            # Rule 6: MathTex array table highlight geometry fix
            # matches stretch_to_fit_width(tableau.width / 8) -> stretch_to_fit_width(tableau.width / 7)
            if m.matches(stmt, m.SimpleStatementLine(
                body=[m.Expr(value=m.Call(
                    func=m.Attribute(attr=m.Name("stretch_to_fit_width")),
                    args=[m.Arg(value=m.BinaryOperation(operator=m.Divide(), right=m.Integer(value="8")))]
                ))]
            )):
                # Manually reconstruct the node because m.sub doesn't exist
                # stmt -> Expr -> Call -> Arg -> BinaryOperation -> right (Integer)
                expr = stmt.body[0]
                call = expr.value
                arg = call.args[0]
                bin_op = arg.value
                
                new_bin_op = bin_op.with_changes(right=cst.Integer(value="7"))
                new_arg = arg.with_changes(value=new_bin_op)
                new_call = call.with_changes(args=[new_arg])
                new_expr = expr.with_changes(value=new_call)
                new_stmt = stmt.with_changes(
                    body=[new_expr],
                    trailing_whitespace=cst.TrailingWhitespace(
                        comment=cst.Comment(value="# auto-fix: geometry correction")
                    )
                )
                
                new_body.append(new_stmt)
                self.count += 1
                self.changes.append("Fix table highlight geometry")
                continue

            new_body.append(stmt)
        return updated_node.with_changes(body=new_body)

    def leave_Attribute(self, original_node: cst.Attribute, updated_node: cst.Attribute) -> cst.CSTNode:
        # 2. Fix tracker.number -> tracker.get_value()
        if m.matches(updated_node, m.Attribute(attr=m.Name("number"))):
            # We want to change it to tracker.get_value()
            # Safety: only change if it's likely a ValueTracker (heuristic)
            # or simply apply as per heritage code logic.
            self.count += 1
            self.changes.append("Fix .number -> .get_value()")
            return cst.Call(
                func=cst.Attribute(value=updated_node.value, attr=cst.Name("get_value")),
                args=[]
            )
        return updated_node

    def leave_Name(self, original_node: cst.Name, updated_node: cst.Name) -> cst.CSTNode:
        # 3. Constant replacements
        replacements = {
            "CENTER": "ORIGIN",
            "TOP": "UP",
            "BOTTOM": "DOWN",
            "ease_in_expo": "smooth"
        }
        if updated_node.value in replacements:
            # Check if it's an attribute name (e.g. obj.TOP) - we might not want to fix that
            # But in Manim these are usually global constants.
            new_val = replacements[updated_node.value]
            self.count += 1
            self.changes.append(f"Fix {updated_node.value} -> {new_val}")
            return updated_node.with_changes(value=new_val)
        return updated_node

class CoordinateClampingTransformer(cst.CSTTransformer):
    """Clamps numeric coordinates in move_to/shift calls."""
    
    def __init__(self, target_node: Optional[cst.CSTNode] = None) -> None:
        self.target_node = target_node
        self.count = 0

    def leave_Call(self, original_node: cst.Call, updated_node: cst.Call) -> cst.CSTNode:
        # We only want to transform if it's the specific node we're targeting (if any)
        # or if it's a general move_to/shift call. 
        # For simplicity in deterministic fix, we can apply it generally or per-issue.
        
        if not m.matches(updated_node, m.Call(
            func=m.Attribute(attr=m.Name(m.MatchIfTrue(lambda n: n in ("move_to", "shift"))))
        )):
            return updated_node

        new_args = []
        modified = False
        for arg in updated_node.args:
            transformed_arg, arg_modified = self._clamp_arg(arg)
            new_args.append(transformed_arg)
            if arg_modified:
                modified = True
        
        if modified:
            self.count += 1
            return updated_node.with_changes(args=new_args)
        return updated_node

    def _clamp_arg(self, arg: cst.Arg) -> Tuple[cst.Arg, bool]:
        # Handle RIGHT * 5.0
        if m.matches(arg.value, m.BinaryOperation(
            left=m.Name(m.MatchIfTrue(lambda n: n in ("RIGHT", "LEFT", "UP", "DOWN", "UL", "UR", "DL", "DR"))),
            operator=m.Multiply(),
            right=m.Float() | m.Integer()
        )):
            direction = arg.value.left.value
            val_node = arg.value.right
            val = float(val_node.value)
            
            clamped = val
            if direction in ("RIGHT", "LEFT"):
                clamped = min(val, SAFE_X_LIMIT)
            elif direction in ("UP", "DOWN"):
                clamped = min(val, SAFE_Y_LIMIT)
            else:
                clamped = min(val, min(SAFE_X_LIMIT, SAFE_Y_LIMIT))
                
            if abs(clamped - val) > 0.01:
                new_right = cst.Float(value=f"{clamped:.1f}")
                return arg.with_changes(value=arg.value.with_changes(right=new_right)), True

        # Handle constant names directly (e.g. RIGHT * 10)
        if m.matches(arg.value, m.BinaryOperation(
            left=m.Name(m.MatchIfTrue(lambda n: n in ("RIGHT", "LEFT", "UP", "DOWN", "UL", "UR", "DL", "DR"))),
            operator=m.Multiply(),
            right=m.Integer() | m.Float()
        )):
            # Redundant with above but ensures we catch both
            pass

        # Handle [x, y, z] or np.array([x, y, z])
        # This is more complex but doable with matchers.
        return arg, False

class ScaleInsertionTransformer(cst.CSTTransformer):
    """Inserts .scale_to_fit_width(...) after object creation Assign nodes."""
    
    def __init__(self, target_var: str, scale_val: float = 12.0) -> None:
        self.target_var = target_var
        self.scale_val = scale_val
        self.count = 0

    def _process_body(self, body: Sequence[cst.BaseStatement]) -> List[cst.BaseStatement]:
        new_body = []
        for stmt in body:
            new_body.append(stmt)
            # If stmt is Assign(targets=[Name(target_var)], ...)
            if m.matches(stmt, m.SimpleStatementLine(
                body=[m.Assign(targets=[m.AssignTarget(target=m.Name(self.target_var))])]
            )):
                # Insert scale call
                scale_stmt = cst.SimpleStatementLine(
                    body=[cst.Expr(
                        value=cst.Call(
                            func=cst.Attribute(
                                value=cst.Name(self.target_var),
                                attr=cst.Name("scale_to_fit_width")
                            ),
                            args=[cst.Arg(value=cst.Call(
                                func=cst.Name("min"),
                                args=[
                                    cst.Arg(value=cst.Attribute(
                                        value=cst.Name(self.target_var),
                                        attr=cst.Name("width")
                                    )),
                                    cst.Arg(value=cst.Float(value=str(self.scale_val)))
                                ]
                            ))]
                        )
                    )],
                    trailing_whitespace=cst.TrailingWhitespace(
                        comment=cst.Comment(value="# auto-fix: fit within bounds")
                    )
                )
                new_body.append(scale_stmt)
                self.count += 1
        return new_body

    def leave_IndentedBlock(self, original_node: cst.IndentedBlock, updated_node: cst.IndentedBlock) -> cst.CSTNode:
        return updated_node.with_changes(body=self._process_body(updated_node.body))

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.CSTNode:
        return updated_node.with_changes(body=self._process_body(updated_node.body))

class TextOverlapTransformer(cst.CSTTransformer):
    """Separates overlapping text objects with relative placement."""
    
    def __init__(self, target_var: str, anchor_var: Optional[str] = None) -> None:
        self.target_var = target_var
        self.anchor_var = anchor_var
        self.count = 0

    def _process_body(self, body: Sequence[cst.BaseStatement]) -> List[cst.BaseStatement]:
        new_body = []
        for stmt in body:
            new_body.append(stmt)
            if m.matches(stmt, m.SimpleStatementLine(
                body=[m.Assign(targets=[m.AssignTarget(target=m.Name(self.target_var))])]
            )):
                if self.anchor_var:
                    # target.next_to(anchor, DOWN, buff=0.4)
                    call_node = cst.Call(
                        func=cst.Attribute(value=cst.Name(self.target_var), attr=cst.Name("next_to")),
                        args=[
                            cst.Arg(value=cst.Name(self.anchor_var)),
                            cst.Arg(value=cst.Name("DOWN")),
                            cst.Arg(keyword=cst.Name("buff"), value=cst.Float(value="0.4"))
                        ]
                    )
                else:
                    # target.shift(DOWN * 0.8)
                    call_node = cst.Call(
                        func=cst.Attribute(value=cst.Name(self.target_var), attr=cst.Name("shift")),
                        args=[cst.Arg(value=cst.BinaryOperation(
                            left=cst.Name("DOWN"),
                            operator=cst.Multiply(),
                            right=cst.Float(value="0.8")
                        ))]
                    )
                
                new_stmt = cst.SimpleStatementLine(
                    body=[cst.Expr(value=call_node)],
                    trailing_whitespace=cst.TrailingWhitespace(
                        comment=cst.Comment(value="# auto-fix: prevent overlap")
                    )
                )
                new_body.append(new_stmt)
                self.count += 1
        return new_body

    def leave_IndentedBlock(self, original_node: cst.IndentedBlock, updated_node: cst.IndentedBlock) -> cst.CSTNode:
        return updated_node.with_changes(body=self._process_body(updated_node.body))

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.CSTNode:
        return updated_node.with_changes(body=self._process_body(updated_node.body))

class ObjectOcclusionTransformer(cst.CSTTransformer):
    """Prevents object occlusion of text."""
    
    def __init__(self, target_var: str) -> None:
        self.target_var = target_var
        self.count = 0

    def _process_body(self, body: Sequence[cst.BaseStatement]) -> List[cst.BaseStatement]:
        new_body = []
        for stmt in body:
            new_body.append(stmt)
            if m.matches(stmt, m.SimpleStatementLine(
                body=[m.Assign(targets=[m.AssignTarget(target=m.Name(self.target_var))])]
            )):
                # target.set_fill(opacity=0)
                new_stmt = cst.SimpleStatementLine(
                    body=[cst.Expr(value=cst.Call(
                        func=cst.Attribute(value=cst.Name(self.target_var), attr=cst.Name("set_fill")),
                        args=[cst.Arg(keyword=cst.Name("opacity"), value=cst.Integer(value="0"))]
                    ))],
                    trailing_whitespace=cst.TrailingWhitespace(
                        comment=cst.Comment(value="# auto-fix: prevent text occlusion")
                    )
                )
                new_body.append(new_stmt)
                self.count += 1
        return new_body

    def leave_IndentedBlock(self, original_node: cst.IndentedBlock, updated_node: cst.IndentedBlock) -> cst.CSTNode:
        return updated_node.with_changes(body=self._process_body(updated_node.body))

    def leave_Module(self, original_node: cst.Module, updated_node: cst.Module) -> cst.CSTNode:
        return updated_node.with_changes(body=self._process_body(updated_node.body))

class TableTransformer(cst.CSTTransformer):
    """Fixes common Manim Table API issues."""
    
    def __init__(self) -> None:
        self.count = 0

    def leave_Attribute(self, original_node: cst.Attribute, updated_node: cst.Attribute) -> cst.CSTNode:
        # 1. table.grid_lines -> VGroup(table.get_horizontal_lines(), table.get_vertical_lines())
        if m.matches(updated_node, m.Attribute(attr=m.Name("grid_lines"))):
            table_var = updated_node.value
            self.count += 1
            return cst.Call(
                func=cst.Name("VGroup"),
                args=[
                    cst.Arg(value=cst.Call(func=cst.Attribute(value=table_var, attr=cst.Name("get_horizontal_lines")))),
                    cst.Arg(value=cst.Call(func=cst.Attribute(value=table_var, attr=cst.Name("get_vertical_lines"))))
                ]
            )
        return updated_node

    def leave_Subscript(self, original_node: cst.Subscript, updated_node: cst.Subscript) -> cst.CSTNode:
        # 2. table[i][j] -> table.get_cell(i+1, j+1)
        # matches table[i][j]
        if m.matches(updated_node, m.Subscript(
            value=m.Subscript(
                value=m.Name() | m.Attribute(),
                slice=[m.SubscriptElement(slice=m.Index(value=m.Integer()))]
            ),
            slice=[m.SubscriptElement(slice=m.Index(value=m.Integer()))]
        )):
            try:
                table_node = updated_node.value.value
                row_idx = int(updated_node.value.slice[0].slice.value.value) + 1
                col_idx = int(updated_node.slice[0].slice.value.value) + 1
                self.count += 1
                return cst.Call(
                    func=cst.Attribute(value=table_node, attr=cst.Name("get_cell")),
                    args=[
                        cst.Arg(value=cst.Integer(value=str(row_idx)), comma=cst.Comma(whitespace_after=cst.SimpleWhitespace(" "))),
                        cst.Arg(value=cst.Integer(value=str(col_idx)))
                    ]
                )
            except Exception as e:
                logger.debug(f"Table subscript transform skipped: {e}")
        return updated_node

class CSTFixer:
    """Manages deterministic code fixes using LibCST."""

    def __init__(self) -> None:
        pass

    def fix_known_patterns(self, code: str) -> Tuple[str, int]:
        """Apply generic and table-specific pattern rewrites."""
        try:
            module = cst.parse_module(code)
            
            # Generic
            t1 = GenericPatternTransformer()
            module = module.visit(t1)
            
            # Table
            t2 = TableTransformer()
            module = module.visit(t2)
            
            total = t1.count + t2.count
            if total > 0:
                return module.code, total
            return code, 0
        except Exception as e:
            logger.warning(f"CST parsing failed for known patterns: {e}")
            return code, 0

    def fix(
        self,
        code: str,
        issues: List[ValidationIssue],
    ) -> Tuple[str, List[ValidationIssue], int]:
        """Apply fixes for specific validation issues."""
        remaining: List[ValidationIssue] = []
        total_fixes = 0
        current_code = code

        for issue in issues:
            if not issue.should_auto_fix:
                remaining.append(issue)
                continue
                
            new_code = self._dispatch_fix(current_code, issue)
            if new_code and new_code != current_code:
                current_code = new_code
                total_fixes += 1
            else:
                remaining.append(issue)
                
        return current_code, remaining, total_fixes

    def _dispatch_fix(self, code: str, issue: ValidationIssue) -> Optional[str]:
        handlers = {
            IssueCategory.OUT_OF_BOUNDS: self._fix_out_of_bounds,
            IssueCategory.TEXT_OVERLAP: self._fix_text_overlap,
            IssueCategory.OBJECT_OCCLUSION: self._fix_object_occlusion,
        }
        handler = handlers.get(issue.category)
        if handler:
            return handler(code, issue)
        return None

    def _fix_out_of_bounds(self, code: str, issue: ValidationIssue) -> Optional[str]:
        details = issue.details
        try:
            module = cst.parse_module(code)
            
            # 1. Coordinate Clamping
            transformer = CoordinateClampingTransformer()
            updated_module = module.visit(transformer)
            
            # 2. Scale Insertion if needed
            if details.get("is_group_overflow"):
                obj_type = details.get("object_type", "")
                var_name = self._find_variable_for_type(module, obj_type)
                if var_name:
                    scale_transformer = ScaleInsertionTransformer(var_name)
                    updated_module = updated_module.visit(scale_transformer)
                
            if updated_module.code != code:
                return updated_module.code
        except Exception as e:
            logger.warning(f"CST OOB fix failed: {e}")
        return None

    def _fix_text_overlap(self, code: str, issue: ValidationIssue) -> Optional[str]:
        details = issue.details
        try:
            module = cst.parse_module(code)
            txt1 = details.get("text1", "")
            txt2 = details.get("text2", "")
            
            var1 = self._find_variable_for_text(module, txt1) if txt1 else None
            var2 = self._find_variable_for_text(module, txt2) if txt2 else None
            
            if var2:
                transformer = TextOverlapTransformer(var2, var1)
                updated_module = module.visit(transformer)
                if updated_module.code != code:
                    return updated_module.code
        except Exception as e:
            logger.warning(f"CST Text overlap fix failed: {e}")
        return None

    def _fix_object_occlusion(self, code: str, issue: ValidationIssue) -> Optional[str]:
        details = issue.details
        try:
            module = cst.parse_module(code)
            obj_type = details.get("object_type", "")
            var_name = self._find_variable_for_type(module, obj_type)
            
            if var_name:
                transformer = ObjectOcclusionTransformer(var_name)
                updated_module = module.visit(transformer)
                if updated_module.code != code:
                    return updated_module.code
        except Exception as e:
            logger.warning(f"CST Occlusion fix failed: {e}")
        return None

    def _find_variable_for_type(self, module: cst.Module, obj_type: str) -> Optional[str]:
        """Find the variable name assigned to a specific Manim type."""
        if not obj_type:
            return None
        
        # Simple search for Assign(targets=[Name(var)], value=Call(func=Name(obj_type)))
        # Matcher for this
        matcher = m.Assign(
            targets=[m.AssignTarget(target=m.Name())],
            value=m.Call(func=m.Name(obj_type) | m.Attribute(attr=m.Name(obj_type)))
        )
        
        # Search everywhere
        for node in module.body:
            if isinstance(node, cst.SimpleStatementLine):
                for stmt in node.body:
                    if m.matches(stmt, matcher):
                        return stmt.targets[0].target.value
            if isinstance(node, (cst.ClassDef, cst.FunctionDef)):
                # Recursive search in bodies
                inner_match = self._find_variable_for_type(node.body, obj_type)
                if inner_match:
                    return inner_match

        return None

    def _find_variable_for_text(self, module: cst.Module, text_content: str) -> Optional[str]:
        """Find the variable name assigned to a Text/Tex object containing text_content."""
        if not text_content:
            return None
        
        # Look for Call(func=Name("Text"|"Tex"|"MathTex"), args=[Arg(value=SimpleString(contains context))])
        matcher = m.Assign(
            targets=[m.AssignTarget(target=m.Name())],
            value=m.Call(
                func=m.Name(m.MatchIfTrue(lambda n: (n.value if hasattr(n, "value") else n) in ("Text", "Tex", "MathTex"))),
                args=[m.Arg(value=m.SimpleString(m.MatchIfTrue(lambda s: text_content[:20] in (s.value if hasattr(s, "value") else s))))]
            )
        )
        
        # Search everywhere
        for node in module.body:
            if isinstance(node, cst.SimpleStatementLine):
                for stmt in node.body:
                    if m.matches(stmt, matcher):
                        return stmt.targets[0].target.value
            if isinstance(node, (cst.ClassDef, cst.FunctionDef)):
                inner_match = self._find_variable_for_text(node.body, text_content)
                if inner_match:
                    return inner_match

        return None
