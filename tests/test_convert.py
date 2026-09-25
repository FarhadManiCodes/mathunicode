"""Tests for LaTeX -> Unicode conversion. Every case here was found and
verified live against pylatexenc's actual behavior (not guessed) while
building this package -- see individual test docstrings for what each one
caught."""

from mathunicode.convert import (
    _looks_like_prose,
    _normalize_math_spacing,
    _unicode_scripts,
    collapse_math_blocks,
    convert_math_spans,
    latex_to_unicode,
)

# ---------------------------------------------------------------------------
# _normalize_math_spacing -- undoing OCR tools' inconsistent spacing
# ---------------------------------------------------------------------------


def test_normalize_strips_space_around_underscore_and_caret():
    assert _normalize_math_spacing("x _ {i}") == "x_{i}"
    assert _normalize_math_spacing("x ^ {2}") == "x^{2}"


def test_normalize_collapses_letter_spacing_inside_group_only():
    # 'u _ {p h y}' -> 'u_{phy}': OCR sometimes inserts spaces *between*
    # letters of a multi-character subscript, not just around the marker.
    assert _normalize_math_spacing("u _ {p h y}") == "u_{phy}"


def test_normalize_does_not_touch_body_text_spacing():
    # Letter-spacing collapse is scoped to _{...}/^{...} groups only --
    # 'a b' in body text could be intentional (implicit multiplication).
    assert _normalize_math_spacing("a b _ {i}") == "a b_{i}"


# ---------------------------------------------------------------------------
# _unicode_scripts -- real Unicode subscript/superscript substitution
# ---------------------------------------------------------------------------


def test_unicode_scripts_single_char_braced():
    assert _unicode_scripts("x_{i}") == "xᵢ"
    assert _unicode_scripts("x^{2}") == "x²"


def test_unicode_scripts_bare_no_braces():
    assert _unicode_scripts("x_1") == "x₁"
    assert _unicode_scripts("x^2") == "x²"


def test_unicode_scripts_multi_char_fully_covered():
    # i, n, t are all in the subscript map -- full conversion, not partial.
    assert _unicode_scripts("_{int}") == "ᵢₙₜ"


def test_unicode_scripts_no_partial_conversion():
    # 'y' has no Unicode subscript form -- must stay as literal text
    # entirely, never a mix like 'ₚhy'.
    assert _unicode_scripts("u_{phy}") == "u_{phy}"
    assert _unicode_scripts("u_{syn}") == "u_{syn}"


def test_unicode_scripts_uppercase_never_convertible():
    assert _unicode_scripts("X_{ABC}") == "X_{ABC}"


def test_unicode_scripts_skips_macro_content():
    # Content containing a backslash needs pylatexenc's own macro expansion
    # first (and Greek letters have no Unicode subscript forms anyway).
    assert _unicode_scripts("L_{\\Theta}") == "L_{\\Theta}"


def test_unicode_scripts_operators_in_group():
    assert _unicode_scripts("x_{i+1}") == "xᵢ₊₁"
    assert _unicode_scripts("z^{(k+1)}") == "z⁽ᵏ⁺¹⁾"


def test_unicode_scripts_protects_macro_name_tokenization():
    # Regression: substituting Unicode chars directly after a bare macro
    # name with no separator (e.g. '\\sum_{i=1}' -> '\\sumᵢ₌₁') glues onto
    # the name -- pylatexenc then reads '\\sumᵢ₌₁' as one unknown macro and
    # silently drops \\sum entirely. A protecting space must be inserted.
    result = _unicode_scripts("\\sum_{i=1}^{n}")
    assert result.startswith("\\sum ")
    assert "ᵢ₌₁" in result
    assert result.endswith("ⁿ")


def test_unicode_scripts_no_protecting_space_for_plain_letter_base():
    # Only a *macro name* prefix needs the protecting space; an ordinary
    # letter base (not preceded by a backslash) must stay tight, since that
    # is the overwhelmingly common case (x_1 -> x₁, not x _1 -> "x ₁").
    assert _unicode_scripts("x_{1}") == "x₁"
    assert " " not in _unicode_scripts("x_{1}")


def test_unicode_scripts_macro_expands_correctly_after_protection():
    # The protecting space must not prevent pylatexenc from still expanding
    # the macro correctly downstream -- verified end-to-end via
    # latex_to_unicode, not just _unicode_scripts in isolation.
    assert latex_to_unicode("\\Theta_{i}") == "Θᵢ"
    assert latex_to_unicode("\\sum_{i=1}^{n}") == "∑ᵢ₌₁ⁿ"


# ---------------------------------------------------------------------------
# _looks_like_prose -- guarding against $...$ false positives
# ---------------------------------------------------------------------------


def test_looks_like_prose_detects_multiword_text():
    assert _looks_like_prose("50 to train, compared to") is True
    assert _looks_like_prose("profit equals revenue minus cost") is True


def test_looks_like_prose_false_for_real_math():
    assert _looks_like_prose("x_i") is False
    assert _looks_like_prose("u_{phy}") is False
    assert _looks_like_prose("y = x + 1") is False
    assert _looks_like_prose("a + b = c") is False


def test_looks_like_prose_false_when_macro_present():
    assert _looks_like_prose("\\det(A) = 0") is False


# ---------------------------------------------------------------------------
# latex_to_unicode -- the full pipeline, plus the macro fixes found by
# testing every macro used across a real paper library (149 unique names)
# ---------------------------------------------------------------------------


def test_latex_to_unicode_previously_dropped_macros():
    # pylatexenc's defaults silently dropped or mishandled these -- not
    # cosmetically, but as real content loss.
    assert latex_to_unicode("\\| x \\|^2") == "‖ x ‖²"
    assert "‖" in latex_to_unicode(
        "\\| \\boldsymbol{u}_{syn}(x) - \\boldsymbol{u}_{phy}(x) \\|^2"
    )
    assert latex_to_unicode("\\det(A) = 0") == "det(A) = 0"
    assert latex_to_unicode("\\cot(x) + \\csc(x)") == "cot(x) + csc(x)"
    assert latex_to_unicode("\\Pr(X > 0)") == "Pr(X > 0)"
    assert latex_to_unicode("a^{\\circledR}") == "a^®"
    assert latex_to_unicode("p \\land q") == "p ∧ q"
    assert ":=" in latex_to_unicode("\\coloneqq")


def test_latex_to_unicode_ocr_spacing_artifacts():
    assert latex_to_unicode("x _ {i}") == "xᵢ"
    assert latex_to_unicode("u _ {p h y}") == "u_phy"
    assert latex_to_unicode("\\mathsf {L} _ {p h y} (\\Lambda)") == "𝖫_phy (Λ)"


def test_latex_to_unicode_prose_guard_restores_dollar_signs():
    # Called the way convert_math_spans would, with $ already stripped --
    # must come back with $ signs restored, not just left plain.
    assert latex_to_unicode("50 to train, compared to") == "$50 to train, compared to$"


def test_latex_to_unicode_never_raises_on_malformed_input():
    # Falls back to the original text rather than raising, so one bad
    # expression never breaks a larger document being converted.
    result = latex_to_unicode("\\left( unbalanced")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# convert_math_spans -- finding $...$/$$...$$ spans in a larger text
# ---------------------------------------------------------------------------


def test_convert_math_spans_inline_and_display():
    text = "The loss is $$ x_{i} $$ and inline $y^2$ here."
    result = convert_math_spans(text)
    assert "xᵢ" in result
    assert "y²" in result


def test_convert_math_spans_currency_false_positive_restored_verbatim():
    text = "The model costs $50 to train, compared to $100 for the baseline."
    assert convert_math_spans(text) == text


def test_convert_math_spans_inline_does_not_cross_paragraph_break():
    # Real inline math never spans a paragraph break; $...$ matching must
    # stay on one line so it can't accidentally pair a $ on one line with
    # an unrelated $ later in the document.
    text = "Price is $5 on line one.\nAnother $ amount on line two."
    result = convert_math_spans(text)
    assert result == text


def test_convert_math_spans_display_can_span_multiple_lines():
    text = "before\n$$\nx_{i}\n$$\nafter"
    result = convert_math_spans(text)
    assert "xᵢ" in result


def test_convert_math_spans_escaped_dollars_not_a_span():
    # '\$' is the Markdown escape for a literal dollar. The backslash it
    # introduces used to defeat the prose guard (which treats any backslash as
    # "real math"), so escaped currency got paired into a span and mangled.
    text = r"cost is \$5 and \$10 dollars"
    assert convert_math_spans(text) == text


def test_convert_math_spans_display_prose_restores_double_dollar():
    # A false positive inside a $$...$$ display block must come back as
    # $$...$$, not silently downgraded to a single-$ inline span.
    text = "$$ the quick brown fox jumps $$"
    assert convert_math_spans(text) == text


def test_unicode_scripts_no_partial_conversion_inside_nested_group():
    # A '_'/'^' group left whole because it isn't fully representable must not
    # have its interior reached by the bare pass: 'x^{i_j}' stays 'x^{i_j}',
    # never a partial 'x^{iⱼ}'.
    assert _unicode_scripts("x^{i_j}") == "x^{i_j}"
    assert _unicode_scripts("L_{a\\Theta}") == "L_{a\\Theta}"


# ---------------------------------------------------------------------------
# collapse_math_blocks -- fixing render-markdown.nvim's concealment gap
# ---------------------------------------------------------------------------


def test_collapse_math_blocks_basic():
    text = "before\n$$\n\\Pr[x_1] = F(x)\n$$\nafter"
    assert collapse_math_blocks(text) == "before\n$$ \\Pr[x_1] = F(x) $$\nafter"


def test_collapse_math_blocks_leaves_single_line_untouched():
    text = "before\n$$ x_i^2 $$\nafter"
    assert collapse_math_blocks(text) == text


def test_collapse_math_blocks_multiple_content_lines_joined():
    text = "$$\nline one\nline two\n$$"
    assert collapse_math_blocks(text) == "$$ line one line two $$"


def test_collapse_math_blocks_multiple_blocks_in_one_document():
    text = "$$\na\n$$\ntext between\n$$\nb\n$$"
    assert collapse_math_blocks(text) == "$$ a $$\ntext between\n$$ b $$"


def test_collapse_math_blocks_no_matching_close_left_untouched():
    text = "$$\nunclosed content"
    assert collapse_math_blocks(text) == text


def test_latex_to_unicode_is_thread_safe():
    # pylatexenc's LatexNodes2Text temporarily overwrites its own settings
    # inside math nodes like '\(...\)'; a converter shared across threads got
    # permanently corrupted by interleaved save/restore.
    import sys
    import threading

    inputs = ["\\alpha \\beta x \\(\\gamma  y\\) \\sum z", "a \\det c", "\\[ \\alpha  x \\] \\cot y"]
    expected = {s: latex_to_unicode(s) for s in inputs}
    mismatches = []

    def work(k):
        for i in range(300):
            s = inputs[(i + k) % len(inputs)]
            if latex_to_unicode(s) != expected[s]:
                mismatches.append(s)

    old_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        threads = [threading.Thread(target=work, args=(k,)) for k in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        sys.setswitchinterval(old_interval)
    assert not mismatches
    assert {s: latex_to_unicode(s) for s in inputs} == expected

# ---------------------------------------------------------------------------
# Escaped '\_' and the accent macro '\^' are not script markers
# ---------------------------------------------------------------------------


def test_accent_macro_circumflex_not_treated_as_superscript():
    # '\^{o}' used to become '\ᵒ' -- an unknown macro pylatexenc drops.
    assert latex_to_unicode("\\^{o}") == "ô"
    assert latex_to_unicode("\\^o") == "ô"


def test_escaped_underscore_not_treated_as_subscript():
    assert latex_to_unicode("a\\_1") == "a_1"
    assert _normalize_math_spacing("a \\_ b") == "a \\_ b"


def test_line_break_before_subscript_still_converts():
    # '\\_1' is a line break followed by a real subscript, not an escape.
    assert _unicode_scripts("a\\\\_1") == "a\\\\₁"


def test_control_space_before_marker_is_kept():
    # Stripping the space of '\ ' would turn it into the escape '\_'.
    assert _normalize_math_spacing("x\\ _1") == "x\\ _1"
    assert latex_to_unicode("x\\ _1") == "x ₁"


# ---------------------------------------------------------------------------
# Fallback on conversion failure
# ---------------------------------------------------------------------------


class _FailingConverter:
    def __init__(self, **kwargs):
        pass

    def latex_to_text(self, tex, **kwargs):
        raise ValueError("boom")


def test_latex_to_unicode_fallback_returns_original_input(monkeypatch):
    # Not the half-processed text ('xᵢ') -- the input exactly as given.
    monkeypatch.setattr("mathunicode.convert.LatexNodes2Text", _FailingConverter)
    assert latex_to_unicode("x _ {i}") == "x _ {i}"


def test_convert_math_spans_fallback_keeps_span_verbatim(monkeypatch):
    monkeypatch.setattr("mathunicode.convert.LatexNodes2Text", _FailingConverter)
    text = "see $x _ {i}$ and $$ y^2 $$ here"
    assert convert_math_spans(text) == text


def test_collapse_math_blocks_empty_block_does_not_mispair():
    # The empty block's closing '$$' must not become the opener of a new
    # block that swallows the prose line after it.
    text = "$$\n$$\nprose line\n$$\nmore"
    assert collapse_math_blocks(text) == text


def test_collapse_math_blocks_keeps_indentation():
    text = "- item\n  $$\n  x\n  $$\n"
    assert collapse_math_blocks(text) == "- item\n  $$ x $$\n"


def test_collapse_math_blocks_keeps_crlf_line_ending():
    text = "a\r\n$$\r\nx\r\n$$\r\nb\r\n"
    assert collapse_math_blocks(text) == "a\r\n$$ x $$\r\nb\r\n"


def test_collapse_math_blocks_skips_fenced_code():
    for fence in ("```", "~~~", "````"):
        text = f"{fence}\n$$\nx\n$$\n{fence}\n$$\ny\n$$"
        assert collapse_math_blocks(text) == f"{fence}\n$$\nx\n$$\n{fence}\n$$ y $$"


def test_collapse_math_blocks_shorter_fence_does_not_close():
    text = "````\n```\n$$\nx\n$$\n````"
    assert collapse_math_blocks(text) == text


def test_collapse_math_blocks_drops_blank_content_lines():
    assert collapse_math_blocks("$$\na\n\nb\n$$") == "$$ a b $$"


def test_collapse_math_blocks_leaves_tex_comment_block_untouched():
    # Joined onto one line, '% c' would comment out '+ y' as well.
    text = "$$\nx % c\n+ y\n$$"
    assert collapse_math_blocks(text) == text
    # An escaped '\%' is a literal percent sign, not a comment.
    assert collapse_math_blocks("$$\n50\\%\n$$") == "$$ 50\\% $$"


def test_latex_to_unicode_more_previously_dropped_macros():
    # pylatexenc drops all of these entirely.
    cases = {
        "\\sec(x)": "sec(x)",
        "\\coth(x)": "coth(x)",
        "\\lg(n)": "lg(n)",
        "\\ker(f)": "ker(f)",
        "\\dim(V)": "dim(V)",
        "\\deg(p)": "deg(p)",
        "\\gcd(a,b)": "gcd(a,b)",
        "\\hom(A,B)": "hom(A,B)",
        "(a)\\bmod(n)": "(a)mod(n)",
        "(p)\\lor(q)": "(p)∨(q)",
        "\\neg(p)": "¬(p)",
        "(A)\\iff(B)": "(A)⟺(B)",
        "(A)\\implies(B)": "(A)⟹(B)",
        "(A)\\impliedby(B)": "(A)⟸(B)",
        "x\\gets(1)": "x←(1)",
    }
    for tex, expected in cases.items():
        assert latex_to_unicode(tex) == expected, tex


def test_latex_to_unicode_pmod_keeps_its_argument():
    # Used to give 'a n' -- the 'mod' lost, only the argument left.
    assert latex_to_unicode("a\\pmod{n}") == "a(mod n)"


# ---------------------------------------------------------------------------
# convert_math_spans -- which '$'s pair up
# ---------------------------------------------------------------------------


def test_convert_math_spans_currency_never_pairs():
    for text in ("pay $5 or $6", "costs $5-$10", "from $250 to $10,000.", "US $49.99 CAN $52.99"):
        assert convert_math_spans(text) == text


def test_convert_math_spans_rejected_match_does_not_swallow_real_math():
    # A '$' that doesn't open a span must not eat the opening '$' of a real
    # span after it.
    assert convert_math_spans("pay $5 or $x$ now") == "pay $5 or x now"
    assert convert_math_spans("pay $5 for $x^2$") == "pay $5 for x²"
    # Nor may a prose-guard rejection eat it.
    assert convert_math_spans("The $ sign is used a lot, $x$") == "The $ sign is used a lot, x"


def test_convert_math_spans_symbol_before_number():
    # The no-digit-after-closing-'$' rule only applies to bodies that start
    # with a digit (currency); '$\pm$0.26' is still math.
    assert convert_math_spans("0.20$\\pm$0.26") == "0.20±0.26"
    assert convert_math_spans("$\\gg$175B") == "≫175B"


def test_convert_math_spans_ocr_padding():
    # OCR output pads inline spans: '$ r $', and sometimes only one side.
    assert convert_math_spans("an $ r $ -dimensional") == "an r -dimensional"
    assert convert_math_spans("$ x _ {i} $ ok") == "xᵢ ok"
    assert convert_math_spans("$ t\\in[0,1]$ ;") == "t∈[0,1] ;"
    assert convert_math_spans("$C_{\\alpha}^{*} $ is") == "C_α^* is"


def test_convert_math_spans_trailing_pad_needs_latex():
    # Space only before the closing '$' is accepted only for clear LaTeX;
    # otherwise it looks just like '$5 or $'.
    assert convert_math_spans("$^ -o $@") == "$^ -o $@"
    assert convert_math_spans("$5 for a \\to b $") == "$5 for a \\to b $"


def test_convert_math_spans_strips_padding_from_output():
    assert convert_math_spans("$$ \\alpha $$") == "α"
    assert convert_math_spans("before\n$$\nx_{i}\n$$\nafter") == "before\nxᵢ\nafter"


def test_convert_math_spans_skips_inline_code():
    assert convert_math_spans("run `echo $HOME and $PATH` now") == "run `echo $HOME and $PATH` now"
    # The code span's '$' must not pair with the real math opener after it.
    assert convert_math_spans("see `$HOME` and $x$") == "see `$HOME` and x"
    assert convert_math_spans("``a ` $x$ ``, $y_1$") == "``a ` $x$ ``, y₁"


def test_convert_math_spans_skips_fenced_code():
    assert convert_math_spans("```\nx = $a$\n```\n$b^2$") == "```\nx = $a$\n```\nb²"
    # A shorter or different fence inside doesn't close it.
    assert convert_math_spans("~~~~\n```\n$a$\n~~~~\n$b^2$") == "~~~~\n```\n$a$\n~~~~\nb²"
    # An unclosed fence runs to the end of the text.
    assert convert_math_spans("```\n$a$") == "```\n$a$"


# ---------------------------------------------------------------------------
# Spacing after operator names and relations
# ---------------------------------------------------------------------------


def test_space_kept_after_word_operators():
    # pylatexenc glued these into one word: 'sinx', 'detA', 'cost'.
    assert latex_to_unicode("\\sin x") == "sin x"
    assert latex_to_unicode("\\det A") == "det A"
    assert latex_to_unicode("1 - \\cos t") == "1 - cos t"
    assert latex_to_unicode("\\log \\alpha") == "log α"
    assert latex_to_unicode("a \\bmod n") == "a mod n"


def test_space_kept_after_relations():
    assert latex_to_unicode("a \\to b") == "a → b"
    assert latex_to_unicode("x \\in [0,1]") == "x ∈ [0,1]"
    assert latex_to_unicode("a \\le b") == "a ≤ b"
    assert latex_to_unicode("p \\land q") == "p ∧ q"
    assert latex_to_unicode("x \\coloneqq y") == "x := y"
    assert latex_to_unicode("\\mathbf {u} \\otimes \\mathbf {u}") == "𝐮 ⊗ 𝐮"


def test_other_macros_stay_tight():
    # Greek letters and other symbols: 'Δt', not 'Δ t'.
    assert latex_to_unicode("\\Delta t") == "Δt"
    assert latex_to_unicode("\\alpha x") == "αx"
    assert latex_to_unicode("\\nabla f") == "∇f"
    # '\in' must not match inside '\int'.
    assert latex_to_unicode("\\int x") == "∫x"


def test_no_space_added_where_source_has_none():
    assert latex_to_unicode("\\exp(x)") == "exp(x)"
    assert latex_to_unicode("\\sin\\theta") == "sinθ"
    assert latex_to_unicode("\\max_i x_i") == "maxᵢ xᵢ"
    assert latex_to_unicode("\\sin \\left( x \\right)") == "sin( x )"


def test_tight_relation_stays_tight():
    # The space after '\leq' in 'a\leq b' only ends the macro name; keeping
    # it would give a lopsided 'a≤ b'. The usual LLM style.
    assert latex_to_unicode("a\\leq b") == "a≤b"
    assert latex_to_unicode("\\forall x\\in A") == "∀x∈A"
    assert latex_to_unicode("x\\to 0") == "x→0"


def test_word_operator_before_norm():
    assert latex_to_unicode("\\ln \\|x\\|") == "ln ‖x‖"


def test_colon_macro_not_dropped():
    # Set like punctuation: no space before, one after.
    assert latex_to_unicode("f\\colon X\\to Y") == "f: X→Y"
    assert latex_to_unicode("f \\colon X \\to Y") == "f: X → Y"


def test_one_line_triple_backticks_are_a_code_span_not_a_fence():
    # A backtick fence's info string can't contain backticks, so this is an
    # inline code span -- treating it as an unclosed fence masked everything
    # after it.
    text = "```ls $HOME``` then $x^2$\n\nlater $y_1$"
    assert convert_math_spans(text) == "```ls $HOME``` then x²\n\nlater y₁"
    assert collapse_math_blocks("```x```\n$$\na\n$$") == "```x```\n$$ a $$"


def test_convert_math_spans_input_containing_mask_sentinel():
    # '\x01' is the code-mask sentinel; input already holding it used to crash.
    assert convert_math_spans("\x010\x01 and $x$") == "\x010\x01 and x"


def test_convert_math_spans_many_backtick_runs_is_fast():
    import time

    text = " ".join("`" * k for k in range(1, 400))
    start = time.perf_counter()
    assert convert_math_spans(text) == text
    assert time.perf_counter() - start < 1.0


def test_fence_inside_list_item_or_blockquote():
    # LLMs often put fences in numbered lists. Unrecognised, the indented
    # closer was taken as a new opener and masked everything after it.
    text = "1. ```bash\n   echo $HOME and $PATH\n   ```\n2. then $x^2$"
    assert convert_math_spans(text) == "1. ```bash\n   echo $HOME and $PATH\n   ```\n2. then x²"
    assert convert_math_spans("- ```\n  $a$\n  ```\n$b_1$") == "- ```\n  $a$\n  ```\nb₁"
    text = "1. ```\n   $$\n   x\n   $$\n   ```\n$$\ny\n$$"
    assert collapse_math_blocks(text) == "1. ```\n   $$\n   x\n   $$\n   ```\n$$ y $$"


def test_relation_after_alignment_or_spacing_macro():
    assert latex_to_unicode("x &\\leq y") == "x    ≤ y"
    assert latex_to_unicode("x\\quad\\implies y") == "x  ⟹ y"
    assert latex_to_unicode("x\\;\\to y") == "x → y"


def test_colon_keeps_control_space_before_it():
    # Stripping the space of '\ ' turned '\ \colon' into '\\colon'.
    assert "colon" not in latex_to_unicode("x\\ \\colon y")


def test_latex_to_unicode_dropped_symbols_batch_two():
    # Also dropped entirely by pylatexenc; all used in the paper library.
    cases = {
        "a \\models b": "a ⊨ b",
        "\\varSigma": "Σ",
        "\\varPhi": "Φ",
        "\\varOmega_i": "Ωᵢ",
        "\\Box p": "□p",
        "\\checkmark": "✓",
        "\\ddagger": "‡",
        "(a)\\bot(b)": "(a)⊥(b)",
        "\\llbracket x\\rrbracket": "⟦x⟧",
        "\\S 3": "§3",
        "a \\colonequals b": "a := b",
        "a \\eqqcolon b": "a =: b",
    }
    for tex, expected in cases.items():
        assert latex_to_unicode(tex) == expected, tex


def test_wide_accents_keep_their_mark():
    # pylatexenc dropped the accent: '\overline{x}' -> 'x'.
    assert latex_to_unicode("\\overline{x}") == "x̅"
    assert latex_to_unicode("\\overline{AB}") == "A̅B̅"
    assert latex_to_unicode("\\widetilde{x}") == "x̃"
    assert latex_to_unicode("\\widehat{\\theta}") == "θ̂"


def test_labelled_arrows_and_binomials():
    # '\xrightarrow{f}' vanished entirely, label and arrow both.
    assert latex_to_unicode("A \\xrightarrow{f} B") == "A -f→ B"
    assert latex_to_unicode("A \\xleftarrow{f} B") == "A ←f- B"
    assert latex_to_unicode("\\xrightarrow{}") == "→"
    # '\binom{n}{k}' gave 'nk'.
    assert latex_to_unicode("\\binom{n}{k}") == "C(n,k)"
    assert latex_to_unicode("\\dbinom nk") == "C(n,k)"


def test_no_doubled_space_around_spacing_macros():
    # Math mode ignores spaces next to '\,' '\;' '\:' '\!'; pylatexenc printed
    # them as well as the macro's own space.
    assert latex_to_unicode("x\\,\\to\\, y") == "x → y"
    assert latex_to_unicode("\\int f(x) \\, d x") == "∫f(x) d x"
    assert latex_to_unicode("a \\; b") == "a b"
    # '\\,' is a line break followed by a comma, not a thin space.
    assert latex_to_unicode("a\\\\, b") == "a\n, b"


def test_colon_at_end_has_no_trailing_space():
    assert latex_to_unicode("f\\colon") == "f:"
    assert latex_to_unicode("f\\colon\\mathbb{R}\\to\\mathbb{R}") == "f: ℝ→ℝ"
