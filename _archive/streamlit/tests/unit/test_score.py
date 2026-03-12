from src.engine import calculate_merit_score

# User Scenario:
# BM = C (6 points)
# Others = A+ (18 points)?
# Need to know the subject list structure to simulate accurately.

# Let's assume a typical 8-subject implementation.
# If the user got 97.19%, let's reverse engineer what points sum up to that.
# Formula: Merit = (Academic * 0.9) + (CoQ * 0.1) -> Assuming CoQ is 10.

# Let's test standard case first.
# Section 1: 5 subjects. 
# Section 2: 3 subjects.
# Section 3: 0 subjects?

# If BM=C, and others=A+
# S1: BM(6) + 4x18 = 6+72 = 78
# S2: 3x18 = 54
# S3: 0?

def test_calc(s1_grades, s2_grades, s3_grades, coq):
    res = calculate_merit_score(s1_grades, s2_grades, s3_grades, coq)
    print(f"Inputs: S1={s1_grades}, S2={s2_grades}, S3={s3_grades}, CoQ={coq}")
    print(f"Result: {res}")
    return res

# Case 1: BM=C, others A+
# S1: BM, Eng, Math, Hist (4 subjects)
s1 = ['C', 'A+', 'A+', 'A+'] 
# S2: 2 Electives
s2 = ['A+', 'A+'] 
# S3: 2 Extra
s3 = ['A+', 'A+'] 

test_calc(s1, s2, s3, 10.0)
