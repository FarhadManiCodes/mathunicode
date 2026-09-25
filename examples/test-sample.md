# mathunicode test document

A hand-picked set of cases covering every code path. The comment after each
line is the expected rendering of its math, in order, separated by ` / `
("no math" where nothing on the line may be taken for math); it is checked by
`tests/test_examples.py`. Multi-row math and script grouping have their own
file, `multiline.md`.

## Inline math ($...$)

- Subscript: $x_{i}$ and bare $x_1$            <!-- expect: xᵢ / x₁ -->
- Superscript: $\alpha^2$ and $10^6$           <!-- expect: α² / 10⁶ -->
- Multi-char subscript fully covered: $_{int}$ <!-- expect: ᵢₙₜ -->
- No subscript form for 'y', so grouped: $u_{phy}$ <!-- expect: u_(phy) -->
- Sum with protected macro: $\sum_{i=1}^{n}$   <!-- expect: ∑ᵢ₌₁ⁿ -->
- Nested script, grouping kept: $x^{i_j}$         <!-- expect: x^(iⱼ) -->

## Macros pylatexenc drops or mishandles

- Norm: $\| x \|^2$                            <!-- expect: ‖x‖² -->
- Determinant: $\det(A) = 0$                   <!-- expect: det(A) = 0 -->
- Trig: $\cot(x) + \csc(x)$                    <!-- expect: cot(x) + csc(x) -->
- Probability: $\Pr(X > 0)$                    <!-- expect: Pr(X > 0) -->
- Logic: $p \land q$                           <!-- expect: p ∧ q -->

## Prose / currency guards (must stay verbatim)

- Two amounts: costs $50 to train, compared to $100 for the baseline. <!-- expect: no math -->
- Escaped dollars: the item is \$5 and the combo is \$10 total. <!-- expect: no math -->

## Display block on one line ($$ ... $$)

$$ \Pr[x_1] = F(x) $$

## Multi-line display block (target of `mathunicode-collapse-blocks`)

$$
\| \boldsymbol{u}_{syn}(x) - \boldsymbol{u}_{phy}(x) \|^2
$$

## A second multi-line block

$$
a = b
c = d
$$
