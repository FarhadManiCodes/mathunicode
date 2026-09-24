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
