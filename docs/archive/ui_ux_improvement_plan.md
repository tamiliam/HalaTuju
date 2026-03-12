# UX Improvement Plan: Smart SPM Result Entry (Mobile-First)

> **Status**: Phase 1 Implemented (2026-02-03)
>
> **Completed**:
> - Slider-based grade entry for compulsory subjects (BM, Eng, Math, Hist)
> - Stream selection radio buttons now properly control elective dropdowns (fixed cascading logic)
>
> **Pending**: Elective subjects (deferred - needs multiselect + slider combo for "Not Taken" handling)

---

## 1. Problem Analysis
The current implementation uses multiple pairs of `st.selectbox` (Subject + Grade).
*   **Pain Point**: Requires 2 taps per subject + scrolling a long list of 10+ grades.
*   **Cognitive Load**: Users see "Stream Subject 1", "Stream Subject 2" placeholders instead of their actual subjects.
*   **Mobile Issue**: Dropdowns are native system pickers, which can feel "heavy" and disjointed from the app UI on iOS/Android.

## 2. The Solution: "Slide & Select"
We will transform the input flow into a modern, tactile experience.

### A. Subject Selection (The "Cart" Model) - PENDING
Instead of empty placeholders, let users **search and add** their subjects first.
*   **Component**: `st.multiselect`
*   **Label**: "Add your Elective Subjects"
*   **Behavior**: Users type "Chem" and select "Chemistry". It adds to their list. "Compulsory" subjects are locked/always visible.

### B. Grade Input (The "Slider" Model) - PHASE 1 COMPLETE
Replace Dropdowns with **`st.select_slider`**.
*   **Why?**:
    *   **Tactile**: Users "swipe" to their grade.
    *   **Visual**: They see the full range (G to A+).
    *   **Faster**: One interaction (drag/click) vs Two (open list, find item).
*   **Layout**:
    *   **Left**: Subject Name (e.g., "History")
    *   **Bottom**: The Slider [G -- D -- C -- ... -- A+]

## 3. Implementation Details

### Step 1: Compulsory Section - ✅ IMPLEMENTED
Render the 4 core subjects (BM, Eng, Math, Hist) automatically.
*   Use `st.select_slider` for each.
*   Default value: "C" (Passing grade)
*   Slider options: `["G", "E", "D", "C", "C+", "B", "B+", "A-", "A", "A+"]`

**Implementation** (main.py lines 181-195):
```python
SLIDER_GRADES = ["G", "E", "D", "C", "C+", "B", "B+", "A-", "A", "A+"]

def get_slider_default(subject_key):
    if current_grades and subject_key in current_grades:
        grade = current_grades[subject_key]
        if grade in SLIDER_GRADES:
            return grade
    return "C"

st.markdown(f"**{t['subj_bm']}**")
bm = st.select_slider("BM Grade", options=SLIDER_GRADES, value=get_slider_default('bm'), ...)
```

### Step 1b: Stream Selection Cascading - ✅ FIXED
The stream radio buttons (Science/Arts/Tech-Voc) now immediately update the elective dropdowns.

**Problem**: Inside Streamlit forms, widget values don't update until form submission. `on_change` callbacks are also prohibited inside forms.

**Solution**: Move stream radio button OUTSIDE the form (main.py lines ~1100, ~520):
```python
# OUTSIDE the form - updates immediately
st.sidebar.radio(
    "Select Stream",
    ["Science (STEM)", "Arts (Sastera)", "Technical/Vocational"],
    horizontal=True,
    key="stream_selection_sb"  # Sets session state
)

with st.sidebar.form("grades_form"):
    # INSIDE the form - reads from session state
    raw_grades = render_grade_inputs(t, guest_grades, key_suffix="_sb")
```

Inside `render_grade_inputs()`:
```python
# Read stream from session state (set by radio OUTSIDE the form)
stream_state_key = f"stream_selection{key_suffix}"
stream_mode = st.session_state.get(stream_state_key, "Science (STEM)")
is_stem = "Science" in stream_mode
```

**Key Insight**: Widgets outside forms update session state immediately on interaction, while widgets inside forms only update on form submission.

### Step 2: Elective Selector - PENDING
*   **Prompt**: "Select your Stream/Elective subjects:"
*   **Widget**: `st.multiselect` populated with `SUBJ_LIST_SCIENCE + SUBJ_LIST_ARTS`.
*   **Dynamic**: As items are added, new "Cards" appear below for grade entry.
*   **Challenge**: Need to handle "Not Taken" which doesn't fit slider model naturally

### Step 3: The Grade Card Component - PENDING
Create a reusable function `render_subject_card(subject_key, subject_name)`:
```python
st.markdown(f"**{subject_name}**")
grade = st.select_slider(
    "Grade",
    options=["G", "E", "D", "C", "C+", "B", "B+", "A-", "A", "A+"],
    value="C",
    key=f"slider_{subject_key}",
    label_visibility="collapsed"
)
```

## 4. UI Polish (CSS) - OPTIONAL
*   Add custom CSS to style the sliders nicely (make the track thicker/colored?).
*   Group subjects into a "Card" container with a light border/shadow for separation.

## 5. Phase 2 Considerations

When implementing electives:
1. **Multiselect first**: Let users pick which subjects they took
2. **Dynamic sliders**: Show sliders only for selected subjects
3. **No "Not Taken" needed**: If not in multiselect, it's automatically "Not Taken"

This avoids the awkward checkbox+slider combo while maintaining clean UX.
