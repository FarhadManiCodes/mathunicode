# mathunicode: multi-row math and script grouping

Open this in nvim (render-markdown with `converter = { "mathunicode" }`) to
see each formula rendered in place. The comment after each line is the
expected rendering of its math, in order, separated by ` / `; it is checked
by `tests/test_examples.py`.

## Multi-row environments: one line, rows joined by `;`

A true 2-D layout would need a typesetter; rows as separate lines misalign
as soon as anything surrounds the environment. Every construct has a linear
form instead, and composes with the math around it.

- Cases: $f(x) = \begin{cases} 1 & x > 0 \\ 0 & \text{otherwise} \end{cases}$ <!-- expect: f(x) = {1, x > 0; 0, otherwise -->
- Cases, comma before `&`: $|x| = \begin{cases} x, & x \ge 0 \\ -x, & x < 0 \end{cases}$ <!-- expect: |x| = {x, x ≥ 0; −x, x < 0 -->
- Cases as OCR writes them: $\left\{ \begin{array}{ll} 1 & x > 0 \\ 0 & \text{else} \end{array} \right.$ <!-- expect: {1, x > 0; 0, else -->
- Matrix: $A = \begin{pmatrix} 1 & 2 \\ 3 & 4 \end{pmatrix}$ <!-- expect: A = (1, 2; 3, 4) -->
- Determinant: $\det \begin{vmatrix} a & b \\ c & d \end{vmatrix} = ad - bc$ <!-- expect: det |a, b; c, d| = ad − bc -->
- Column vector: $\mathbf{x} = \begin{bmatrix} x_{1} \\ x_{2} \\ x_{3} \end{bmatrix}$ <!-- expect: 𝐱 = [x₁; x₂; x₃] -->
- Aligned: $\begin{aligned} a &= b + c \\ d &= e - f \end{aligned}$ <!-- expect: a = b + c; d = e − f -->
- OCR array of equations: $\begin{array}{l} u_{t} + u u_{x} = 0 \\ u(0, x) = -\sin(\pi x) \end{array}$ <!-- expect: uₜ + uuₓ = 0; u(0, x) = −sin(πx) -->
- Stacked subscript: $\sum_{\substack{i < n \\ j < m}} x_{ij}$ <!-- expect: ∑_(i < n; j < m) xᵢⱼ -->

## Script grouping

Unicode sub/superscript characters where every character has one; otherwise
parentheses when the script is more than one token, so the grouping stays
visible (`x^i_j` would read as x^i with a subscript j).

- Nested script: $x^{i_j}$ <!-- expect: x^(iⱼ) -->
- Signed exponent: $e^{-x^2}$ <!-- expect: e^(−x²) -->
- Greek in the exponent: $e^{-i\omega t}$ <!-- expect: e^(−iωt) -->
- List subscript: $\min_{\Theta, \Lambda} f$ and $x_{i,j}^{2}$ <!-- expect: min_(Θ, Λ) f / x_(i, j)² -->
- Product dimension: $\mathbb{R}^{n \times m}$ <!-- expect: ℝ^(n × m) -->
- Representable, OCR-spaced: $x^{n + 1}$ <!-- expect: xⁿ⁺¹ -->
- Symbols with their own character: $A^{T}$, $f^{\prime}$, $90^{\circ}$ <!-- expect: Aᵀ / f′ / 90° -->
- One token, left as is: $u_{phy}$ and $\min_{\mathbf{x}} f$ <!-- expect: u_phy / min_𝐱 f -->
- OCR-spaced math font: $\mathrm{a r g m i n}_{x} f(x)$ <!-- expect: argminₓ f(x) -->

## Multi-line source

A display block written over several lines: in LaTeX a source line break
is only a space, so these render on one line too. render-markdown can only
conceal a formula whose *source* is on one line, so it draws these above
the block with the source still visible -- `:MathCollapse` (<leader>lm)
rewrites the block onto one line.

$$
a +
b
$$
<!-- expect: a + b -->

$$
\begin{aligned}
a &= b \\
c &= d
\end{aligned}
$$
<!-- expect: a = b; c = d -->
