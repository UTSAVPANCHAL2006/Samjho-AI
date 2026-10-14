# Full student journey — 22/22 sets with no problem

| Class | Sets | Wrong attempt caught (✗ on a line, marks lost) | Right attempt full marks | False accusations |
|---|---|---|---|---|
| 6 | 1 | 1/1 | 1/1 | 0 |
| 7 | 1 | 1/1 | 1/1 | 0 |
| 8 | 2 | 2/2 | 2/2 | 0 |
| 9 | 5 | 5/5 | 5/5 | 0 |
| 10 | 13 | 13/13 | 13/13 | 0 |

## c6_set_01_fractions — OK
- wrong: graded 0.0/2, ✗ line 3 `= (2 + 1) / (3 + 4)` — You added the tops and also added the bottoms: $ 2/3 + 1/4$ became $(2 + 1) / (3 + 4)$. Fractions can be added only when the bottoms (denominators) are the same — first make them equal with the LCM, then add only the tops. Check with numbers: $\frac{1}{2} + \frac{1}{3} = \frac{5}{6}$, but adding tops and bottoms gives $\frac{2}{5}$, which is even smaller than $\frac{1}{2}$ alone.
- right: graded 2.0/2, ✗ line None `None` — None
- planted mistake: Adding numerators together and denominators together (Freshman's Dream on fractions)
- insight: Fractions ko add karte waqt denominators ko directly add nahi karte. Pehle LCM lekar denominators ko same banao, phir sirf numerators ko add karo.

## c7_set_05_triangle_angles — OK
- wrong: graded 0.0/3, ✗ line 2 `50 + 60 + x = 360 \text{ (used } 360 \text{ instead of } 180)` — Your answer goes wrong here: this line gives $250$, which is not what this question needs. The lines after it are calculated correctly — they just carry this value forward. Check two things in this line: is the formula right, and did each number go in the right place?
- right: graded 3.0/3, ✗ line None `None` — None
- planted mistake: Sum of triangle angles confused with quadrilateral: using 360° instead of 180°
- insight: Triangle ke teeno angles ka sum $180^{\circ}$ hota hai, $360^{\circ}$ nahi. Isliye next time angles ki property dhyan se use karna.

## c8_set_05_surface_area — OK
- wrong: graded 0.0/2, ✗ line 5 `\text{TSA} = l * b * h \text{ (used volume formula)}` — This line works out to $400$ — that is exactly what you get if you used the volume formula instead of the total surface area formula. Fix this one idea and the rest of your working will follow.
- right: graded 2.0/2, ✗ line None `None` — None
- planted mistake: Concept confusion: calculating volume (l*b*h) instead of surface area 2(lb+bh+hl)
- insight: Tumne yahan total surface area ki jagah volume ka formula $l \times b \times h$ laga diya. Next time yaad rakho ki surface area mein saari faces ka area nikalte hain, isliye formula $2(lb + bh + hl)$ use hoga.

## c9_set_04_herons_semiperim — OK
- wrong: graded 0.5/3, ✗ line 9 `= \text{sqrt}(24 \times 18 \times 16 \times 14)` — This line works out to $48 \sqrt{42}$ — that is exactly what you get if you used the perimeter a + b + c as s — Heron's s is the SEMI-perimeter (a + b + c)/2. Fix this one idea and the rest of your working will follow.
- right: graded 3.0/3, ✗ line None `None` — None
- planted mistake: Semi-perimeter definition slip: using perimeter s = a + b + c directly without / 2
- insight: Tumne line 5 mein semi-perimeter nikalte waqt $2$ se divide karna bhool diya, isliye line 8 mein $s$ ki jagah galat value use ho gayi. Heron's formula mein $s$ semi-perimeter hota hai, yaani teeno sides ka sum divide by $2$.

## c10_set_02_linear_elimination — OK
- wrong: graded 0.0/4, ✗ line 4 `-y = -13` — This line does not follow from the line before it — something changed that should not have. Do just this one step again, slowly, and compare it with the line above.
- right: graded 4.0/4, ✗ line None `None` — None
- planted mistake: Double negative subtraction slip: 3y - (-4y) written as -y instead of 7y
- insight: Dekho, equation (3) mein subtract karte waqt signs change karne the: $3y - (-4y)$ karne se $7y$ aana chahiye tha, tumne sirf $3y - 4y$ kar diya. Next time subtraction mein niche wale equation ke saare signs dhyan se badla karo.

## c10_set_03_ap_nth_term — OK
- wrong: graded 0.0/2, ✗ line 5 `a_{15} = 4 + 15 * 5` — This line works out to $79$ — that is exactly what you get if you used aₙ = a + n·d instead of a + (n − 1)d. Fix this one idea and the rest of your working will follow.
- right: graded 2.0/2, ✗ line None `None` — None
- planted mistake: Formula slip: using a + nd instead of a + (n - 1)d
- insight: Line 5 mein tumne n ki jagah seedha 15 likh diya, jabki formula $a + (n - 1)d$ hota hai jisme $n - 1$ yaani $(15 - 1)$ likhna tha. Agli baar dhyan rakhna ki $n^{\text{th}}$ term ke liye hamesha $(n - 1)$ use karte hain.

## c10_set_05_sector_area — OK
- wrong: graded 0.0/2, ✗ line 4 `= (60/360) * 2 * (22/7) * 6` — This line works out to $\frac{44}{7}$ — that is exactly what you get if you used the arc length formula instead of the area formula. Fix this one idea and the rest of your working will follow.
- right: graded 2.0/2, ✗ line None `None` — None
- planted mistake: Arc length vs Sector area confusion: using 2*pi*r instead of pi*r^2
- insight: Area of sector ke liye formula $\frac{\theta}{360} \times \pi r^2$ hota hai, circumference wala nahi. Agli baar dhyan rakhna ki area mein radius ka square karte hain.

## c8_set_08_negative_exponent — OK
- wrong: graded 0.0/2, ✗ line 4 `= -(2^3)` — Your answer goes wrong here: this line gives $-8$, which is not what this question needs. The lines after it are calculated correctly — they just carry this value forward. Check two things in this line: is the formula right, and did each number go in the right place?
- right: graded 2.0/2, ✗ line None `None` — None
- planted mistake: Interpreting 2^(-3) as negative multiplication 2 x (-3) = -6 or -8
- insight: Negative power ka matlab negative number nahi hota hai, iska formula reciprocal ke liye hota hai: $a^{-m} = \frac{1}{a^m}$. Next time yaad rakhna ki minus sign power mein ho toh base ko denominator mein le jaate hain.

## c9_set_07_surds_conjugate — OK
- wrong: graded 0.0/2, ✗ line 6 `= 9 - 4` — This line works out to $5$ — the first place your wrong value appears — but this question needs a different value. Every line after it only simplifies this value. Check the formula here and every number you put into it.
- right: graded 2.0/2, ✗ line None `None` — None
- planted mistake: Squaring root 2 as (sqrt(2))^2 = 4 instead of 2
- insight: Dekho, $\text{sqrt}(2)$ ka square 2 hota hai, 4 nahi. Next time, root wale number ka square karte waqt number wahi rehta hai.

## c9_set_09_experimental_prob — OK
- wrong: graded 0.0/2, ✗ line 3 `P(6) = 1 / 6` — This line works out to $\frac{1}{6}$ — the first place your wrong value appears — but this question needs a different value. Every line after it only simplifies this value. Check the formula here and every number you put into it.
- right: graded 2.0/2, ✗ line None `None` — None
- planted mistake: Writing theoretical probability 1/6 of standard die instead of experimental frequency 15/60
- insight: Experimental probability ke liye theoretical formula $1 / 6$ seedha use nahi karte, balki total trials aur favourable outcomes ka ratio nikalte hain. Agli baar dhyan rakhna ki question mein diye gaye numbers $15$ aur $60$ ko use karke probability calculate karni hai, standard dice rule nahi lagana.

## c9_set_10_quadrilateral_angles — OK
- wrong: graded 0.0/3, ✗ line 4 `75^\circ + 90^\circ + 105^\circ + x = 180^\circ` — This line does not match the question (it leads to $-90$). Read the question again and check the rule or total you used to write it.
- right: graded 3.0/3, ✗ line None `None` — None
- planted mistake: Taking sum of angles as 180° (triangle) instead of 360° (quadrilateral)
- insight: Quadrilateral ke charon angles ka sum $360^\circ$ hota hai, $180^\circ$ nahi kyunki $180^\circ$ toh triangle ka sum hota hai. Next time yaad rakhna ki polygon ki sides ke hisaab se angle sum property lagani hai.

## c9_set_11_ap_15th_term — OK
- wrong: graded 0.0/2, ✗ line 6 `= 4 + 15(5)` — This line works out to $79$ — that is exactly what you get if you used aₙ = a + n·d instead of a + (n − 1)d.
- right: graded 2.0/2, ✗ line None `None` — None
- planted mistake: Using Tn = a + nd instead of Tn = a + (n-1)d
- insight: $n$-th term ke liye formula $a_n = a + (n - 1)d$ hota hai, jisme $n$ me se $1$ minus karna zaroori hai. Agli baar dhyan rakhna ki $15$th term ke liye $14d$ lena hai, seedha $15d$ nahi.

## c10_set_06_real_numbers_lcm_hcf — OK
- wrong: graded 0.0/2, ✗ line 4 `\text{LCM} = 36 \times 657` — Moving the numbers to one side, the line before gives $\text{LCM} = 22338$, but this line gives $\text{LCM} = 23652$.
- right: graded 2.0/2, ✗ line None `None` — None
- planted mistake: Arithmetic division slip: 306/9 written as 36 instead of 34
- insight: Dekho, 306 ko 9 se divide karte waqt calculation mistake ho gayi, division dhyan se karo. Next time multiplication aur division step-by-step check karo taaki aisi silly mistake na ho.

## c10_set_07_polynomial_middle_term — OK
- wrong: graded 0.0/2, ✗ line 3 `= (x + 3)(x + 4)` — Multiply this line back out: it gives $x^{2} + 7 x + 12$, but the line before is $x^{2} - 7 x + 12$ — so the factors are not right.
- right: graded 2.0/2, ✗ line None `None` — None
- planted mistake: Middle term sign error: using +3, +4 instead of -3, -4 for sum -7
- insight: Dekho, line 3 mein middle term $-7x$ lane ke liye dono numbers minus chahiye the, kyunki $(-3) + (-4) = -7$ hota hai aur $(-3) \times (-4) = +12$ hota hai. Next time signs ka dhyan rakho ki multiply karne par positive aur add karne par negative aaye.

## c10_set_08_ap_sum_formula — OK
- wrong: graded 0.0/2, ✗ line 8 `= 10[1 + 57]` — This line works out to $580$ — that is exactly what you get if you used Sₙ = n/2[a + (n − 1)d] — the formula needs 2a, not a.
- right: graded 2.0/2, ✗ line None `None` — None
- planted mistake: Omission of factor 2 in formula: writing Sn = n/2 [a + (n-1)d]
- insight: AP ke sum ka formula $S_n = \frac{n}{2}[2a + (n - 1)d]$ hota hai, jisme $2a$ likhte hain sirf $a$ nahi. Agli baar formula yaad rakhte waqt dhyan do ki pehle term $a$ ko $2$ se multiply karte hain.

## c10_set_09_trigonometric_values — OK
- wrong: graded 0.0/2, ✗ line 5 `= 2(1) + \sqrt{3}/2 - \sqrt{3}/2` — The question has squares (like $\tan^2 45^\circ$): each value must be squared before it is added, but this line uses the values without their squares. The answer only came out right because two terms cancel — the working is not right.
- right: graded 2.0/2, ✗ line None `None` — None
- planted mistake: Omitting squares of trigonometric values, calculating 2(1) + sqrt(3)/2 - sqrt(3)/2
- insight: Yahan square karna bhool gaye ho: $\tan^2 45^\circ$, $\cos^2 30^\circ$ aur $\sin^2 60^\circ$ mein values ka square likhna zaroori hai. Agli baar table ki values put karte waqt powers ka dhyan rakho.

## c10_set_10_heights_shadow — OK
- wrong: graded 0.0/3, ✗ line 5 `\sin 45^\circ = h / 20` — Your answer goes wrong here: this line gives $10 \sqrt{2}$, which is not what this question needs. The lines after it are calculated correctly — they just carry this value forward. Check two things in this line: is the formula right, and did each number go in the right place?
- right: graded 3.0/3, ✗ line None `None` — None
- planted mistake: Using sin 45° instead of tan 45° for height / base ratio
- insight: Line 5 mein tumne perpendicular ke liye $\sin 45^\circ$ ka formula laga diya, jabki yahan base aur perpendicular ka relation hai toh $\tan 45^\circ$ use karna chahiye tha. Agli baar dhyan rakhna ki angle aur sides ke beech ka sahi trigonometric ratio chuno.

## c10_set_11_circle_tangent_pythagoras — OK
- wrong: graded 0.0/3, ✗ line 4 `PT^2 = 13^2 + 5^2` — This line does not follow from the line before it. Redo this one step slowly and compare.
- right: graded 3.0/3, ✗ line None `None` — None
- planted mistake: Adding squares instead of subtracting from hypotenuse: PT = sqrt(13^2 + 5^2)
- insight: Tangent aur radius ke beech ka angle $90^{\circ}$ hota hai, isliye $OP$ hypotenuse banega, aur Pythagoras theorem mein hypotenuse ka square baaki dono sides ke squares ke sum ke barabar hota hai, isliye minus karna chahiye tha plus nahi.

## c10_set_12_hemisphere_volume — OK
- wrong: graded 0.0/2, ✗ line 3 `\text{volume} = (4/3) \times \pi \times r^{\wedge}3` — In this line the r^3 term should be 0, the line gives 4*pi/3; the r term should be 1, the line gives 0; the number term should be -21, the line gives 0.
- right: graded 2.0/2, ✗ line None `None` — None
- planted mistake: Using full sphere formula 4/3 pi*r^3 instead of hemisphere 2/3 pi*r^3
- insight: Dekho, hemisphere ka volume $\frac{2}{3}\pi r^3$ hota hai, poore sphere ka $\frac{4}{3}\pi r^3$ nahi. Yaad rakho, solid hemisphere ke liye formula me fraction $\frac{2}{3}$ use karte hain.

## c10_set_13_triangles_thales — OK
- wrong: graded 0.0/2, ✗ line 6 `AD / DB = EC / AE` — This line works out to $\frac{8}{3}$ — the first place your wrong value appears — but this question needs a different value. Every line after it only simplifies this value. Check the formula here and every number you put into it.
- right: graded 2.0/2, ✗ line None `None` — None
- planted mistake: Inverting ratio in Thales theorem: AD/DB = EC/AE instead of AE/EC
- insight: Dekho, Thales Theorem mein ratio lete waqt $AD / DB = AE / EC$ hota hai, tumne $EC / AE$ likh diya. Agli baar formula mein sides ka order check karke values put karna.

## c10_set_14_grouped_mean — OK
- wrong: graded 0.0/2, ✗ line 3 `\text{Sol: } \text{Mean} = \text{Sum}(f) / \text{Sum}(fx)` — This line works out to $\frac{1}{13}$ — the first place your wrong value appears — but this question needs a different value. Every line after it only simplifies this value. Check the formula here and every number you put into it.
- right: graded 2.0/2, ✗ line None `None` — None
- planted mistake: Inverting division: calculating Sigma f / Sigma (f*x) instead of Sigma (f*x) / Sigma f
- insight: Dekho, arithmetic mean ka formula $\frac{\Sigma(f \cdot x)}{\Sigma f}$ hota hai, isme tumne ulta likh diya. Agli baar dhyan rakhna ki sum of observations ko total frequency se divide karte hain, frequency ko upar nahi rakhte.

## c10_set_15_probability_cards — OK
- wrong: graded 0.0/2, ✗ line 6 `= 1 / 26` — The line before equals $15.0 Q$, but this line equals $\frac{1}{26}$ — they are not the same.
- right: graded 2.0/2, ✗ line None `None` — None
- planted mistake: Confusing number of Kings in deck as 2 (thinking only 1 red and 1 black) instead of 4
- insight: Dekho, ek standard deck me total $4$ Kings hote hain, $2$ nahi. Isliye $P(\text{King})$ nikalte waqt favorable outcomes me $4$ lena chahiye tha.
