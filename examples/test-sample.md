# mathunicode test document

A hand-picked set of cases covering every code path. Expected results are in
the comment after each line.

## Inline math ($...$)

- Subscript: $x_{i}$ and bare $x_1$            <!-- xᵢ / x₁ -->
- Superscript: $\alpha^2$ and $10^6$           <!-- α² / 10⁶ -->
- Multi-char subscript fully covered: $_{int}$ <!-- ᵢₙₜ -->
- Not fully representable, stays plain: $u_{phy}$   <!-- u_phy (y has no subscript form) -->
- Sum with protected macro: $\sum_{i=1}^{n}$   <!-- ∑ᵢ₌₁ⁿ -->
- Nested script left whole (no partial): $x^{i_j}$  <!-- x^i_j, never x^iⱼ -->

## Macros pylatexenc drops or mishandles

- Norm: $\| x \|^2$                            <!-- ‖ x ‖² -->
- Determinant: $\det(A) = 0$                   <!-- det(A) = 0 -->
- Trig: $\cot(x) + \csc(x)$                    <!-- cot(x) + csc(x) -->
- Probability: $\Pr(X > 0)$                    <!-- Pr(X > 0) -->
- Logic: $p \land q$                           <!-- p ∧ q -->

## Prose / currency guards (must stay verbatim)

- Two amounts: costs $50 to train, compared to $100 for the baseline.
- Escaped dollars: the item is \$5 and the combo is \$10 total.

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
