# Curriculum eval (121 cases, real models, 2026-10-15)

| Outcome | Cases |
|---|---|
| pass | 119/121 |
| false success | 0/121 |
| unnecessary refusal | 2/121 |
| wrong status | 0/121 |
| provider limit | 0/121 |

Trust of solved answers: verified 107, AI agreement only 3, single reading 0 (of 110).
Latency per question: median 1.5 s; AI calls per question: 1.6 on average (cached calls included).

## By class

| Class | Pass |
|---|---|
| input handling | 6/6 |
| 6 | 16/17 |
| 7 | 18/19 |
| 8 | 26/26 |
| 9 | 19/19 |
| 10 | 34/34 |

## By problem family

| Family | Pass |
|---|---|
| conceptual | 4/4 |
| coordinates | 3/3 |
| equations | 22/22 |
| expression | 52/54 |
| hcf_lcm | 5/5 |
| identity | 1/1 |
| interest | 1/1 |
| invalid | 6/6 |
| mensuration | 9/9 |
| progression | 6/6 |
| statistics | 6/6 |
| unsupported | 4/4 |

## Every failure

| Class | Chapter | Question | Expected | Got | Outcome |
|---|---|---|---|---|---|
| 6 | Number Play | What is the smallest 5-digit palindrome? | 10001 | [needs_clarification] The question does not seem to give all the numbers needed (I would h | unnecessary refusal |
| 7 | Large Numbers Around Us | Write 3 crore 45 lakh in figures. | 34500000 | [needs_clarification] The question does not seem to give all the numbers needed (I would h | unnecessary refusal |
